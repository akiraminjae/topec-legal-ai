"""Multi-file attachment support for the regular (CONTRACT/LITIGATION)
document upload flow — a document can have several DocumentFile rows, but
the pipeline always analyzes the first-uploaded one. `skip_analysis=true`
lets the frontend attach several files in one submit without dispatching a
redundant analysis run per file (see routers/documents.py::upload_document_file).
"""
import io

from app.models.enums import RoleName
from tests.conftest import login


def _create_document(client, csrf, title="다중첨부 테스트"):
    resp = client.post(
        "/api/documents",
        json={
            "title": title,
            "contract_type": "SUBCONTRACT",
            "topec_position": "PRINCIPAL_CONTRACTOR",
            "security_level": "INTERNAL",
            "retention_policy": "KEEP_1_YEAR",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200
    return resp.json()["id"]


def _upload(client, csrf, document_id, filename, content, skip_analysis):
    files = {"file": (filename, io.BytesIO(content), "text/plain")}
    return client.post(
        f"/api/documents/{document_id}/files",
        files=files,
        params={"skip_analysis": skip_analysis},
        headers={"X-CSRF-Token": csrf},
    )


def test_multiple_files_can_be_attached_and_listed(client, make_user, monkeypatch):
    dispatched = []
    monkeypatch.setattr(
        "app.worker.celery_app.celery_app.send_task", lambda name, args=None, **kw: dispatched.append((name, args))
    )

    user, password = make_user(RoleName.USER)
    _, csrf = login(client, user.email, password)
    document_id = _create_document(client, csrf)

    r1 = _upload(client, csrf, document_id, "primary.txt", b"primary contract text", skip_analysis=False)
    assert r1.status_code == 200
    r2 = _upload(client, csrf, document_id, "attachment1.txt", b"annex A", skip_analysis=True)
    assert r2.status_code == 200
    r3 = _upload(client, csrf, document_id, "attachment2.txt", b"annex B", skip_analysis=True)
    assert r3.status_code == 200

    # Only the skip_analysis=False call should have dispatched analysis.
    assert len(dispatched) == 1
    assert dispatched[0][0] == "app.worker.tasks.process_document_task"

    resp = client.get(f"/api/documents/{document_id}/files")
    assert resp.status_code == 200
    listed = resp.json()
    assert len(listed) == 3
    assert [f["original_filename"] for f in listed] == ["primary.txt", "attachment1.txt", "attachment2.txt"]


def test_skip_analysis_true_does_not_change_document_status(client, make_user, monkeypatch, db_session):
    from app.models.document import Document

    monkeypatch.setattr("app.worker.celery_app.celery_app.send_task", lambda name, args=None, **kw: None)

    user, password = make_user(RoleName.USER)
    _, csrf = login(client, user.email, password)
    document_id = _create_document(client, csrf)

    before = db_session.get(Document, document_id).status
    _upload(client, csrf, document_id, "attachment.txt", b"reference material", skip_analysis=True)
    db_session.refresh(db_session.get(Document, document_id))
    after = db_session.get(Document, document_id).status
    assert before == after == "UPLOADED"


def test_reattaching_identical_file_to_same_document_is_silently_reused(client, make_user, monkeypatch):
    """Regression test: uploading the exact same file content twice to the same
    document used to raise 409 "이미 업로드된 동일한 파일이 존재합니다." — with
    multi-file attach it's common to accidentally select the same file twice,
    or retry a submission where some files already succeeded. This must not
    error; the existing attachment is reused instead."""
    monkeypatch.setattr("app.worker.celery_app.celery_app.send_task", lambda name, args=None, **kw: None)

    user, password = make_user(RoleName.USER)
    _, csrf = login(client, user.email, password)
    document_id = _create_document(client, csrf)

    r1 = _upload(client, csrf, document_id, "annex.txt", b"identical content", skip_analysis=True)
    assert r1.status_code == 200
    first_file_id = r1.json()["id"]

    r2 = _upload(client, csrf, document_id, "annex-renamed.txt", b"identical content", skip_analysis=False)
    assert r2.status_code == 200
    assert r2.json()["id"] == first_file_id  # reused, no duplicate row

    resp = client.get(f"/api/documents/{document_id}/files")
    assert len(resp.json()) == 1


def test_identical_file_on_a_different_document_is_still_allowed(client, make_user, monkeypatch):
    """The old global (cross-document) SHA-256 uniqueness check blocked
    legitimately attaching the same annex file (e.g. a shared power-of-attorney
    PDF) to more than one document. That must now be allowed."""
    monkeypatch.setattr("app.worker.celery_app.celery_app.send_task", lambda name, args=None, **kw: None)

    user, password = make_user(RoleName.USER)
    _, csrf = login(client, user.email, password)
    document_a = _create_document(client, csrf, title="문서A")
    document_b = _create_document(client, csrf, title="문서B")

    r1 = _upload(client, csrf, document_a, "shared-annex.txt", b"shared attachment content", skip_analysis=False)
    assert r1.status_code == 200

    r2 = _upload(client, csrf, document_b, "shared-annex.txt", b"shared attachment content", skip_analysis=False)
    assert r2.status_code == 200
    assert r2.json()["id"] != r1.json()["id"]
