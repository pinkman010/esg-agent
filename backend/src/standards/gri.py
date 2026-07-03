import json
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.domain.models import DisclosureRequirement, DisclosureTask


_CHINESE_KEYWORDS_BY_REQUIREMENT = {
    "GRI 2-1-a": ["法定名称", "公司名称", "有限公司", "Co., Ltd.", "远景能源有限公司", "Envision Energy Co., Ltd."],
    "GRI 2-1-b": ["所有权性质", "法律形式", "ownership", "legal form"],
    "GRI 2-1-c": ["总部", "上海总部", "总部大楼", "所在地", "地址"],
    "GRI 2-1-d": ["运营国家", "运营地区", "国家", "地区", "全球市场", "海外订单", "全球项目", "亚太"],
    "GRI 2-2-a": ["报告边界", "实际运营场所", "统计口径", "合并范围", "纳入报告"],
    "GRI 2-2-c": ["报告边界", "实际运营场所", "多实体", "合并方法", "合并口径"],
    "GRI 2-2-c-ii": ["合并口径", "并购", "收购", "实体处置"],
    "GRI 2-3-a": ["报告期", "报告周期", "报告频率"],
    "GRI 2-3-d": ["联系方式", "联系邮箱", "获取及回应本报告", "f_esg_office"],
    "GRI 2-4-a": ["信息重述", "无信息重述"],
    "GRI 2-4-a-i": ["信息重述", "无信息重述", "重述原因"],
    "GRI 2-4-a-ii": ["信息重述", "无信息重述", "重述影响"],
    "GRI 2-5-a": ["鉴证报告", "独立有限鉴证", "有限保证", "外部鉴证"],
    "GRI 2-5-b": ["鉴证报告", "独立有限鉴证", "有限保证", "外部鉴证声明"],
    "GRI 2-5-b-i": ["鉴证报告", "独立有限鉴证", "有限保证", "外部鉴证声明"],
}


class GRIAdapter:
    standard_id = "GRI"

    def __init__(self, requirements_path: str | Path, standard_version: str = "2021", max_requirements: int | None = None):
        self.requirements_path = Path(requirements_path)
        self.standard_version = standard_version
        self.max_requirements = max_requirements

    def load_requirements(self) -> list[DisclosureRequirement]:
        try:
            raw_data = json.loads(self.requirements_path.read_text(encoding="utf-8"))
            if isinstance(raw_data, list):
                return [DisclosureRequirement(**item) for item in raw_data]
            if isinstance(raw_data, dict) and isinstance(raw_data.get("requirements"), list):
                return self._convert_checklist_requirements(raw_data["requirements"])
            raise TypeError("unsupported GRI requirement data shape")
        except (OSError, json.JSONDecodeError, TypeError, ValidationError) as exc:
            raise ValueError("invalid GRI requirement data") from exc

    def build_tasks(self, run_id: str, report_id: str) -> list[DisclosureTask]:
        tasks: list[DisclosureTask] = []
        for requirement in self.load_requirements():
            tasks.append(
                DisclosureTask(
                    task_id=f"{run_id}:{requirement.requirement_id}",
                    run_id=run_id,
                    report_id=report_id,
                    standard_id=requirement.standard_id,
                    standard_version=requirement.standard_version,
                    disclosure_id=requirement.disclosure_id,
                    requirement_id=requirement.requirement_id,
                    requirement_text=requirement.requirement_text,
                    keywords=requirement.keywords,
                )
            )
        return tasks

    def _convert_checklist_requirements(self, raw_items: list[dict[str, Any]]) -> list[DisclosureRequirement]:
        requirements: list[DisclosureRequirement] = []
        for item in raw_items:
            if not self._is_current_gap_requirement(item):
                continue
            requirement_id = self._requirement_id_from_checklist_item(item)
            requirements.append(
                DisclosureRequirement(
                    standard_id=self._standard_id_from_checklist_item(item),
                    standard_version=str(item.get("standard_year") or self.standard_version),
                    disclosure_id=self._disclosure_id_from_checklist_item(item),
                    requirement_id=requirement_id,
                    requirement_text=str(item.get("requirement_text") or "").strip(),
                    keywords=self._keywords_from_text(
                        str(item.get("requirement_text") or ""),
                        requirement_id=requirement_id,
                    ),
                )
            )
            if self.max_requirements is not None and len(requirements) >= self.max_requirements:
                break
        return requirements

    def _is_current_gap_requirement(self, item: dict[str, Any]) -> bool:
        return (
            item.get("assessment_mode") == "current_gap"
            and item.get("requirement_type") == "requirement"
            and item.get("is_mandatory") is True
            and item.get("scoring_role") == "hard_score"
        )

    def _standard_id_from_checklist_item(self, item: dict[str, Any]) -> str:
        raw_id = str(item.get("requirement_id") or "")
        parts = raw_id.split(":")
        if len(parts) >= 2:
            match = re.fullmatch(r"GRI(\d+)", parts[1])
            if match:
                return f"GRI {match.group(1)}"
        return self.standard_id

    def _disclosure_id_from_checklist_item(self, item: dict[str, Any]) -> str:
        canonical_disclosure_id = str(item.get("canonical_disclosure_id") or "").strip()
        if canonical_disclosure_id:
            return f"GRI {canonical_disclosure_id}"
        return self._standard_id_from_checklist_item(item)

    def _requirement_id_from_checklist_item(self, item: dict[str, Any]) -> str:
        canonical_disclosure_id = str(item.get("canonical_disclosure_id") or "").strip()
        raw_id = str(item.get("requirement_id") or "")
        parts = raw_id.split(":")
        if canonical_disclosure_id and len(parts) >= 4:
            suffix = "-".join(part for part in parts[3:] if part)
            if suffix:
                return f"GRI {canonical_disclosure_id}-{suffix}"
            return f"GRI {canonical_disclosure_id}"
        return raw_id

    def _keywords_from_text(self, text: str, requirement_id: str | None = None) -> list[str]:
        stopwords = {
            "a",
            "all",
            "an",
            "and",
            "are",
            "as",
            "by",
            "for",
            "from",
            "how",
            "if",
            "in",
            "including",
            "into",
            "is",
            "it",
            "its",
            "of",
            "on",
            "or",
            "report",
            "the",
            "their",
            "this",
            "to",
            "whether",
            "with",
        }
        keywords: list[str] = []
        for match in re.findall(r"[A-Za-z][A-Za-z0-9'-]*", text.lower()):
            keyword = match.strip("'-")
            if len(keyword) <= 2 or keyword in stopwords or keyword in keywords:
                continue
            keywords.append(keyword)
            if len(keywords) >= 8:
                break
        for keyword in _CHINESE_KEYWORDS_BY_REQUIREMENT.get(requirement_id or "", []):
            if keyword not in keywords:
                keywords.append(keyword)
        return keywords
