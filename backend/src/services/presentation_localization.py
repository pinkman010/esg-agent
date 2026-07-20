from __future__ import annotations

from collections.abc import Sequence
from hashlib import sha256
import logging
import re


logger = logging.getLogger(__name__)


RATIONALE_TRANSLATIONS = {
    "No report evidence was found for this requirement.": "未找到支持该要求的报告证据。",
    "The report index contains an omission note, but no substantive disclosure evidence was found.": "报告 GRI 内容索引包含从略说明，但未找到实质性披露证据。",
    "The GRI index states that no violations occurred during the reporting period, but it does not provide full substantive detail for this sub-requirement.": "GRI 内容索引说明报告期内未发生违规，但未提供该子要求所需的完整实质性披露。",
}


MISSING_ITEM_TRANSLATIONS = {
    "1000 kilograms per metric ton or metric tons directly": "每公吨按 1,000 千克换算，或直接以公吨计量",
    "absolute energy numerator and organization-specific denominator": "绝对能源消耗分子和组织特定分母",
    "absolute GHG emissions numerator and organization-specific denominator": "绝对温室气体排放分子和组织特定分母",
    "applicability of EVG&D source basis": "EVG&D 数据来源依据的适用性说明",
    "applicability of no-system fallback": "无计算系统时替代方案的适用性说明",
    "audited consolidated financial statement/public record source basis": "经审计的合并财务报表或公开记录的数据来源依据",
    "avoid double-counting self-generated energy": "避免重复计算自产能源",
    "basis of estimation when default figures are unavailable": "默认数据不可用时的估算依据",
    "biogenic CO2 reported separately": "单独披露生物源二氧化碳",
    "calculation based on published emission factors": "基于公开排放因子的计算",
    "calculation based on site-specific data": "基于场所特定数据的计算",
    "commuting incidents included only when transport is organization-arranged": "仅在交通由组织安排时计入通勤事故",
    "current tax accrued for reported period": "报告期当期应计税额",
    "direct measurement of significant air emissions": "重大大气排放的直接测量",
    "emission-factor source may be not applicable when direct measurement is used": "采用直接测量时排放因子来源可能不适用",
    "entities owned or controlled by the organization": "组织拥有或控制的实体",
    "EVG&D source basis from audited financial/P&L statement or internally audited management accounts": "EVG&D 数据来源依据：经审计的财务报表或损益表，或经内部审计的管理账目",
    "exclude deferred corporate income tax and uncertain tax position provisions": "排除递延企业所得税和不确定税务处理准备",
    "exclude effluent unless national law requires inclusion in total waste": "除非国家法律要求计入废弃物总量，否则排除废水",
    "exclude energy already reported in 302-1": "排除已在 GRI 302-1 中披露的能源",
    "exclude fatalities from high-consequence injury count and rate": "从高后果工伤数量和比率中排除死亡事件",
    "exclude GHG trades from gross Scope 1 emissions": "从范围一温室气体排放总量中排除温室气体交易",
    "exclude GHG trades from gross Scope 2 emissions": "从范围二温室气体排放总量中排除温室气体交易",
    "exclude incidents where organization was determined not at fault": "排除已认定组织无过错的事件",
    "exclude in-kind general welfare programs": "排除非现金形式的一般性福利计划",
    "exclude labeling-related non-compliance from 416-2 and route to 417-2": "从 GRI 416-2 中排除标签相关不合规，并归入 GRI 417-2",
    "exclude reductions from reduced production capacity or outsourcing": "排除因产能下降或外包造成的减排",
    "exclude rejects and recalls of products": "排除退货和产品召回",
    "exclude Scope 2 emissions from Scope 3 disclosure": "从范围三披露中排除范围二排放",
    "exclude Scope 3 emissions from Scope 2 disclosure": "从范围二披露中排除范围三排放",
    "explanation for reconciliation differences": "对勾稽差异的说明",
    "GAAP or consistent accounting basis": "公认会计原则（GAAP）或一致的会计基础",
    "GWP rates": "GWP 数值",
    "GWP来源或引用": "GWP 来源或引用",
    "hazard-specific training 细节": "针对特定危害的培训细节",
    "head count 或 FTE 口径": "人数或全职当量（FTE）口径",
    "identify current-period labeling non-compliance related to prior-period events": "识别本期确认且与以前期间事件相关的标签不合规",
    "identify current-period marketing non-compliance related to prior-period events": "识别本期确认且与以前期间事件相关的营销传播不合规",
    "identify current-period non-compliance related to prior-period events": "识别本期确认且与以前期间事件相关的不合规",
    "include fatalities in recordable injury count and rate": "在可记录工伤数量和比率中计入死亡事件",
    "include fatalities in recordable work-related ill health cases": "在可记录工作相关健康问题病例中计入死亡病例",
    "inventory or project accounting method": "清单核算方法或项目核算方法",
    "location-based and market-based methods when contractual instruments exist": "存在合同工具时采用基于地点和基于市场的方法",
    "location-based method when product or supplier-specific data is unavailable": "产品或供应商特定数据不可用时采用基于地点的方法",
    "method used for estimation or modeling": "估算或建模所采用的方法",
    "monetary value of government financial assistance": "政府财政援助的货币价值",
    "NOx/SOx 等重大气体排放数据": "氮氧化物、硫氧化物等重大气体排放数据",
    "ODS production minus approved destruction and feedstock use": "消耗臭氧层物质产量扣除经批准的销毁量和原料用途量",
    "offset-derived reductions reported separately": "单独披露来自抵消项目的减排量",
    "percentage": "百分比",
    "percentage calculated using full-time employee data": "使用全职员工数据计算的百分比",
    "percentage of reclaimed products and packaging by product category": "按产品类别划分的回收产品及包装材料百分比",
    "period covered by the most recent audited statements or permitted fallback period": "最近一期经审计报表覆盖的期间，或允许采用的替代期间",
    "plans and timeline when financial implication or cost calculation system is unavailable": "财务影响或成本计算系统不可用时的计划和时间表",
    "primary effects plus significant secondary effects": "主要影响及重大次生影响",
    "public and credible water stress assessment tool or methodology": "公开且可信的水资源压力评估工具或方法",
    "rates based on 200000 or 1000000 hours worked": "基于 20 万或 100 万工作小时计算的比率",
    "reconciliation to audited consolidated statements for selected fields": "选定字段与经审计合并报表的勾稽",
    "recovery operation 拆分": "按回收利用作业类型拆分",
    "recycled input material percentage formula": "再生投入材料百分比计算公式",
    "reductions reported separately by Scope type": "按范围类型分别披露减排量",
    "Scope 3 intensity separately from Scope 1 and Scope 2 intensity": "范围三排放强度与范围一、范围二排放强度分别披露",
    "separate internal and external energy intensity ratios": "分别披露组织内部和外部能源强度比率",
    "separate non-renewable and renewable fuel consumption": "分别披露不可再生和可再生燃料消耗",
    "significant locations of operation": "重要运营地点",
    "specified biogenic non-CO2 and lifecycle emissions excluded": "排除规定的生物源非二氧化碳排放和生命周期排放",
    "specified discrimination grounds, internal/external stakeholders, operations, and reporting period": "明确歧视事由、内外部利益相关方、运营范围和报告期",
    "stateless entity reported separately": "单独披露无税收管辖归属的实体",
    "substantial number of privacy breaches related to preceding years": "与以前年度相关的大量隐私泄露事件",
    "tax jurisdiction boundary": "税收管辖区边界",
    "total employee numbers at reporting period end for hire and turnover rates": "用于计算招聘率和流失率的报告期末员工总数",
    "total internal energy formula in joules or multiples": "以焦耳或其倍数表示的组织内部能源总量计算公式",
    "total material weight or volume used as denominator consistent with 301-1": "与 GRI 301-1 一致的材料总重量或体积计算分母",
    "whether reduction is estimated, modeled, or directly measured": "减排量采用估算、建模或直接测量的说明",
    "业务关系相关 OHS 影响预防和缓解全过程": "业务关系相关职业健康与安全影响的完整预防和缓解过程",
    "危险废弃物 recovery operation 拆分": "危险废弃物按回收利用作业类型拆分",
    "完整 GWP 来源": "完整的 GWP 来源",
    "完整 input/activity/output 映射": "完整的投入、活动和产出映射",
    "完整 OHS 范围、覆盖、流程、职责或获取方式": "完整的职业健康与安全范围、覆盖、流程、职责或获取方式",
    "完整 work-related ill health 口径": "完整的工作相关健康问题口径",
    "非危险废弃物 recovery operation 拆分": "非危险废弃物按回收利用作业类型拆分",
}


_PARTIAL_DISCLOSURE_SUFFIX = "因此判定为 partially_disclosed。"


def localize_rationale(value: str | None, *, exact_only: bool = False) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if normalized in RATIONALE_TRANSLATIONS:
        return RATIONALE_TRANSLATIONS[normalized]
    if normalized.endswith(_PARTIAL_DISCLOSURE_SUFFIX) and re.search(r"[\u4e00-\u9fff]", normalized):
        return normalized[: -len(_PARTIAL_DISCLOSURE_SUFFIX)] + "因此判定为部分披露。"
    if exact_only or not re.search(r"[A-Za-z]{3}", normalized):
        return value

    lowered = normalized.casefold()
    if "directionally relevant" in lowered:
        return "现有证据与该要求相关，但尚未完整满足 GRI 披露要求，需人工复核证据充分性。"
    if (
        "directly satisfies" in lowered
        or lowered.startswith("evidence was found")
        or "directly discloses" in lowered
        or "discloses channels for" in lowered
        or "discloses the relevant climate-related" in lowered
    ):
        return "已找到直接支持该要求的报告证据。"
    if any(
        marker in lowered
        for marker in (
            "does not",
            "do not",
            "no valid report evidence",
            "it is not complete enough",
            "is narrower than",
        )
    ):
        return "报告未提供该要求所需的完整披露，具体缺失内容见“缺失项”。"

    _warn_unmapped("rationale", normalized)
    return value


def localize_missing_items(values: Sequence[str]) -> list[str]:
    localized: list[str] = []
    for value in values:
        normalized = value.strip()
        translated = MISSING_ITEM_TRANSLATIONS.get(normalized)
        if translated is None:
            if re.search(r"[A-Za-z]{3}", normalized):
                _warn_unmapped("missing_item", normalized)
            translated = value
        localized.append(translated)
    return localized


def _warn_unmapped(template_type: str, value: str) -> None:
    fingerprint = sha256(value.encode("utf-8")).hexdigest()[:12]
    logger.warning(
        "unmapped_presentation_template type=%s fingerprint=%s",
        template_type,
        fingerprint,
    )
