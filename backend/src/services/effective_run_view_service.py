from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from src.domain.models import AnalysisRun, DisclosureAssessment


@dataclass(frozen=True)
class EffectiveAssessment:
    assessment: DisclosureAssessment
    source_run_id: str


@dataclass(frozen=True)
class EffectiveRunView:
    latest_run: AnalysisRun | None
    assessments_by_requirement: Mapping[str, EffectiveAssessment]
    failed_requirement_ids: frozenset[str]
    not_generated_requirement_ids: frozenset[str]


class EffectiveRunViewService:
    def __init__(self, repository: Any, *, max_depth: int = 32):
        if max_depth < 1:
            raise ValueError("effective run lineage depth must be at least one")
        self.repository = repository
        self.max_depth = max_depth

    def lineage_contains_eligible_count(
        self,
        *,
        latest_run: AnalysisRun,
        eligible_count: int,
    ) -> bool:
        report_id = latest_run.report_id
        current: AnalysisRun | None = latest_run
        seen_run_ids: set[str] = set()
        depth = 0
        while current is not None:
            if depth >= self.max_depth:
                raise ValueError("effective run lineage exceeds maximum depth")
            if current.run_id in seen_run_ids:
                raise ValueError("effective run lineage contains a cycle")
            if current.report_id != report_id:
                raise ValueError(
                    "effective run lineage contains a run from another report"
                )
            if current.eligible_requirement_count == eligible_count:
                return True
            seen_run_ids.add(current.run_id)
            depth += 1
            if current.parent_run_id is None:
                return False
            current = self.repository.get_run(current.parent_run_id)
            if current is None:
                raise ValueError(
                    "effective run lineage references a missing parent run"
                )
        return False

    def build(
        self,
        *,
        report_id: str,
        independent_requirement_ids: set[str],
    ) -> EffectiveRunView:
        expected_ids = frozenset(independent_requirement_ids)
        latest_run = self.repository.latest_run_for_report(report_id)
        if latest_run is None:
            return EffectiveRunView(
                latest_run=None,
                assessments_by_requirement=MappingProxyType({}),
                failed_requirement_ids=frozenset(),
                not_generated_requirement_ids=expected_ids,
            )

        effective: dict[str, EffectiveAssessment] = {}
        failed_ids: set[str] = set()
        seen_run_ids: set[str] = set()
        current: AnalysisRun | None = latest_run
        depth = 0

        while current is not None:
            if depth >= self.max_depth:
                raise ValueError("effective run lineage exceeds maximum depth")
            if current.run_id in seen_run_ids:
                raise ValueError("effective run lineage contains a cycle")
            if current.report_id != report_id:
                raise ValueError("effective run lineage contains a run from another report")

            seen_run_ids.add(current.run_id)
            depth += 1
            seen_requirement_ids: set[str] = set()
            for assessment in self.repository.list_assessments_by_run(
                current.run_id
            ):
                requirement_id = assessment.requirement_id
                if requirement_id not in expected_ids:
                    continue
                if requirement_id in seen_requirement_ids:
                    raise ValueError(
                        "effective run lineage contains a duplicate assessment "
                        f"for requirement {requirement_id}"
                    )
                seen_requirement_ids.add(requirement_id)
                effective.setdefault(
                    requirement_id,
                    EffectiveAssessment(
                        assessment=assessment,
                        source_run_id=current.run_id,
                    ),
                )

            failed_ids.update(
                _failure_requirement_ids(current.failure_summary, expected_ids)
            )
            if current.parent_run_id is None:
                current = None
                continue
            current = self.repository.get_run(current.parent_run_id)
            if current is None:
                raise ValueError("effective run lineage references a missing parent run")

        generated_ids = set(effective)
        failed_ids.difference_update(generated_ids)
        missing_ids = set(expected_ids).difference(generated_ids)
        failed_ids.intersection_update(missing_ids)
        not_generated_ids = missing_ids.difference(failed_ids)
        return EffectiveRunView(
            latest_run=latest_run,
            assessments_by_requirement=MappingProxyType(effective),
            failed_requirement_ids=frozenset(failed_ids),
            not_generated_requirement_ids=frozenset(not_generated_ids),
        )


def _failure_requirement_ids(
    failure_summary: dict[str, Any] | None,
    expected_ids: frozenset[str],
) -> set[str]:
    if not isinstance(failure_summary, dict):
        return set()
    failed_ids: set[str] = set()
    for key in ("failed_requirement_ids", "retry_requirement_ids"):
        values = failure_summary.get(key, [])
        if not isinstance(values, list):
            continue
        failed_ids.update(
            value
            for value in values
            if isinstance(value, str) and value in expected_ids
        )
    return failed_ids
