"""Case-scoped RAG: indexes each case document's extracted text into
`case_knowledge_chunks` and searches it filtered by `case_id`.

Deliberately a separate index from the shared `knowledge_chunks` table
(statutes/case law) — see `models/legal_case.py::CaseKnowledgeChunk` docstring.
Search ranking reuses the same cosine-similarity approach as
`knowledge/search.py::hybrid_search`, duplicated rather than imported because
the two tables have different join shapes (no `KnowledgeDocument` metadata
here) and duplicating ~15 lines is simpler than forcing a shared abstraction
over two now-diverging schemas.
"""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.document import DocumentExtractedPage
from app.models.legal_case import CaseKnowledgeChunk
from app.services.knowledge.chunking import chunk_text
from app.services.knowledge.embeddings import generate_embedding


def index_case_document(db: Session, case_id, document_id) -> int:
    """Chunk + embed a single document's already-extracted pages into the case's index.

    Called after that document's own litigation pipeline run finishes. Safe to
    call again (e.g. on reanalysis) — existing chunks for this document are
    replaced, not duplicated.
    """
    db.query(CaseKnowledgeChunk).filter(
        CaseKnowledgeChunk.case_id == case_id, CaseKnowledgeChunk.document_id == document_id
    ).delete(synchronize_session=False)

    pages = (
        db.query(DocumentExtractedPage)
        .filter(DocumentExtractedPage.document_id == document_id)
        .order_by(DocumentExtractedPage.page_number)
        .all()
    )
    chunk_count = 0
    for page in pages:
        for idx, chunk in enumerate(chunk_text(page.raw_text)):
            db.add(
                CaseKnowledgeChunk(
                    case_id=case_id,
                    document_id=document_id,
                    chunk_index=chunk_count,
                    content=chunk,
                    page_number=page.page_number,
                    embedding=generate_embedding(chunk),
                )
            )
            chunk_count += 1
            _ = idx
    db.commit()
    return chunk_count


@dataclass
class CaseSearchHit:
    chunk_id: str
    document_id: str
    page_number: int | None
    excerpt: str
    score: float


def search_case_knowledge(db: Session, case_id, query: str, *, limit: int = 8) -> list[CaseSearchHit]:
    candidates = db.query(CaseKnowledgeChunk).filter(CaseKnowledgeChunk.case_id == case_id).limit(500).all()
    if not candidates:
        return []

    query_vector = generate_embedding(query) if query else None
    scored: list[CaseSearchHit] = []
    for chunk in candidates:
        score = 0.0
        if query_vector is not None and chunk.embedding is not None:
            score = 1 - _cosine_distance(query_vector, list(chunk.embedding))
        scored.append(
            CaseSearchHit(
                chunk_id=str(chunk.id),
                document_id=str(chunk.document_id),
                page_number=chunk.page_number,
                excerpt=chunk.content[:400],
                score=score,
            )
        )
    scored.sort(key=lambda h: h.score, reverse=True)
    return scored[:limit]


def _cosine_distance(a: list[float], b: list[float]) -> float:
    import math

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return 1 - (dot / (norm_a * norm_b))


def delete_case_knowledge(db: Session, case_id) -> None:
    """Remove all embeddings for a case — called when the case itself is deleted (§29).

    Existing chat messages that cited one of these chunks keep their message
    text (the citation's title/excerpt is already denormalized onto
    CaseChatMessageCitation), but the FK back to the now-deleted chunk must be
    cleared first or the delete fails with a foreign-key violation.
    """
    from app.models.legal_case import CaseChatMessageCitation

    chunk_ids = [
        row[0] for row in db.query(CaseKnowledgeChunk.id).filter(CaseKnowledgeChunk.case_id == case_id).all()
    ]
    if chunk_ids:
        db.query(CaseChatMessageCitation).filter(CaseChatMessageCitation.case_knowledge_chunk_id.in_(chunk_ids)).update(
            {"case_knowledge_chunk_id": None}, synchronize_session=False
        )
    db.query(CaseKnowledgeChunk).filter(CaseKnowledgeChunk.case_id == case_id).delete(synchronize_session=False)
    db.commit()
