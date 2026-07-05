from dataclasses import dataclass
from enum import StrEnum

from src.standards.evidence_ontology import EvidenceKind, RequirementFacet, SemanticGroup


class NoEvidenceGuardrailCategory(StrEnum):
    INCIDENT_CLASSIFICATION = "incident_classification"
    RISK_LOCATION = "risk_location"
    METHOD_SCOPE = "method_scope"
    BREAKDOWN_DIMENSION = "breakdown_dimension"
    SECURITY_PERSONNEL = "security_personnel"


@dataclass(frozen=True)
class NoEvidenceGuardrail:
    requirement_id: str
    category: NoEvidenceGuardrailCategory
    semantic_group: SemanticGroup | None
    required_facets: tuple[RequirementFacet, ...]
    forbidden_evidence_kinds: tuple[EvidenceKind, ...]
    missing_items: tuple[str, ...]
    rationale: str


def _incident_classification_guardrail(
    requirement_id: str,
    *,
    missing_items: tuple[str, ...],
    rationale: str,
    facets: tuple[RequirementFacet, ...] = (RequirementFacet.REQUIRES_INCIDENT_CLASSIFICATION,),
) -> NoEvidenceGuardrail:
    return NoEvidenceGuardrail(
        requirement_id=requirement_id,
        category=NoEvidenceGuardrailCategory.INCIDENT_CLASSIFICATION,
        semantic_group=SemanticGroup.ZERO_EVENT_COMPLIANCE,
        required_facets=facets,
        forbidden_evidence_kinds=(EvidenceKind.EXPLICIT_ZERO_STATEMENT,),
        missing_items=missing_items,
        rationale=rationale,
    )


def _risk_location_guardrail(
    requirement_id: str,
    *,
    missing_items: tuple[str, ...],
    rationale: str,
    semantic_group: SemanticGroup = SemanticGroup.HUMAN_RIGHTS_POLICY,
    forbidden_evidence_kinds: tuple[EvidenceKind, ...] = (
        EvidenceKind.POLICY,
        EvidenceKind.MANAGEMENT_MECHANISM,
        EvidenceKind.CASE,
    ),
) -> NoEvidenceGuardrail:
    return NoEvidenceGuardrail(
        requirement_id=requirement_id,
        category=NoEvidenceGuardrailCategory.RISK_LOCATION,
        semantic_group=semantic_group,
        required_facets=(RequirementFacet.REQUIRES_RISK_LOCATION,),
        forbidden_evidence_kinds=forbidden_evidence_kinds,
        missing_items=missing_items,
        rationale=rationale,
    )


def _method_scope_guardrail(
    requirement_id: str,
    *,
    missing_items: tuple[str, ...],
    rationale: str,
    semantic_group: SemanticGroup | None,
) -> NoEvidenceGuardrail:
    return NoEvidenceGuardrail(
        requirement_id=requirement_id,
        category=NoEvidenceGuardrailCategory.METHOD_SCOPE,
        semantic_group=semantic_group,
        required_facets=(RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION,),
        forbidden_evidence_kinds=(EvidenceKind.KPI_VALUE, EvidenceKind.METHODOLOGY),
        missing_items=missing_items,
        rationale=rationale,
    )


def _generic_guardrail(
    requirement_id: str,
    *,
    category: NoEvidenceGuardrailCategory,
    semantic_group: SemanticGroup | None,
    required_facets: tuple[RequirementFacet, ...],
    forbidden_evidence_kinds: tuple[EvidenceKind, ...],
    missing_items: tuple[str, ...],
    rationale: str,
) -> NoEvidenceGuardrail:
    return NoEvidenceGuardrail(
        requirement_id=requirement_id,
        category=category,
        semantic_group=semantic_group,
        required_facets=required_facets,
        forbidden_evidence_kinds=forbidden_evidence_kinds,
        missing_items=missing_items,
        rationale=rationale,
    )


_ZERO_EVENT_CLASSIFICATION_RULES: dict[str, tuple[tuple[str, ...], str, tuple[RequirementFacet, ...]]] = {
    "GRI 406-1-b": (
        ("歧视事件审查状态",),
        "A general zero discrimination incident statement does not disclose incident review status.",
        (RequirementFacet.REQUIRES_INCIDENT_CLASSIFICATION,),
    ),
    "GRI 406-1-b-i": (
        ("补救计划",),
        "A general zero discrimination incident statement does not disclose remediation plans.",
        (RequirementFacet.REQUIRES_INCIDENT_CLASSIFICATION,),
    ),
    "GRI 406-1-b-ii": (
        ("补救计划实施结果",),
        "A general zero discrimination incident statement does not disclose remediation implementation results.",
        (RequirementFacet.REQUIRES_INCIDENT_CLASSIFICATION,),
    ),
    "GRI 406-1-b-iii": (
        ("已审查且不再采取行动的事件状态",),
        "A general zero discrimination incident statement does not disclose reviewed incidents no longer subject to action.",
        (RequirementFacet.REQUIRES_INCIDENT_CLASSIFICATION,),
    ),
    "GRI 406-1-b-iv": (
        ("结案状态",),
        "A general zero discrimination incident statement does not disclose incident closure status.",
        (RequirementFacet.REQUIRES_INCIDENT_CLASSIFICATION,),
    ),
    "GRI 416-2-a-i": (
        ("罚款或处罚事件数量",),
        "A general zero product-safety harm statement does not disclose incidents resulting in fines or penalties.",
        (RequirementFacet.REQUIRES_INCIDENT_CLASSIFICATION,),
    ),
    "GRI 416-2-a-ii": (
        ("警告事件数量",),
        "A general zero product-safety harm statement does not disclose incidents resulting in warnings.",
        (RequirementFacet.REQUIRES_INCIDENT_CLASSIFICATION,),
    ),
    "GRI 416-2-a-iii": (
        ("自愿准则违规事件数量",),
        "A general zero product-safety harm statement does not disclose incidents of non-compliance with voluntary codes.",
        (RequirementFacet.REQUIRES_INCIDENT_CLASSIFICATION,),
    ),
    "GRI 417-2-a": (
        ("产品信息与标签违规事件总数",),
        "General product information evidence does not disclose labeling non-compliance incident totals.",
        (RequirementFacet.REQUIRES_INCIDENT_CLASSIFICATION,),
    ),
    "GRI 417-2-a-i": (
        ("罚款或处罚事件数量",),
        "General product information evidence does not disclose labeling non-compliance incidents resulting in fines or penalties.",
        (RequirementFacet.REQUIRES_INCIDENT_CLASSIFICATION,),
    ),
    "GRI 417-2-a-ii": (
        ("警告事件数量",),
        "General product information evidence does not disclose labeling non-compliance incidents resulting in warnings.",
        (RequirementFacet.REQUIRES_INCIDENT_CLASSIFICATION,),
    ),
    "GRI 417-2-a-iii": (
        ("自愿准则违规事件数量",),
        "General product information evidence does not disclose labeling non-compliance incidents with voluntary codes.",
        (RequirementFacet.REQUIRES_INCIDENT_CLASSIFICATION,),
    ),
    "GRI 417-2-b": (
        ("无违规事件声明",),
        "General product information evidence does not disclose a concise no-incident statement for labeling non-compliance.",
        (RequirementFacet.REQUIRES_INCIDENT_CLASSIFICATION,),
    ),
    "GRI 417-3-a": (
        ("营销传播违规事件总数",),
        "General compliance evidence does not disclose marketing communication non-compliance incident totals.",
        (RequirementFacet.REQUIRES_INCIDENT_CLASSIFICATION,),
    ),
    "GRI 417-3-a-i": (
        ("罚款或处罚事件数量",),
        "General compliance evidence does not disclose marketing communication non-compliance incidents resulting in fines or penalties.",
        (RequirementFacet.REQUIRES_INCIDENT_CLASSIFICATION,),
    ),
    "GRI 417-3-a-ii": (
        ("警告事件数量",),
        "General compliance evidence does not disclose marketing communication non-compliance incidents resulting in warnings.",
        (RequirementFacet.REQUIRES_INCIDENT_CLASSIFICATION,),
    ),
    "GRI 417-3-a-iii": (
        ("自愿准则违规事件数量",),
        "General compliance evidence does not disclose marketing communication non-compliance incidents with voluntary codes.",
        (RequirementFacet.REQUIRES_INCIDENT_CLASSIFICATION,),
    ),
    "GRI 417-3-b": (
        ("无违规事件声明",),
        "General compliance evidence does not disclose a concise no-incident statement for marketing communication non-compliance.",
        (RequirementFacet.REQUIRES_INCIDENT_CLASSIFICATION,),
    ),
    "GRI 418-1-a-i": (
        ("外部主体投诉数量",),
        "A general zero complaint statement does not split complaints received from outside parties.",
        (RequirementFacet.REQUIRES_COMPLAINT_SOURCE_BREAKDOWN,),
    ),
    "GRI 418-1-a-ii": (
        ("监管机构投诉数量",),
        "A general zero complaint statement does not split complaints received from regulatory bodies.",
        (RequirementFacet.REQUIRES_COMPLAINT_SOURCE_BREAKDOWN,),
    ),
}


_RISK_LOCATION_RULES: dict[str, tuple[tuple[str, ...], str, SemanticGroup]] = {
    "GRI 407-1-a": (
        ("存在风险的运营点或供应商",),
        "Policy and employee representation evidence does not identify operations or suppliers where freedom of association and collective bargaining rights may be at risk.",
        SemanticGroup.HUMAN_RIGHTS_POLICY,
    ),
    "GRI 407-1-a-i": (
        ("风险运营点或供应商类型",),
        "Policy and employee representation evidence does not disclose operation or supplier types at risk for freedom of association and collective bargaining.",
        SemanticGroup.HUMAN_RIGHTS_POLICY,
    ),
    "GRI 407-1-a-ii": (
        ("风险国家或地区",),
        "Policy and employee representation evidence does not disclose countries or geographic areas where these rights may be at risk.",
        SemanticGroup.HUMAN_RIGHTS_POLICY,
    ),
    "GRI 408-1-b": (
        ("青年员工危险工作风险识别结果",),
        "Child-labor policy evidence does not identify operations and suppliers at risk for young workers exposed to hazardous work.",
        SemanticGroup.HUMAN_RIGHTS_POLICY,
    ),
    "GRI 408-1-b-i": (
        ("风险运营点或供应商类型",),
        "Child-labor policy evidence does not disclose operation or supplier types at risk for young workers exposed to hazardous work.",
        SemanticGroup.HUMAN_RIGHTS_POLICY,
    ),
    "GRI 408-1-b-ii": (
        ("风险国家或地区",),
        "Child-labor policy evidence does not disclose countries or geographic areas with young worker hazardous work risk.",
        SemanticGroup.HUMAN_RIGHTS_POLICY,
    ),
    "GRI 409-1-a-i": (
        ("风险运营点或供应商类型",),
        "Forced-labor policy evidence does not disclose operation or supplier types at risk for forced or compulsory labor.",
        SemanticGroup.HUMAN_RIGHTS_POLICY,
    ),
    "GRI 409-1-a-ii": (
        ("风险国家或地区",),
        "Forced-labor policy evidence does not disclose countries or geographic areas with forced or compulsory labor risk.",
        SemanticGroup.HUMAN_RIGHTS_POLICY,
    ),
    "GRI 413-2-a": (
        ("重大负面影响运营点",),
        "Community project evidence does not identify operations with significant actual or potential negative impacts on local communities.",
        SemanticGroup.COMMUNITY_PROGRAM,
    ),
    "GRI 413-2-a-i": (
        ("运营点所在地",),
        "Community project evidence does not disclose the location of operations with significant negative impacts on local communities.",
        SemanticGroup.COMMUNITY_PROGRAM,
    ),
    "GRI 413-2-a-ii": (
        ("重大负面影响",),
        "Community project evidence does not disclose significant actual or potential negative impacts on local communities.",
        SemanticGroup.COMMUNITY_PROGRAM,
    ),
}


_METHOD_SCOPE_RULES: dict[str, tuple[tuple[str, ...], str, SemanticGroup | None]] = {
    "GRI 305-2-c": (
        ("温室气体种类",),
        "Scope 2 emissions amount or factor-source evidence does not explicitly list gases included in the calculation.",
        SemanticGroup.GHG_EMISSIONS_KPI,
    ),
    "GRI 305-2-d": (
        ("基准年", "选择基准年的理由"),
        "Scope 2 emissions amount or factor-source evidence does not disclose base year and rationale.",
        SemanticGroup.GHG_EMISSIONS_KPI,
    ),
    "GRI 305-2-d-i": (
        ("基准年排放量",),
        "Scope 2 emissions amount or factor-source evidence does not disclose base-year emissions.",
        SemanticGroup.GHG_EMISSIONS_KPI,
    ),
    "GRI 305-7-a": (
        ("NOx/SOx 等重大气体排放数据", "空气污染物类别拆分"),
        "Waste management text and water pollutant KPI rows do not substantively disclose significant air emissions such as NOx, SOx, POP, VOC, HAP, or PM.",
        SemanticGroup.GHG_EMISSIONS_KPI,
    ),
    "GRI 403-9-f": (
        ("排除人员说明",),
        "OHS KPI evidence does not disclose whether workers have been excluded from injury data.",
        SemanticGroup.OHS_KPI,
    ),
    "GRI 403-9-g": (
        ("数据编制方法和假设",),
        "OHS KPI evidence does not disclose injury data compilation methods and assumptions beyond rate denominator.",
        SemanticGroup.OHS_KPI,
    ),
    "GRI 403-10-d": (
        ("排除人员说明",),
        "Work-related ill-health KPI evidence does not disclose whether workers have been excluded from the data.",
        SemanticGroup.OHS_KPI,
    ),
    "GRI 403-10-e": (
        ("数据编制方法和假设",),
        "Work-related ill-health KPI evidence does not disclose data compilation methods and assumptions.",
        SemanticGroup.OHS_KPI,
    ),
}


_REMAINING_RULES: dict[
    str,
    tuple[
        NoEvidenceGuardrailCategory,
        SemanticGroup | None,
        tuple[RequirementFacet, ...],
        tuple[EvidenceKind, ...],
        tuple[str, ...],
        str,
    ],
] = {
    "GRI 402-1-b": (
        NoEvidenceGuardrailCategory.METHOD_SCOPE,
        SemanticGroup.NOTICE_PERIOD,
        (RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION,),
        (EvidenceKind.KPI_VALUE, EvidenceKind.MANAGEMENT_MECHANISM),
        ("集体协议中的通知期或协商安排",),
        "The report does not disclose whether notice and consultation provisions are specified in collective agreements.",
    ),
    "GRI 403-1-a-i": (
        NoEvidenceGuardrailCategory.METHOD_SCOPE,
        SemanticGroup.OHS_MANAGEMENT,
        (RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION,),
        (EvidenceKind.MANAGEMENT_MECHANISM,),
        ("适用法律要求清单",),
        "The report references compliance with local OHS laws but does not list the legal requirements.",
    ),
    "GRI 403-2-c": (
        NoEvidenceGuardrailCategory.METHOD_SCOPE,
        SemanticGroup.OHS_MANAGEMENT,
        (RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION,),
        (EvidenceKind.MANAGEMENT_MECHANISM,),
        ("危险工作情境撤离机制", "反报复保护"),
        "The report does not disclose worker removal from dangerous work situations or retaliation protection.",
    ),
    "GRI 403-8-a-ii": (
        NoEvidenceGuardrailCategory.BREAKDOWN_DIMENSION,
        SemanticGroup.OHS_MANAGEMENT,
        (RequirementFacet.REQUIRES_WORKER_BOUNDARY, RequirementFacet.REQUIRES_PERCENTAGE),
        (EvidenceKind.KPI_VALUE, EvidenceKind.MANAGEMENT_MECHANISM),
        ("受组织控制的非雇员工作者覆盖人数及比例",),
        "The report does not disclose the number and percentage of workers who are not employees but whose work or workplace is controlled by the organization and are covered by the OHS system.",
    ),
    "GRI 403-8-b": (
        NoEvidenceGuardrailCategory.METHOD_SCOPE,
        SemanticGroup.OHS_MANAGEMENT,
        (RequirementFacet.REQUIRES_WORKER_BOUNDARY,),
        (EvidenceKind.KPI_VALUE, EvidenceKind.MANAGEMENT_MECHANISM),
        ("未覆盖人员", "排除原因"),
        "The report does not disclose workers excluded from OHS management system coverage.",
    ),
    "GRI 403-8-c": (
        NoEvidenceGuardrailCategory.METHOD_SCOPE,
        SemanticGroup.OHS_MANAGEMENT,
        (RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION,),
        (EvidenceKind.KPI_VALUE, EvidenceKind.MANAGEMENT_MECHANISM),
        ("数据编制方法",),
        "The report does not disclose how OHS coverage data was compiled.",
    ),
    "GRI 403-9-a-iv": (
        NoEvidenceGuardrailCategory.METHOD_SCOPE,
        SemanticGroup.OHS_KPI,
        (RequirementFacet.REQUIRES_IMPACT_TYPE,),
        (EvidenceKind.KPI_VALUE,),
        ("主要工伤类型",),
        "The report does not disclose the main types of employee work-related injuries.",
    ),
    "GRI 403-9-b-iv": (
        NoEvidenceGuardrailCategory.METHOD_SCOPE,
        SemanticGroup.OHS_KPI,
        (RequirementFacet.REQUIRES_IMPACT_TYPE, RequirementFacet.REQUIRES_WORKER_BOUNDARY),
        (EvidenceKind.KPI_VALUE,),
        ("非雇员工作者主要工伤类型",),
        "The report does not disclose the main types of work-related injuries for non-employee workers controlled by the organization.",
    ),
    "GRI 403-9-c-ii": (
        NoEvidenceGuardrailCategory.METHOD_SCOPE,
        SemanticGroup.OHS_KPI,
        (RequirementFacet.REQUIRES_IMPACT_TYPE,),
        (EvidenceKind.KPI_VALUE, EvidenceKind.MANAGEMENT_MECHANISM),
        ("其他工伤危害清单",),
        "The report does not fully disclose other work-related injury hazards.",
    ),
    "GRI 403-10-a-iii": (
        NoEvidenceGuardrailCategory.METHOD_SCOPE,
        SemanticGroup.OHS_KPI,
        (RequirementFacet.REQUIRES_IMPACT_TYPE,),
        (EvidenceKind.KPI_VALUE,),
        ("主要工作相关健康问题类型",),
        "The report does not disclose the main types of employee work-related ill health.",
    ),
    "GRI 403-10-b-iii": (
        NoEvidenceGuardrailCategory.METHOD_SCOPE,
        SemanticGroup.OHS_KPI,
        (RequirementFacet.REQUIRES_IMPACT_TYPE, RequirementFacet.REQUIRES_WORKER_BOUNDARY),
        (EvidenceKind.KPI_VALUE,),
        ("非雇员工作者主要工作相关健康问题类型",),
        "The report does not disclose the main types of work-related ill health for non-employee workers controlled by the organization.",
    ),
    "GRI 403-10-c-ii": (
        NoEvidenceGuardrailCategory.METHOD_SCOPE,
        SemanticGroup.OHS_KPI,
        (RequirementFacet.REQUIRES_IMPACT_TYPE,),
        (EvidenceKind.KPI_VALUE, EvidenceKind.MANAGEMENT_MECHANISM),
        ("其他工作相关健康问题危害清单",),
        "The report does not fully disclose other work-related ill-health hazards.",
    ),
    "GRI 404-1-a-i": (
        NoEvidenceGuardrailCategory.BREAKDOWN_DIMENSION,
        SemanticGroup.BREAKDOWN_DIMENSION,
        (RequirementFacet.REQUIRES_GENDER_BREAKDOWN,),
        (EvidenceKind.KPI_VALUE,),
        ("按性别拆分的平均培训小时数",),
        "The report does not disclose average training hours by gender.",
    ),
    "GRI 404-1-a-ii": (
        NoEvidenceGuardrailCategory.BREAKDOWN_DIMENSION,
        SemanticGroup.BREAKDOWN_DIMENSION,
        (RequirementFacet.REQUIRES_EMPLOYEE_CATEGORY_BREAKDOWN,),
        (EvidenceKind.KPI_VALUE,),
        ("按员工类别拆分的平均培训小时数",),
        "The report does not disclose average training hours by employee category.",
    ),
    "GRI 404-2-b": (
        NoEvidenceGuardrailCategory.METHOD_SCOPE,
        SemanticGroup.TRAINING_PROGRAM,
        (RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION,),
        (EvidenceKind.MANAGEMENT_MECHANISM,),
        ("退休或解雇转型援助计划",),
        "The report does not disclose transition assistance programs for retirement or employment termination.",
    ),
    "GRI 405-2-b": (
        NoEvidenceGuardrailCategory.BREAKDOWN_DIMENSION,
        SemanticGroup.BREAKDOWN_DIMENSION,
        (RequirementFacet.REQUIRES_REGION_BREAKDOWN,),
        (EvidenceKind.KPI_VALUE,),
        ("重要运营地定义",),
        "The report does not disclose the definition of significant operating locations for pay ratio reporting.",
    ),
    "GRI 410-1-a": (
        NoEvidenceGuardrailCategory.SECURITY_PERSONNEL,
        SemanticGroup.HUMAN_RIGHTS_TRAINING,
        (RequirementFacet.REQUIRES_SECURITY_PERSONNEL, RequirementFacet.REQUIRES_PERCENTAGE),
        (EvidenceKind.MANAGEMENT_MECHANISM, EvidenceKind.POLICY),
        ("安保人员人权政策培训比例",),
        "The report does not disclose the percentage of security personnel trained in human rights policies or procedures.",
    ),
    "GRI 410-1-b": (
        NoEvidenceGuardrailCategory.SECURITY_PERSONNEL,
        SemanticGroup.HUMAN_RIGHTS_TRAINING,
        (RequirementFacet.REQUIRES_SECURITY_PERSONNEL,),
        (EvidenceKind.MANAGEMENT_MECHANISM, EvidenceKind.POLICY),
        ("第三方安保人员培训要求",),
        "The report does not disclose whether third-party security personnel are subject to equivalent human rights training requirements.",
    ),
    "GRI 413-1-a-i": (
        NoEvidenceGuardrailCategory.BREAKDOWN_DIMENSION,
        SemanticGroup.COMMUNITY_PROGRAM,
        (RequirementFacet.REQUIRES_PERCENTAGE,),
        (EvidenceKind.CASE, EvidenceKind.MANAGEMENT_MECHANISM),
        ("社会影响评估覆盖比例",),
        "The report does not disclose social impact assessment coverage by operation.",
    ),
    "GRI 413-1-a-ii": (
        NoEvidenceGuardrailCategory.BREAKDOWN_DIMENSION,
        SemanticGroup.COMMUNITY_PROGRAM,
        (RequirementFacet.REQUIRES_PERCENTAGE,),
        (EvidenceKind.CASE, EvidenceKind.MANAGEMENT_MECHANISM),
        ("环境影响评估及监测覆盖比例",),
        "The report does not disclose environmental impact assessment or ongoing monitoring coverage by operation for local communities.",
    ),
    "GRI 413-1-a-iii": (
        NoEvidenceGuardrailCategory.METHOD_SCOPE,
        SemanticGroup.COMMUNITY_PROGRAM,
        (RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION,),
        (EvidenceKind.CASE, EvidenceKind.MANAGEMENT_MECHANISM),
        ("影响评估结果公开披露",),
        "The report does not disclose public disclosure of environmental and social impact assessment results.",
    ),
    "GRI 413-1-a-vi": (
        NoEvidenceGuardrailCategory.METHOD_SCOPE,
        SemanticGroup.COMMUNITY_PROGRAM,
        (RequirementFacet.REQUIRES_PERCENTAGE, RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION),
        (EvidenceKind.CASE, EvidenceKind.MANAGEMENT_MECHANISM),
        ("基于利益相关方映射的参与计划覆盖比例",),
        "The report does not disclose stakeholder engagement plans based on stakeholder mapping by operation.",
    ),
    "GRI 413-1-a-vii": (
        NoEvidenceGuardrailCategory.METHOD_SCOPE,
        SemanticGroup.COMMUNITY_PROGRAM,
        (RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION,),
        (EvidenceKind.CASE, EvidenceKind.MANAGEMENT_MECHANISM),
        ("社区咨询委员会和流程",),
        "The report does not disclose broad-based local community consultation committees and processes.",
    ),
    "GRI 413-1-a-viii": (
        NoEvidenceGuardrailCategory.METHOD_SCOPE,
        SemanticGroup.COMMUNITY_PROGRAM,
        (RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION,),
        (EvidenceKind.CASE, EvidenceKind.MANAGEMENT_MECHANISM),
        ("社区专门申诉机制",),
        "The report does not disclose formal local community grievance processes.",
    ),
    "GRI 416-1-a": (
        NoEvidenceGuardrailCategory.BREAKDOWN_DIMENSION,
        SemanticGroup.PRODUCT_INFORMATION,
        (RequirementFacet.REQUIRES_PERCENTAGE,),
        (EvidenceKind.MANAGEMENT_MECHANISM,),
        ("产品/服务类别总数", "被评估类别数量和比例"),
        "The report describes product quality and safety management, but does not disclose the percentage of significant product and service categories assessed for health and safety impacts.",
    ),
    "GRI 417-1-a-i": (
        NoEvidenceGuardrailCategory.METHOD_SCOPE,
        SemanticGroup.PRODUCT_INFORMATION,
        (RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION,),
        (EvidenceKind.MANAGEMENT_MECHANISM,),
        ("组件来源信息",),
        "The report does not disclose sourcing of components for product and service information.",
    ),
    "GRI 417-1-a-iv": (
        NoEvidenceGuardrailCategory.METHOD_SCOPE,
        SemanticGroup.PRODUCT_INFORMATION,
        (RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION,),
        (EvidenceKind.MANAGEMENT_MECHANISM,),
        ("处置方式", "处置阶段影响"),
        "The report does not disclose disposal of the product and environmental or social impacts at disposal.",
    ),
    "GRI 417-1-a-v": (
        NoEvidenceGuardrailCategory.METHOD_SCOPE,
        SemanticGroup.PRODUCT_INFORMATION,
        (RequirementFacet.REQUIRES_METHOD_OR_ASSUMPTION,),
        (EvidenceKind.MANAGEMENT_MECHANISM,),
        ("其他标签信息类型",),
        "The report does not disclose other types of product or service information required by labeling procedures.",
    ),
    "GRI 417-1-b": (
        NoEvidenceGuardrailCategory.BREAKDOWN_DIMENSION,
        SemanticGroup.PRODUCT_INFORMATION,
        (RequirementFacet.REQUIRES_PERCENTAGE,),
        (EvidenceKind.MANAGEMENT_MECHANISM,),
        ("产品类别覆盖比例",),
        "The report does not disclose the percentage of significant product or service categories covered by product information and labeling procedures.",
    ),
}


_GUARDRAILS: dict[str, NoEvidenceGuardrail] = {
    requirement_id: _incident_classification_guardrail(
        requirement_id,
        missing_items=missing_items,
        rationale=rationale,
        facets=facets,
    )
    for requirement_id, (missing_items, rationale, facets) in _ZERO_EVENT_CLASSIFICATION_RULES.items()
}
_GUARDRAILS.update(
    {
        requirement_id: _risk_location_guardrail(
            requirement_id,
            missing_items=missing_items,
            rationale=rationale,
            semantic_group=semantic_group,
        )
        for requirement_id, (missing_items, rationale, semantic_group) in _RISK_LOCATION_RULES.items()
    }
)
_GUARDRAILS.update(
    {
        requirement_id: _generic_guardrail(
            requirement_id,
            category=category,
            semantic_group=semantic_group,
            required_facets=required_facets,
            forbidden_evidence_kinds=forbidden_evidence_kinds,
            missing_items=missing_items,
            rationale=rationale,
        )
        for requirement_id, (
            category,
            semantic_group,
            required_facets,
            forbidden_evidence_kinds,
            missing_items,
            rationale,
        ) in _REMAINING_RULES.items()
    }
)
_GUARDRAILS.update(
    {
        requirement_id: _method_scope_guardrail(
            requirement_id,
            missing_items=missing_items,
            rationale=rationale,
            semantic_group=semantic_group,
        )
        for requirement_id, (missing_items, rationale, semantic_group) in _METHOD_SCOPE_RULES.items()
    }
)


def get_no_evidence_guardrail(requirement_id: str) -> NoEvidenceGuardrail | None:
    return _GUARDRAILS.get(requirement_id)
