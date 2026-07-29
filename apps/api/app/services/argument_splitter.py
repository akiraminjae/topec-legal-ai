"""Split a litigation document (준비서면/소장/답변서 등) into argument segments.

Litigation briefs are structured very differently from contracts — there is no
"제N조" article numbering. Arguments are conventionally organized under numbered
or Korean-numeral headings ("1.", "2.", "가.", "나.", "다.") or explicit section
labels ("청구원인", "항변", "다툼 없는 사실"). We split on whichever numbering
scheme actually appears; if none is detected, fall back to paragraph blocks so
the pipeline still produces reviewable units instead of one giant blob.
"""
import re

_NUMBERED_HEADING_RE = re.compile(
    r"(?:^|\n)\s*((?:\d{1,2}\s*[.)]|[가나다라마바사아자차카타파하]\s*[.)]))\s*"
)

_SECTION_LABEL_RE = re.compile(
    r"(?:^|\n)\s*((?:청구\s*원인|항변|재항변|다툼\s*없는\s*사실|이\s*사건의?\s*경위|결\s*론))\s*"
)


class ArgumentSegment:
    def __init__(self, label: str | None, text: str, order_index: int):
        self.label = label
        self.text = text
        self.order_index = order_index


def _split_by_pattern(full_text: str, pattern: re.Pattern) -> list[ArgumentSegment]:
    matches = list(pattern.finditer(full_text))
    if len(matches) < 2:
        return []

    segments: list[ArgumentSegment] = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(full_text)
        label = match.group(1).strip()
        text = full_text[start:end].strip()
        if text:
            segments.append(ArgumentSegment(label=label, text=text, order_index=idx))
    return segments


def split_into_arguments(full_text: str) -> list[ArgumentSegment]:
    segments = _split_by_pattern(full_text, _SECTION_LABEL_RE)
    if not segments:
        segments = _split_by_pattern(full_text, _NUMBERED_HEADING_RE)

    if not segments:
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", full_text) if p.strip()]
        segments = [ArgumentSegment(label=None, text=p, order_index=i) for i, p in enumerate(paragraphs)]

    return segments
