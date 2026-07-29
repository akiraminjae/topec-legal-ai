import io

import pytest

from app.models.analysis import AnalysisRun, DocumentSummary, RiskFinding
from app.models.document import Document, DocumentExtractedPage
from app.models.enums import DocumentCategory, DocumentStatus, RoleName
from app.models.legal_case import CaseChatMessage, CaseChatMessageCitation, CaseChatSession, CaseDocument, CaseKnowledgeChunk, LegalCase
from app.services.legal_case.rag import index_case_document, search_case_knowledge
from tests.conftest import login


@pytest.fixture(autouse=True)
def _force_mock_ai_provider(monkeypatch):
    """Case analysis/chat tests must never hit a real, billed AI API — this repo's
    .env is configured with a real Anthropic key for manual/browser testing, so
    without this override every automated test run would make live API calls."""
    import app.services.ai.router as ai_router_module

    monkeypatch.setattr(ai_router_module.settings, "AI_PROVIDER", "mock")


def _create_case(client, csrf, case_name="테스트 사건", security_level="INTERNAL"):
    resp = client.post(
        "/api/legal-cases",
        json={"case_name": case_name, "security_level": security_level},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def _upload_file(client, csrf, case_id, batch_id, filename="doc.txt", content=b"test content", doc_type="COMPLAINT"):
    files = {"file": (filename, io.BytesIO(content), "text/plain")}
    return client.post(
        f"/api/legal-cases/{case_id}/upload-batches/{batch_id}/files",
        files=files,
        params={"litigation_document_type": doc_type},
        headers={"X-CSRF-Token": csrf},
    )


def _seed_completed_case_document(db_session, case_id, owner_id, title="문서1", summary_text="요약"):
    """Bypasses the (Celery/AI-dependent) pipeline and directly inserts a
    finished document + its analysis output, so analysis/report tests can run
    fast and deterministically without a live worker or AI call."""
    document = Document(
        title=title,
        document_category=DocumentCategory.LITIGATION,
        litigation_document_type="COMPLAINT",
        owner_id=owner_id,
        status=DocumentStatus.WAITING_FOR_REVIEW,
        overall_risk_level="MEDIUM",
        legal_review_required=True,
    )
    db_session.add(document)
    db_session.flush()

    run = AnalysisRun(document_id=document.id, ai_provider="mock", ai_model="mock", status="DONE", is_mock=True)
    db_session.add(run)
    db_session.flush()

    db_session.add(
        DocumentSummary(
            document_id=document.id,
            analysis_run_id=run.id,
            scope_summary=summary_text,
            overall_risk_level="MEDIUM",
            top_risks_summary="핵심 쟁점 요약",
        )
    )
    db_session.add(
        RiskFinding(
            document_id=document.id,
            analysis_run_id=run.id,
            category="OPPOSING_ARGUMENT",
            title="테스트 쟁점",
            risk_level="MEDIUM",
            issue_summary="쟁점 요약",
            reason="사유",
            impact_on_topec="영향",
            recommended_action="대응",
            legal_review_required=True,
            confidence=50,
        )
    )
    case_doc = CaseDocument(case_id=case_id, document_id=document.id, sequence_number=1)
    db_session.add(case_doc)
    db_session.commit()
    return document, case_doc


# --------------------------------------------------------------- CRUD/access --

def test_create_and_get_case(client, make_user):
    user, password = make_user(RoleName.USER)
    _, csrf = login(client, user.email, password)
    case_id = _create_case(client, csrf)

    resp = client.get(f"/api/legal-cases/{case_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["case_name"] == "테스트 사건"
    assert body["document_count"] == 0
    assert body["status"] == "ACTIVE"


def test_other_user_cannot_access_case_idor(client, make_user):
    owner, owner_password = make_user(RoleName.USER)
    _, csrf = login(client, owner.email, owner_password)
    case_id = _create_case(client, csrf)

    other, other_password = make_user(RoleName.USER)
    login(client, other.email, other_password)

    resp = client.get(f"/api/legal-cases/{case_id}")
    assert resp.status_code == 403


def test_admin_can_access_any_case(client, make_user):
    owner, owner_password = make_user(RoleName.USER)
    _, csrf = login(client, owner.email, owner_password)
    case_id = _create_case(client, csrf)

    admin, admin_password = make_user(RoleName.SYSTEM_ADMIN)
    login(client, admin.email, admin_password)

    resp = client.get(f"/api/legal-cases/{case_id}")
    assert resp.status_code == 200


def test_update_and_delete_case(client, make_user, db_session):
    user, password = make_user(RoleName.USER)
    _, csrf = login(client, user.email, password)
    case_id = _create_case(client, csrf)

    resp = client.patch(f"/api/legal-cases/{case_id}", json={"status": "CLOSED"}, headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 200
    assert resp.json()["status"] == "CLOSED"

    resp = client.delete(f"/api/legal-cases/{case_id}", headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 200

    case = db_session.get(LegalCase, case_id)
    assert case.is_deleted is True

    resp = client.get(f"/api/legal-cases/{case_id}")
    assert resp.status_code == 404


# ------------------------------------------------------------- batch upload --

def test_batch_upload_and_exact_duplicate_detection(client, make_user):
    user, password = make_user(RoleName.USER)
    _, csrf = login(client, user.email, password)
    case_id = _create_case(client, csrf)

    resp = client.post(f"/api/legal-cases/{case_id}/upload-batches", headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 200
    batch_id = resp.json()["id"]

    content = b"identical content for dedup test"
    resp1 = _upload_file(client, csrf, case_id, batch_id, filename="a.txt", content=content)
    assert resp1.status_code == 200
    assert resp1.json()["is_duplicate"] is False

    resp2 = _upload_file(client, csrf, case_id, batch_id, filename="a_renamed.txt", content=content)
    assert resp2.status_code == 200
    assert resp2.json()["is_duplicate"] is True
    assert resp2.json()["duplicate_of_document_id"] == resp1.json()["document_id"]

    resp = client.get(f"/api/legal-cases/{case_id}/upload-batches/{batch_id}")
    batch = resp.json()
    assert batch["total_files"] == 2
    assert batch["uploaded_files"] == 2
    assert batch["failed_files"] == 1  # the duplicate counts toward failed/needs-review, not processed

    resp = client.get(f"/api/legal-cases/{case_id}/documents")
    docs = resp.json()
    assert len(docs) == 2
    assert sum(1 for d in docs if d["is_duplicate"]) == 1


def test_case_batch_does_not_reuse_a_non_primary_attachment_of_a_multi_file_document(client, make_user, monkeypatch):
    """Regression test: a regular (non-case) Document can have several attached
    files via §documents.py multi-attach — but only the first ever gets
    analyzed. If a case batch upload's exact-duplicate check matched one of
    those *other* (unanalyzed) attachments and reused that Document's id, every
    such file would end up wrongly aliased to the SAME single-file analysis,
    and the individual files would never get their own independent analysis.
    Content identical to a non-primary attachment must become its own new,
    independently-analyzed Document instead."""
    dispatched = []
    monkeypatch.setattr(
        "app.worker.celery_app.celery_app.send_task", lambda name, args=None, **kw: dispatched.append((name, args))
    )

    user, password = make_user(RoleName.USER)
    _, csrf = login(client, user.email, password)

    # Set up a regular multi-attach document: primary file (analysis dispatched)
    # + one attachment (skip_analysis=True, never independently analyzed).
    resp = client.post(
        "/api/documents",
        json={
            "title": "다중첨부 원본",
            "contract_type": "SUBCONTRACT",
            "topec_position": "PRINCIPAL_CONTRACTOR",
            "security_level": "INTERNAL",
            "retention_policy": "KEEP_1_YEAR",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200
    source_document_id = resp.json()["id"]

    primary_content = b"primary contract body"
    attachment_content = b"attachment body reused later in a case"
    client.post(
        f"/api/documents/{source_document_id}/files",
        files={"file": ("primary.txt", io.BytesIO(primary_content), "text/plain")},
        params={"skip_analysis": False},
        headers={"X-CSRF-Token": csrf},
    )
    client.post(
        f"/api/documents/{source_document_id}/files",
        files={"file": ("attachment.txt", io.BytesIO(attachment_content), "text/plain")},
        params={"skip_analysis": True},
        headers={"X-CSRF-Token": csrf},
    )
    dispatched.clear()  # only care about dispatches from the case batch upload below

    case_id = _create_case(client, csrf)
    resp = client.post(f"/api/legal-cases/{case_id}/upload-batches", headers={"X-CSRF-Token": csrf})
    batch_id = resp.json()["id"]

    # Upload content identical to the *attachment* (not the primary file) into the case.
    resp = _upload_file(client, csrf, case_id, batch_id, filename="reused.txt", content=attachment_content)
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_duplicate"] is False  # must NOT be treated as a safe, already-analyzed duplicate
    assert body["document_id"] != source_document_id  # must be its own new, independent Document
    assert len(dispatched) == 1  # analysis was dispatched for the new document
    assert dispatched[0][0] == "app.worker.tasks.process_case_document_task"


def test_batch_upload_rejects_oversized_file(client, make_user, monkeypatch):
    import app.services.legal_case.batch as batch_module

    monkeypatch.setattr(batch_module.settings, "LITIGATION_SINGLE_FILE_MAX_SIZE_MB", 0.00001)

    user, password = make_user(RoleName.USER)
    _, csrf = login(client, user.email, password)
    case_id = _create_case(client, csrf)
    resp = client.post(f"/api/legal-cases/{case_id}/upload-batches", headers={"X-CSRF-Token": csrf})
    batch_id = resp.json()["id"]

    resp = _upload_file(client, csrf, case_id, batch_id, content=b"x" * 1000)
    assert resp.status_code == 400


def test_batch_upload_isolated_between_cases(client, make_user):
    """A file uploaded into case A must not appear in case B's document list."""
    user, password = make_user(RoleName.USER)
    _, csrf = login(client, user.email, password)
    case_a = _create_case(client, csrf, case_name="사건A")
    case_b = _create_case(client, csrf, case_name="사건B")

    resp = client.post(f"/api/legal-cases/{case_a}/upload-batches", headers={"X-CSRF-Token": csrf})
    batch_a = resp.json()["id"]
    _upload_file(client, csrf, case_a, batch_a, filename="only_in_a.txt")

    resp = client.get(f"/api/legal-cases/{case_b}/documents")
    assert resp.json() == []
    resp = client.get(f"/api/legal-cases/{case_a}/documents")
    assert len(resp.json()) == 1


# ----------------------------------------------------------- case analysis --

def test_case_analysis_requires_at_least_one_finished_document(client, make_user):
    user, password = make_user(RoleName.USER)
    _, csrf = login(client, user.email, password)
    case_id = _create_case(client, csrf)

    resp = client.post(f"/api/legal-cases/{case_id}/analysis", headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 409


def test_case_analysis_synthesizes_document_summaries(client, make_user, db_session):
    user, password = make_user(RoleName.USER)
    _, csrf = login(client, user.email, password)
    case_id = _create_case(client, csrf)

    case = db_session.get(LegalCase, case_id)
    _seed_completed_case_document(db_session, case_id, case.owner_user_id, title="소장", summary_text="원고 청구 요약")
    _seed_completed_case_document(db_session, case_id, case.owner_user_id, title="답변서", summary_text="피고 답변 요약")

    resp = client.post(f"/api/legal-cases/{case_id}/analysis", headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["document_count"] == 2
    assert body["is_mock"] is True
    assert body["case_overview"]

    resp = client.get(f"/api/legal-cases/{case_id}/analysis")
    assert resp.status_code == 200
    assert resp.json()["document_count"] == 2


# ---------------------------------------------------------------- reports --

def test_case_report_requires_prior_analysis(client, make_user):
    user, password = make_user(RoleName.USER)
    _, csrf = login(client, user.email, password)
    case_id = _create_case(client, csrf)

    resp = client.post(
        f"/api/legal-cases/{case_id}/reports",
        json={"report_type": "PREPARATORY_BRIEF_DRAFT", "format": "DOCX"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 409


def test_case_report_generation_after_analysis(client, make_user, db_session):
    user, password = make_user(RoleName.USER)
    _, csrf = login(client, user.email, password)
    case_id = _create_case(client, csrf)
    case = db_session.get(LegalCase, case_id)
    _seed_completed_case_document(db_session, case_id, case.owner_user_id)

    resp = client.post(f"/api/legal-cases/{case_id}/analysis", headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 200

    resp = client.post(
        f"/api/legal-cases/{case_id}/reports",
        json={"report_type": "PREPARATORY_BRIEF_DRAFT", "format": "DOCX"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200
    report_id = resp.json()["id"]

    resp = client.get(f"/api/legal-cases/{case_id}/reports/{report_id}/download")
    assert resp.status_code == 200
    assert len(resp.content) > 0


# --------------------------------------------------------------- case RAG --

def test_search_case_knowledge_isolated_between_cases(client, make_user, db_session):
    user, password = make_user(RoleName.USER)
    _, csrf = login(client, user.email, password)
    case_a = _create_case(client, csrf, case_name="RAG-A")
    case_b = _create_case(client, csrf, case_name="RAG-B")
    case_a_row = db_session.get(LegalCase, case_a)

    document, _ = _seed_completed_case_document(db_session, case_a, case_a_row.owner_user_id, title="사건A 문서")
    db_session.add(DocumentExtractedPage(document_id=document.id, page_number=1, raw_text="고유한 검색 대상 문자열 XYZ123"))
    db_session.commit()

    index_case_document(db_session, case_a, document.id)

    hits_in_a = search_case_knowledge(db_session, case_a, "XYZ123")
    assert len(hits_in_a) > 0

    hits_in_b = search_case_knowledge(db_session, case_b, "XYZ123")
    assert len(hits_in_b) == 0


def test_delete_case_removes_case_knowledge_chunks(client, make_user, db_session):
    user, password = make_user(RoleName.USER)
    _, csrf = login(client, user.email, password)
    case_id = _create_case(client, csrf)
    case = db_session.get(LegalCase, case_id)
    document, _ = _seed_completed_case_document(db_session, case_id, case.owner_user_id)

    db_session.add(
        CaseKnowledgeChunk(case_id=case_id, document_id=document.id, chunk_index=0, content="삭제 검증용 청크")
    )
    db_session.commit()

    resp = client.delete(f"/api/legal-cases/{case_id}", headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 200

    remaining = db_session.query(CaseKnowledgeChunk).filter(CaseKnowledgeChunk.case_id == case_id).count()
    assert remaining == 0


def test_delete_case_with_existing_chat_citation_does_not_fail(client, make_user, db_session):
    """Regression test: deleting a case whose chat history cites one of its own
    case_knowledge_chunks used to raise a ForeignKeyViolation (500) because the
    chunk was deleted while a case_chat_message_citations row still pointed at
    it. See services/legal_case/rag.py::delete_case_knowledge."""
    user, password = make_user(RoleName.USER)
    _, csrf = login(client, user.email, password)
    case_id = _create_case(client, csrf)
    case = db_session.get(LegalCase, case_id)
    document, _ = _seed_completed_case_document(db_session, case_id, case.owner_user_id)

    chunk = CaseKnowledgeChunk(case_id=case_id, document_id=document.id, chunk_index=0, content="인용된 청크")
    db_session.add(chunk)
    db_session.flush()

    session = CaseChatSession(case_id=case_id, user_id=case.owner_user_id, title="테스트")
    db_session.add(session)
    db_session.flush()
    message = CaseChatMessage(session_id=session.id, role="assistant", content="답변")
    db_session.add(message)
    db_session.flush()
    db_session.add(
        CaseChatMessageCitation(message_id=message.id, case_knowledge_chunk_id=chunk.id, source_title="인용 출처")
    )
    db_session.commit()

    resp = client.delete(f"/api/legal-cases/{case_id}", headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 200

    db_session.refresh(message)
    citation = db_session.query(CaseChatMessageCitation).filter(CaseChatMessageCitation.message_id == message.id).first()
    assert citation.case_knowledge_chunk_id is None  # FK cleared, message/citation text preserved
    assert citation.source_title == "인용 출처"
