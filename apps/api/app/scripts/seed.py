"""Development seed data: roles, departments, demo accounts, risk rules, retention policies.

Run inside the api container: `python -m app.scripts.seed`
Passwords come from environment variables (see .env.example) — never hard-coded.
This is explicitly a DEVELOPMENT convenience; production accounts must be created
by a SYSTEM_ADMIN via the admin UI/API.
"""
import os

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.admin import FileRetentionPolicy
from app.models.analysis import RiskRule
from app.models.enums import ContractType, RetentionPolicy, RiskLevel, RoleName
from app.models.user import Department, Role, User, UserRole

DEPARTMENTS = [
    ("디지털혁신팀", "DX"),
    ("사업관리본부", "PMO"),
    ("경영지원본부", "ADMIN"),
    ("재무팀", "FIN"),
    ("구매팀", "PUR"),
    ("법무담당", "LEGAL"),
]

RETENTION_POLICIES = [
    (RetentionPolicy.DELETE_AFTER_ANALYSIS, 0, "분석 후 삭제"),
    (RetentionPolicy.KEEP_30_DAYS, 30, "30일 보관"),
    (RetentionPolicy.KEEP_1_YEAR, 365, "1년 보관"),
    (RetentionPolicy.KEEP_UNTIL_MANUAL_DELETE, None, "직접 삭제할 때까지 보관"),
]

RISK_RULES = [
    dict(
        code="UNLIMITED_DAMAGES",
        title="손해배상 책임한도 부재",
        category="DAMAGES",
        applicable_contract_types=[ContractType.SUBCONTRACT, ContractType.GENERAL_SERVICE, ContractType.DESIGN_SUPERVISION_CM],
        default_risk_level=RiskLevel.CRITICAL,
        description="손해배상 조항은 있으나 책임한도(상한) 문구가 없는 경우 탐지",
    ),
    dict(
        code="NO_DELAY_PENALTY_CAP",
        title="지체상금 상한 부재",
        category="DELAY_PENALTY",
        applicable_contract_types=[ContractType.SUBCONTRACT, ContractType.DESIGN_SUPERVISION_CM, ContractType.GENERAL_SERVICE],
        default_risk_level=RiskLevel.HIGH,
        description="지체상금 조항은 있으나 상한 비율/금액이 명시되지 않은 경우 탐지",
    ),
    dict(
        code="UNILATERAL_TERMINATION",
        title="발주자의 임의해지, 기수행 비용 보전 부재",
        category="TERMINATION",
        applicable_contract_types=[ContractType.SUBCONTRACT, ContractType.GENERAL_SERVICE, ContractType.DESIGN_SUPERVISION_CM],
        default_risk_level=RiskLevel.HIGH,
        description="상대방의 임의 해지권만 존재하고 기수행 부분에 대한 비용 보전 조항이 없는 경우",
    ),
    dict(
        code="NO_ADDITIONAL_WORK_COMPENSATION",
        title="추가업무 비용 미지급 조항",
        category="ADDITIONAL_WORK",
        applicable_contract_types=[ContractType.SUBCONTRACT, ContractType.DESIGN_SUPERVISION_CM, ContractType.GENERAL_SERVICE],
        default_risk_level=RiskLevel.HIGH,
        description="추가업무·설계변경 발생 시 비용 정산 조항이 없는 경우",
    ),
    dict(
        code="FULL_IP_ASSIGNMENT",
        title="지식재산권 전체 무상 양도",
        category="INTELLECTUAL_PROPERTY",
        applicable_contract_types=[
            ContractType.GENERAL_SERVICE,
            ContractType.SOFTWARE_SAAS,
            ContractType.CONSULTING,
            ContractType.SUBCONTRACT,
            ContractType.DESIGN_SUPERVISION_CM,
        ],
        default_risk_level=RiskLevel.HIGH,
        description="기존 보유 지식재산권까지 포함하여 전체를 무상 양도하는 문구 탐지",
    ),
    dict(
        code="COUNTERPARTY_JURISDICTION",
        title="상대방 소재지 전속관할",
        category="JURISDICTION",
        applicable_contract_types=[ContractType.SUBCONTRACT, ContractType.GENERAL_SERVICE, ContractType.NDA, ContractType.MOU],
        default_risk_level=RiskLevel.MEDIUM,
        description="관할법원이 TOPEC이 아닌 상대방 소재지로 전속 지정된 경우",
    ),
    dict(
        code="PERPETUAL_CONFIDENTIALITY",
        title="비밀유지 기간 무기한",
        category="CONFIDENTIALITY",
        applicable_contract_types=[ContractType.NDA, ContractType.MOU, ContractType.CONSORTIUM],
        default_risk_level=RiskLevel.MEDIUM,
        description="비밀유지 의무 종료 시점이 명시되지 않고 무기한으로 규정된 경우",
    ),
    dict(
        code="NO_PRICE_ADJUSTMENT",
        title="물가변동 조정 조항 부재",
        category="PRICE_ADJUSTMENT",
        applicable_contract_types=[ContractType.SUBCONTRACT, ContractType.DESIGN_SUPERVISION_CM],
        default_risk_level=RiskLevel.MEDIUM,
        description="장기계약임에도 물가변동에 따른 계약금액 조정 조항이 없는 경우",
    ),
    dict(
        code="MISSING_CONTRACT_END_DATE",
        title="계약기간 종료일 누락",
        category="SCHEDULE",
        applicable_contract_types=[],
        default_risk_level=RiskLevel.LOW,
        description="계약기간(종료일)이 문서에서 명확히 확인되지 않는 경우",
    ),
    dict(
        code="UNILATERAL_AMENDMENT",
        title="상대방의 일방적 계약조건 변경권",
        category="CHANGE_ORDER",
        applicable_contract_types=[ContractType.SUBCONTRACT, ContractType.GENERAL_SERVICE],
        default_risk_level=RiskLevel.HIGH,
        description="상대방이 TOPEC 동의 없이 계약조건을 일방적으로 변경할 수 있도록 규정된 경우",
    ),
    dict(
        code="NO_FORCE_MAJEURE",
        title="불가항력 조항 부재",
        category="FORCE_MAJEURE",
        applicable_contract_types=[],
        default_risk_level=RiskLevel.LOW,
        description="천재지변 등 불가항력 사유에 대한 면책 조항이 없는 경우",
    ),
    dict(
        code="AMBIGUOUS_ACCEPTANCE",
        title="불명확하거나 상대방 재량에 따른 검수 기준",
        category="ACCEPTANCE",
        applicable_contract_types=[ContractType.SUBCONTRACT, ContractType.GENERAL_SERVICE, ContractType.PURCHASE_SUPPLY],
        default_risk_level=RiskLevel.MEDIUM,
        description="검수·인수 기준이 구체적으로 명시되지 않고 전적으로 상대방 재량에 맡겨진 경우",
    ),
]


def run():
    db = SessionLocal()
    try:
        role_map = {}
        for role_name in RoleName:
            role = db.scalar(select(Role).where(Role.name == role_name))
            if not role:
                role = Role(name=role_name, description=role_name.value)
                db.add(role)
                db.flush()
            role_map[role_name] = role

        dept_map = {}
        for name, code in DEPARTMENTS:
            dept = db.scalar(select(Department).where(Department.code == code))
            if not dept:
                dept = Department(name=name, code=code)
                db.add(dept)
                db.flush()
            dept_map[code] = dept

        for policy, days, desc in RETENTION_POLICIES:
            existing = db.scalar(select(FileRetentionPolicy).where(FileRetentionPolicy.policy_code == policy))
            if not existing:
                db.add(FileRetentionPolicy(policy_code=policy, days=days, description=desc))

        for rule in RISK_RULES:
            existing = db.scalar(select(RiskRule).where(RiskRule.code == rule["code"]))
            if not existing:
                db.add(RiskRule(**rule))

        db.commit()

        seed_users = [
            (
                "EMP-0001",
                os.environ.get("SEED_ADMIN_EMAIL", "admin@topec.local"),
                "관리자",
                os.environ.get("SEED_ADMIN_PASSWORD", "ChangeMe1234!"),
                dept_map["DX"],
                [RoleName.SYSTEM_ADMIN],
            ),
            (
                "EMP-0002",
                os.environ.get("SEED_LEGAL_EMAIL", "legal@topec.local"),
                "법무담당",
                os.environ.get("SEED_LEGAL_PASSWORD", "ChangeMe1234!"),
                dept_map["LEGAL"],
                [RoleName.LEGAL_REVIEWER],
            ),
            (
                "EMP-0003",
                os.environ.get("SEED_USER_EMAIL", "user@topec.local"),
                "일반사용자",
                os.environ.get("SEED_USER_PASSWORD", "ChangeMe1234!"),
                dept_map["PMO"],
                [RoleName.USER],
            ),
        ]

        for employee_no, email, full_name, password, dept, roles in seed_users:
            user = db.scalar(select(User).where(User.email == email))
            if not user:
                user = User(
                    employee_no=employee_no,
                    email=email,
                    full_name=full_name,
                    department_id=dept.id,
                    password_hash=hash_password(password),
                    must_change_password=True,
                )
                db.add(user)
                db.flush()
                for role_name in roles:
                    db.add(UserRole(user_id=user.id, role_id=role_map[role_name].id))

        db.commit()
        print("시드 데이터 생성 완료.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
