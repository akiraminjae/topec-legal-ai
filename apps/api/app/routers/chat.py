import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.chat import ChatMessage, ChatMessageCitation, ChatSession
from app.models.document import Document, DocumentExtractedPage
from app.models.user import User
from app.schemas.chat import ChatMessageCreate, ChatMessageOut, ChatSessionOut
from app.services.ai.prompts import CHAT_SYSTEM_PROMPT, build_chat_user_prompt
from app.services.ai.router import AIRoutingBlockedError, get_ai_provider_for_document
from app.services.ai.schema import AIOutputValidationError, validate_citations_exist
from app.services.document_access import can_access_document
from app.services.knowledge.search import hybrid_search
from app.services.legal_source.cache import fetch_and_cache_external_legal_sources
from app.services.masking import mask_sensitive_text

router = APIRouter(tags=["chat"])


def _get_document_or_404(db: Session, document_id: uuid.UUID, user: User) -> Document:
    document = db.get(Document, document_id)
    if not document or document.is_deleted:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
    if not can_access_document(db, user, document):
        raise HTTPException(status_code=403, detail="이 문서에 접근할 권한이 없습니다.")
    return document


@router.post("/api/documents/{document_id}/chat/sessions", response_model=ChatSessionOut)
def create_chat_session(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    document = _get_document_or_404(db, document_id, user)
    session = ChatSession(document_id=document.id, user_id=user.id, title=f"{document.title} 질의응답")
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/api/documents/{document_id}/chat/sessions", response_model=list[ChatSessionOut])
def list_chat_sessions(document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    document = _get_document_or_404(db, document_id, user)
    return (
        db.query(ChatSession)
        .filter(ChatSession.document_id == document.id, ChatSession.user_id == user.id)
        .order_by(ChatSession.created_at.desc())
        .all()
    )


def _get_session_or_404(db: Session, session_id: uuid.UUID, user: User) -> ChatSession:
    session = db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="대화 세션을 찾을 수 없습니다.")
    document = db.get(Document, session.document_id)
    if not can_access_document(db, user, document) or session.user_id != user.id:
        raise HTTPException(status_code=403, detail="이 대화에 접근할 권한이 없습니다.")
    return session


@router.get("/api/chat/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
def list_messages(session_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    session = _get_session_or_404(db, session_id, user)
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at)
        .all()
    )


@router.post("/api/chat/sessions/{session_id}/messages", response_model=ChatMessageOut)
def send_message(
    session_id: uuid.UUID,
    payload: ChatMessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session = _get_session_or_404(db, session_id, user)
    document = db.get(Document, session.document_id)

    user_message = ChatMessage(session_id=session.id, role="user", content=payload.content)
    db.add(user_message)
    db.commit()

    history = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(10)
        .all()
    )
    history_context = "\n".join(f"{m.role}: {m.content}" for m in reversed(history))

    pages = (
        db.query(DocumentExtractedPage)
        .filter(DocumentExtractedPage.document_id == document.id)
        .order_by(DocumentExtractedPage.page_number)
        .all()
    )
    full_text = "\n".join(p.raw_text for p in pages)
    masked_text, was_masked = mask_sensitive_text(full_text)

    external_hits = []
    if document.security_level != "CONFIDENTIAL":
        external_hits = fetch_and_cache_external_legal_sources(db, payload.content)

    internal_hits = hybrid_search(
        db, payload.content, max_security_level=document.security_level, contract_type=document.contract_type
    )
    seen_chunk_ids = {h.chunk_id for h in external_hits}
    knowledge_hits = external_hits + [h for h in internal_hits if h.chunk_id not in seen_chunk_ids]
    known_chunk_ids = {h.chunk_id for h in knowledge_hits}
    knowledge_context = "\n".join(
        f"- [{h.doc_type}] {h.title} (chunk_id={h.chunk_id}): {h.excerpt}" for h in knowledge_hits
    ) or "검색된 법률지식자료가 없습니다."

    try:
        provider = get_ai_provider_for_document(document.security_level)
    except AIRoutingBlockedError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    user_prompt = build_chat_user_prompt(
        question=payload.content,
        contract_context=masked_text[:8000],
        knowledge_context=knowledge_context,
        history_context=history_context or "이전 대화 없음",
    )

    try:
        answer, usage = provider.answer_chat(CHAT_SYSTEM_PROMPT, user_prompt)
    except AIOutputValidationError as exc:
        raise HTTPException(status_code=502, detail=f"AI 응답 처리에 실패했습니다: {exc}")

    verified_citations = validate_citations_exist(answer.citations, known_chunk_ids)

    structured = answer.model_dump()
    structured["is_mock"] = provider.is_mock
    structured["ai_provider"] = provider.name
    content_text = answer.conclusion

    assistant_message = ChatMessage(
        session_id=session.id, role="assistant", content=content_text, structured_answer=structured
    )
    db.add(assistant_message)
    db.flush()

    for c in verified_citations:
        db.add(
            ChatMessageCitation(
                message_id=assistant_message.id,
                knowledge_chunk_id=c.knowledge_chunk_id,
                source_title=c.source_title,
                excerpt=c.excerpt,
            )
        )

    db.commit()
    db.refresh(assistant_message)
    return assistant_message
