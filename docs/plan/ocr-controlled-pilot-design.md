# OCR 受控试点设计

## 0. 状态与决策

**设计状态：** 已批准方案方向，实施尚未开始。

**决策日期：** 2026-08-17。

**核心决策：** 对后端进行一次范围受控的 OCR 条件解冻，先解决 Envision PDF 第 77 页鉴证正文未提取的问题，同时补齐依赖 preflight、能力检查、安全错误和运行审计。OCR 默认保持关闭；VLM、Docling、PaddleOCR、后台队列和通用 ParserBackend 抽象继续延期。

本设计承接 `docs/plan/ocr-production-readiness-deferred-plan.md`。后者规定的触发条件已经部分满足：真实报告存在图片正文未提取，影响 4 个 GRI 2-5 独立判断项；但当前仍没有足够样本支持“通用扫描 PDF 生产就绪”的对外承诺。

## 1. 第一性原理与目标

ESG 核查的基础是“结论能够追溯到正确页面和可复核正文”。OCR 的价值需要通过新增有效证据证明，不能用 OCR 成功退出、文字长度增加或更高模型 confidence 代替。

本试点目标为：

1. 用户显式启用 OCR 时，系统只处理经过验证的目标页。
2. 缺少 OCRmyPDF、Ghostscript、Tesseract 或语言包时，分析前返回稳定、脱敏、可操作的错误。
3. Envision 第 77 页能够生成来源页正确的 OCR chunk，并保留人工复核标记。
4. 除 GRI 2-5 四项外，其余 495 个独立判断项不得产生规则、证据页、风险或适用性差异。
5. 原始 PDF 不覆盖、不转换、不移动；OCR 输出只进入派生目录。

本试点完成后只能表述为“受控 OCR 路由通过真实样本验收”。没有多报告、多语言和全扫描样本集时，不能表述为通用 OCR 生产能力。

## 2. 已确认数据

### 2.1 Envision

- 78 个 PDF 页，77 个 pdfplumber 文本 chunk。
- 页面级分类为 77 个 `digital_text`、1 个 `low_text_density + scanned`、6 个 `complex_table`。
- 当前自动 OCR 只会选择 PDF 第 78 页。
- PDF 第 77 页包含 3 个图片对象，pdfplumber 只提取 46 个字符，视觉内容为德勤独立有限鉴证报告正文。
- 第 77 页影响 `GRI 2-5-a`、`GRI 2-5-b-i`、`GRI 2-5-b-ii`、`GRI 2-5-b-iii`；4 条 evidence 均标记 `requires_ocr=true`、`image_body_not_extracted` 和 `assurance_page_text_too_short`。
- Envision profile 已将 PDF 第 77 页登记为 `assurance_pages[].requires_ocr=true`。

### 2.2 Goldwind

- 52 个 PDF 页，52 个 pdfplumber 文本 chunk。
- 1 个 `low_text_density + scanned` 页；鉴证页第 47、48 页分别提取 1925 和 2454 个字符。
- 499 个独立判断项中，没有 evidence 标记 `requires_ocr`、`requires_vlm` 或 `image_body_not_extracted`。

### 2.3 本机依赖

- OCRmyPDF 17.8.0 可通过项目虚拟环境运行。
- Tesseract 可用，`chi_sim`、`eng` 和 `osd` 语言包存在。
- Ghostscript 命令当前不可用。

上述事实支持小范围 OCR 试点，不支持直接接入 VLM，也不支持提前建设后台队列或通用解析器抽象。

## 3. 范围与非目标

### 3.1 本次范围

1. OCR 全局开关正式化。
2. OCRmyPDF、Ghostscript、Tesseract 和语言包 preflight。
3. 显式页、profile 要求页和低质量页的确定性选择。
4. 页码边界校验、执行超时、结构化异常和 stderr 脱敏。
5. 非阻断 OCR capability API。
6. run、stage 和 audit 的 OCR 选择、成功与失败记录。
7. Envision 第 77 页真实 OCR 对比和完整回归。

### 3.2 非目标

- 不默认启用 OCR。
- 不新增前端 OCR 开关或改变普通用户流程。
- 不接入 VLM、Docling 或 PaddleOCR。
- 不修改数据库结构、OpenAPI 业务结论字段或正式导出 schema。
- 不修改 `577/499/78/0`、GRI checklist、evidence contract、ontology、风险规则或人工复核优先级。
- 不修改 DeepSeek 模型、Prompt、候选筛选或三层权威顺序。
- 不引入 Celery、RQ、任务表、后台队列或新的 run 状态机。
- 不通过公司名、固定页码或正文关键词在通用代码中硬编码 Envision 行为。

Envision 第 77 页通过既有 profile 的结构化 `requires_ocr` 字段进入选择器；通用代码只处理 profile 契约。

## 4. 目标架构

### 4.1 全局开关

`OCR_ENABLED` 形成正式全局门禁：

- `OCR_ENABLED=false` 且请求 `enable_ocr=true`：API 在创建 run 前返回 `ocr_feature_disabled`。
- `OCR_ENABLED=true` 且请求 `enable_ocr=false`：完全保持当前 pdfplumber 默认链路，不运行 preflight。
- `OCR_ENABLED=true` 且请求 `enable_ocr=true`：先完成基础解析和目标页选择；只有目标页非空才运行 preflight 和 OCR。

默认配置继续为 `false`。实际验收只在隔离 demo 服务中临时设置为 `true`，不提交本机 `.env`。

### 4.2 目标页选择

选择优先级固定为：

1. 请求显式提供 `ocr_pages` 时，只使用显式页；去重、排序并校验 `1 <= page <= report.page_count`。
2. 未提供显式页时，先选择 report profile 中 `assurance_pages[].requires_ocr=true` 的页。
3. 在剩余预算内追加基础解析标记为 `low_text_density` 或 `scanned` 的页。
4. 总页数受 `OCR_MAX_PAGES` 限制，profile 页优先于普通低质量页。

页码为 0、负数或超过报告页数时，在 run 创建前返回稳定的请求错误，不把越界页静默丢弃。

该规则使 Envision 自动选择第 77、78 页；Goldwind只选择第 5 页。用户显式传入 `[77]` 时只处理 Envision 第 77 页，作为首个真实验收路径。

### 4.3 运行顺序

```text
analyze request
  -> OCR_ENABLED 与显式页边界校验
  -> pypdf + pdfplumber 基础解析
  -> 合并 profile 要求页与低质量页
  -> 目标页为空：记录 ocr_not_required，继续规则链路
  -> 目标页非空：OCR preflight
  -> OCRmyPDF --force-ocr 生成派生 PDF
  -> pdfplumber 从派生 PDF 读取目标页文字
  -> 原始 chunk + OCR chunk 进入既有 evidence assessment
  -> OCR evidence 强制 needs_manual_review
```

基础解析结果只存在内存中；最终只保存一次 page/chunk 集合，避免重复 document page 记录。

### 4.4 Preflight 与 capability

增加共享的只读 preflight 服务，依次检查：

- OCRmyPDF 命令可执行；
- Ghostscript 命令可执行；
- Tesseract 命令可执行；
- 请求语言中的全部语言包存在。

新增 `GET /api/capabilities/ocr`：

- 始终返回 HTTP 200；
- 返回 `enabled`、`available`、依赖状态码、OCR 语言和最大页数；
- 不返回可执行文件绝对路径、数据库 URL、环境变量值或原始 stderr；
- OCR 不可用不影响 `/api/health` 的存活状态。

capability 和 workflow 必须调用同一个 preflight 实现，避免两套判断口径。

### 4.5 执行与派生文件

- 继续使用参数数组和 `shell=False` 等价行为运行 OCRmyPDF。
- 使用 `--force-ocr`，保证已带少量文本层但主要正文为图片的第 77 页能够处理。
- 增加有限超时；超时或失败时删除本次未完成派生文件。
- 输出目录仍为 `derived/ocr/{report_id}/`，原始 PDF 哈希在运行前后必须一致。
- OCR chunk 使用 `source_method=ocr`、原始 PDF 页码和 `needs_manual_review`，不得伪装为原生数字文本。

## 5. 错误与审计契约

稳定错误码：

| 错误码 | 含义 |
|---|---|
| `ocr_feature_disabled` | 全局 OCR 开关关闭 |
| `ocr_page_out_of_range` | 请求页码不在报告范围内 |
| `ocrmypdf_missing` | OCRmyPDF 不可用 |
| `ghostscript_missing` | Ghostscript 不可用 |
| `tesseract_missing` | Tesseract 不可用 |
| `tesseract_language_missing` | 请求语言包不完整 |
| `ocr_execution_timeout` | OCR 超时 |
| `ocr_execution_failed` | OCRmyPDF 执行失败 |

对外 `error_message`、stage `error_summary` 和 audit 只保存错误码、安全中文说明、目标页数和已脱敏依赖状态。原始 stderr 可用于进程内诊断，但不得进入数据库、API 或文档。

新增或扩展审计事件：

- `ocr_pages_selected`：选择来源、目标页数和目标页列表；
- `ocr_preflight_completed`：available 与依赖状态码；
- `ocr_completed`：成功页数、每页文字长度、耗时和派生文件哈希；
- `analysis_failed`：复用现有事件，保存稳定 OCR 错误码。

审计中的页码是业务可复核信息，可以保留；本机路径和完整命令行必须移除。

## 6. 真实样本验收

### 6.1 隔离原则

- 新建 Envision report/run，不覆盖历史运行。
- 首轮使用 `confirm_llm=false`，隔离 OCR 与外部模型变量。
- 显式传入 `enable_ocr=true` 和 `ocr_pages=[77]`。
- 不执行 demo reset，不修改原始 PDF，不回填历史 assessment。

### 6.2 OCR 内容门禁

第 77 页 OCR 结果必须：

- 来源 PDF 页为 77；
- 文本长度显著高于当前 46 个字符；
- 至少识别“德勤”“独立有限鉴证报告”“鉴证结论”三个锚点中的两个；
- 不包含其他 PDF 页正文的明显串页内容；
- 生成 `source_method=ocr` 且带人工复核标记的 chunk/evidence。

锚点只用于样本验收，不进入通用解析或规则代码。

### 6.3 业务差异门禁

- `577/499/78/0` 保持不变。
- GRI 2-5 四项允许出现可解释的 evidence、rationale、verdict、risk 或 review status 差异，但最终仍进入人工复核。
- 其余 495 个独立判断项的 system verdict、evidence page、risk、applicability 和 missing items 差异必须为 0。
- 新增 false disclosed、wrong source page、global fallback、audit error 和 audit warning 必须为 0。
- 原始 Envision PDF SHA-256 前后相同。

没有独立 ESG 专家 gold，因此本试点不能宣称 GRI 2-5 的最终合规结论已经正确；只能证明正文恢复、来源页正确和结果变化受控。

## 7. 预计影响文件

### 后端

- `backend/src/config/settings.py`
- `backend/src/services/ocr.py`
- `backend/src/services/analysis_runner.py`
- `backend/src/workflows/single_report_workflow.py`
- `backend/src/api/routes/reports.py`
- `backend/src/api/routes/capabilities.py`（新增）
- `backend/src/main.py`
- 对应 services、workflow 和 API tests

### 文档

- `README.md`
- `docs/DESIGN.md`
- `docs/DEVELOPMENT.md`
- `docs/plan/ocr-production-readiness-deferred-plan.md`
- 新增 OCR 试点验收报告

### 明确不修改

- Alembic migration 和数据库模型
- GRI manifest、evidence contract、ontology 和 risk rules
- AI 模型、Prompt 和 suggestion schema
- 前端页面和生成 API 类型
- 正式 export schema

## 8. 验证策略

实施遵循测试先行：

1. preflight、页选择、越界和错误脱敏单元测试先进入 RED。
2. workflow 测试覆盖默认关闭、显式页、profile 页、低质量页、零目标页和 OCR 失败。
3. capability API 测试覆盖 available/unavailable、HTTP 200 和核心 health 不变。
4. 后端 OCR focused tests、全量 pytest 和 Ruff。
5. 前端无代码变化，但仍运行 test、typecheck 和 production build，确认 API 注册没有影响产品构建。
6. Envision v3 regeneration、真实 OCR 新 run、前后逐项差异和 audit。

真实 OCR、Ghostscript 安装或系统 PATH 修改必须在实施计划中作为独立执行门禁；安装前再次说明影响和回滚方式。

## 9. 风险与回滚

### 主要风险

1. OCRmyPDF 强制 OCR 可能降低原有少量文本层质量。
2. Ghostscript 安装和 PATH 配置具有系统级影响。
3. OCR chunk 进入规则链路后可能改变 GRI 2-5 结论或风险。
4. profile 自动页和低质量页合并可能增加耗时。

### 控制措施

- 默认 OCR 和全局开关均关闭。
- 首个真实 run 只显式处理第 77 页。
- 原始 PDF 只读保留，派生文件可删除重建。
- 495 项非目标差异为硬门禁。
- 任一安全门禁失败时，不继续扩大到自动 profile 页、Goldwind、VLM 或通用扫描样本。

### 回滚

代码回滚后，`enable_ocr=false` 主链路和历史运行不受影响；试点生成的 report/run 作为审计历史保留，派生 OCR 文件按明确目标单独清理。不得删除原始报告或历史业务记录。

## 10. 停止条件

出现任一情况立即停止实施并重新评估：

1. 必须新增数据库迁移、run 状态或 export 字段。
2. 必须接入 VLM、Docling、PaddleOCR 或后台队列才能完成第 77 页。
3. 除 GRI 2-5 外出现规则、证据页、风险或适用性差异。
4. 原始 PDF 哈希变化、OCR 错页或派生文件越界。
5. 安全错误泄露本机路径、命令行、stderr 或环境变量。
6. 全量 gates 或 Envision 安全门禁失败。

## 11. 宏观完成标准

完成本试点后，项目获得“显式授权、按页、可观测、可失败恢复”的 OCR 最小能力。是否扩展到通用扫描报告，继续由真实扫描样本数量、关键证据召回、错页率、耗时和人工复核负担决定；VLM 仍需独立证据和独立设计。
