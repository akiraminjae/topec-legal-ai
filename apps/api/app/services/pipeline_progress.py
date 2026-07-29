"""0~100% progress estimation for the document analysis pipeline.

The pipeline records one DocumentProcessingJob row per step; this module turns
those rows into a single percentage for the UI's progress gauge. Steps are
weighted by their typical wall-clock share (the AI review call dominates), so
the number moves believably instead of jumping 12.5% per step. A RUNNING step
contributes half of its weight.
"""
from app.models.enums import DocumentCategory

# Weight per step name. Contract and litigation pipelines share most names;
# category determines which steps are *expected* so the denominator is right.
_STEP_WEIGHTS: dict[str, int] = {
    "파일 검증": 4,
    "텍스트 추출": 10,
    "OCR 수행": 8,
    "조항 구분": 8,
    "주장·쟁점 구분": 8,
    "주요정보 추출": 4,
    "위험규칙 분석": 6,
    "법령·판례자료 검색": 10,
    "AI 법률검토": 44,
    "AI 대응방향 검토": 48,
    "보고서 생성 준비": 4,
    "완료": 2,
}

_CONTRACT_STEPS = ["파일 검증", "텍스트 추출", "OCR 수행", "조항 구분", "주요정보 추출", "위험규칙 분석", "법령·판례자료 검색", "AI 법률검토", "보고서 생성 준비", "완료"]
_LITIGATION_STEPS = ["파일 검증", "텍스트 추출", "OCR 수행", "주장·쟁점 구분", "법령·판례자료 검색", "AI 대응방향 검토", "보고서 생성 준비", "완료"]

_TERMINAL_DONE_STATUSES = {"WAITING_FOR_REVIEW", "IN_LEGAL_REVIEW", "COMPLETED", "ARCHIVED"}


def compute_progress_percent(document_category: str, document_status: str, jobs) -> int:
    """jobs: iterable with .step and .status (DocumentProcessingJob or schema rows)."""
    if document_status in _TERMINAL_DONE_STATUSES:
        return 100

    expected = _LITIGATION_STEPS if document_category == DocumentCategory.LITIGATION else _CONTRACT_STEPS
    total = sum(_STEP_WEIGHTS[s] for s in expected)

    earned = 0.0
    for job in jobs:
        weight = _STEP_WEIGHTS.get(job.step)
        if weight is None or job.step not in expected:
            continue
        if job.status == "DONE":
            earned += weight
        elif job.status == "RUNNING":
            earned += weight / 2

    percent = round(earned / total * 100)
    # Never claim 100% before the document itself reaches a terminal status.
    return max(0, min(percent, 99))
