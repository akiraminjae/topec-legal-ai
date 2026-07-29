from app.models.enums import RoleName
from tests.conftest import login


def _create_document(client, csrf, title="테스트 계약"):
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


def test_owner_can_access_own_document(client, make_user):
    user, password = make_user(RoleName.USER)
    _, csrf = login(client, user.email, password)
    doc_id = _create_document(client, csrf)

    resp = client.get(f"/api/documents/{doc_id}")
    assert resp.status_code == 200


def test_other_user_cannot_access_document_idor(client, make_user):
    owner, owner_password = make_user(RoleName.USER)
    _, csrf = login(client, owner.email, owner_password)
    doc_id = _create_document(client, csrf)

    other, other_password = make_user(RoleName.USER)
    login(client, other.email, other_password)

    resp = client.get(f"/api/documents/{doc_id}")
    assert resp.status_code == 403


def test_admin_can_access_any_document(client, make_user):
    owner, owner_password = make_user(RoleName.USER)
    _, csrf = login(client, owner.email, owner_password)
    doc_id = _create_document(client, csrf)

    admin, admin_password = make_user(RoleName.SYSTEM_ADMIN)
    login(client, admin.email, admin_password)

    resp = client.get(f"/api/documents/{doc_id}")
    assert resp.status_code == 200


def test_non_admin_cannot_list_users(client, make_user):
    user, password = make_user(RoleName.USER)
    login(client, user.email, password)
    resp = client.get("/api/users")
    assert resp.status_code == 403


def test_non_legal_reviewer_cannot_access_review_queue(client, make_user):
    user, password = make_user(RoleName.USER)
    login(client, user.email, password)
    resp = client.get("/api/legal-reviews")
    assert resp.status_code == 403
