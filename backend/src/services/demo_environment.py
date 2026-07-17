import os
import shutil
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from src.config.environment_safety import validate_demo_environment
from src.config.settings import Settings
from src.db.repositories import Repository


class DemoResetError(RuntimeError):
    pass


class DemoEnvironmentUnavailableError(DemoResetError):
    pass


class DemoResetConfirmationError(DemoResetError):
    pass


class DemoActiveRunsError(DemoResetError):
    def __init__(self, run_id: str):
        super().__init__(f"active analysis run blocks demo reset: {run_id}")
        self.run_id = run_id


class DemoDatabaseCleanupError(DemoResetError):
    pass


class DemoRuntimeCleanupError(DemoResetError):
    def __init__(self, *, cleared_report_count: int):
        super().__init__("demo database was cleared but runtime cleanup failed")
        self.cleared_report_count = cleared_report_count


@dataclass(frozen=True)
class DemoResetResult:
    cleared_report_count: int
    cleared_runtime_directories: tuple[str, ...] = ("uploads", "derived")


def is_reparse_point(path: Path) -> bool:
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _assert_no_reparse_points(
    directory: Path,
    *,
    reparse_detector: Callable[[Path], bool],
) -> None:
    if not directory.exists():
        return
    if reparse_detector(directory):
        raise ValueError(f"refusing to clear runtime reparse point: {directory}")
    pending = [directory]
    while pending:
        current = pending.pop()
        with os.scandir(current) as entries:
            for entry in entries:
                path = Path(entry.path)
                if reparse_detector(path):
                    raise ValueError(f"refusing to clear runtime containing reparse point: {path}")
                if entry.is_dir(follow_symlinks=False):
                    pending.append(path)


def _clear_directory_children(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for child in directory.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def clear_runtime_directories(
    upload_dir: Path,
    derived_dir: Path,
    *,
    reparse_detector: Callable[[Path], bool] | None = None,
) -> None:
    detector = reparse_detector or is_reparse_point
    _assert_no_reparse_points(upload_dir, reparse_detector=detector)
    _assert_no_reparse_points(derived_dir, reparse_detector=detector)
    _clear_directory_children(upload_dir)
    _clear_directory_children(derived_dir)


def _validate_settings(settings: Settings) -> None:
    try:
        validate_demo_environment(
            app_env=settings.app_env,
            database_url=settings.database_url,
            upload_dir=settings.upload_dir,
            derived_dir=settings.derived_dir,
        )
    except ValueError as exc:
        raise DemoEnvironmentUnavailableError("demo reset environment is unavailable") from exc


def reset_demo_environment_data(
    repository: Repository,
    settings: Settings,
    *,
    confirmation: str,
    runtime_cleaner: Callable[[Path, Path], None] = clear_runtime_directories,
) -> DemoResetResult:
    _validate_settings(settings)
    if repository.get_current_database() != "esg_agent_demo":
        raise DemoEnvironmentUnavailableError("actual database is not esg_agent_demo")
    if confirmation != "RESET_DEMO":
        raise DemoResetConfirmationError("demo reset confirmation is invalid")

    active_runs = repository.list_active_runs()
    if active_runs:
        raise DemoActiveRunsError(active_runs[0].run_id)

    try:
        cleared_report_count = repository.clear_demo_business_data()
    except Exception as exc:
        repository.rollback()
        raise DemoDatabaseCleanupError("demo database cleanup failed") from exc

    try:
        _validate_settings(settings)
        runtime_cleaner(settings.upload_dir, settings.derived_dir)
    except Exception as exc:
        raise DemoRuntimeCleanupError(cleared_report_count=cleared_report_count) from exc

    return DemoResetResult(cleared_report_count=cleared_report_count)
