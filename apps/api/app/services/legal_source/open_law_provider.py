"""국가법령정보 공동활용 LINK API — law.go.kr DRF 엔드포인트, OC 인증.

공공데이터포털 화면에는 판례가 "LINK" 유형으로 안내되지만 실제 호출은 law.go.kr(또는
open.law.go.kr)의 DRF API로 직접 이루어지며, 인증도 공공데이터포털 serviceKey가 아닌 OC를
사용한다. 이 Provider가 담당하는 범위:
  - 판례 목록  (lawSearch.do?target=prec)
  - 판례 본문  (lawService.do?target=prec)
  - 법령 상세본문/조문 (lawService.do?target=law) — PublicDataPortalProvider가 찾은
    법령일련번호(MST)를 이어받아 조문 원문을 가져올 때 사용한다.
"""
import xml.etree.ElementTree as ET

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from app.core.config import get_settings
from app.services.legal_source.base import ExternalLegalHit, LegalSourceNotConfiguredError, LegalSourceProvider
from app.services.legal_source.rate_limit import check_rate_limit
from app.services.legal_source.xml_utils import first, text_map

settings = get_settings()

_ARTICLE_TEXT_TAGS = ("조문내용", "항내용", "호내용", "목내용")


def _article_relevance_score(query_terms: list[str], title: str, content: str) -> float:
    """Rank articles by how well they match the query.

    A pure "does the term appear anywhere in the body" check systematically
    prefers long articles (e.g. a definitions article that restates every term
    once) over the short, specific article that's actually on point — the
    definitions article for 하도급법 out-scored 제13조(하도급대금의 지급 등) on a
    "하도급대금 지급" query for exactly this reason. Article titles (조문제목) are
    short, purpose-built labels — a term match there is a far stronger signal
    than a term match buried in a long body, so it's weighted heavily. Body
    matches are normalized by article length so a term's density matters more
    than raw repetition count.
    """
    if not query_terms:
        return 0.0
    title_hits = sum(1 for t in query_terms if t in title)
    body_hits = sum(content.count(t) for t in query_terms)
    body_density = body_hits / max(len(content), 1) * 1000
    return title_hits * 100 + body_density


def _full_article_text(article: ET.Element) -> str:
    """`조문내용` only holds the article heading (e.g. "제13조(하도급대금의 지급 등)")
    — the substantive body lives in sibling `<항>` (and nested `<호>`/`<목>`)
    elements, each of which wraps its own `-번호`/`-내용` children rather than
    exposing text directly on `<항>` itself. Walk the whole subtree in document
    order so heading + clauses + items come out in the same order as the
    original statute text."""
    parts = [
        node.text.strip()
        for node in article.iter()
        if node.tag in _ARTICLE_TEXT_TAGS and node.text and node.text.strip()
    ]
    return "\n".join(parts)


class OpenLawProvider(LegalSourceProvider):
    name = "open_law"

    def _require_oc(self) -> str:
        if not settings.OPEN_LAW_OC:
            raise LegalSourceNotConfiguredError(
                "국가법령정보 공동활용 OC(OPEN_LAW_OC)가 설정되지 않았습니다. "
                "https://open.law.go.kr 에서 발급받은 OC 값을 .env에 설정하세요."
            )
        return settings.OPEN_LAW_OC

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_fixed(1),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError)),
        reraise=True,
    )
    def _get(self, path: str, params: dict) -> ET.Element:
        with httpx.Client(timeout=settings.EXTERNAL_LEGAL_TIMEOUT) as client:
            response = client.get(f"{settings.OPEN_LAW_BASE_URL.rstrip('/')}/{path}", params=params)
            response.raise_for_status()
            return ET.fromstring(response.content)

    # -- LegalSourceProvider interface: 판례 목록을 이 Provider의 기본 검색으로 삼는다 --
    def search(self, query: str, limit: int) -> list[ExternalLegalHit]:
        return self.search_cases(query, limit)

    def search_cases(self, query: str, limit: int) -> list[ExternalLegalHit]:
        """판례 목록 조회 (lawSearch.do?target=prec)."""
        oc = self._require_oc()
        check_rate_limit(f"{self.name}.search_cases")

        root = self._get(
            "lawSearch.do",
            {"OC": oc, "target": "prec", "type": "XML", "query": query, "display": limit},
        )

        hits: list[ExternalLegalHit] = []
        for prec_elem in root.iter("prec"):
            fields = text_map(prec_elem)
            case_name = first(fields, "사건명")
            case_number = first(fields, "사건번호")
            if not case_number:
                continue
            court = first(fields, "법원명")
            decision_date = first(fields, "선고일자")
            case_id = first(fields, "판례일련번호", "ID")
            # 판시사항(쟁점)과 판결요지(결론)를 함께 제공 — 쟁점명만으로는 결론이 드러나지 않는다.
            issue = first(fields, "판시사항")
            holding = first(fields, "판결요지")
            summary = " / ".join(p for p in (issue, holding) if p) or None
            detail_link = first(fields, "판례상세링크")
            detail_url = f"http://www.law.go.kr{detail_link}" if detail_link and detail_link.startswith("/") else detail_link

            hits.append(
                ExternalLegalHit(
                    source_type="COURT_CASE",
                    title=case_name or case_number,
                    excerpt=(summary or case_name or "요지 정보 없음")[:600],
                    dedup_key=f"case:{case_number}",
                    case_number=case_number,
                    court=court,
                    decision_date=decision_date,
                    detail_url=detail_url,
                    mst=case_id,
                )
            )
            if len(hits) >= limit:
                break
        return hits

    def get_case_detail(self, case_id: str) -> str | None:
        """판례 본문 전체 조회 (lawService.do?target=prec&ID=...). 실패 시 None —
        호출자는 검색 결과의 요약(판시사항/판결요지)으로 대체해야 한다."""
        oc = self._require_oc()
        check_rate_limit(f"{self.name}.get_case_detail")
        try:
            root = self._get("lawService.do", {"OC": oc, "target": "prec", "ID": case_id, "type": "XML"})
        except Exception:
            return None

        fields = text_map(root)
        content = first(fields, "판례내용", "전문")
        return content[:4000] if content else None

    def get_statute_detail(self, mst: str, query: str) -> tuple[str | None, str | None]:
        """법령 상세본문에서 질의어와 가장 관련도 높은 조문을 best-effort로 추출한다.
        반환: (조문번호, 조문내용). 실패 시 (None, None)."""
        oc = self._require_oc()
        check_rate_limit(f"{self.name}.get_statute_detail")
        try:
            root = self._get("lawService.do", {"OC": oc, "target": "law", "MST": mst, "type": "XML"})
        except Exception:
            return None, None

        query_terms = [t for t in query.replace(",", " ").split() if t]
        best_no, best_text, best_score = None, None, 0.0
        for article in root.iter("조문단위"):
            fields = text_map(article)
            no = first(fields, "조문번호")
            title = first(fields, "조문제목") or ""
            content = _full_article_text(article)
            if not content:
                continue
            score = _article_relevance_score(query_terms, title, content)
            if score > best_score:
                best_score, best_no, best_text = score, (f"제{no}조" if no else None), content
        return (best_no, best_text[:600]) if best_score > 0 else (None, None)
