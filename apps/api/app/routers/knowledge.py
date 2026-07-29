import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_system_admin
from app.db.session import get_db
from app.models.enums import AuditAction, KnowledgeDocType
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.models.user import User
from app.schemas.knowledge import (
    KnowledgeDocumentOut,
    KnowledgeDocumentUpdate,
    KnowledgeSearchHitOut,
    KnowledgeSearchRequest,
)
from app.services.audit import write_audit_log
from app.services.extraction.base import ExtractionError
from app.services.extraction.dispatch import extract_text_by_extension
from app.services.file_validation import validate_upload
from app.services.knowledge.chunking import chunk_text
from app.services.knowledge.embeddings import generate_embedding
from app.services.knowledge.search import hybrid_search
from app.services.storage import get_storage

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.post("/documents", response_model=KnowledgeDocumentOut)
async def upload_knowledge_document_form(
    request: Request,
    doc_type: str,
    title: str,
    case_number: str | None = None,
    court: str | None = None,
    source: str | None = None,
    security_level: str = "INTERNAL",
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_system_admin),
):
    try:
        KnowledgeDocType(doc_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="잘못된 자료유형입니다.")

    content = await file.read()
    validation = validate_upload(file, content)

    try:
        extraction = extract_text_by_extension(validation.extension, content)
    except ExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    storage = get_storage()
    stored_key = f"knowledge/{uuid.uuid4().hex}_{validation.safe_filename}"
    storage.put_object(stored_key, content, file.content_type or "application/octet-stream")

    kdoc = KnowledgeDocument(
        doc_type=doc_type,
        title=title,
        case_number=case_number,
        court=court,
        source=source,
        security_level=security_level,
        original_filename=validation.safe_filename,
        stored_key=stored_key,
    )
    db.add(kdoc)
    db.flush()

    chunks = chunk_text(extraction.full_text)
    for i, chunk in enumerate(chunks):
        embedding = generate_embedding(chunk)
        db.add(
            KnowledgeChunk(
                knowledge_document_id=kdoc.id,
                chunk_index=i,
                content=chunk,
                embedding=embedding,
            )
        )

    db.commit()
    db.refresh(kdoc)
    write_audit_log(
        db, action=AuditAction.KNOWLEDGE_UPLOADED, user_id=user.id, target_type="knowledge_document",
        target_id=str(kdoc.id), request=request,
    )
    return kdoc


@router.get("/documents", response_model=list[KnowledgeDocumentOut])
def list_knowledge_documents(db: Session = Depends(get_db), user: User = Depends(require_system_admin)):
    return db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.is_deleted.is_(False))).all()


@router.get("/documents/{document_id}", response_model=KnowledgeDocumentOut)
def get_knowledge_document(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_system_admin)):
    doc = db.get(KnowledgeDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="자료를 찾을 수 없습니다.")
    return doc


@router.patch("/documents/{document_id}", response_model=KnowledgeDocumentOut)
def update_knowledge_document(
    document_id: uuid.UUID,
    payload: KnowledgeDocumentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_system_admin),
):
    doc = db.get(KnowledgeDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="자료를 찾을 수 없습니다.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(doc, field, value)
    db.commit()
    write_audit_log(db, action=AuditAction.KNOWLEDGE_UPDATED, user_id=user.id, target_type="knowledge_document", target_id=str(doc.id), request=request)
    db.refresh(doc)
    return doc


@router.delete("/documents/{document_id}")
def delete_knowledge_document(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_system_admin)):
    doc = db.get(KnowledgeDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="자료를 찾을 수 없습니다.")
    doc.is_deleted = True
    doc.is_valid = False
    db.commit()
    return {"message": "지식자료가 삭제(비활성화)되었습니다."}


@router.post("/search", response_model=list[KnowledgeSearchHitOut])
def search_knowledge(payload: KnowledgeSearchRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    hits = hybrid_search(
        db, payload.query, contract_type=payload.contract_type, clause_type=payload.clause_type, limit=payload.limit
    )
    return [KnowledgeSearchHitOut(**h.__dict__) for h in hits]
