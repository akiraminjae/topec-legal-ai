from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_system_admin
from app.db.session import get_db
from app.models.user import Department
from app.schemas.user import DepartmentCreate, DepartmentOut

router = APIRouter(prefix="/api/departments", tags=["departments"])


@router.get("", response_model=list[DepartmentOut])
def list_departments(db: Session = Depends(get_db)):
    return db.scalars(select(Department).where(Department.is_deleted.is_(False))).all()


@router.post("", response_model=DepartmentOut, dependencies=[Depends(require_system_admin)])
def create_department(payload: DepartmentCreate, db: Session = Depends(get_db)):
    dept = Department(name=payload.name, code=payload.code)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


@router.patch("/{department_id}", response_model=DepartmentOut, dependencies=[Depends(require_system_admin)])
def update_department(department_id: str, payload: DepartmentCreate, db: Session = Depends(get_db)):
    dept = db.get(Department, department_id)
    dept.name = payload.name
    dept.code = payload.code
    db.commit()
    db.refresh(dept)
    return dept
