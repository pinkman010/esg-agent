# esg-agent 从零重建实施计划

> 状态：历史计划。当前技术设计以 docs/DESIGN.md 为准；本文件仅保留早期规划记录，后续实施计划需要基于 docs/DESIGN.md 重新生成。

## 1. 项目结论

本计划从零新建一个前后端一体仓库 `esg-agent`，原 `envision` 和现有 `esg-dashboard` 仅作为资产来源，不删除、不覆盖、不回退。

新系统采用功能型智能体架构：第一版实现披露分析智能体 `DisclosureAgent`，标准能力通过适配器接入。当前只接入 `GRIAdapter`，后续扩展 ISSB、ESRS 时新增标准适配器；后续做同行对标时新增 `BenchmarkAgent`。

## 2. 已确认技术选型

### 2.1 仓库与目录

- 新仓库名：`esg-agent`
- 新仓库路径：`.`
- 单仓结构：前后端在同一个仓库
- 后端目录：`backend`
- 前端目录：`frontend`
- 文档目录：`docs`
- 原仓库处理：`../envision` 保留，只作为后端资产来源
- 现有前端处理：`../esg-dashboard` 保留，只作为前端参考来源

### 2.2 后端技术栈

- 语言：Python 3.11
- Web 框架：FastAPI
- 服务运行：Uvicorn
- 数据校验：Pydantic v2
- 配置管理：`.env` + `pydantic-settings`
- 数据库：SQLite
- 测试：pytest
- PDF 解析：`pypdf` 为基础解析器，`pdfplumber` 为可选增强解析器
- 模型调用：OpenAI-compatible SDK
- 包管理：`pyproject.toml` + `pip install -e ".[dev]"`

### 2.3 前端技术栈

- 框架：Next.js
- 语言：TypeScript
- 样式：Tailwind CSS
- 组件：shadcn/ui
- 图标：lucide-react
- 表格：TanStack Table
- 图表：Recharts
- API 调用：`fetch` 封装在 `frontend/lib/api.ts`
- 第一版登录：不做

### 2.4 智能体架构

- 第一版智能体：`DisclosureAgent`
- 中文名：披露分析智能体
- 当前标准适配器：`GRIAdapter`
- 后续标准适配器：`ISSBAdapter`、`ESRSAdapter`
- 后续功能型智能体：`BenchmarkAgent`

架构原则：

```text
功能用 Agent 表达
标准用 Adapter 表达
工具用 Tool 表达
确定性业务能力用 Service 表达
```

第一版能力：

```text
DisclosureAgent
  -> GRIAdapter
  -> RetrievalTool
  -> EvidenceTool
  -> JudgmentTool
  -> GuardrailTool
```

后续扩展形态：

```text
DisclosureAgent
  -> GRIAdapter
  -> ISSBAdapter
  -> ESRSAdapter

BenchmarkAgent
  -> PeerCorpusService
  -> MetricCompareTool
  -> DisclosureCompareTool
```

## 3. 目标仓库结构

```text
esg-agent/
  README.md
  .gitignore
  .env.example

  backend/
    pyproject.toml
    .env.example
    src/
      main.py

      config/
        settings.py
        paths.py

      domain/
        enums.py
        models.py

      standards/
        base.py
        gri.py

      agents/
        base.py
        disclosure_agent.py

      workflows/
        single_report_workflow.py

      services/
        document_parser.py
        requirement_context.py
        recommendation.py
        review_store.py
        export_service.py
        audit_log.py

      tools/
        retrieval.py
        evidence.py
        judgment.py
        guardrails.py

      api/
        router.py
        health.py
        reports.py
        runs.py
        review.py
        exports.py

    tests/
      test_document_parser.py
      test_gri_adapter.py
      test_disclosure_agent.py
      test_single_report_workflow.py
      test_review_store.py
      test_api_reports.py
      test_api_review.py

    data/
      reports/
      standards/
        gri/
      manifests/
      runtime/
        uploads/
        sqlite/
        exports/

  frontend/
    package.json
    next.config.ts
    tsconfig.json
    tailwind.config.ts
    app/
      page.tsx
      reports/page.tsx
      runs/[runId]/page.tsx
      review/page.tsx
      audit/page.tsx
    components/
      layout/
      upload/
      analysis/
      evidence/
      review/
    lib/
      api.ts
      types.ts
      utils.ts

  docs/
    architecture.md
    user-guide.md
    dev-log.md
```

## 4. 第一版产品闭环

用户流程：

```text
上传 PDF
  -> 后端保存报告
  -> 用户确认是否调用外部模型
  -> 后端解析报告
  -> GRIAdapter 构建条款任务
  -> DisclosureAgent 逐条分析
  -> 生成条款判断和建议
  -> 前端展示条款结果
  -> 用户人工复核
  -> 导出 CSV/JSON
```

第一版不做：

- 登录权限
- 多公司批量处理
- 同行对标
- 舆情监测
- 历史 SQLite 数据迁移
- PDF 原文内嵌预览
- 多标准混合分析

## 5. 后端领域模型

### 5.1 核心对象

```text
Report
AnalysisRun
StandardProfile
DisclosureRequirement
DisclosureTask
Evidence
RequirementCheck
DisclosureAssessment
Recommendation
ReviewDecision
AuditEvent
```

### 5.2 关键枚举

```text
AssessmentVerdict:
  disclosed
  partially_disclosed
  not_disclosed
  not_applicable
  manual_review

RequirementSupportStatus:
  met
  partially_met
  not_met
  not_applicable_claimed
  manual_review

ReviewStatus:
  pending
  approved
  rejected
  needs_revision
```

### 5.3 追溯字段

每条披露判断必须保留：

- `run_id`
- `report_id`
- `standard_id`
- `standard_version`
- `disclosure_id`
- `requirement_id`
- `evidence_id`
- `source_text`
- `source_page`
- `source_file_hash`
- `model_called`
- `review_status`

## 6. 标准适配器设计

### 6.1 `StandardAdapter` 接口

职责：

- 读取标准资料和 manifest
- 生成披露任务
- 提供条款要求
- 提供判断口径
- 标准化输出字段

接口草案：

```python
class StandardAdapter(Protocol):
    standard_code: str

    def load_profile(self) -> StandardProfile:
        ...

    def build_tasks(self, report_context: ReportContext) -> list[DisclosureTask]:
        ...

    def requirement_text(self, task: DisclosureTask) -> str:
        ...

    def verdict_policy(self, task: DisclosureTask) -> dict:
        ...
```

### 6.2 `GRIAdapter`

第一版实现：

- 读取 GRI manifest
- 读取 GRI requirement checklist
- 读取报告证据索引
- 构建 GRI 披露任务
- 输出 GRI 条款级 `DisclosureTask`

后续扩展：

- `ISSBAdapter`
- `ESRSAdapter`

## 7. 智能体设计

### 7.1 `DisclosureAgent`

职责：

- 接收单个 `DisclosureTask`
- 调用检索工具获取候选证据
- 调用证据工具标准化证据
- 调用判断工具生成披露判断
- 调用护栏工具修正或转人工复核
- 输出 `DisclosureAssessment`

输入：

```python
DisclosureAgentInput(
    run_id="...",
    report_id="...",
    standard_code="GRI",
    task=DisclosureTask(...),
    confirm_llm=False,
)
```

输出：

```python
DisclosureAssessment(...)
```

### 7.2 `BenchmarkAgent`

第一版不实现，仅预留架构说明。

未来职责：

- 对比本公司与同行披露覆盖度
- 对比指标披露完整性
- 识别披露深度差距
- 生成同行对标建议

## 8. 后端 API 设计

API 前缀：

```text
/api
```

接口：

```text
GET  /api/health

POST /api/reports/upload
POST /api/reports/{report_id}/analyze

GET  /api/runs
GET  /api/runs/{run_id}
GET  /api/runs/{run_id}/assessments
GET  /api/runs/{run_id}/recommendations

GET  /api/review/runs
GET  /api/review/runs/{run_id}/assessments
POST /api/review/runs/{run_id}/decisions

GET  /api/exports/runs/{run_id}/assessments.csv
GET  /api/exports/runs/{run_id}/review.csv
GET  /api/exports/runs/{run_id}/assessments.json
GET  /api/exports/runs/{run_id}/review.json
```

上传和分析分开：

- 上传接口只保存文件并返回 `report_id`
- 分析接口显式触发工作流
- 模型调用由 `confirm_llm` 控制

## 9. 前端页面设计

### 9.1 首页

路径：

```text
/
```

展示：

- 系统定位
- 最近运行记录
- 快速入口
- 合规提示

### 9.2 报告上传与分析

路径：

```text
/reports
```

功能：

- 上传 PDF
- 显示上传状态
- 选择是否授权模型调用
- 启动分析
- 跳转到分析结果

### 9.3 分析结果页

路径：

```text
/runs/[runId]
```

功能：

- 运行摘要
- 条款判断表格
- 证据详情面板
- 缺口和建议
- 复核入口

### 9.4 人工复核页

路径：

```text
/review
```

功能：

- 按 run 查看待复核条款
- 筛选结论、标准、复核状态、关键词
- 保存人工复核记录
- 查看已保存复核记录

### 9.5 审计页

路径：

```text
/audit
```

功能：

- 运行事件
- 模型调用状态
- 文件哈希
- 错误信息

## 10. 资产迁移清单

### 10.1 从 `envision` 复制

复制到新仓库：

```text
backend/data/reports/Envision Energy 2024-zh.pdf
backend/data/standards/gri/
backend/data/manifests/
backend/src/prompts/
```

建议迁移的 prompt：

```text
analyst_prompt.j2
advisor_prompt.j2
```

不复制：

```text
旧 src/agent/
旧 Streamlit 页面
历史运行目录
归档脚本
旧 SQLite 数据
旧分阶段测试
旧日志
```

### 10.2 从 `esg-dashboard` 参考

只参考 UI 视觉和交互，不直接整体复制。

可复用：

- 颜色方案
- 表格布局经验
- 卡片样式经验
- 页面信息架构

不复用：

- 静态假数据
- 与真实后端无关的页面状态
- 无数据来源的指标展示

## 11. 实施阶段

### 阶段 1：初始化仓库

目标：

- 创建 `.`
- 初始化 Git
- 创建 `backend/ frontend/ docs/`
- 写入根 README、`.gitignore`、`.env.example`

验证：

```powershell
git status
```

### 阶段 2：后端骨架

目标：

- 创建 FastAPI 应用
- 创建 `/api/health`
- 创建 settings 和 paths
- 配置 pytest

验证：

```powershell
cd backend
python -m pytest -q
python -m uvicorn src.main:app --reload
```

### 阶段 3：领域模型

目标：

- 实现 enums
- 实现核心 Pydantic 模型
- 写模型校验测试

验证：

```powershell
python -m pytest tests/test_domain_models.py -q
```

### 阶段 4：资产迁移

目标：

- 复制必要知识库和 manifest
- 生成 source manifest
- 校验文件存在和哈希

验证：

```powershell
python -m pytest tests/test_assets.py -q
```

### 阶段 5：标准适配器

目标：

- 实现 `StandardAdapter`
- 实现 `GRIAdapter`
- 生成 GRI 披露任务

验证：

```powershell
python -m pytest tests/test_gri_adapter.py -q
```

### 阶段 6：披露分析智能体

目标：

- 实现 `DisclosureAgent`
- 实现 retrieval/evidence/judgment/guardrails tools
- 无模型模式自动进入人工复核
- 授权模型时调用模型判断

验证：

```powershell
python -m pytest tests/test_disclosure_agent.py -q
```

### 阶段 7：工作流

目标：

- 实现 `SingleReportWorkflow`
- 上传报告后生成 run
- 顺序执行条款任务
- 汇总 assessments 和 recommendations

验证：

```powershell
python -m pytest tests/test_single_report_workflow.py -q
```

### 阶段 8：复核和导出

目标：

- 实现 `ReviewStore`
- 实现复核 API
- 实现 CSV/JSON 导出

验证：

```powershell
python -m pytest tests/test_review_store.py tests/test_api_review.py -q
```

### 阶段 9：前端骨架

目标：

- 初始化 Next.js
- 配置 Tailwind
- 安装 shadcn/ui
- 创建基础布局

验证：

```powershell
cd frontend
npm run lint
npm run build
```

### 阶段 10：前端业务页

目标：

- 首页
- 报告上传页
- 运行结果页
- 人工复核页
- 审计页

验证：

```powershell
npm run build
```

### 阶段 11：端到端验证

目标：

- 启动后端
- 启动前端
- 上传远景能源 2024 PDF
- 触发无模型分析
- 展示条款结果
- 保存人工复核
- 导出结果

验收：

```text
后端 pytest 全部通过
前端 build 通过
上传和分析链路通过
复核保存链路通过
导出链路通过
```

## 12. 风险与控制

### 风险一：标准条款数据迁移不完整

控制：

- 对 manifest 做存在性校验
- 对关键文件做 sha256 校验
- 不用静态演示数据替代真实来源

### 风险二：PDF 解析页码不准确

控制：

- `pypdf` 做基础文本提取
- `pdfplumber` 做可选增强
- 页码无法确认时进入人工复核

### 风险三：模型输出不可控

控制：

- 默认不调用外部模型
- `confirm_llm=true` 才允许调用
- 所有模型输出必须过 Pydantic 校验
- 校验失败进入人工复核

### 风险四：前端展示静态假数据

控制：

- 前端所有核心指标来自 API
- 空状态明确显示暂无数据
- 不展示无来源的准确率或完成率

### 风险五：功能和标准维度混淆

控制：

- Agent 按功能命名
- 标准按 Adapter 命名
- 第一版只实现 `DisclosureAgent + GRIAdapter`

## 13. 验收标准

- 新仓库结构清晰，前后端在一个仓库内。
- 后端不依赖旧 `envision` 代码运行。
- 前端不依赖旧 `esg-dashboard` 静态数据运行。
- `DisclosureAgent` 能输出合法 `DisclosureAssessment`。
- `GRIAdapter` 能生成 GRI 披露任务。
- 无模型模式能完成端到端分析并进入人工复核。
- 人工复核记录能保存和导出。
- 后端测试通过。
- 前端 build 通过。
- 原仓库和旧前端仓库未被删除或覆盖。



