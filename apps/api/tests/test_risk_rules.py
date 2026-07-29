from app.models.enums import ContractType
from app.services.clause_splitter import split_into_clauses
from app.services.risk_rules.engine import run_rule_engine

UNLIMITED_DAMAGES_CONTRACT = """
제1조(목적) 본 계약은 갑과 을 간의 용역계약에 관한 사항을 정한다.
제4조(손해배상) 을의 귀책사유로 갑에게 손해가 발생한 경우 을은 그 손해를 배상하여야 한다.
"""

CAPPED_DAMAGES_CONTRACT = """
제1조(목적) 본 계약은 갑과 을 간의 용역계약에 관한 사항을 정한다.
제4조(손해배상) 을의 손해배상 책임은 계약금액의 100%를 한도로 한다.
"""

NO_DELAY_CAP_CONTRACT = """
제5조(지체상금) 을이 준공기한 내에 용역을 완료하지 못한 경우 지체일수에 따라 지체상금을 지급한다.
"""


def _run(text: str, has_end_date: bool = True):
    clauses = split_into_clauses(text)
    return run_rule_engine(clauses, ContractType.GENERAL_SERVICE, has_end_date)


def test_unlimited_damages_detected():
    results = _run(UNLIMITED_DAMAGES_CONTRACT)
    matched_codes = {r.rule_code for r in results if r.matched}
    assert "UNLIMITED_DAMAGES" in matched_codes


def test_capped_damages_not_flagged():
    results = _run(CAPPED_DAMAGES_CONTRACT)
    matched_codes = {r.rule_code for r in results if r.matched}
    assert "UNLIMITED_DAMAGES" not in matched_codes


def test_delay_penalty_without_cap_detected():
    results = _run(NO_DELAY_CAP_CONTRACT)
    matched_codes = {r.rule_code for r in results if r.matched}
    assert "NO_DELAY_PENALTY_CAP" in matched_codes


def test_missing_end_date_flag_respects_input():
    results_missing = _run(UNLIMITED_DAMAGES_CONTRACT, has_end_date=False)
    results_present = _run(UNLIMITED_DAMAGES_CONTRACT, has_end_date=True)
    missing_codes = {r.rule_code for r in results_missing if r.matched}
    present_codes = {r.rule_code for r in results_present if r.matched}
    assert "MISSING_CONTRACT_END_DATE" in missing_codes
    assert "MISSING_CONTRACT_END_DATE" not in present_codes
