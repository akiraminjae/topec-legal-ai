"""Mask personally-identifiable information before sending contract text to an
external AI provider. Applied only to the text handed to the AI Provider; the
original text stored in the DB/object storage is never altered."""
import re

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("RRN", re.compile(r"\d{6}[-\s]?[1-4]\d{6}")),  # 주민등록번호
    ("PASSPORT", re.compile(r"\b[MS]\d{8}\b")),  # 여권번호(형식 예시)
    ("PHONE", re.compile(r"01[0-9][-\s]?\d{3,4}[-\s]?\d{4}")),
    ("EMAIL", re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")),
    ("CARD", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("ACCOUNT", re.compile(r"\b\d{2,6}-\d{2,6}-\d{2,8}\b")),
]


def mask_sensitive_text(text: str) -> tuple[str, bool]:
    masked = text
    was_masked = False
    for label, pattern in _PATTERNS:
        def _replace(match: re.Match, label: str = label) -> str:
            nonlocal was_masked
            was_masked = True
            return f"[{label}_MASKED]"

        masked = pattern.sub(_replace, masked)
    return masked, was_masked
