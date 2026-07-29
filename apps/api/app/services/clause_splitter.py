"""Split extracted contract text into clauses and classify each by ClauseType.

Korean contracts are conventionally structured as "제N조(제목)" articles. We split
on that pattern first; if fewer than two matches are found (e.g. a short NDA or a
poorly-OCR'd document), we fall back to paragraph-based splitting so the pipeline
still produces reviewable units instead of one giant blob.
"""
import re

from app.models.enums import ClauseType

_ARTICLE_RE = re.compile(r"(제\s*\d+\s*조(?:의\s*\d+)?)\s*(?:\(([^)]{0,60})\))?")

_CLAUSE_KEYWORDS: list[tuple[ClauseType, list[str]]] = [
    (ClauseType.DEFINITIONS, ["정의", "용어의 정의"]),
    (ClauseType.PURPOSE, ["목적"]),
    (ClauseType.SCOPE, ["업무범위", "계약범위", "범위"]),
    (ClauseType.DELIVERABLES, ["납품", "산출물", "성과물"]),
    (ClauseType.CONTRACT_AMOUNT, ["계약금액", "대금", "용역대가"]),
    (ClauseType.PAYMENT, ["대금지급", "지급방법", "지급조건", "기성"]),
    (ClauseType.ADVANCE_PAYMENT, ["선급금"]),
    (ClauseType.PRICE_ADJUSTMENT, ["물가변동", "금액조정", "단가조정"]),
    (ClauseType.CHANGE_ORDER, ["설계변경", "계약내용의 변경", "변경계약"]),
    (ClauseType.ADDITIONAL_WORK, ["추가업무", "추가공사", "추가용역"]),
    (ClauseType.ACCEPTANCE, ["검사", "검수", "인수"]),
    (ClauseType.SCHEDULE, ["계약기간", "이행기간", "납기"]),
    (ClauseType.DELAY_PENALTY, ["지체상금", "지연손해금"]),
    (ClauseType.WARRANTY, ["하자보수", "하자담보", "보증기간"]),
    (ClauseType.PERFORMANCE_BOND, ["계약보증금", "이행보증"]),
    (ClauseType.DAMAGES, ["손해배상"]),
    (ClauseType.LIABILITY_LIMIT, ["책임의 한계", "책임한도", "책임제한"]),
    (ClauseType.INDEMNITY, ["면책", "배상책임"]),
    (ClauseType.INSURANCE, ["보험"]),
    (ClauseType.INTELLECTUAL_PROPERTY, ["지식재산권", "저작권", "특허"]),
    (ClauseType.CONFIDENTIALITY, ["비밀유지", "기밀유지", "비밀정보"]),
    (ClauseType.PERSONAL_DATA, ["개인정보"]),
    (ClauseType.TECHNICAL_DATA, ["기술자료"]),
    (ClauseType.SUBCONTRACTING, ["재하도급", "하도급", "재위탁"]),
    (ClauseType.ASSIGNMENT, ["권리의 양도", "계약의 양도", "양도금지"]),
    (ClauseType.TERMINATION, ["계약의 해지", "해지", "해제"]),
    (ClauseType.FORCE_MAJEURE, ["불가항력"]),
    (ClauseType.DISPUTE_RESOLUTION, ["분쟁해결", "중재"]),
    (ClauseType.GOVERNING_LAW, ["준거법"]),
    (ClauseType.JURISDICTION, ["관할법원", "합의관할"]),
    (ClauseType.RENEWAL, ["갱신", "자동연장"]),
    (ClauseType.NOTICES, ["통지"]),
    (ClauseType.SURVIVAL, ["존속"]),
    (ClauseType.COMPLIANCE, ["관계법령", "준수사항", "법령준수"]),
    (ClauseType.SAFETY, ["안전관리", "산업안전"]),
]


def classify_clause(title: str, text: str) -> ClauseType:
    """Classify a clause by keyword match.

    The article title (e.g. "제9조(지체상금)") is checked on its own first, since
    it names the clause's actual topic precisely. Falling straight to a combined
    title+body scan lets generic body keywords (e.g. "대금" appearing inside a
    damages or termination clause) get matched against an earlier, more generic
    category (e.g. CONTRACT_AMOUNT) before the correct, more specific one is ever
    tried — silently misclassifying the clause. Only when the title alone yields
    no match do we fall back to scanning title+body together.
    """
    if title:
        for clause_type, keywords in _CLAUSE_KEYWORDS:
            if any(kw in title for kw in keywords):
                return clause_type

    haystack = f"{title} {text[:200]}"
    for clause_type, keywords in _CLAUSE_KEYWORDS:
        if any(kw in haystack for kw in keywords):
            return clause_type
    return ClauseType.OTHER


class SplitClause:
    def __init__(self, clause_no: str | None, title: str | None, text: str, order_index: int):
        self.clause_no = clause_no
        self.title = title
        self.text = text
        self.order_index = order_index
        self.clause_type = classify_clause(title or "", text)


def split_into_clauses(full_text: str) -> list[SplitClause]:
    matches = list(_ARTICLE_RE.finditer(full_text))

    if len(matches) < 2:
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", full_text) if p.strip()]
        return [
            SplitClause(clause_no=None, title=None, text=p, order_index=i)
            for i, p in enumerate(paragraphs)
        ]

    clauses: list[SplitClause] = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(full_text)
        clause_no = match.group(1).strip()
        title = match.group(2).strip() if match.group(2) else None
        text = full_text[start:end].strip()
        clauses.append(SplitClause(clause_no=clause_no, title=title, text=text, order_index=idx))

    return clauses
