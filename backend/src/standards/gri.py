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
    "GRI 2-20-a-iii": ["从略披露", "因商业保密限制从略披露", "薪酬确定流程"],
    "GRI 2-20-b": ["从略披露", "因商业保密限制从略披露", "薪酬确定流程"],
    "GRI 2-21-a": ["从略披露", "因商业保密限制从略披露", "年度总薪酬比率"],
    "GRI 2-21-b": ["从略披露", "因商业保密限制从略披露", "年度总薪酬比率"],
    "GRI 2-21-c": ["从略披露", "因商业保密限制从略披露", "年度总薪酬比率"],
    "GRI 2-22-a": ["董事长致辞", "CSO 致辞", "可持续发展战略", "零碳目标", "三新战略"],
    "GRI 2-23-a": ["政策承诺", "UNGC", "世界人权宣言", "ILO", "供应商行为准则", "合规制度"],
    "GRI 2-23-a-i": ["政策承诺", "UNGC", "十项原则", "世界人权宣言", "ILO"],
    "GRI 2-23-a-ii": ["尽职调查", "供应商尽调", "第三方反腐败尽调"],
    "GRI 2-23-a-iii": ["预防原则"],
    "GRI 2-23-a-iv": ["劳工与人权", "人权保护政策", "供应商行为准则"],
    "GRI 2-23-b": ["政策承诺", "UNGC", "世界人权宣言", "供应商行为准则"],
    "GRI 2-23-b-i": ["政策承诺", "UNGC", "世界人权宣言", "供应商行为准则"],
    "GRI 2-23-b-ii": ["政策承诺", "UNGC", "世界人权宣言", "供应商行为准则"],
    "GRI 2-23-c": ["政策链接", "公开链接"],
    "GRI 2-23-d": ["审批层级", "最高治理机构批准"],
    "GRI 2-23-e": ["运营环节", "员工政策", "供应商网络"],
    "GRI 2-23-f": ["人权培训", "供应商培训与赋能", "合规文化培训"],
    "GRI 2-24-a": ["融合政策承诺", "ESG战略", "ESG治理架构", "供应商行为准则", "合规制度"],
    "GRI 2-24-a-i": ["融合政策承诺", "ESG战略", "供应商风险管理"],
    "GRI 2-24-a-ii": ["融合政策承诺", "供应商行为准则", "合规制度"],
    "GRI 2-24-a-iii": ["融合政策承诺", "供应商培训", "合规培训"],
    "GRI 2-24-a-iv": ["融合政策承诺", "监控", "整改闭环"],
    "GRI 2-25-a": ["补救负面影响", "人权侵害投诉机制", "供应商整改", "举报调查处理"],
    "GRI 2-25-b": ["阳光热线", "投诉机制", "举报电话", "举报邮箱"],
    "GRI 2-25-c": ["整改闭环", "合规风险排查", "举报调查处理"],
    "GRI 2-25-d": ["使用者参与", "机制设计"],
    "GRI 2-25-e": ["投诉处理率", "舞弊案件调查完结率", "整改闭环率"],
    "GRI 2-26-a": ["阳光热线", "举报电话", "举报邮箱", "挑战者代表"],
    "GRI 2-26-a-i": ["寻求建议", "合规建议"],
    "GRI 2-26-a-ii": ["举报电话", "举报邮箱", "阳光热线", "举报人保护"],
    "GRI 2-27-a": ["未发生违法违规事件", "遵守法律法规"],
    "GRI 2-27-a-i": ["未发生违法违规事件", "罚款"],
    "GRI 2-27-a-ii": ["未发生违法违规事件", "非经济处罚"],
    "GRI 2-27-b": ["未发生违法违规事件", "以前报告期"],
    "GRI 2-27-b-i": ["未发生违法违规事件", "以前报告期罚款"],
    "GRI 2-27-b-ii": ["未发生违法违规事件", "以前报告期非经济处罚"],
    "GRI 2-27-c": ["未发生违法违规事件", "重大违法违规事件"],
    "GRI 2-27-d": ["重大违法违规界定"],
    "GRI 2-28-a": ["UNGC", "RE100", "SBTi", "CDP", "IEA", "WEF", "协会的成员资格"],
    "GRI 2-29-a": ["利益相关方沟通", "关注议题", "沟通渠道", "重要性评估"],
    "GRI 2-29-a-i": ["利益相关方沟通", "关注议题", "沟通渠道"],
    "GRI 2-29-a-ii": ["利益相关方沟通", "沟通频率", "沟通渠道"],
    "GRI 2-29-a-iii": ["利益相关方沟通", "重要性评估", "利益相关方调研"],
    "GRI 2-30-a": ["从略披露", "因商业保密限制从略披露", "集体谈判协议"],
    "GRI 2-30-b": ["从略披露", "因商业保密限制从略披露", "集体谈判协议"],
    "GRI 3-1-a": ["重要性评估", "重要性矩阵", "利益相关方调研"],
    "GRI 3-1-a-i": ["重要性评估", "利益相关方调研", "问卷"],
    "GRI 3-1-a-ii": ["重要性评估", "部门访谈", "重要性矩阵"],
    "GRI 3-1-b": ["重要性评估", "重要性矩阵", "重大议题"],
    "GRI 201-1-a": ["从略披露", "因商业保密限制从略披露", "直接产生和分配的经济价值"],
    "GRI 201-1-a-i": ["从略披露", "因商业保密限制从略披露", "直接产生和分配的经济价值"],
    "GRI 201-1-a-ii": ["从略披露", "因商业保密限制从略披露", "直接产生和分配的经济价值"],
    "GRI 201-1-a-iii": ["从略披露", "因商业保密限制从略披露", "直接产生和分配的经济价值"],
    "GRI 201-1-b": ["从略披露", "因商业保密限制从略披露", "直接产生和分配的经济价值"],
    "GRI 201-2-a": ["气候风险", "气候机遇", "财务影响", "风险管理流程", "应对措施"],
    "GRI 201-2-a-i": ["气候风险", "气候机遇", "实体风险", "转型风险", "市场风险", "法律风险"],
    "GRI 201-2-a-ii": ["气候风险", "气候机遇", "影响分析", "维修成本", "订单损失", "低成本资金"],
    "GRI 201-2-a-iii": ["财务影响", "维修成本", "订单损失", "绿色投融资", "新能源政策激励"],
    "GRI 201-2-a-iv": ["应对措施", "风险管理流程", "识别", "分析", "审查"],
    "GRI 201-2-a-v": ["行动成本", "采取行动的成本", "成本"],
    "GRI 201-3-a": ["养老金", "退休计划", "设定受益计划", "离职后福利", "负债估算"],
    "GRI 201-3-b": ["养老金", "退休计划", "设定受益计划", "基金资产覆盖", "精算假设"],
    "GRI 201-3-b-i": ["养老金", "退休计划", "计划负债", "基金资产"],
    "GRI 201-3-b-ii": ["养老金", "退休计划", "估算基础", "精算假设"],
    "GRI 201-3-b-iii": ["养老金", "退休计划", "估算时间", "估值日期"],
    "GRI 201-3-c": ["养老金", "退休计划", "覆盖策略", "资金覆盖"],
    "GRI 201-3-d": ["养老金", "退休计划", "养老保险缴费", "雇主缴费", "雇员缴费", "缴费比例"],
    "GRI 201-3-e": ["养老金", "退休计划", "参与水平", "参与比例"],
    "GRI 201-4-a": ["从略披露", "因商业保密限制从略披露", "政府给予的财政补贴"],
    "GRI 201-4-a-i": ["从略披露", "因商业保密限制从略披露", "政府给予的财政补贴"],
    "GRI 201-4-a-ii": ["从略披露", "因商业保密限制从略披露", "政府给予的财政补贴"],
    "GRI 201-4-a-iii": ["从略披露", "因商业保密限制从略披露", "政府给予的财政补贴"],
    "GRI 201-4-a-iv": ["从略披露", "因商业保密限制从略披露", "政府给予的财政补贴"],
    "GRI 201-4-a-v": ["从略披露", "因商业保密限制从略披露", "政府给予的财政补贴"],
    "GRI 201-4-a-vi": ["从略披露", "因商业保密限制从略披露", "政府给予的财政补贴"],
    "GRI 201-4-a-vii": ["从略披露", "因商业保密限制从略披露", "政府给予的财政补贴"],
    "GRI 201-4-a-viii": ["从略披露", "因商业保密限制从略披露", "政府给予的财政补贴"],
    "GRI 201-4-b": ["从略披露", "因商业保密限制从略披露", "政府给予的财政补贴"],
    "GRI 201-4-c": ["从略披露", "因商业保密限制从略披露", "政府给予的财政补贴"],
    "GRI 202-1-a": ["最低工资", "标准起薪", "按性别", "重要运营地"],
    "GRI 202-1-b": ["最低工资", "标准起薪", "其他工作者"],
    "GRI 202-1-c": ["最低工资", "可变情况", "重要运营地"],
    "GRI 202-1-d": ["最低工资", "重要运营地定义", "运营地"],
    "GRI 202-2-a": ["从略披露", "因商业保密限制从略披露", "当地社区高管比例"],
    "GRI 202-2-b": ["从略披露", "因商业保密限制从略披露", "当地社区高管比例"],
    "GRI 202-2-c": ["从略披露", "因商业保密限制从略披露", "当地社区高管比例"],
    "GRI 202-2-d": ["从略披露", "因商业保密限制从略披露", "当地社区高管比例"],
    "GRI 203-1-a": ["携手社区", "贡献社会", "乡村振兴", "基础设施投资", "支持性服务"],
    "GRI 203-1-b": ["携手社区", "贡献社会", "当地经济", "社区影响"],
    "GRI 203-1-c": ["携手社区", "公益", "捐赠", "研究基金", "商业合作"],
    "GRI 203-2-a": ["间接经济影响", "乡村振兴", "绿色能源项目", "产业升级", "社区公益"],
    "GRI 203-2-b": ["间接经济影响", "UN SDGs", "一带一路", "G20", "利益相关方优先事项"],
    "GRI 204-1-a": ["从略披露", "因商业保密限制从略披露", "向当地供应商采购的支出比例"],
    "GRI 204-1-b": ["从略披露", "因商业保密限制从略披露", "当地供应商", "重要运营地"],
    "GRI 204-1-c": ["从略披露", "因商业保密限制从略披露", "当地采购支出比例"],
    "GRI 205-1-a": ["反腐败", "贪污贿赂", "风险评估", "内部审计", "经营地点占比"],
    "GRI 205-1-b": ["反腐败", "廉洁风险", "高风险环节", "关键业务流程"],
    "GRI 205-2-a": ["反腐败政策", "治理机构成员", "传达"],
    "GRI 205-2-b": ["合规培训", "利益冲突申报", "反腐败和贿赂培训次数", "累计小时数"],
    "GRI 205-2-c": ["供应商阳光协议", "第三方反腐败尽调", "供应商行为准则", "可持续采购章程"],
    "GRI 205-2-d": ["治理机构成员", "反腐败培训"],
    "GRI 205-2-e": ["员工合规培训", "纪律合规文化月", "反腐败和贿赂培训次数", "累计小时数"],
    "GRI 205-3-a": ["贪污腐败事件数量", "舞弊案件", "商业道德管理"],
    "GRI 205-3-b": ["员工因腐败被开除或受到处分的事件数量"],
    "GRI 205-3-c": ["腐败", "合同终止", "不续约"],
    "GRI 205-3-d": ["腐败", "公开法律案件", "法律案件结果"],
    "GRI 206-1-a": ["反竞争行为事件数量", "反竞争行为", "反垄断", "反托拉斯"],
    "GRI 206-1-b": ["反竞争", "法律行动结果", "判决"],
    "GRI 207-1-a": ["税务治理", "财务合规与安全部门", "税务管理标准", "税收协定"],
    "GRI 207-1-a-iii": ["税收协定", "税法要求", "监管合规", "税务管理标准"],
    "GRI 207-2-a": ["税务治理", "财务合规与安全部门", "财务风险管理", "税务管理标准"],
    "GRI 207-2-a-i": ["税务治理", "财务合规与安全部门", "责任主体"],
    "GRI 207-2-a-ii": ["税务治理", "财务风险管理", "嵌入机制"],
    "GRI 207-2-a-iii": ["税法要求", "风险演变", "风险识别", "风险监控"],
    "GRI 207-2-a-iv": ["内部审计", "风险控制", "评估机制"],
    "GRI 207-3-a": ["利益相关方", "税务管理的期待", "税务相关关切"],
    "GRI 207-3-a-i": ["税务机关沟通", "税务机关"],
    "GRI 207-3-a-ii": ["公共政策倡导", "税务公共政策"],
    "GRI 207-3-a-iii": ["外部利益相关方意见", "税务意见收集"],
    "GRI 207-4-a": ["从略披露", "因商业保密限制从略披露", "国别报告"],
    "GRI 207-4-b": ["从略披露", "因商业保密限制从略披露", "国别报告"],
    "GRI 207-4-b-i": ["从略披露", "因商业保密限制从略披露", "国别报告"],
    "GRI 207-4-b-ii": ["从略披露", "因商业保密限制从略披露", "国别报告"],
    "GRI 207-4-b-iii": ["从略披露", "因商业保密限制从略披露", "国别报告"],
    "GRI 207-4-b-iv": ["从略披露", "因商业保密限制从略披露", "国别报告"],
    "GRI 207-4-b-v": ["从略披露", "因商业保密限制从略披露", "国别报告"],
    "GRI 207-4-b-vi": ["从略披露", "因商业保密限制从略披露", "国别报告"],
    "GRI 207-4-b-vii": ["从略披露", "因商业保密限制从略披露", "国别报告"],
    "GRI 207-4-b-viii": ["从略披露", "因商业保密限制从略披露", "国别报告"],
    "GRI 207-4-b-ix": ["从略披露", "因商业保密限制从略披露", "国别报告"],
    "GRI 207-4-b-x": ["从略披露", "因商业保密限制从略披露", "国别报告"],
    "GRI 207-4-c": ["从略披露", "因商业保密限制从略披露", "国别报告"],
    "GRI 302-1-a": ["不可再生能源燃料消耗量", "不可再生能源消耗总量", "汽油", "柴油", "天然气"],
    "GRI 302-1-b": ["可再生燃料消耗", "可再生燃料"],
    "GRI 302-1-c": ["电力消耗总量", "办公用电总量", "绿色电力使用总量"],
    "GRI 302-1-d": ["售出的电力", "售出的热力", "售出的制冷", "售出的蒸汽"],
    "GRI 302-1-e": ["能源使用总量", "总能耗", "组织内部总能耗"],
    "GRI 302-1-f": ["能源数据标准", "计算方法", "假设", "换算因子"],
    "GRI 302-1-g": ["能源数据标准", "方法", "假设", "计算工具", "换算因子来源"],
    "GRI 302-2-a": ["组织外部能源消耗", "组织外部能耗"],
    "GRI 302-2-b": ["组织外部能源消耗", "组织外部能耗", "方法", "假设"],
    "GRI 302-2-c": ["组织外部能源消耗", "换算因子", "换算因子来源"],
    "GRI 302-3-a": ["能源强度", "强度比率"],
    "GRI 302-3-b": ["能源强度", "分母"],
    "GRI 302-3-c": ["能源强度", "包含能源类型"],
    "GRI 302-3-d": ["能源强度", "组织内外边界"],
    "GRI 302-4-a": ["节能改造", "节约用电", "节能措施促成节电量", "减少能源消耗"],
    "GRI 302-4-b": ["节电量", "减少能源消耗", "能源类型"],
    "GRI 302-4-c": ["节能量", "基准年", "基准"],
    "GRI 302-4-d": ["节能量", "计算方法", "假设", "工具"],
    "GRI 302-5-a": ["售出产品和服务", "能源需求降低量"],
    "GRI 302-5-b": ["售出产品和服务", "能源需求降低量", "基准"],
    "GRI 302-5-c": ["售出产品和服务", "能源需求降低量", "计算方法"],
    "GRI 303-1-a": ["水资源使用", "取水", "排水", "耗水", "水资源 KPI"],
    "GRI 303-1-b": ["WWF Water Risk Filter", "水资源风险评估", "水相关影响"],
    "GRI 303-1-c": ["废水分类处理", "废水分类收集", "回用", "节水", "循环水", "雨水替代", "逆流清洗"],
    "GRI 303-1-d": ["水资源目标", "行动路径", "水资源管理目标"],
    "GRI 303-2-a": ["废水分类收集", "分质处理", "排放水质", "法规限值"],
    "GRI 303-2-a-i": ["当地排放要求", "排放标准"],
    "GRI 303-2-a-ii": ["水资源管控标准", "水资源管理标准", "水资源政策"],
    "GRI 303-2-a-iii": ["行业特定排水标准", "排水标准"],
    "GRI 303-2-a-iv": ["受纳水体", "受纳水体特征"],
    "GRI 303-3-a": ["总取水量", "取水总量"],
    "GRI 303-3-a-i": ["地表水总量"],
    "GRI 303-3-a-ii": ["地下水总量"],
    "GRI 303-3-a-iii": ["海水取水", "海水总量"],
    "GRI 303-3-a-iv": ["采出水", "采出水总量"],
    "GRI 303-3-a-v": ["第三方取水总量"],
    "GRI 303-3-b": ["高水风险区域取水", "高风险区域运营地点", "取水占比"],
    "GRI 303-3-b-i": ["高水风险区域地表水"],
    "GRI 303-3-b-ii": ["高水风险区域地下水"],
    "GRI 303-3-b-iii": ["高水风险区域海水"],
    "GRI 303-3-b-iv": ["高水风险区域采出水"],
    "GRI 303-3-b-v": ["高水风险区域第三方水"],
    "GRI 303-3-c": ["第三方淡水总量", "第三方其他水总量"],
    "GRI 303-3-c-i": ["第三方淡水总量"],
    "GRI 303-3-c-ii": ["第三方其他水总量"],
    "GRI 303-3-d": ["取水数据编制方法", "取水数据标准", "取水计算方法"],
    "GRI 303-4-a": ["总排水量", "废水分类处理"],
    "GRI 303-4-a-i": ["地表水排水量"],
    "GRI 303-4-a-ii": ["地下水排水量"],
    "GRI 303-4-a-iii": ["海水排水量"],
    "GRI 303-4-a-iv": ["第三方水排水量"],
    "GRI 303-4-b": ["淡水排水量", "其他水排水量"],
    "GRI 303-4-b-i": ["淡水排水量"],
    "GRI 303-4-b-ii": ["其他水排水量"],
    "GRI 305-1-a": ["范围一", "直接温室气体排放", "Scope 1", "tCO2e"],
    "GRI 305-1-d": ["基准年", "基准年排放", "选择基准年的理由"],
    "GRI 305-1-d-i": ["基准年", "基准年排放"],
    "GRI 305-1-d-ii": ["选择基准年的理由", "基准年理由"],
    "GRI 305-1-d-iii": ["基准年重算", "重大变化"],
    "GRI 305-1-e": ["排放因子", "全球变暖潜势", "GWP", "温室气体核算方法"],
    "GRI 305-1-f": ["合并方法", "权益比例", "财务控制", "运营控制"],
    "GRI 305-1-g": ["温室气体核算方法", "核算标准", "GHG Protocol", "ISO 14064"],
    "GRI 305-2-a": ["范围二（基于位置）", "基于位置", "Scope 2", "location-based"],
    "GRI 305-2-b": ["范围二（基于市场）", "基于市场", "Scope 2", "market-based"],
    "GRI 305-2-c": ["温室气体种类", "气体种类", "CO2", "CH4", "N2O"],
    "GRI 305-2-d": ["基准年", "基准年排放", "选择基准年的理由"],
    "GRI 305-2-d-i": ["基准年", "基准年排放"],
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
