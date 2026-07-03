from typing import Protocol

from src.domain.models import DisclosureRequirement, DisclosureTask


class StandardAdapter(Protocol):
    standard_id: str
    standard_version: str

    def load_requirements(self) -> list[DisclosureRequirement]:
        ...

    def build_tasks(self, run_id: str, report_id: str) -> list[DisclosureTask]:
        ...