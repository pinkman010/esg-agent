# 产品验收主流程体验修复实施计划

> **执行要求：** 实施时使用 `superpowers:executing-plans`，严格按测试驱动开发顺序执行。所有修改、数据库重置、服务重启、提交和推送均遵守项目授权规则；本计划不授权自动提交或 push。

**目标：** 修复远景2024中文ESG报告首次上传演示中暴露的metadata识别、内部ID展示、分析进度表达和完成态导航问题，使用户能够从上传自然进入分析结果与高风险复核。

**架构：** 后端新增纯本地metadata检测服务，从文件名和PDF前两页可提取文本识别企业名称、年度与语言；不调用外部模型、OCR或VLM。前端继续使用现有run和七阶段API，在纯函数中按业务阶段计算百分比，不显示577条计数；进度页读取报告详情用于业务标题，并在终态提供dashboard与review入口。

**技术栈：** FastAPI、Pydantic v2、pypdf、pytest、Next.js App Router、TypeScript、TanStack Query、Vitest、React Testing Library。

---

## 一、验收问题与目标行为

| 问题 | 当前行为 | 目标行为 | 严重程度 |
| --- | --- | --- | --- |
| 企业名称未识别 | `metadata_detected`没有`company_name`，用户手填 | 从PDF前两页识别“远景能源有限公司”并预填 | 高 |
| 语言识别失败 | 文件名`-zh`仍返回`language=null` | 识别为`zh-CN` | 中 |
| 内部report ID外露 | 进度页显示`报告 report-...` | 显示企业、年度和原文件名 | 中 |
| 577条计数造成误解 | 显示`X / 577条已生成结果` | 显示七阶段业务进度百分比和当前阶段 | 中 |
| 完成后没有结果入口 | 完成页没有下一步按钮 | 显示“查看分析结果”和“进入高风险复核” | 高 |

### 1.1 进度文案规则

```text
尚未取得run：正在读取进度...
pending：等待分析
running：分析进度 N% · 当前阶段：<业务阶段名称>
completed：分析完成
partially_completed：分析已完成，部分项目需要重跑
failed：分析未完成，请查看失败阶段
```

上传页和metadata确认页不显示577。进度页、dashboard普通文案也不使用“577条已生成结果”作为流程状态。后端仍保留`eligible_requirement_count=577`用于分析完整性、审计和回归门禁。

### 1.2 百分比定义

七个固定业务阶段按顺序参与计算：

```text
总体进度 = floor((已完成阶段数 + 当前阶段完成比例) / 7 * 100)
```

约束：

- `completed`阶段贡献1；
- 第一个`running`或`partially_failed`阶段使用`completed_units / total_units`，结果限制在0到1；
- 尚无阶段事件时为0%；
- run为`completed`时强制100%；
- run为`partially_completed`时强制100%，通过文案提示存在失败项；
- run为`failed`时保留失败前已完成比例，不显示100%；
- 该百分比表示业务流程进度，不表示预计剩余时间。

---

## 二、文件变更总览

| 文件 | 动作 | 职责 |
| --- | --- | --- |
| `backend/src/services/metadata_detection.py` | 新建 | 文件名、PDF页数、前两页文本的本地metadata检测 |
| `backend/src/api/routes/reports.py` | 修改 | 上传接口调用metadata检测服务，移除路由内简化检测函数 |
| `backend/tests/services/test_metadata_detection.py` | 新建 | 企业、年度、语言、无文本和损坏PDF测试 |
| `backend/tests/api/test_reports_api.py` | 修改 | 上传响应后验证报告详情的检测结果 |
| `frontend/components/analysis/progress-model.ts` | 新建 | 七阶段百分比和当前阶段纯函数 |
| `frontend/components/analysis/progress-model.test.ts` | 新建 | 0%、阶段中、终态和失败态边界测试 |
| `frontend/components/analysis/analysis-progress.tsx` | 修改 | 业务标题、百分比、终态文案和导航按钮 |
| `frontend/components/analysis/analysis-progress.test.tsx` | 修改 | 隐藏ID、百分比、完成/部分完成导航测试 |
| `frontend/components/reports/report-metadata-confirmation.test.tsx` | 修改 | 验证企业、年度、语言自动预填 |
| `docs/DESIGN.md` | 修改 | 明确metadata本地检测和百分比展示规则 |
| `docs/DEVELOPMENT.md` | 修改 | 更新人工验收路径和已知问题状态 |

本次不修改数据库schema，不新增Alembic migration，不删除`eligible_requirement_count`，不修改577回归口径。

---

## 三、任务1：本地metadata检测服务

**文件：**

- 新建：`backend/src/services/metadata_detection.py`
- 新建：`backend/tests/services/test_metadata_detection.py`

- [ ] **步骤1：写远景PDF文本识别失败测试**

测试使用内存PDF或mock `PdfReader`页面文本，输入包含：

```text
环境、社会及公司治理报告
远景能源有限公司
Envision Energy Co., Ltd.
2024 远景能源 ESG 报告
```

断言：

```python
assert result.page_count == 78
assert result.metadata["company_name"] == "远景能源有限公司"
assert result.metadata["report_year"] == 2024
assert result.metadata["language"] == "zh-CN"
```

- [ ] **步骤2：写文件名信号测试**

覆盖`Envision Energy 2024-zh.pdf`、`report-2023-en.pdf`和没有年份/语言后缀的文件名。`-zh`、`_zh`、`中文`映射为`zh-CN`；`-en`、`_en`映射为`en`。

- [ ] **步骤3：写降级测试**

损坏PDF返回`page_count=None`，仍保留文件名可识别字段；前两页没有可靠公司名称时不生成`company_name`，禁止猜测或补造企业名称。

- [ ] **步骤4：运行测试确认RED**

```powershell
cd backend
uv run --no-sync pytest tests/services/test_metadata_detection.py -q --basetemp=../tmp/pytest-metadata-red
```

预期：模块尚不存在或断言失败。

- [ ] **步骤5：实现最小检测服务**

公开接口：

```python
@dataclass(frozen=True)
class DetectedReportMetadata:
    page_count: int | None
    metadata: dict[str, object]

def detect_report_metadata(filename: str, content: bytes) -> DetectedReportMetadata:
    ...
```

实现要求：

- 单次构造`PdfReader`；
- 最多读取前两页文本；
- 中文企业名称只接受包含`有限公司`、`集团`、`公司`等组织后缀的完整行；
- 优先使用封面完整企业名称，文件名只作为年度和语言补充信号；
- 年份限制在1900至2100；
- 不读取固定PDF页码，不调用report profile，不硬编码“远景能源”结论；
- 解析失败时返回安全降级结果。

- [ ] **步骤6：运行测试确认GREEN**

```powershell
cd backend
uv run --no-sync pytest tests/services/test_metadata_detection.py -q --basetemp=../tmp/pytest-metadata-green
```

---

## 四、任务2：上传接口接入metadata检测

**文件：**

- 修改：`backend/src/api/routes/reports.py`
- 修改：`backend/tests/api/test_reports_api.py`
- 修改：`frontend/components/reports/report-metadata-confirmation.test.tsx`

- [ ] **步骤1：写API失败测试**

上传包含封面文本的PDF后请求`GET /api/reports/{report_id}`，断言`metadata_detected`包含`company_name`、`report_year`和`language`，但`company_name`正式字段在用户确认前仍为`null`。

- [ ] **步骤2：运行API测试确认RED**

```powershell
cd backend
uv run --no-sync pytest tests/api/test_reports_api.py -q --basetemp=../tmp/pytest-metadata-api-red
```

- [ ] **步骤3：替换路由内检测函数**

删除`reports.py`中的`_detect_metadata()`，改为：

```python
detected = detect_report_metadata(file.filename, content)
page_count = detected.page_count
metadata_detected = detected.metadata
```

上传响应契约保持不变，报告详情契约继续通过`metadata_detected`提供候选值。

- [ ] **步骤4：修正确认页预填优先级**

确认页使用：

```text
已确认正式字段
→ metadata_detected候选值
→ 空值或安全默认值
```

企业名称不能只读取`report.company_name`。语言默认值只在检测值为空时使用`zh-CN`，不得用空字符串覆盖有效候选值。

- [ ] **步骤5：运行后端和前端针对性测试**

```powershell
cd backend
uv run --no-sync pytest tests/services/test_metadata_detection.py tests/api/test_reports_api.py -q --basetemp=../tmp/pytest-metadata-api-green

cd ../frontend
pnpm test -- components/reports/report-metadata-confirmation.test.tsx
```

---

## 五、任务3：七阶段百分比纯函数

**文件：**

- 新建：`frontend/components/analysis/progress-model.ts`
- 新建：`frontend/components/analysis/progress-model.test.ts`

- [ ] **步骤1：写百分比边界失败测试**

至少覆盖：

```text
无阶段事件 → 0%
第1阶段完成 → 14%
前3阶段完成、第4阶段50% → 50%
completed run → 100%
partially_completed run → 100%
failed run且前2阶段完成 → 28%
total_units=0 → 当前阶段贡献0
completed_units超过total_units → 限制为100%
```

- [ ] **步骤2：写当前阶段失败测试**

纯函数返回当前第一个`running`、`partially_failed`或`failed`阶段代码；全部完成时返回`null`。

- [ ] **步骤3：运行测试确认RED**

```powershell
cd frontend
pnpm test -- components/analysis/progress-model.test.ts
```

- [ ] **步骤4：实现纯函数**

公开接口：

```typescript
export function calculateAnalysisProgress(
  runStatus: string | undefined,
  stages: AnalysisStageResponse[],
): { percent: number; currentStageCode: string | null }
```

函数只依赖七阶段状态和完成量，不读取`eligible_requirement_count`或`succeeded_requirement_count`。

- [ ] **步骤5：运行测试确认GREEN**

```powershell
cd frontend
pnpm test -- components/analysis/progress-model.test.ts
```

---

## 六、任务4：重构分析进度页展示

**文件：**

- 修改：`frontend/components/analysis/analysis-progress.tsx`
- 修改：`frontend/components/analysis/analysis-progress.test.tsx`

- [ ] **步骤1：写隐藏内部ID失败测试**

mock `GET /api/reports/{report_id}`返回：

```json
{
  "company_name": "远景能源有限公司",
  "report_year": 2024,
  "original_filename": "Envision Energy 2024-zh.pdf"
}
```

断言页面显示企业、年度和文件名，不显示`report-63850c3b21e74bdda722c61bc1848b44`。

- [ ] **步骤2：写进度文案失败测试**

running状态断言显示`分析进度 50%`和`当前阶段：GRI requirement匹配`；断言页面不存在`577`和`条已生成结果`。

- [ ] **步骤3：写完成态导航失败测试**

completed状态断言存在：

```text
查看分析结果 → /reports/{reportId}/dashboard
进入高风险复核 → /reports/{reportId}/review
```

partially_completed状态同时显示“查看分析结果”和“重跑N条失败项”。failed状态不显示结果完成文案。

- [ ] **步骤4：运行组件测试确认RED**

```powershell
cd frontend
pnpm test -- components/analysis/analysis-progress.test.tsx
```

- [ ] **步骤5：实现报告详情查询和业务标题**

复用`getReport(reportId)`，页面标题按以下优先级：

```text
company_name + report_year
→ original_filename
→ “ESG报告”
```

不在可见文本中回退到report ID。

- [ ] **步骤6：实现百分比和状态文案**

使用`calculateAnalysisProgress()`。保留七阶段明细；阶段右侧不显示内部英文状态，使用中文状态：等待中、进行中、已完成、部分失败、失败。

- [ ] **步骤7：实现终态按钮**

使用Next.js `Link`：

```tsx
<Link href={`/reports/${reportId}/dashboard`}>查看分析结果</Link>
<Link href={`/reports/${reportId}/review`}>进入高风险复核</Link>
```

- [ ] **步骤8：运行组件测试确认GREEN**

```powershell
cd frontend
pnpm test -- components/analysis/progress-model.test.ts components/analysis/analysis-progress.test.tsx
```

---

## 七、任务5：同步设计和验收文档

**文件：**

- 修改：`docs/DESIGN.md`
- 修改：`docs/DEVELOPMENT.md`

- [ ] **步骤1：更新metadata设计**

记录封面前两页本地文本检测、候选值人工确认和失败留空规则。明确不调用外部模型、OCR或VLM。

- [ ] **步骤2：更新进度设计**

记录七阶段等权业务进度公式、终态文案和“不表示预计剩余时间”的限制。

- [ ] **步骤3：更新人工验收路径**

增加检查项：

```text
企业名称/年度/语言自动预填
普通页面不显示内部report ID
进度页不显示577计数
完成页存在查看结果和高风险复核入口
```

- [ ] **步骤4：检查文档一致性**

```powershell
rg -n "577 / 577|条已生成结果|报告 \{reportId\}|metadata|分析进度" docs frontend/components
```

预期：旧体验文案只允许出现在历史记录或明确的反例说明中。

---

## 八、任务6：自动门禁与demo人工验收

- [ ] **步骤1：运行后端针对性测试**

```powershell
cd backend
uv run --no-sync pytest tests/services/test_metadata_detection.py tests/api/test_reports_api.py -q --basetemp=../tmp/pytest-product-ux-targeted
```

- [ ] **步骤2：运行后端全量测试**

```powershell
cd backend
uv run --no-sync pytest -q --basetemp=../tmp/pytest-product-ux-full
```

- [ ] **步骤3：运行前端门禁**

```powershell
cd frontend
pnpm typecheck
pnpm test
pnpm build
```

- [ ] **步骤4：运行Envision 577 gate**

按`docs/DEVELOPMENT.md`执行`regenerate_review_csv`。要求audit通过，verdict、review status和source page无非预期变化，外部模型、OCR和VLM均未调用。

- [ ] **步骤5：重置空demo环境**

该步骤会删除`esg_agent_demo`和`backend/data/runtime/demo/`中的演示数据，执行前再次确认目标环境：

```powershell
cd backend
uv run --no-sync python -m src.tools.reset_demo_environment --dry-run
uv run --no-sync python -m src.tools.reset_demo_environment --confirm-database esg_agent_demo
```

- [ ] **步骤6：使用普通浏览器人工验收**

```text
上传远景2024中文ESG报告
→ 企业名称自动预填“远景能源有限公司”
→ 年度自动预填2024
→ 语言自动预填中文
→ 启动分析
→ 页面只显示百分比和七阶段业务进度
→ 页面不显示内部report ID和577计数
→ 分析完成后点击“查看分析结果”进入dashboard
→ 点击“进入高风险复核”进入review工作台
```

- [ ] **步骤7：验收高风险表述边界**

确认“高风险复核已完成”没有表达为全部577条均已人工确认。发现问题时记录复现步骤、严重程度、影响范围、建议修复和验证结果。

---

## 九、完成标准

全部满足后才可报告完成：

1. 远景PDF首次上传自动检测企业名称、年度和语言；
2. 无可靠证据时metadata候选值保持空，不补造企业事实；
3. 普通页面不展示内部report ID；
4. 上传和确认阶段不显示577；
5. 进度页不显示`X / 577条已生成结果`；
6. 进度百分比只依赖七阶段数据并覆盖边界测试；
7. completed和partially_completed均可查看已有结果；
8. completed提供dashboard和高风险复核入口；
9. 数据库schema、577分析口径和旧兼容API保持不变；
10. 后端全量、前端typecheck/test/build和Envision 577 gate通过；
11. demo重置后完整人工流程通过；
12. 不自动提交或push。

## 十、回滚与限制

- metadata检测失败时回退为空候选值，由用户人工确认；
- 百分比采用七阶段等权模型，不能解释为时间估算；
- 已上传报告不会自动回填新metadata，必须重新上传或另做显式回填；
- 本次不清理现有demo数据，真实重置属于实施阶段的独立高风险步骤；
- 任何verdict或source page变化都视为停止条件，先调查后继续；
- 不使用`git reset --hard`、`git checkout --`或自动push处理失败。
