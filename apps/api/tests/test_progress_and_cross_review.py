"""Progress-percent computation and the dual-AI cross-review flow."""
from dataclasses import dataclass

from app.models.analysis import AICrossReview, AnalysisRun
from app.models.document import Document
from app.models.enums import DocumentCategory, RoleName, SecurityLevel
from app.services.ai.schema import AIAnalysisOutput, AICrossReviewResult
from app.services.pipeline_progress import compute_progress_percent
from tests.conftest import login


@dataclass
class _Job:
    step: str
    status: str


# ------------------------------------------------------------- progress % --

def test_progress_is_100_on_terminal_status():
    assert compute_progress_percent(DocumentCategory.LITIGATION, "WAITING_FOR_REVIEW", []) == 100
    assert compute_progress_percent(DocumentCategory.CONTRACT, "COMPLETED", []) == 100


def test_progress_starts_at_zero_and_grows_monotonically():
    steps = ["파일 검증", "텍스트 추출", "OCR 수행", "주장·쟁점 구분", "법령·판례자료 검색", "AI 대응방향 검토", "보고서 생성 준비", "완료"]
    previous = -1
    for done_count in range(len(steps) + 1):
        jobs = [_Job(step=s, status="DONE") for s in steps[:done_count]]
        pct = compute_progress_percent(DocumentCategory.LITIGATION, "ANALYZING", jobs)
        assert pct > previous or (pct == previous == 99)
        previous = pct
    # all steps DONE but document not yet terminal → capped at 99, never a false 100
    assert previous == 99


def test_running_step_contributes_half_weight():
    done = [_Job("파일 검증", "DONE"), _Job("텍스트 추출", "DONE")]
    running = done + [_Job("AI 대응방향 검토", "RUNNING")]
    pct_done_only = compute_progress_percent(DocumentCategory.LITIGATION, "ANALYZING", done)
    pct_with_running = compute_progress_percent(DocumentCategory.LITIGATION, "ANALYZING", running)
    assert pct_with_running > pct_done_only


def test_unknown_steps_are_ignored():
    jobs = [_Job("존재하지 않는 단계", "DONE")]
    assert compute_progress_percent(DocumentCategory.CONTRACT, "ANALYZING", jobs) == 0


# ----------------------------------------------------------- cross review --

def _make_document_and_run(db, owner, security_level=SecurityLevel.INTERNAL):
    doc = Document(
        title="교차검토 테스트",
        document_category=DocumentCategory.LITIGATION,
        owner_id=owner.id,
        security_level=security_level,
    )
    db.add(doc)
    db.commit()
    run = AnalysisRun(document_id=doc.id, ai_provider="anthropic", ai_model="claude-sonnet-5", status="DONE", is_mock=False)
    db.add(run)
    db.commit()
    return doc, run


_AI_OUTPUT = AIAnalysisOutput(
    scope_summary="요약",
    overall_risk_level="HIGH",
    top_risks_summary="위험 요약",
    findings=[],
)


def test_cross_review_disabled_when_secondary_not_configured(db_session, make_user, monkeypatch):
    from app.services.ai import router as ai_router
    from app.services.ai.cross_review import run_cross_review

    monkeypatch.setattr(ai_router.settings, "SECONDARY_AI_PROVIDER", "")
    owner, _ = make_user()
    doc, run = _make_document_and_run(db_session, owner)

    assert run_cross_review(db_session, doc, run, _AI_OUTPUT, "원문") is None
    assert db_session.query(AICrossReview).filter(AICrossReview.document_id == doc.id).count() == 0


def test_cross_review_creates_row_with_mock_secondary(db_session, make_user, monkeypatch):
    from app.services.ai import router as ai_router
    from app.services.ai.cross_review import run_cross_review

    monkeypatch.setattr(ai_router.settings, "SECONDARY_AI_PROVIDER", "mock")
    owner, _ = make_user()
    doc, run = _make_document_and_run(db_session, owner)

    row = run_cross_review(db_session, doc, run, _AI_OUTPUT, "원문 텍스트")
    assert row is not None
    assert row.provider == "mock"
    assert row.agreement_level in ("AGREE", "PARTIALLY_AGREE", "DISAGREE")
    assert row.overall_opinion


def test_cross_review_skipped_for_confidential_documents(db_session, make_user, monkeypatch):
    from app.services.ai import router as ai_router
    from app.services.ai.cross_review import run_cross_review

    monkeypatch.setattr(ai_router.settings, "SECONDARY_AI_PROVIDER", "mock")
    owner, _ = make_user()
    doc, run = _make_document_and_run(db_session, owner, security_level=SecurityLevel.CONFIDENTIAL)

    assert run_cross_review(db_session, doc, run, _AI_OUTPUT, "원문") is None


def test_cross_review_skipped_when_secondary_equals_primary(db_session, make_user, monkeypatch):
    from app.services.ai import router as ai_router
    from app.services.ai.cross_review import run_cross_review

    monkeypatch.setattr(ai_router.settings, "SECONDARY_AI_PROVIDER", "mock")
    owner, _ = make_user()
    doc, run = _make_document_and_run(db_session, owner)
    run.ai_provider = "mock"  # 1차와 2차가 같은 프로바이더 → 자기검증은 무의미
    db_session.commit()

    assert run_cross_review(db_session, doc, run, _AI_OUTPUT, "원문") is None


def test_cross_review_endpoint_returns_row_or_null(client, db_session, make_user, monkeypatch):
    from app.services.ai import router as ai_router
    from app.services.ai.cross_review import run_cross_review

    user, password = make_user(RoleName.USER)
    _, _csrf = login(client, user.email, password)
    doc, run = _make_document_and_run(db_session, user)

    resp = client.get(f"/api/documents/{doc.id}/cross-review")
    assert resp.status_code == 200
    assert resp.json() is None

    monkeypatch.setattr(ai_router.settings, "SECONDARY_AI_PROVIDER", "mock")
    run_cross_review(db_session, doc, run, _AI_OUTPUT, "원문")

    resp = client.get(f"/api/documents/{doc.id}/cross-review")
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "mock"
    assert body["agreement_level"] in ("AGREE", "PARTIALLY_AGREE", "DISAGREE")


def test_agreement_level_normalization():
    assert AICrossReviewResult(agreement_level="agree", overall_opinion="ok").agreement_level == "AGREE"
    assert AICrossReviewResult(agreement_level="이상한값", overall_opinion="ok").agreement_level == "PARTIALLY_AGREE"
    # float confidence (real Claude/Gemini behavior) is coerced to 0-100 int
    assert AICrossReviewResult(agreement_level="AGREE", overall_opinion="ok", confidence=0.8).confidence == 80
