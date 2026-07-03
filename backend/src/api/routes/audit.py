from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.schemas import AuditRun
from src.db.repositories import Repository
from src.db.session import get_db_session

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/runs", response_model=list[AuditRun])
def list_audit_runs(session: Session = Depends(get_db_session)) -> list[dict]:
    return Repository(session).list_audit_runs()
