"""Rule-based risk engine.

Each rule is a small deterministic function over the document's clauses. Rules
detect clear patterns (presence of a topic without a corresponding cap/limit,
one-sided rights, missing clauses) that don't require language-model judgement.
AI analysis (see app/services/ai) handles contextual/ambiguous risks separately;
results from both are merged downstream.
"""
import re
from dataclasses import dataclass

from app.models.enums import ClauseType, ContractType, TopecPosition
from app.services.clause_splitter import SplitClause

_CAP_PATTERN = re.compile(r"(상한|한도|초과하지|최대|%|퍼센트|이내)")
_DAMAGES_PATTERN = re.compile(r"손해\s*배상")
_DELAY_PENALTY_PATTERN = re.compile(r"지체상금|지연손해금")
_TERMINATION_UNILATERAL_PATTERN = re.compile(r"(발주자|갑|위탁자).{0,20}(해지할\s*수\s*있다|해지권)")
_COST_COMPENSATION_PATTERN = re.compile(r"(기\s*수행|기성|이미\s*수행).{0,20}(비용|대가|정산)")
_ADDITIONAL_WORK_PATTERN = re.compile(r"추가\s*(업무|공사|용역)")
_COMPENSATION_KEYWORD_PATTERN = re.compile(r"비용|대가|정산|지급|대금")
_IP_FULL_ASSIGNMENT_PATTERN = re.compile(r"(지식재산권|저작권).{0,30}(양도|귀속)")
_IP_EXISTING_CARVE_OUT_PATTERN = re.compile(
    r"(기존|사전\s*보유|기\s*보유|이전부터\s*보유|체결\s*이전|이전에\s*(취득|보유)).{0,20}(지식재산권|저작권)"
)
_JURISDICTION_PATTERN = re.compile(r"(관할법원|합의관할)")
_TOPEC_JURISDICTION_HINT_BASE = re.compile(r"(topec|토펙|본사\s*소재지)", re.IGNORECASE)

# 계약서는 관례적으로 당사자를 "갑"/"을"로 표기하는 경우가 많다. TOPEC의 계약상 지위로부터
# 어느 쪽 표기가 TOPEC에 해당하는지 추정한다. 계약서마다 실제 갑/을 배정이 다를 수 있으므로
# 이는 어디까지나 휴리스틱이며, 근거가 불명확하면 아무 쪽도 가정하지 않는다.
_TOPEC_AS_GAP_POSITIONS = {
    TopecPosition.CLIENT,
    TopecPosition.PRINCIPAL_CONTRACTOR,
    TopecPosition.PURCHASER,
    TopecPosition.SERVICE_RECIPIENT,
    TopecPosition.CONFIDENTIAL_INFO_RECIPIENT,
}
_TOPEC_AS_EUL_POSITIONS = {
    TopecPosition.SUBCONTRACTOR,
    TopecPosition.SERVICE_PROVIDER,
    TopecPosition.SUPPLIER,
    TopecPosition.CONFIDENTIAL_INFO_PROVIDER,
}


def _jurisdiction_hint_pattern(topec_position: TopecPosition | None) -> re.Pattern:
    if topec_position in _TOPEC_AS_GAP_POSITIONS:
        return re.compile(r"(topec|토펙|본사\s*소재지|갑의\s*본점|갑\s*소재지)", re.IGNORECASE)
    if topec_position in _TOPEC_AS_EUL_POSITIONS:
        return re.compile(r"(topec|토펙|본사\s*소재지|을의\s*본점|을\s*소재지)", re.IGNORECASE)
    return _TOPEC_JURISDICTION_HINT_BASE
_CONFIDENTIALITY_PATTERN = re.compile(r"비밀\s*유지|기밀\s*유지")
_PERPETUAL_PATTERN = re.compile(r"영구히|기한\s*없이|무기한")
_CONFIDENTIALITY_TERM_PATTERN = re.compile(r"(\d+)\s*년|계약\s*종료\s*후\s*(\d+)\s*년")
_PRICE_ADJUSTMENT_PATTERN = re.compile(r"물가변동|단가조정|금액조정")
_AMENDMENT_UNILATERAL_PATTERN = re.compile(r"(갑|발주자|위탁자).{0,20}(변경할\s*수\s*있다|변경권)")
_AMENDMENT_CONSENT_PATTERN = re.compile(r"협의|동의|합의")
_FORCE_MAJEURE_PATTERN = re.compile(r"불가항력")
_ACCEPTANCE_DISCRETION_PATTERN = re.compile(r"(갑|발주자).{0,15}(판단|재량)에?\s*따라")


@dataclass
class RuleMatch:
    rule_code: str
    matched: bool
    clause: SplitClause | None
    detail: str


def _find_clauses(clauses: list[SplitClause], clause_types: set[ClauseType] | None, pattern: re.Pattern) -> list[SplitClause]:
    result = []
    for c in clauses:
        if clause_types and c.clause_type not in clause_types:
            continue
        if pattern.search(c.text):
            result.append(c)
    return result


def rule_unlimited_damages(clauses: list[SplitClause]) -> RuleMatch:
    hits = _find_clauses(clauses, {ClauseType.DAMAGES, ClauseType.LIABILITY_LIMIT}, _DAMAGES_PATTERN)
    for c in hits:
        if not _CAP_PATTERN.search(c.text):
            return RuleMatch("UNLIMITED_DAMAGES", True, c, "손해배상 조항에 책임한도(상한) 문구가 확인되지 않습니다.")
    return RuleMatch("UNLIMITED_DAMAGES", False, None, "")


def rule_no_delay_penalty_cap(clauses: list[SplitClause]) -> RuleMatch:
    hits = _find_clauses(clauses, {ClauseType.DELAY_PENALTY}, _DELAY_PENALTY_PATTERN)
    for c in hits:
        if not _CAP_PATTERN.search(c.text):
            return RuleMatch("NO_DELAY_PENALTY_CAP", True, c, "지체상금 조항에 상한 비율/금액이 확인되지 않습니다.")
    return RuleMatch("NO_DELAY_PENALTY_CAP", False, None, "")


def rule_unilateral_termination(clauses: list[SplitClause]) -> RuleMatch:
    hits = _find_clauses(clauses, {ClauseType.TERMINATION}, _TERMINATION_UNILATERAL_PATTERN)
    for c in hits:
        if not _COST_COMPENSATION_PATTERN.search(c.text):
            return RuleMatch(
                "UNILATERAL_TERMINATION", True, c,
                "상대방의 임의 해지권은 확인되나 기수행 부분 비용 보전 문구는 확인되지 않습니다.",
            )
    return RuleMatch("UNILATERAL_TERMINATION", False, None, "")


def rule_no_additional_work_compensation(clauses: list[SplitClause]) -> RuleMatch:
    all_text_hits = _find_clauses(clauses, None, _ADDITIONAL_WORK_PATTERN)
    for c in all_text_hits:
        if not _COMPENSATION_KEYWORD_PATTERN.search(c.text):
            return RuleMatch(
                "NO_ADDITIONAL_WORK_COMPENSATION", True, c,
                "추가업무 관련 문구는 있으나 비용 정산 조항이 확인되지 않습니다.",
            )
    if not all_text_hits:
        return RuleMatch(
            "NO_ADDITIONAL_WORK_COMPENSATION", True, None,
            "계약서 전체에서 추가업무·설계변경 시 비용 정산에 관한 조항이 확인되지 않습니다.",
        )
    return RuleMatch("NO_ADDITIONAL_WORK_COMPENSATION", False, None, "")


def rule_full_ip_assignment(clauses: list[SplitClause]) -> RuleMatch:
    hits = _find_clauses(clauses, {ClauseType.INTELLECTUAL_PROPERTY}, _IP_FULL_ASSIGNMENT_PATTERN)
    for c in hits:
        if not _IP_EXISTING_CARVE_OUT_PATTERN.search(c.text):
            return RuleMatch(
                "FULL_IP_ASSIGNMENT", True, c,
                "지식재산권 양도 조항에 기존 보유 지식재산권 제외 문구가 확인되지 않습니다.",
            )
    return RuleMatch("FULL_IP_ASSIGNMENT", False, None, "")


def rule_counterparty_jurisdiction(clauses: list[SplitClause], topec_position: TopecPosition | None = None) -> RuleMatch:
    hits = _find_clauses(clauses, {ClauseType.JURISDICTION}, _JURISDICTION_PATTERN)
    hint_pattern = _jurisdiction_hint_pattern(topec_position)
    for c in hits:
        if not hint_pattern.search(c.text):
            return RuleMatch(
                "COUNTERPARTY_JURISDICTION", True, c,
                "관할법원 조항에 TOPEC 소재지 관련 문구가 확인되지 않아 상대방 소재지 전속관할일 가능성이 있습니다.",
            )
    return RuleMatch("COUNTERPARTY_JURISDICTION", False, None, "")


def rule_perpetual_confidentiality(clauses: list[SplitClause]) -> RuleMatch:
    hits = _find_clauses(clauses, {ClauseType.CONFIDENTIALITY}, _CONFIDENTIALITY_PATTERN)
    for c in hits:
        if _PERPETUAL_PATTERN.search(c.text) or not _CONFIDENTIALITY_TERM_PATTERN.search(c.text):
            return RuleMatch(
                "PERPETUAL_CONFIDENTIALITY", True, c,
                "비밀유지 조항에 명확한 종료 기한이 확인되지 않습니다(무기한 표현 포함 가능).",
            )
    return RuleMatch("PERPETUAL_CONFIDENTIALITY", False, None, "")


def rule_no_price_adjustment(clauses: list[SplitClause]) -> RuleMatch:
    hits = _find_clauses(clauses, None, _PRICE_ADJUSTMENT_PATTERN)
    if not hits:
        return RuleMatch(
            "NO_PRICE_ADJUSTMENT", True, None, "계약서 전체에서 물가변동에 따른 금액 조정 조항이 확인되지 않습니다."
        )
    return RuleMatch("NO_PRICE_ADJUSTMENT", False, None, "")


def rule_missing_contract_end_date(clauses: list[SplitClause], has_end_date: bool) -> RuleMatch:
    if not has_end_date:
        return RuleMatch("MISSING_CONTRACT_END_DATE", True, None, "계약기간 종료일이 문서에서 명확히 확인되지 않습니다.")
    return RuleMatch("MISSING_CONTRACT_END_DATE", False, None, "")


def rule_unilateral_amendment(clauses: list[SplitClause]) -> RuleMatch:
    hits = _find_clauses(clauses, {ClauseType.CHANGE_ORDER}, _AMENDMENT_UNILATERAL_PATTERN)
    for c in hits:
        if not _AMENDMENT_CONSENT_PATTERN.search(c.text):
            return RuleMatch(
                "UNILATERAL_AMENDMENT", True, c, "상대방이 TOPEC 동의 없이 계약조건을 변경할 수 있는 것으로 보입니다."
            )
    return RuleMatch("UNILATERAL_AMENDMENT", False, None, "")


def rule_no_force_majeure(clauses: list[SplitClause]) -> RuleMatch:
    hits = _find_clauses(clauses, None, _FORCE_MAJEURE_PATTERN)
    if not hits:
        return RuleMatch("NO_FORCE_MAJEURE", True, None, "불가항력 면책 조항이 확인되지 않습니다.")
    return RuleMatch("NO_FORCE_MAJEURE", False, None, "")


def rule_ambiguous_acceptance(clauses: list[SplitClause]) -> RuleMatch:
    hits = _find_clauses(clauses, {ClauseType.ACCEPTANCE}, _ACCEPTANCE_DISCRETION_PATTERN)
    if hits:
        return RuleMatch(
            "AMBIGUOUS_ACCEPTANCE", True, hits[0], "검수 기준이 상대방의 판단·재량에 따르는 것으로 규정되어 있습니다."
        )
    return RuleMatch("AMBIGUOUS_ACCEPTANCE", False, None, "")


RULE_FUNCTIONS = {
    "UNLIMITED_DAMAGES": rule_unlimited_damages,
    "NO_DELAY_PENALTY_CAP": rule_no_delay_penalty_cap,
    "UNILATERAL_TERMINATION": rule_unilateral_termination,
    "NO_ADDITIONAL_WORK_COMPENSATION": rule_no_additional_work_compensation,
    "FULL_IP_ASSIGNMENT": rule_full_ip_assignment,
    "PERPETUAL_CONFIDENTIALITY": rule_perpetual_confidentiality,
    "NO_PRICE_ADJUSTMENT": rule_no_price_adjustment,
    "UNILATERAL_AMENDMENT": rule_unilateral_amendment,
    "NO_FORCE_MAJEURE": rule_no_force_majeure,
    "AMBIGUOUS_ACCEPTANCE": rule_ambiguous_acceptance,
}

# 각 규칙이 적용되는 계약유형. 빈 목록은 "모든 계약유형에 적용"을 의미하며,
# scripts/seed.py의 RISK_RULES 시드 데이터와 일치해야 한다.
RULE_APPLICABLE_CONTRACT_TYPES: dict[str, set[ContractType]] = {
    "UNLIMITED_DAMAGES": {ContractType.SUBCONTRACT, ContractType.GENERAL_SERVICE, ContractType.DESIGN_SUPERVISION_CM},
    "NO_DELAY_PENALTY_CAP": {ContractType.SUBCONTRACT, ContractType.DESIGN_SUPERVISION_CM, ContractType.GENERAL_SERVICE},
    "UNILATERAL_TERMINATION": {ContractType.SUBCONTRACT, ContractType.GENERAL_SERVICE, ContractType.DESIGN_SUPERVISION_CM},
    "NO_ADDITIONAL_WORK_COMPENSATION": {ContractType.SUBCONTRACT, ContractType.DESIGN_SUPERVISION_CM, ContractType.GENERAL_SERVICE},
    "FULL_IP_ASSIGNMENT": {
        ContractType.GENERAL_SERVICE,
        ContractType.SOFTWARE_SAAS,
        ContractType.CONSULTING,
        ContractType.SUBCONTRACT,
        ContractType.DESIGN_SUPERVISION_CM,
    },
    "COUNTERPARTY_JURISDICTION": {ContractType.SUBCONTRACT, ContractType.GENERAL_SERVICE, ContractType.NDA, ContractType.MOU},
    "PERPETUAL_CONFIDENTIALITY": {ContractType.NDA, ContractType.MOU, ContractType.CONSORTIUM},
    "NO_PRICE_ADJUSTMENT": {ContractType.SUBCONTRACT, ContractType.DESIGN_SUPERVISION_CM},
    "UNILATERAL_AMENDMENT": {ContractType.SUBCONTRACT, ContractType.GENERAL_SERVICE},
    "AMBIGUOUS_ACCEPTANCE": {ContractType.SUBCONTRACT, ContractType.GENERAL_SERVICE, ContractType.PURCHASE_SUPPLY},
    # NO_FORCE_MAJEURE, MISSING_CONTRACT_END_DATE: 빈 목록 = 모든 계약유형에 적용
}


def _is_applicable(rule_code: str, contract_type: ContractType) -> bool:
    applicable = RULE_APPLICABLE_CONTRACT_TYPES.get(rule_code)
    return not applicable or contract_type in applicable


def run_rule_engine(
    clauses: list[SplitClause],
    contract_type: ContractType,
    has_end_date: bool,
    topec_position: TopecPosition | None = None,
) -> list[RuleMatch]:
    results = []
    for code, fn in RULE_FUNCTIONS.items():
        if not _is_applicable(code, contract_type):
            continue
        results.append(fn(clauses))

    if _is_applicable("COUNTERPARTY_JURISDICTION", contract_type):
        results.append(rule_counterparty_jurisdiction(clauses, topec_position))

    results.append(rule_missing_contract_end_date(clauses, has_end_date))
    return results
