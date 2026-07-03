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
    "GRI 2-5-b-ii": ["鉴证报告", "独立有限鉴证", "有限保证", "鉴证标准", "编制基础", "鉴证范围"],
    "GRI 2-5-b-iii": ["鉴证报告", "独立有限鉴证", "有限保证", "鉴证限制"],
    "GRI 2-6-b": ["主要业务", "业务包括", "智能风电", "智慧储能", "绿氢", "责任采购", "产业共荣", "全球企业", "深化合作", "供应商准入", "供应商退出", "供应商培训"],
    "GRI 2-6-b-i": ["主要业务", "业务包括", "智能风电", "智慧储能", "绿氢", "服务市场", "全球企业", "深化合作"],
    "GRI 2-6-b-ii": ["责任采购", "产业共荣", "可持续供应链", "供应商", "价值链", "供应商准入", "尽职调查", "供应商退出", "供应商培训"],
    "GRI 2-6-c": ["ESG 合作网络", "ESG合作网络", "价值链", "业务关系", "供应商大会", "SMI", "CN100", "全球企业", "深化合作", "UNGC", "RE100", "SBTi", "CDP", "IEA", "WEF"],
    "GRI 2-6-d": ["重大变化", "业务关系变化", "价值链变化", "活动变化"],
    "GRI 2-7-c": ["人员结构", "员工组成", "截至报告期末", "head count", "FTE", "编制方法"],
    "GRI 2-7-c-ii": ["人员结构", "员工组成", "截至报告期末"],
    "GRI 2-7-d": ["员工总数", "合同类型", "地区分布", "必要背景"],
    "GRI 2-7-e": ["重大波动", "员工人数变化", "员工流失率"],
    "GRI 2-8-a": ["非雇员工作者", "非员工", "工作者总数", "合同关系"],
    "GRI 2-8-a-ii": ["非雇员工作者", "工作类型", "合同关系"],
    "GRI 2-8-b": ["非雇员工作者", "编制方法", "head count", "FTE"],
    "GRI 2-8-b-ii": ["非雇员工作者", "报告期末", "平均值", "统计方法"],
    "GRI 2-9-a": ["ESG治理架构", "ESG 治理架构", "ESG委员会", "ESG办公室", "ESG议题执行小组", "治理架构"],
    "GRI 2-9-b": ["ESG治理架构", "ESG 治理架构", "ESG委员会", "ESG办公室", "ESG议题执行小组", "治理架构"],
    "GRI 2-10-a": ["从略披露", "因商业保密限制从略披露", "提名和遴选"],
    "GRI 2-10-b": ["从略披露", "因商业保密限制从略披露", "提名和遴选"],
    "GRI 2-10-b-i": ["从略披露", "因商业保密限制从略披露", "提名和遴选"],
    "GRI 2-10-b-ii": ["从略披露", "因商业保密限制从略披露", "提名和遴选"],
    "GRI 2-10-b-iii": ["从略披露", "因商业保密限制从略披露", "提名和遴选"],
    "GRI 2-10-b-iv": ["从略披露", "因商业保密限制从略披露", "提名和遴选"],
    "GRI 2-12-a": ["ESG治理架构", "ESG委员会", "ESG办公室", "战略审批", "政策监督"],
    "GRI 2-12-b": ["ESG治理架构", "ESG委员会", "利益相关方", "识别ESG风险", "季度汇报"],
    "GRI 2-12-b-i": ["ESG治理架构", "利益相关方", "ESG诉求"],
    "GRI 2-12-b-ii": ["ESG委员会", "季度汇报", "目标进展"],
    "GRI 2-12-c": ["ESG委员会", "季度汇报", "年度ESG报告", "效果评估"],
    "GRI 2-13-a": ["ESG治理架构", "ESG委员会", "ESG办公室", "责任授权"],
    "GRI 2-13-a-i": ["ESG委员会", "ESG办公室", "CSO", "季度汇报", "高级管理人员"],
    "GRI 2-13-a-ii": ["ESG议题执行小组", "月度拉通", "执行层"],
    "GRI 2-13-b": ["ESG办公室", "ESG委员会", "季度汇报", "年度汇报", "月度拉通"],
    "GRI 2-19-a": ["从略披露", "因商业保密限制从略披露", "薪酬政策"],
    "GRI 2-19-a-i": ["从略披露", "因商业保密限制从略披露", "薪酬政策"],
    "GRI 2-19-a-ii": ["从略披露", "因商业保密限制从略披露", "薪酬政策"],
    "GRI 2-19-a-iii": ["从略披露", "因商业保密限制从略披露", "薪酬政策"],
    "GRI 2-19-a-iv": ["从略披露", "因商业保密限制从略披露", "薪酬政策"],
    "GRI 2-19-a-v": ["从略披露", "因商业保密限制从略披露", "薪酬政策"],
    "GRI 2-19-b": ["从略披露", "因商业保密限制从略披露", "薪酬政策"],
    "GRI 2-20-a": ["从略披露", "因商业保密限制从略披露", "薪酬确定流程"],
    "GRI 2-20-a-i": ["从略披露", "因商业保密限制从略披露", "薪酬确定流程"],
    "GRI 2-20-a-ii": ["从略披露", "因商业保密限制从略披露", "薪酬确定流程"],
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
