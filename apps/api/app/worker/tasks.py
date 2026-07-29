from app.db.session import SessionLocal
from app.services.document_pipeline import process_document
from app.services.litigation_pipeline import process_litigation_document
from app.worker.celery_app import celery_app


@celery_app.task(name="app.worker.tasks.process_case_document_task", bind=True, max_retries=0)
def process_case_document_task(self, case_document_id: str) -> str:
    """Runs the existing litigation pipeline for one file in a case upload batch,
    then indexes it into the case's own RAG index and refreshes the batch's
    aggregate progress. A failure in one file's pipeline is caught here (the
    pipeline itself already records it on the Document) so it never aborts the
    rest of the batch — see services/legal_case/batch.py module docstring.
    """
    from app.models.legal_case import CaseDocument
    from app.services.legal_case.batch import recompute_batch_progress
    from app.services.legal_case.extraction import extract_case_document_metadata
    from app.services.legal_case.rag import index_case_document

    db = SessionLocal()
    try:
        case_doc = db.get(CaseDocument, case_document_id)
        if not case_doc:
            return "MISSING"
        try:
            process_litigation_document(db, case_doc.document_id)
        except Exception:  # noqa: BLE001 — isolate this file's failure from the rest of the batch
            import logging

            logging.getLogger(__name__).exception("process_litigation_document failed for case_document %s", case_document_id)
        else:
            try:
                index_case_document(db, case_doc.case_id, case_doc.document_id)
            except Exception:  # noqa: BLE001
                import logging

                logging.getLogger(__name__).exception("index_case_document failed for case_document %s", case_document_id)
            try:
                extract_case_document_metadata(db, case_doc.case_id, case_doc.document_id)
            except Exception:  # noqa: BLE001
                import logging

                logging.getLogger(__name__).exception("extract_case_document_metadata failed for case_document %s", case_document_id)
        finally:
            if case_doc.batch_id:
                recompute_batch_progress(db, case_doc.batch_id)
        return "OK"
    finally:
        db.close()


@celery_app.task(name="app.worker.tasks.ping")
def ping() -> str:
    return "pong"


@celery_app.task(name="app.worker.tasks.send_verification_email_task", bind=True, max_retries=2, default_retry_delay=30)
def send_verification_email_task(self, user_id: str, token: str) -> str:
    """Sends the signup e-mail verification link. Runs in the worker so the
    signup request itself never blocks on (or fails because of) SMTP latency."""
    from app.core.config import get_settings
    from app.models.user import User
    from app.services.email import send_signup_verification_email

    settings = get_settings()
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        if not user:
            return "MISSING"
        verification_url = f"{settings.APP_PUBLIC_URL}/verify-email?token={token}"
        try:
            send_signup_verification_email(user.email, user.full_name, verification_url)
        except Exception as exc:  # noqa: BLE001 — retry transient SMTP failures
            raise self.retry(exc=exc)
        return "OK"
    finally:
        db.close()


@celery_app.task(name="app.worker.tasks.process_document_task", bind=True, max_retries=0)
def process_document_task(self, document_id: str) -> str:
    from app.models.document import Document
    from app.models.enums import DocumentCategory

    db = SessionLocal()
    try:
        document = db.get(Document, document_id)
        if document and document.document_category == DocumentCategory.LITIGATION:
            process_litigation_document(db, document_id)
        else:
            process_document(db, document_id)
        return "OK"
    finally:
        db.close()


@celery_app.task(name="app.worker.tasks.apply_retention_policy_task")
def apply_retention_policy_task() -> str:
    """Periodic task: hard-deletes documents whose retention period has expired.

    Scheduled via Celery beat in production; safe to invoke manually/for tests.
    """
    from datetime import datetime, timezone

    from app.models.document import Document
    from app.models.enums import DocumentStatus
    from app.services.document_service import purge_document

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        expired = (
            db.query(Document)
            .filter(
                Document.retention_expires_at.isnot(None),
                Document.retention_expires_at < now,
                Document.status != DocumentStatus.DELETED,
                Document.is_deleted.is_(False),
            )
            .all()
        )
        for doc in expired:
            purge_document(db, doc)
        return f"purged {len(expired)} documents"
    finally:
        db.close()
