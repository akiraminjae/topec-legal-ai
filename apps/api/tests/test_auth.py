from app.core.config import get_settings
from app.models.enums import RoleName
from tests.conftest import login

settings = get_settings()


def test_login_success(client, make_user):
    user, password = make_user(RoleName.USER)
    resp, _ = login(client, user.email, password)
    assert resp.status_code == 200
    assert resp.json()["email"] == user.email


def test_login_wrong_password(client, make_user):
    user, _ = make_user(RoleName.USER)
    resp, _ = login(client, user.email, "WrongPassword123!")
    assert resp.status_code == 401


def test_account_lockout_after_max_attempts(client, make_user):
    user, password = make_user(RoleName.USER)
    for _ in range(settings.LOGIN_MAX_FAILED_ATTEMPTS):
        client.post("/api/auth/login", json={"identifier": user.email, "password": "wrong"})

    resp, _ = login(client, user.email, password)
    assert resp.status_code == 423


def test_me_requires_session(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_csrf_required_for_mutations(client, make_user):
    user, password = make_user(RoleName.SYSTEM_ADMIN)
    login(client, user.email, password)
    # Deliberately omit X-CSRF-Token header
    resp = client.post("/api/departments", json={"name": "테스트부서", "code": f"T{user.id.hex[:6]}"})
    assert resp.status_code == 403


def test_inactive_account_cannot_login(client, make_user, db_session):
    user, password = make_user(RoleName.USER)
    user.is_active = False
    db_session.commit()
    resp, _ = login(client, user.email, password)
    assert resp.status_code == 401
