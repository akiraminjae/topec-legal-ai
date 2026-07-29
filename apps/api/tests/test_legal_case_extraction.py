"""Tests for the case-level AI extraction features added on top of the base
LegalCase feature: document classification/date/case-info extraction (§10-12),
the real-date timeline (§13), document relationships (§14), and conflict
detection (§16). Uses a stub AIProvider (not MockAIProvider, whose
extract_structured always returns empty results) so the plumbing — index
mapping, DB writes, confidence coercion — is actually exercised.
"""
import pytest

from app.models.document import Document, DocumentExtractedPage
from app.models.enums import RoleName
from app.models.legal_case import CaseConflict, CaseDocument, CaseDocumentDate, CaseDocumentRelation, LegalCase
from app.services.ai.base import TokenUsage
from app.services.ai.case_extraction_schema import (
    CaseConflictDetectionResult,
    CaseConflictItem,
    DocumentMetadataExtraction,
    DocumentRelationPair,
    DocumentRelationshipResult,
    ExtractedDateItem,
)
from app.services.ai.schema import AIChatAnswer, _coerce_confidence_to_int
from app.services.legal_case.extraction import extract_case_document_metadata
from tests.conftest import login
from tests.test_legal_cases import _create_case, _seed_completed_case_document


class _StubProvider:
    """Minimal AIProvider double whose extract_structured/answer_chat return
    whatever canned result the test configures, so relationship/conflict
    index-mapping and DB writes are exercised deterministically."""

    name = "stub"
    is_mock = False

    def __init__(self, structured_result=None, chat_result=None):
        self._structured_result = structured_result
        self._chat_result = chat_result

    def extract_structured(self, system_prompt, user_prompt, model_cls):
        return self._structured_result, TokenUsage(input_tokens=10, output_tokens=10)

    def answer_chat(self, system_prompt, user_prompt):
        return self._chat_result, TokenUsage(input_tokens=10, output_tokens=10)

    def analyze_contract(self, *args, **kwargs):  # pragma: no cover - unused here
        raise NotImplementedError


# --------------------------------------------------------- confidence coercion --

@pytest.mark.parametrize(
    "raw,expected",
    [
        (0.25, 25),  # observed live bug: model returned a 0-1 fraction
        (0.9, 90),
        (85, 85),  # already an int — untouched
        (85.0, 85.0),  # integer-valued float — untouched, pydantic's own lax int coercion handles it
        (150.0, 150),  # out-of-[0,1] float — just rounded, range validation catches it downstream
    ],
)
def test_coerce_confidence_to_int(raw, expected):
    assert _coerce_confidence_to_int(raw) == expected


def test_ai_chat_answer_accepts_fractional_confidence():
    """Regression test for the live bug: case analysis crashed with a 500 when
    Claude returned confidence=0.25 instead of an int 0-100."""
    answer = AIChatAnswer(
        conclusion="c", facts_and_premises="f", related_clauses="r", impact_on_topec="i",
        legal_sources="l", recommended_action="a", confidence=0.25,
    )
    assert answer.confidence == 25


# ------------------------------------------------------------- per-doc extraction --

def test_extract_case_document_metadata_populates_fields_and_applies_type(client, make_user, db_session, monkeypatch):
    user, password = make_user(RoleName.USER)
    _, csrf = login(client, user.email, password)
    case_id = _create_case(client, csrf)
    case = db_session.get(LegalCase, case_id)

    document = Document(
        title="분류전문서", document_category="LITIGATION", litigation_document_type="OTHER",
        owner_id=case.owner_user_id, status="WAITING_FOR_REVIEW",
    )
    db_session.add(document)
    db_session.flush()
    db_session.add(DocumentExtractedPage(document_id=document.id, page_number=1, raw_text="본 소장은 2026년 1월 5일 작성됨"))
    case_doc = CaseDocument(case_id=case_id, document_id=document.id, sequence_number=1)
    db_session.add(case_doc)
    db_session.commit()

    result = DocumentMetadataExtraction(
        suggested_document_type="COMPLAINT",
        classification_confidence=88,
        classification_reasoning="청구취지 문구가 확인됨",
        case_number="2026가합99",
        court="서울중앙지방법원",
        plaintiff="원고A",
        defendant="피고B",
        case_info_confidence=80,
        dates=[ExtractedDateItem(date_type="DOCUMENT_DATE", date_value="2026-01-05", source_text="2026년 1월 5일 작성됨", confidence=90)],
    )
    stub = _StubProvider(structured_result=result)
    monkeypatch.setattr("app.services.legal_case.extraction.get_ai_provider_for_document", lambda level: stub)

    extract_case_document_metadata(db_session, case_id, document.id)

    db_session.refresh(case_doc)
    db_session.refresh(document)
    assert case_doc.ai_suggested_document_type == "COMPLAINT"
    assert case_doc.classification_confidence == 88
    assert case_doc.extracted_case_number == "2026가합99"
    assert document.litigation_document_type == "COMPLAINT"  # was OTHER — AI value applied
    assert case_doc.needs_user_confirmation is False  # both confidences above threshold, no mismatch

    dates = db_session.query(CaseDocumentDate).filter(CaseDocumentDate.case_document_id == case_doc.id).all()
    assert len(dates) == 1
    assert dates[0].date_type == "DOCUMENT_DATE"
    assert str(dates[0].date_value) == "2026-01-05"


def test_extract_case_document_metadata_does_not_override_user_choice(client, make_user, db_session, monkeypatch):
    """If the user already picked a document type at upload time, the AI
    suggestion is recorded separately but must not silently overwrite it."""
    user, password = make_user(RoleName.USER)
    _, csrf = login(client, user.email, password)
    case_id = _create_case(client, csrf)
    case = db_session.get(LegalCase, case_id)

    document = Document(
        title="사용자지정문서", document_category="LITIGATION", litigation_document_type="ANSWER",
        owner_id=case.owner_user_id, status="WAITING_FOR_REVIEW",
    )
    db_session.add(document)
    db_session.flush()
    db_session.add(DocumentExtractedPage(document_id=document.id, page_number=1, raw_text="텍스트"))
    case_doc = CaseDocument(case_id=case_id, document_id=document.id, sequence_number=1)
    db_session.add(case_doc)
    db_session.commit()

    result = DocumentMetadataExtraction(
        suggested_document_type="COMPLAINT", classification_confidence=95,
        classification_reasoning="근거", case_info_confidence=10,
    )
    stub = _StubProvider(structured_result=result)
    monkeypatch.setattr("app.services.legal_case.extraction.get_ai_provider_for_document", lambda level: stub)

    extract_case_document_metadata(db_session, case_id, document.id)

    db_session.refresh(document)
    db_session.refresh(case_doc)
    assert document.litigation_document_type == "ANSWER"  # untouched
    assert case_doc.ai_suggested_document_type == "COMPLAINT"  # AI suggestion still recorded
    assert case_doc.needs_user_confirmation is True  # type mismatch flagged for review


# ------------------------------------------------------------------- timeline --

def test_timeline_sorted_by_real_extracted_dates(client, make_user, db_session):
    user, password = make_user(RoleName.USER)
    _, csrf = login(client, user.email, password)
    case_id = _create_case(client, csrf)
    case = db_session.get(LegalCase, case_id)

    doc_later, case_doc_later = _seed_completed_case_document(db_session, case_id, case.owner_user_id, title="나중문서")
    doc_earlier, case_doc_earlier = _seed_completed_case_document(db_session, case_id, case.owner_user_id, title="이전문서")
    db_session.add(CaseDocumentDate(case_document_id=case_doc_later.id, date_type="FILING_DATE", date_value="2026-05-01", confidence=90))
    db_session.add(CaseDocumentDate(case_document_id=case_doc_earlier.id, date_type="FILING_DATE", date_value="2026-01-01", confidence=90))
    db_session.commit()

    resp = client.get(f"/api/legal-cases/{case_id}/timeline")
    assert resp.status_code == 200
    entries = resp.json()
    dated = [e for e in entries if e["date_value"]]
    assert [e["document_title"] for e in dated] == ["이전문서", "나중문서"]


def test_timeline_falls_back_to_upload_order_when_no_dates_extracted(client, make_user, db_session):
    user, password = make_user(RoleName.USER)
    _, csrf = login(client, user.email, password)
    case_id = _create_case(client, csrf)
    case = db_session.get(LegalCase, case_id)
    _seed_completed_case_document(db_session, case_id, case.owner_user_id, title="날짜없음")

    resp = client.get(f"/api/legal-cases/{case_id}/timeline")
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) == 1
    assert entries[0]["is_fallback_upload_order"] is True
    assert entries[0]["date_value"] is None


# --------------------------------------------------------------- confirm API --

def test_confirm_case_document_classification(client, make_user, db_session):
    user, password = make_user(RoleName.USER)
    _, csrf = login(client, user.email, password)
    case_id = _create_case(client, csrf)
    case = db_session.get(LegalCase, case_id)
    document, case_doc = _seed_completed_case_document(db_session, case_id, case.owner_user_id)
    case_doc.needs_user_confirmation = True
    db_session.commit()

    resp = client.post(
        f"/api/legal-cases/{case_id}/documents/{case_doc.id}/confirm",
        json={"document_type": "JUDGMENT"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["needs_user_confirmation"] is False
    assert body["litigation_document_type"] == "JUDGMENT"


# --------------------------------------------------- relationships / conflicts --

def test_run_case_analysis_populates_relationships_and_conflicts(client, make_user, db_session, monkeypatch):
    user, password = make_user(RoleName.USER)
    _, csrf = login(client, user.email, password)
    case_id = _create_case(client, csrf)
    case = db_session.get(LegalCase, case_id)
    doc_a, _ = _seed_completed_case_document(db_session, case_id, case.owner_user_id, title="문서A")
    doc_b, _ = _seed_completed_case_document(db_session, case_id, case.owner_user_id, title="문서B")

    chat_answer = AIChatAnswer(
        conclusion="개요", facts_and_premises="주장", related_clauses="입장", impact_on_topec="쟁점",
        legal_sources="누락", recommended_action="대응방향", confidence=70,
    )
    relationship_result = DocumentRelationshipResult(
        relationships=[DocumentRelationPair(document_a_index=1, document_b_index=0, relation_type="REBUTS", reasoning="반박함")]
    )
    conflict_result = CaseConflictDetectionResult(
        conflicts=[
            CaseConflictItem(
                conflict_type="금액 불일치", summary="요약", value_a="1억", source_document_a_index=0,
                value_b="2억", source_document_b_index=1, impact="영향", recommended_check="확인",
                severity="HIGH", confidence=70,
            )
        ]
    )

    call_count = {"n": 0}

    def fake_extract_structured(system_prompt, user_prompt, model_cls):
        call_count["n"] += 1
        if model_cls is DocumentRelationshipResult:
            return relationship_result, TokenUsage()
        return conflict_result, TokenUsage()

    stub = _StubProvider(chat_result=chat_answer)
    stub.extract_structured = fake_extract_structured
    monkeypatch.setattr("app.services.legal_case.analysis.get_ai_provider_for_document", lambda level: stub)

    resp = client.post(f"/api/legal-cases/{case_id}/analysis", headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 200, resp.text
    assert call_count["n"] == 2

    relations = db_session.query(CaseDocumentRelation).filter(CaseDocumentRelation.case_id == case_id).all()
    assert len(relations) == 1
    assert relations[0].document_a_id == doc_b.id  # index 1 -> doc_b
    assert relations[0].document_b_id == doc_a.id  # index 0 -> doc_a
    assert relations[0].relation_type == "REBUTS"

    conflicts = db_session.query(CaseConflict).filter(CaseConflict.case_id == case_id).all()
    assert len(conflicts) == 1
    assert conflicts[0].source_document_a_id == doc_a.id
    assert conflicts[0].severity == "HIGH"

    # API-level read paths
    resp = client.get(f"/api/legal-cases/{case_id}/relations")
    assert resp.status_code == 200 and len(resp.json()) == 1
    resp = client.get(f"/api/legal-cases/{case_id}/conflicts")
    assert resp.status_code == 200 and len(resp.json()) == 1

    conflict_id = resp.json()[0]["id"]
    resp = client.patch(
        f"/api/legal-cases/{case_id}/conflicts/{conflict_id}", json={"resolution_status": "RESOLVED"}, headers={"X-CSRF-Token": csrf}
    )
    assert resp.status_code == 200
    assert resp.json()["resolution_status"] == "RESOLVED"
