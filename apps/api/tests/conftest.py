import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings as _get_settings

_base_settings = _get_settings()


def _resolve_test_database_url() -> str:
    """Tests always run against their own database, never the dev/demo one —
    otherwise every `pytest` run leaves stray documents/users behind in the
    database the running app (and the UI) is also looking at. Derived by
    suffixing the configured DATABASE_URL's database name with `_test`, unless
    TEST_DATABASE_URL is set explicitly (e.g. in CI)."""
    override = os.environ.get("TEST_DATABASE_URL")
    if override:
        return override
    url = make_url(_base_settings.DATABASE_URL)
    # str(url) redacts the password (renders it as "***") — always use
    # render_as_string(hide_password=False) when the result needs to actually
    # authenticate, not just be logged.
    return url.set(database=f"{url.database}_test").render_as_string(hide_password=False)


TEST_DATABASE_URL = _resolve_test_database_url()
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
_get_settings.cache_clear()

from app.core.config import get_settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.enums import RoleName  # noqa: E402
from app.models.user import Department, Role, User, UserRole  # noqa: E402
from app import models  # noqa: E402,F401

settings = get_settings()


def _ensure_test_database_exists() -> None:
    target_url = make_url(TEST_DATABASE_URL)
    maintenance_url = target_url.set(database="postgres")
    maintenance_engine = create_engine(maintenance_url, isolation_level="AUTOCOMMIT")
    try:
        with maintenance_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": target_url.database}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{target_url.database}"'))
    finally:
        maintenance_engine.dispose()


_ensure_test_database_exists()

engine = create_engine(TEST_DATABASE_URL, future=True)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    # Drop and recreate on every session rather than a plain create_all: the
    # latter only creates missing tables and silently leaves a stale schema in
    # place after a model change (new/renamed columns), which then fails with
    # confusing "column does not exist" errors instead of just being current.
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def db_session():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _ensure_role(db, name: RoleName) -> Role:
    role = db.query(Role).filter(Role.name == name).first()
    if not role:
        role = Role(name=name, description=name.value)
        db.add(role)
        db.flush()
    return role


@pytest.fixture()
def make_user(db_session):
    def _make(role: RoleName = RoleName.USER, password: str = "TestPassword123!", email: str | None = None):
        dept = Department(name=f"부서-{uuid.uuid4().hex[:6]}", code=f"D{uuid.uuid4().hex[:6]}")
        db_session.add(dept)
        db_session.flush()

        email = email or f"user-{uuid.uuid4().hex[:8]}@topec.local"
        user = User(
            employee_no=f"EMP-{uuid.uuid4().hex[:8]}",
            email=email,
            full_name="테스트 사용자",
            department_id=dept.id,
            password_hash=hash_password(password),
            must_change_password=False,
        )
        db_session.add(user)
        db_session.flush()

        role_row = _ensure_role(db_session, role)
        db_session.add(UserRole(user_id=user.id, role_id=role_row.id))
        db_session.commit()
        return user, password

    return _make


def login(client: TestClient, email: str, password: str):
    resp = client.post("/api/auth/login", json={"identifier": email, "password": password})
    csrf = client.cookies.get("topec_legal_csrf")
    return resp, csrf
