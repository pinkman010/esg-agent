from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LeafSufficiencyRule:
    requirement_id: str
    expected_components: tuple[str, ...]
    missing_item_templates: tuple[str, ...]
    excluded_neighbor_components: tuple[str, ...] = ()


_RULES = {
    "GRI 303-1-a": LeafSufficiencyRule(
        requirement_id="GRI 303-1-a",
        expected_components=("取水互动", "耗水互动", "排水互动", "水相关影响"),
        missing_item_templates=("取水、耗水和排水互动说明", "水相关影响识别结果"),
        excluded_neighbor_components=("水压力地区拆分", "数据编制方法"),
    ),
    "GRI 305-2-e": LeafSufficiencyRule(
        requirement_id="GRI 305-2-e",
        expected_components=("排放因子来源或引用", "GWP来源或引用"),
        missing_item_templates=("GWP来源或引用",),
        excluded_neighbor_components=("一般核算方法",),
    ),
    "GRI 306-3-a": LeafSufficiencyRule(
        requirement_id="GRI 306-3-a",
        expected_components=("废弃物产生总重量", "废弃物组成"),
        missing_item_templates=("废弃物组成拆分",),
        excluded_neighbor_components=("回收", "处置"),
    ),
    "GRI 401-1-b": LeafSufficiencyRule(
        requirement_id="GRI 401-1-b",
        expected_components=("离职员工人数", "离职率", "性别拆分", "年龄拆分", "地区拆分"),
        missing_item_templates=("离职员工总数", "按性别拆分的离职人数和离职率", "按年龄拆分的离职人数和离职率", "完整地区拆分"),
    ),
    "GRI 404-2-a": LeafSufficiencyRule(
        requirement_id="GRI 404-2-a",
        expected_components=("员工技能提升项目", "持续就业能力支持"),
        missing_item_templates=("员工技能提升项目的内容和覆盖范围", "持续就业能力支持说明"),
        excluded_neighbor_components=("转型援助", "退休", "解雇"),
    ),
    "GRI 416-1-a": LeafSufficiencyRule(
        requirement_id="GRI 416-1-a",
        expected_components=("重大产品和服务类别分母", "接受健康安全影响评估的类别数", "覆盖百分比"),
        missing_item_templates=("重大产品和服务类别总数或计算分母", "接受健康安全影响评估的类别数量", "接受评估的类别百分比"),
        excluded_neighbor_components=("标签程序", "信息类别"),
    ),
    "GRI 305-2-d-i": LeafSufficiencyRule(
        requirement_id="GRI 305-2-d-i",
        expected_components=("基准年选择理由",),
        missing_item_templates=("基准年选择理由",),
    ),
    "GRI 406-1-b-i": LeafSufficiencyRule(
        requirement_id="GRI 406-1-b-i",
        expected_components=("歧视事件审查状态",),
        missing_item_templates=("歧视事件是否已由组织审查",),
        excluded_neighbor_components=("补救计划",),
    ),
    "GRI 406-1-b-ii": LeafSufficiencyRule(
        requirement_id="GRI 406-1-b-ii",
        expected_components=("补救计划实施状态",),
        missing_item_templates=("补救计划是否正在实施",),
        excluded_neighbor_components=("实施结果", "结案"),
    ),
    "GRI 408-1-b": LeafSufficiencyRule(
        requirement_id="GRI 408-1-b",
        expected_components=("消除童工措施",),
        missing_item_templates=("针对已识别高风险运营点或供应商采取的消除童工措施",),
        excluded_neighbor_components=("青年工人危险工作",),
    ),
    "GRI 306-1-a": LeafSufficiencyRule(
        requirement_id="GRI 306-1-a",
        expected_components=("实际和潜在重大废弃物相关影响", "影响发生位置"),
        missing_item_templates=("实际和潜在重大废弃物相关影响", "影响发生于组织活动或上下游价值链的位置"),
    ),
    "GRI 405-1-a": LeafSufficiencyRule(
        requirement_id="GRI 405-1-a",
        expected_components=("治理机构性别拆分", "治理机构年龄组拆分", "其他多元化指标"),
        missing_item_templates=("治理机构成员性别拆分", "治理机构成员年龄组拆分", "治理机构其他多元化指标"),
    ),
    "GRI 407-1-b": LeafSufficiencyRule(
        requirement_id="GRI 407-1-b",
        expected_components=("支持结社自由和集体谈判权的措施",),
        missing_item_templates=("为支持结社自由和集体谈判权采取的措施",),
    ),
}


def get_leaf_sufficiency_rule(requirement_id: str) -> LeafSufficiencyRule | None:
    return _RULES.get(requirement_id)
