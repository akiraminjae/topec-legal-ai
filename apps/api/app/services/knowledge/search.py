from dataclasses import dataclass

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.enums import SecurityLevel
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.services.knowledge.embeddings import generate_embedding


@dataclass
class SearchHit:
    chunk_id: str
    knowledge_document_id: str
    title: str
    doc_type: str
    excerpt: str
    source: str | None
    case_number: str | None
    court: str | None
    decision_date: str | None
    effective_date: str | None
    score: float


def hybrid_search(
    db: Session,
    query: str,
    *,
    max_security_level: SecurityLevel = SecurityLevel.CONFIDENTIAL,
    contract_type: str | None = None,
    clause_type: str | None = None,
    limit: int = 8,
) -> list[SearchHit]:
    """Keyword filter narrowed by metadata, ranked by vector similarity.

    Only chunks belonging to `is_valid=True` knowledge documents are returned so
    stale/repealed material never surfaces as a citation.
    """
    security_order = {
        SecurityLevel.INTERNAL: 0,
        SecurityLevel.IMPORTANT: 1,
        SecurityLevel.CONFIDENTIAL: 2,
    }
    allowed_levels = [
        lvl for lvl, order in security_order.items() if order <= security_order[max_security_level]
    ]

    q = (
        db.query(KnowledgeChunk, KnowledgeDocument)
        .join(KnowledgeDocument, KnowledgeChunk.knowledge_document_id == KnowledgeDocument.id)
        .filter(
            KnowledgeDocument.is_valid.is_(True),
            KnowledgeDocument.is_deleted.is_(False),
            KnowledgeDocument.security_level.in_([lvl.value for lvl in allowed_levels]),
        )
    )

    if contract_type:
        q = q.filter(KnowledgeDocument.applicable_contract_types.contains([contract_type]))
    if clause_type:
        q = q.filter(KnowledgeDocument.applicable_clause_types.contains([clause_type]))
    if query:
        like = f"%{query}%"
        q = q.filter(or_(KnowledgeChunk.content.ilike(like), KnowledgeDocument.title.ilike(like)))

    candidates = q.limit(200).all()
    if not candidates:
        return []

    query_vector = generate_embedding(query) if query else None
    scored: list[SearchHit] = []
    for chunk, doc in candidates:
        score = 0.0
        if query_vector is not None and chunk.embedding is not None:
            score = 1 - _cosine_distance(query_vector, list(chunk.embedding))
        scored.append(
            SearchHit(
                chunk_id=str(chunk.id),
                knowledge_document_id=str(doc.id),
                title=doc.title,
                doc_type=doc.doc_type,
                excerpt=chunk.content[:400],
                source=doc.source,
                case_number=doc.case_number,
                court=doc.court,
                decision_date=doc.decision_date.isoformat() if doc.decision_date else None,
                effective_date=doc.effective_date.isoformat() if doc.effective_date else None,
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
