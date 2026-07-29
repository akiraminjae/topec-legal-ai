"""Golden-set evaluation for the rule-based risk engine.

Runs entirely outside Docker against the pure-Python rule engine (no DB/AI needed).
Usage (from repo root, with apps/api on PYTHONPATH):

    cd apps/api
    python ../../scripts/run_golden_eval.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "api"))

from app.models.enums import ContractType, TopecPosition  # noqa: E402
from app.services.clause_splitter import split_into_clauses  # noqa: E402
from app.services.risk_rules.engine import run_rule_engine  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = ROOT / "sample-data" / "contracts"
GOLDEN_SET_PATH = CONTRACTS_DIR / "golden_set.json"


def main() -> int:
    golden_set = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    total = 0
    passed = 0

    for sample in golden_set["samples"]:
        total += 1
        text = (CONTRACTS_DIR / sample["file"]).read_text(encoding="utf-8")
        clauses = split_into_clauses(text)
        results = run_rule_engine(
            clauses,
            ContractType(sample["contract_type"]),
            has_end_date=True,
            topec_position=TopecPosition(sample["topec_position"]),
        )
        detected = {r.rule_code for r in results if r.matched}
        expected = set(sample["expected_rule_codes"])

        missing = expected - detected
        unexpected = detected - expected
        ok = not missing and not unexpected

        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        print(f"[{status}] {sample['file']}")
        if missing:
            print(f"  누락된 탐지: {sorted(missing)}")
        if unexpected:
            print(f"  예상 외 탐지(오탐 가능): {sorted(unexpected)}")

    print(f"\n{passed}/{total} 샘플 통과")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
