from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db.repositories import Repository, new_id
from src.db.session import get_db_session
from src.domain.enums import ActionPriority, ActionStatus
from src.domain.models import ImprovementAction


report_router = APIRouter(prefix="/api/reports/{report_id}/actions", tags=["actions"])
action_router = APIRouter(prefix="/api/actions", tags=["actions"])


class CreateActionRequest(BaseModel):
    assessment_id: str
    title: str
    priority: ActionPriority = ActionPriority.MEDIUM
    owner_name: str | None = None
    due_date: date | None = None
    recommendation_text: str = ""
    created_by: str


class UpdateActionRequest(BaseModel):
    status: ActionStatus | None = None
    owner_name: str | None = None
    completion_note: str | None = None


@report_router.get("", response_model=list[ImprovementAction])
def list_actions(report_id: str, session: Session = Depends(get_db_session)) -> list[dict]:
    return [item.model_dump(mode="json") for item in Repository(session).list_improvement_actions(report_id)]


@report_router.post("", response_model=ImprovementAction)
def create_action(report_id: str, request: CreateActionRequest, session: Session = Depends(get_db_session)) -> dict:
    repo = Repository(session)
    assessment = repo.get_assessment(request.assessment_id)
    if assessment is None or assessment.report_id != report_id:
        raise HTTPException(status_code=404, detail="assessment not found")
    action = repo.save_improvement_action(
        ImprovementAction(
            action_id=new_id("action"),
            report_id=report_id,
            **request.model_dump(),
        )
    )
    repo.create_audit_event(assessment.run_id, "improvement_action_created", {"action_id": action.action_id})
    return action.model_dump(mode="json")


@action_router.patch("/{action_id}", response_model=ImprovementAction)
def update_action(action_id: str, request: UpdateActionRequest, session: Session = Depends(get_db_session)) -> dict:
    if request.status in {ActionStatus.COMPLETED, ActionStatus.CANCELLED, ActionStatus.OPEN} and not (request.completion_note or "").strip():
        raise HTTPException(status_code=422, detail="completion_note is required for this status change")
    repo = Repository(session)
    try:
        action = repo.update_improvement_action(action_id, **request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    repo.create_audit_event(None, "improvement_action_updated", {"action_id": action_id, "status": action.status.value})
    return action.model_dump(mode="json")
