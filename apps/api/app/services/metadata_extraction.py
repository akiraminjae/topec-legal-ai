"""Heuristic extraction of key contract facts (amount, dates, warranty/delay terms)
directly from extracted text via regex. Runs independently of the AI provider so it
still works in Mock mode. Confidence is intentionally conservative; the user must
confirm or correct the result (extraction_confidence + user_confirmed on the model)."""
import re
from dataclasses import dataclass, field

_AMOUNT_RE = re.compile(r"([0-9][0-9,]{3,})\s*원")
_DATE_RE = re.compile(r"(\d{4})[.\-년\s]\s*(\d{1,2})[.\-월\s]\s*(\d{1,2})\s*일?")
_WARRANTY_RE = re.compile(r"하자\s*담보\s*책임\s*기간[^.]{0,40}")
_DELAY_PENALTY_RE = re.compile(r"지체상금[^.]{0,60}")
_VAT_RE = re.compile(r"부가가치세\s*(포함|별도)")


@dataclass
class ExtractedMetadata:
    contract_amount: float | None = None
    vat_included: bool | None = None
    dates_found: list[str] = field(default_factory=list)
    warranty_period: str | None = None
    delay_penalty: str | None = None
    missing_information: list[str] = field(default_factory=list)
    confidence: int = 0


def extract_metadata(full_text: str) -> ExtractedMetadata:
    result = ExtractedMetadata()
    signals = 0

    amount_match = _AMOUNT_RE.search(full_text)
    if amount_match:
        try:
            result.contract_amount = float(amount_match.group(1).replace(",", ""))
            signals += 1
        except ValueError:
            pass
    else:
        result.missing_information.append("계약금액")

    vat_match = _VAT_RE.search(full_text)
    if vat_match:
        result.vat_included = vat_match.group(1) == "포함"
        signals += 1

    dates = ["-".join(m.groups()) for m in _DATE_RE.finditer(full_text)]
    result.dates_found = dates[:10]
    if dates:
        signals += 1
    else:
        result.missing_information.append("계약기간")

    warranty_match = _WARRANTY_RE.search(full_text)
    if warranty_match:
        result.warranty_period = warranty_match.group(0).strip()
        signals += 1

    delay_match = _DELAY_PENALTY_RE.search(full_text)
    if delay_match:
        result.delay_penalty = delay_match.group(0).strip()
        signals += 1

    result.confidence = min(100, signals * 20)
    return result
