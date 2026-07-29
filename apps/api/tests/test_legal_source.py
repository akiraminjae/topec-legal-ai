import xml.etree.ElementTree as ET
from unittest.mock import patch

import pytest

from app.services.legal_source import cache as cache_module
from app.services.legal_source import open_law_provider as open_law_module
from app.services.legal_source import public_data_portal_provider as pdp_module
from app.services.legal_source.base import LegalSourceNotConfiguredError
from app.services.legal_source.cache import fetch_and_cache_external_legal_sources
from app.services.legal_source.open_law_provider import OpenLawProvider
from app.services.legal_source.public_data_portal_provider import PublicDataPortalProvider

LAW_LIST_XML = """<?xml version="1.0" encoding="UTF-8"?>
<LawSearch>
    <target>law</target>
    <totalCnt>1</totalCnt>
    <law id="1">
        <법령일련번호>123456</법령일련번호>
        <법령명한글>하도급거래 공정화에 관한 법률</법령명한글>
        <시행일자>20240101</시행일자>
        <법령상세링크>/DRF/lawService.do?OC=test&amp;target=law&amp;MST=123456&amp;type=HTML</법령상세링크>
    </law>
</LawSearch>"""

LAW_SERVICE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Law>
    <조문단위>
        <조문번호>13</조문번호>
        <조문내용>제13조(하도급대금의 지급 등) 원사업자는 목적물등의 수령일로부터 60일 이내에 하도급대금을 지급하여야 한다.</조문내용>
    </조문단위>
    <조문단위>
        <조문번호>4</조문번호>
        <조문내용>제4조(부당한 하도급대금의 결정금지) 원사업자는 부당하게 하도급대금을 낮은 수준으로 결정할 수 없다.</조문내용>
    </조문단위>
</Law>"""

PREC_SEARCH_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PrecSearch>
    <target>prec</target>
    <totalCnt>1</totalCnt>
    <prec id="1">
        <판례일련번호>999</판례일련번호>
        <사건명>하도급대금 청구의 소</사건명>
        <사건번호>2020다12345</사건번호>
        <법원명>대법원</법원명>
        <선고일자>20210315</선고일자>
        <판시사항>하도급대금 지급의무의 발생 시기 및 범위</판시사항>
        <판결요지>원사업자는 목적물을 수령한 날부터 60일 이내에 하도급대금을 지급할 의무가 있다.</판결요지>
        <판례상세링크>/DRF/lawService.do?OC=test&amp;target=prec&amp;ID=999&amp;type=HTML</판례상세링크>
    </prec>
</PrecSearch>"""


@pytest.fixture(autouse=True)
def _configure_keys(monkeypatch):
    monkeypatch.setattr(pdp_module.settings, "PUBLIC_DATA_SERVICE_KEY", "test-service-key")
    monkeypatch.setattr(open_law_module.settings, "OPEN_LAW_OC", "test-oc")
    monkeypatch.setattr(cache_module.settings, "PUBLIC_DATA_SERVICE_KEY", "test-service-key")
    monkeypatch.setattr(cache_module.settings, "OPEN_LAW_OC", "test-oc")
    # Rate limiting itself is covered by test_rate_limit.py — neutralize it here so
    # repeated local test runs within the same minute never flake on shared Redis state.
    monkeypatch.setattr(pdp_module, "check_rate_limit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(open_law_module, "check_rate_limit", lambda *_args, **_kwargs: None)
    yield


# ---- PublicDataPortalProvider (법령 목록/메타) ----


def test_public_data_portal_requires_service_key(monkeypatch):
    monkeypatch.setattr(pdp_module.settings, "PUBLIC_DATA_SERVICE_KEY", "")
    provider = PublicDataPortalProvider()
    with pytest.raises(LegalSourceNotConfiguredError):
        provider.search("하도급대금", 5)


def test_public_data_portal_parses_law_list():
    provider = PublicDataPortalProvider()
    with patch.object(PublicDataPortalProvider, "_get", return_value=ET.fromstring(LAW_LIST_XML)):
        hits = provider.search("하도급대금", 5, target="law")

    assert len(hits) == 1
    hit = hits[0]
    assert hit.source_type == "STATUTE"
    assert "하도급거래 공정화에 관한 법률" in hit.title
    assert hit.mst == "123456"
    # 목록 조회 단계에서는 조문 본문이 아직 없다 — 상세조회 전 상태
    assert "시행일자" in hit.excerpt


# ---- OpenLawProvider (판례 목록/본문, 법령 상세본문) ----


def test_open_law_requires_oc(monkeypatch):
    monkeypatch.setattr(open_law_module.settings, "OPEN_LAW_OC", "")
    provider = OpenLawProvider()
    with pytest.raises(LegalSourceNotConfiguredError):
        provider.search_cases("하도급대금", 5)


def test_open_law_search_cases_parses_precedent():
    provider = OpenLawProvider()
    with patch.object(OpenLawProvider, "_get", return_value=ET.fromstring(PREC_SEARCH_XML)):
        hits = provider.search_cases("하도급대금", 5)

    assert len(hits) == 1
    hit = hits[0]
    assert hit.source_type == "COURT_CASE"
    assert hit.case_number == "2020다12345"
    assert hit.court == "대법원"
    assert "60일 이내" in hit.excerpt
    assert hit.mst == "999"  # 판례일련번호, get_case_detail에 이어서 사용 가능


def test_open_law_get_statute_detail_finds_relevant_article():
    provider = OpenLawProvider()
    with patch.object(OpenLawProvider, "_get", return_value=ET.fromstring(LAW_SERVICE_XML)):
        article_no, article_text = provider.get_statute_detail("123456", "하도급대금 지급")

    assert article_no == "제13조"
    assert "60일 이내" in article_text


def test_open_law_get_statute_detail_fails_gracefully_on_error():
    provider = OpenLawProvider()
    with patch.object(OpenLawProvider, "_get", side_effect=RuntimeError("network error")):
        article_no, article_text = provider.get_statute_detail("123456", "하도급대금")

    assert article_no is None
    assert article_text is None


# ---- cache.py orchestration ----


def test_fetch_and_cache_returns_empty_without_any_key(monkeypatch, db_session):
    monkeypatch.setattr(cache_module.settings, "PUBLIC_DATA_SERVICE_KEY", "")
    monkeypatch.setattr(cache_module.settings, "OPEN_LAW_OC", "")
    assert fetch_and_cache_external_legal_sources(db_session, "하도급대금") == []


def test_fetch_and_cache_survives_provider_failure(db_session):
    with patch.object(PublicDataPortalProvider, "search", side_effect=RuntimeError("boom")), \
         patch.object(OpenLawProvider, "search_cases", side_effect=RuntimeError("boom")):
        results = fetch_and_cache_external_legal_sources(db_session, "하도급대금")
    assert results == []


def test_fetch_and_cache_enriches_statute_with_article_and_dedupes(db_session):
    from app.models.knowledge import KnowledgeDocument

    with patch.object(PublicDataPortalProvider, "search", return_value=[
        __import__("app.services.legal_source.base", fromlist=["ExternalLegalHit"]).ExternalLegalHit(
            source_type="STATUTE",
            title="하도급거래 공정화에 관한 법률",
            excerpt="시행일자만 있는 메타정보",
            dedup_key="pdp:law:123456",
            law_name="하도급거래 공정화에 관한 법률",
            mst="123456",
        )
    ]), patch.object(OpenLawProvider, "get_statute_detail", return_value=("제13조", "60일 이내에 하도급대금을 지급하여야 한다.")), \
         patch.object(OpenLawProvider, "search_cases", return_value=[]):
        first = fetch_and_cache_external_legal_sources(db_session, "하도급대금 지급")
        second = fetch_and_cache_external_legal_sources(db_session, "하도급대금 지급")

    assert len(first) == 1
    assert "60일 이내" in first[0].excerpt  # 법령 상세본문으로 보강됨
    assert first[0].chunk_id == second[0].chunk_id  # 중복 캐싱 없음

    docs = db_session.query(KnowledgeDocument).filter(KnowledgeDocument.title.like("%하도급거래%")).all()
    assert len(docs) == 1


def test_fetch_and_cache_persists_cases(db_session):
    from app.models.knowledge import KnowledgeDocument

    with patch.object(PublicDataPortalProvider, "search", return_value=[]), \
         patch.object(
             OpenLawProvider,
             "search_cases",
             return_value=[
                 __import__("app.services.legal_source.base", fromlist=["ExternalLegalHit"]).ExternalLegalHit(
                     source_type="COURT_CASE",
                     title="하도급대금 청구의 소",
                     excerpt="원사업자는 60일 이내에 하도급대금을 지급할 의무가 있다.",
                     dedup_key="case:2020다99999",
                     case_number="2020다99999",
                     court="대법원",
                     decision_date="20210315",
                 )
             ],
         ):
        results = fetch_and_cache_external_legal_sources(db_session, "하도급대금")

    assert len(results) == 1
    cached = db_session.query(KnowledgeDocument).filter(KnowledgeDocument.case_number == "2020다99999").all()
    assert len(cached) == 1
