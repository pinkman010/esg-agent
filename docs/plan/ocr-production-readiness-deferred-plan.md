# OCR 生产就绪延期与条件解冻实施计划

> **For agentic workers:** 只有取得用户对后端条件解冻的明确批准后，才允许使用 `superpowers:executing-plans` 按任务执行。步骤使用复选框跟踪；本文件当前只记录延期决策，不授权代码修改、外部调用、安装系统依赖或提交。

**目标：** 保持 Envision v1.1 后端冻结和 `pypdf + pdfplumber` 正式默认链路，同时明确 OCR 从实验路由进入生产能力所需的触发条件、修改边界和验收门槛。

**架构：** OCR 继续作为请求显式启用、按页处理的派生链路。只有真实扫描 PDF 需求成立后才局部解冻；届时在实际选中 OCR 页之后、启动 OCRmyPDF 之前执行依赖检查，并以结构化安全错误写入 run、stage 和 audit。核心 `/api/health` 保持存活语义，OCR 可用性通过独立非阻断 capability 接口公开。

**技术栈：** Python 3.11、FastAPI、Pydantic v2、OCRmyPDF、Tesseract、Ghostscript、pypdf、pdfplumber、pytest。

**执行状态（2026-08-17）：** 单页受控试点已按 `docs/plan/ocr-controlled-pilot-implementation-plan.md` 完成并重新冻结。Envision 第 77 页真实 OCR、依赖 preflight、capability、错误脱敏和审计已通过；通用扫描 PDF 生产化、VLM、后台队列和 ParserBackend 大抽象继续延期。本文件后续任务只在新增真实扫描样本和再次批准解冻后执行。

---

## 1. 当前事实

- 正式默认链路为 `pypdf + pdfplumber`，当前 Envision 主报告能够完成数字文本解析。
- `enable_ocr=false` 时不进入 OCR；`enable_ocr=true` 支持显式 `ocr_pages`，未指定时只选择 `low_text_density` 或 `scanned` 页并受 `OCR_MAX_PAGES` 限制。
- OCR 输出写入派生目录，不覆盖原始 PDF；OCR chunk 使用 `source_method=ocr` 并携带 `needs_manual_review`。
- OCRmyPDF 17.8.0、Ghostscript CLI 10.07.1 和 Tesseract 5.5.0.20241111 已通过共享 preflight；Tesseract 可见 `chi_sim`、`eng`、`osd`。
- OCR capability、workflow 和 OCR runner 使用同一依赖口径；失败返回稳定错误码和脱敏摘要，不暴露路径、命令行或原始 stderr。
- `OCR_ENABLED` 已作为全局强制门禁；请求仍需显式 `enable_ocr=true`，页码和 `OCR_MAX_PAGES` 在创建 run 前校验。
- Envision 第 77 页真实试点生成 1 个 2,324 字符 OCR chunk，命中 2 个验收锚点；499 项仅 GRI 2-5 四项增加同页 OCR evidence，其余 495 项保护字段零差异。
- Docling 为接口预留，PaddleOCR 未接入，VLM 为字段或设计预留；没有扫描样本评测支持 ParserBackend 大抽象。
- 当前完整门禁为后端 822 项、Ruff、前端 39 个测试文件 149 项测试、typecheck、production build 和 Envision `577/499/78/0` 回归全部通过。

## 2. 延期理由

1. 当前产品主线没有扫描 PDF 交付要求，OCR 不阻塞单报告 ESG 分析闭环。
2. 默认链路已在本次单页试点后重新验证和冻结，继续扩大范围需要再次执行完整门禁。
3. 当前只有一个中文混合文本/图片报告的一页可复核样本，无法衡量完全扫描报告的证据召回、错页和人工复核量。
4. 单页 OCR 约 29 秒，只能证明同步受控执行可行，尚不足以决定 Docling、PaddleOCR、VLM 或后台队列架构。

## 3. 条件解冻触发门槛

满足以下任一条件后，才进入后端解冻审批：

- 实际报告存在扫描页，并造成关键 GRI 披露证据缺失；
- 产品验收或部署合同明确要求支持扫描 PDF；
- 已形成包含原始页、期望文字、关键表格或证据页标注的可复核扫描样本集；
- OCR 需要成为对外承诺能力，必须提供可用性检查、明确错误和运行审计。

进入审批时必须同时确认：

- OCR 支持的语言和操作系统；
- 单报告最大 OCR 页数与超时预算；
- `OCR_ENABLED` 的全局门禁语义；
- capability 接口是否进入前端运行提示；
- 扫描样本的验收指标和可接受误差。

## 4. 条件解冻允许范围

### 4.1 允许修改

- `backend/src/services/ocr.py`：依赖检查、结构化异常、超时和安全错误摘要。
- `backend/src/services/analysis_runner.py`：向 OCR runner 传递已确认的依赖与配置。
- `backend/src/workflows/single_report_workflow.py`：在实际选中 OCR 页时记录安全的失败 stage 和 audit。
- `backend/src/config/settings.py`：确定 `OCR_ENABLED` 的正式语义。
- `backend/src/api/routes/capabilities.py`：新增非阻断 OCR capability 接口。
- `backend/src/main.py`：注册 capability router，保持 `/api/health` 原响应和存活语义。
- `backend/tests/services/test_ocr.py`、`backend/tests/api/test_capabilities_api.py`、`backend/tests/api/test_reports_api.py`、`backend/tests/workflows/test_single_report_workflow.py`：覆盖依赖、默认关闭、自动选页和安全错误。
- `README.md`、`docs/DESIGN.md`、`docs/DEVELOPMENT.md`：在完成真实验收后更新生产能力状态。

### 4.2 禁止扩大

- 不修改 577/499/78/0、GRI checklist、evidence contract、ontology、风险规则或人工复核优先级。
- 不修改规则、AI、人工三层权威顺序。
- 不修改数据库结构、正式导出字段或结论口径。
- 不接入 Docling、PaddleOCR、VLM、Celery 或 RQ。
- 不覆盖、移动或转换原始报告。
- 不因 OCR capability 不可用而使 `/api/health` 返回失败。

## 5. 未来执行任务

### Task 1：建立解冻前基线

**文件：**

- 读取：`backend/src/services/ocr.py`
- 读取：`backend/src/services/document_parser.py`
- 读取：`backend/src/workflows/single_report_workflow.py`
- 读取：`backend/src/api/routes/reports.py`

- [ ] **Step 1：确认工作区和冻结提交**

  运行 `git status --short --branch` 和 `git rev-parse HEAD`；预期工作区无未分类改动，并记录待解冻提交。

- [ ] **Step 2：执行当前 OCR 目标基线**

  运行：

  ```powershell
  cd backend
  uv run pytest tests/services/test_ocr.py tests/api/test_reports_api.py tests/workflows/test_single_report_workflow.py -q
  ```

  预期：现有目标测试全部通过。

- [ ] **Step 3：执行后端全量基线**

  运行：

  ```powershell
  cd backend
  uv run pytest -q
  ```

  预期：测试数量与当时 `pytest --collect-only -q` 一致，失败数为 0；记录新增或减少的测试原因。

### Task 2：先写 OCR preflight 失败测试

**文件：**

- 修改：`backend/tests/services/test_ocr.py`
- 修改：`backend/tests/workflows/test_single_report_workflow.py`

- [ ] **Step 1：覆盖四类依赖结果**

  增加测试，分别断言 OCRmyPDF 缺失、Ghostscript 缺失、Tesseract 缺失、请求语言包缺失时返回稳定错误码；全部可用时返回 available。

- [ ] **Step 2：覆盖调用边界**

  增加测试，断言 `enable_ocr=false` 不运行 preflight；`enable_ocr=true` 但未选中 OCR 页时不运行 preflight；显式页或自动选中的低质量页才运行 preflight。

- [ ] **Step 3：验证测试先失败**

  运行：

  ```powershell
  cd backend
  uv run pytest tests/services/test_ocr.py tests/workflows/test_single_report_workflow.py -q
  ```

  预期：新测试因 preflight 和结构化错误尚未实现而失败，原测试保持通过。

### Task 3：实现最小 preflight 与安全错误

**文件：**

- 修改：`backend/src/services/ocr.py`
- 修改：`backend/src/services/analysis_runner.py`
- 修改：`backend/src/config/settings.py`

- [ ] **Step 1：增加只读依赖检查**

  检查配置的 OCRmyPDF、Tesseract、请求语言包和 Windows/Linux Ghostscript 命令；所有子进程使用参数数组、`shell=False` 等价行为、有限超时和受控环境变量。

- [ ] **Step 2：增加稳定错误契约**

  错误码固定为 `ocrmypdf_missing`、`ghostscript_missing`、`tesseract_missing`、`tesseract_language_missing`、`ocr_execution_failed`。对外消息不包含绝对路径，长度受限；原始 stderr 不进入 API、run 或 audit。

- [ ] **Step 3：确定双重开关**

  `OCR_ENABLED=false` 时拒绝请求级 OCR 并返回 `ocr_feature_disabled`；`OCR_ENABLED=true` 且请求 `enable_ocr=true` 时才允许在选中页后运行 preflight。该语义必须同步 OpenAPI 和运行文档。

- [ ] **Step 4：运行服务测试**

  运行：

  ```powershell
  cd backend
  uv run pytest tests/services/test_ocr.py tests/workflows/test_single_report_workflow.py -q
  ```

  预期：新增和既有服务测试全部通过。

### Task 4：增加失败审计和非阻断 capability

**文件：**

- 新建：`backend/src/api/routes/capabilities.py`
- 修改：`backend/src/main.py`
- 修改：`backend/src/workflows/single_report_workflow.py`
- 新建：`backend/tests/api/test_capabilities_api.py`
- 修改：`backend/tests/api/test_reports_api.py`

- [ ] **Step 1：增加 capability API 测试**

  断言 OCR 可用时返回 `available`；缺少 Ghostscript 时仍返回 HTTP 200，并提供稳定 dependency code；响应不包含绝对路径。

- [ ] **Step 2：保持核心 health 契约**

  断言 `/api/health` 继续返回 `{"status":"ok"}`，OCR 缺失不改变其状态码或响应。

- [ ] **Step 3：增加失败审计测试**

  断言 OCR preflight 失败后 run 为 failed，`pdf_parsing` 或 `result_summary` 记录安全摘要，audit 包含错误码和目标页数，不包含原始 stderr、报告路径或派生目录。

- [ ] **Step 4：实现 capability 与审计**

  capability 调用同一只读 preflight；workflow 只保存结构化安全字段，不改变 `enable_ocr=false` 路径。

- [ ] **Step 5：运行 API 与 workflow 测试**

  运行：

  ```powershell
  cd backend
  uv run pytest tests/api/test_capabilities_api.py tests/api/test_reports_api.py tests/workflows/test_single_report_workflow.py -q
  ```

  预期：新增和既有测试全部通过。

### Task 5：真实扫描样本与回归验收

**文件：**

- 只读输入：经批准的扫描 PDF 样本
- 输出：`tmp/ocr/`
- 修改：`README.md`
- 修改：`docs/DESIGN.md`
- 修改：`docs/DEVELOPMENT.md`

- [ ] **Step 1：运行真实 OCR**

  对批准样本显式启用 OCR，记录目标页、耗时、退出状态、OCR 文字长度和派生文件哈希；原始 PDF 哈希前后必须一致。

- [ ] **Step 2：执行页级质量对比**

  对每个样本比较预期关键文字或表格锚点、来源页码、空页率和人工复核标记；任何错页、原文件变化或越界页均阻断生产就绪。

- [ ] **Step 3：执行完整自动门禁**

  运行：

  ```powershell
  cd backend
  uv run pytest -q
  ```

  随后执行当时冻结文档指定的 Envision v3 regression 和 audit；预期新增 false disclosed、wrong source page、global fallback、audit error 和 audit warning 均为 0。

- [ ] **Step 4：重新冻结**

  在主文档记录依赖版本、样本范围、完整测试结果、回归结果、已知限制和新冻结提交。只有全部门禁通过后，才允许把 OCR 状态从“实验性”改为“生产就绪”。

## 6. 当前停止点

- OCR 受控试点后端重新冻结。
- Ghostscript、真实单页 OCR 和 capability API 已完成；不继续扩展为通用扫描 PDF 生产能力。
- 保留 `enable_ocr=false` 的正式产品运行方式。
- 收集至少两类真实扫描报告、页级 gold 和运行指标；再次满足第 3 节触发条件后重新审批。
