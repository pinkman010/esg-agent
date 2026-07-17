from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.schemas import DemoResetRequest, DemoResetResponse
from src.config.settings import get_settings
from src.db.repositories import Repository
from src.db.session import get_db_session
from src.services.demo_environment import (
    DemoActiveRunsError,
    DemoDatabaseCleanupError,
    DemoEnvironmentUnavailableError,
    DemoResetConfirmationError,
    DemoRuntimeCleanupError,
    reset_demo_environment_data,
)


router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.post("/reset", response_model=DemoResetResponse)
def reset_demo_environment(
    request: DemoResetRequest,
    session: Session = Depends(get_db_session),
) -> dict:
    if request.confirmation != "RESET_DEMO":
        raise HTTPException(
            status_code=400,
            detail={"code": "demo_reset_confirmation_invalid"},
        )

    try:
        result = reset_demo_environment_data(
            Repository(session),
            get_settings(),
            confirmation=request.confirmation,
        )
    except DemoEnvironmentUnavailableError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "demo_reset_unavailable"},
        ) from exc
    except DemoResetConfirmationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "demo_reset_confirmation_invalid"},
        ) from exc
    except DemoActiveRunsError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "demo_reset_blocked_active_run", "run_id": exc.run_id},
        ) from exc
    except DemoDatabaseCleanupError as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "demo_database_cleanup_failed"},
        ) from exc
    except DemoRuntimeCleanupError as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "demo_runtime_cleanup_failed",
                "cleared_report_count": exc.cleared_report_count,
            },
        ) from exc

    return {
        "cleared_report_count": result.cleared_report_count,
        "cleared_runtime_directories": list(result.cleared_runtime_directories),
    }
