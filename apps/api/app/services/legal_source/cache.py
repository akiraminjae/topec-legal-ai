"""Fetch-then-cache bridge between the two live external legal-data providers and
the existing internal knowledge base (pgvector) infrastructure.

Rather than bolting on a separate retrieval path, each external hit is persisted
as an ordinary `KnowledgeDocument` + `KnowledgeChunk` (source clearly labeled per
provider) so it automatically gets: citation validation via the existing
`known_chunk_ids` mechanism, an audit trail visible to admins at
`/api/knowledge/documents`, and de-duplication across repeated queries —
without any new schema or a parallel citation code path.

Provider split (per the two distinct external services):
  - PublicDataPortalProvider (공공데이터포털, serviceKey): 법령 목록/메타정보
  - OpenLawProvider (law.go.kr DRF, OC): 판례 목록/본문 + 법령 상세본문(조문)
Statute hits from the portal are enriched with article text from OpenLawProvider
when both are configured; if only one is configured, that one still contributes
results independently — neither provider is a hard dependency of the other.
"""
import logging
from datetime import date

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.enums import KnowledgeDocType
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.services.knowledge.embeddings import generate_embedding
from app.services.knowledge.search import SearchHit
from app.services.legal_source.base import ExternalLegalHit, LegalSourceNotConfiguredError
from app.services.legal_source.open_law_provider import OpenLawProvider
from app.services.legal_source.public_data_portal_provider import PublicDataPortalProvider
from app.services.legal_source.rate_limit import RateLimitExceededError

logger = logging.getLogger(__name__)
settings = get_settings()

SOURCE_LABEL_STATUTE = "공공데이터포털 법제처 국가법령정보 공유서비스 (data.go.kr)"
SOURCE_LABEL_CASE = "국가법령정보 공동활용 LINK API (law.go.kr)"


def _parse_yyyymmdd(value: str | None) -> date | None:
    if not value or not value.isdigit() or len(value) != 8:
        return None
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        return None


def _find_existing(db: Session, source_label: str, hit: ExternalLegalHit) -> KnowledgeDocument | None:
    query = db.query(KnowledgeDocument).filter(KnowledgeDocument.source == source_label)
    if hit.source_type == "COURT_CASE":
        return query.filter(KnowledgeDocument.case_number == hit.case_number).first()
    return query.filter(KnowledgeDocument.title == hit.title).first()


def _cache_hit(db: Session, source_label: str, hit: ExternalLegalHit) -> SearchHit:
    existing = _find_existing(db, source_label, hit)
    if existing:
        chunk = db.query(KnowledgeChunk).filter(KnowledgeChunk.knowledge_document_id == existing.id).first()
    else:
        doc_type = {
            "STATUTE": KnowledgeDocType.STATUTE,
            "COURT_CASE": KnowledgeDocType.COURT_CASE,
            "ADMIN_RULE": KnowledgeDocType.ADMIN_GUIDELINE,
        }.get(hit.source_type, KnowledgeDocType.STATUTE)

        doc = KnowledgeDocument(
            doc_type=doc_type,
            title=hit.title,
            case_number=hit.case_number,
            court=hit.court,
            source=source_label,
            security_level="INTERNAL",
            is_valid=True,
            is_latest_version=True,
            decision_date=_parse_yyyymmdd(hit.decision_date),
            effective_date=_parse_yyyymmdd(hit.effective_date),
        )
        db.add(doc)
        db.flush()
        chunk = KnowledgeChunk(
            knowledge_document_id=doc.id,
            chunk_index=0,
            content=hit.excerpt,
            embedding=generate_embedding(hit.excerpt),
        )
        db.add(chunk)
        db.flush()
        existing = doc

    return SearchHit(
        chunk_id=str(chunk.id),
        knowledge_document_id=str(existing.id),
        title=existing.title,
        doc_type=existing.doc_type,
        excerpt=hit.excerpt,
        source=hit.detail_url or source_label,
        case_number=hit.case_number,
        court=hit.court,
        decision_date=hit.decision_date,
        effective_date=hit.effective_date,
        score=1.0,
    )


def _fetch_statutes(db: Session, query: str) -> list[SearchHit]:
    if not settings.PUBLIC_DATA_SERVICE_KEY:
        return []
    try:
        portal = PublicDataPortalProvider()
        law_hits = portal.search(query, settings.EXTERNAL_LEGAL_MAX_RESULTS, target="law")
    except (LegalSourceNotConfiguredError, RateLimitExceededError):
        return []
    except Exception as exc:  # noqa: BLE001 — external outage must never break analysis
        logger.warning("공공데이터포털 법령 조회 실패: %s", exc)
        return []

    if settings.OPEN_LAW_OC:
        open_law = OpenLawProvider()
        for hit in law_hits:
            if not hit.mst:
                continue
            try:
                article_no, article_text = open_law.get_statute_detail(hit.mst, query)
            except (LegalSourceNotConfiguredError, RateLimitExceededError):
                break
            except Exception as exc:  # noqa: BLE001
                logger.warning("law.go.kr 법령 상세본문 조회 실패: %s", exc)
                continue
            if article_text:
                hit.article_no = article_no
                hit.title = f"{hit.law_name} {article_no}" if article_no else hit.law_name
                hit.excerpt = article_text
                hit.dedup_key = f"{hit.dedup_key}:{article_no or ''}"

    return [_cache_hit(db, SOURCE_LABEL_STATUTE, h) for h in law_hits]


def _fetch_cases(db: Session, query: str) -> list[SearchHit]:
    if not settings.OPEN_LAW_OC:
        return []
    try:
        open_law = OpenLawProvider()
        case_hits = open_law.search_cases(query, settings.EXTERNAL_LEGAL_MAX_RESULTS)
    except (LegalSourceNotConfiguredError, RateLimitExceededError):
        return []
    except Exception as exc:  # noqa: BLE001
        logger.warning("law.go.kr 판례 조회 실패: %s", exc)
        return []

    return [_cache_hit(db, SOURCE_LABEL_CASE, h) for h in case_hits]


def fetch_and_cache_external_legal_sources(db: Session, query: str) -> list[SearchHit]:
    """Query both live external providers for statutes + court cases matching
    `query` and cache the results as knowledge chunks. Never raises — a
    misconfigured or unreachable external source just means fewer results,
    not a broken analysis."""
    if not query.strip():
        return []
    if not settings.PUBLIC_DATA_SERVICE_KEY and not settings.OPEN_LAW_OC:
        return []

    results = _fetch_statutes(db, query) + _fetch_cases(db, query)
    if results:
        db.commit()
    return results
