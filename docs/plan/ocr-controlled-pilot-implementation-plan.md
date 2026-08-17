# OCR 受控试点实施计划

> **执行要求：** 实施时使用 `superpowers:executing-plans`，按任务顺序执行并通过复核点；步骤使用复选框（`- [ ]`）跟踪。

**目标：** 在保持 OCR 默认关闭和正式结论边界不变的前提下，完成可检查依赖、可按页选择、可安全失败、可审计的 OCR 受控试点，并用 Envision PDF 第 77 页验证图片鉴证正文能否恢复。

**架构：** 请求先经过 `OCR_ENABLED` 和显式页边界门禁，再执行基础 PDF 解析；页选择器按“显式页、profile `requires_ocr` 页、低质量页”优先级产生有限目标页。目标页非空时，共享 preflight 检查 OCRmyPDF、Ghostscript、Tesseract 和语言包，OCRmyPDF 只生成派生 PDF，OCR chunk 进入既有规则链路并强制人工复核；capability API、workflow 和审计复用同一依赖口径。

**技术栈：** Python 3.11、FastAPI、Pydantic v2、SQLAlchemy、OCRmyPDF 17.8.0、Tesseract、Ghostscript、pypdf、pdfplumber、pytest、Ruff、Next.js、Vitest、pnpm。

---

## 0. 执行状态与授权边界

**计划状态：** 设计已批准；代码、Ghostscript 安装和真实 OCR 尚未执行。

**执行方式：** 在当前 `main` 连续执行，按四个代码提交工作包和一个验收文档提交拆分，完成后统一汇报；不自动 push。用户批准执行本计划时，需要同时明确批准 Ghostscript 系统包安装。没有该批准时，只允许完成安装前的代码与 fake 测试，并在 Task 8 前停止。

**冻结保护区：** 数据库 schema、Alembic、GRI `577/499/78/0`、规则与 ontology、风险规则、人工 snapshot、AI 模型与 Prompt、前端产品流程和正式导出 schema。

## 1. 文件职责与预计差异

### 新增文件

- `backend/src/services/ocr_errors.py`：稳定错误码、安全中文消息和 OCR 异常类型。
- `backend/src/services/ocr_capability.py`：共享、只读的 OCR 依赖检查。
- `backend/src/services/ocr_page_selector.py`：显式页、profile 页和低质量页的纯函数选择器。
- `backend/src/api/routes/capabilities.py`：非阻断 OCR capability API。
- `backend/tests/services/test_ocr_capability.py`：依赖和脱敏契约测试。
- `backend/tests/services/test_ocr_page_selector.py`：页优先级、上限和边界测试。
- `backend/tests/api/test_capabilities_api.py`：capability 与 health 契约测试。
- `docs/product/ocr-controlled-pilot-acceptance.md`：真实试点验收报告。

### 修改文件

- `backend/src/config/settings.py`：增加 Ghostscript 命令和 OCR 超时配置，正式化现有 `OCR_ENABLED`。
- `backend/src/services/ocr.py`：超时、结构化错误、派生哈希和安全环境。
- `backend/src/services/document_parser.py`：将派生哈希写入 OCR chunk metadata。
- `backend/src/services/analysis_runner.py`：注入 preflight、selector 所需设置和 runner 参数。
- `backend/src/workflows/single_report_workflow.py`：基础解析、目标页选择、preflight、OCR 二次解析和审计。
- `backend/src/api/routes/reports.py`：run 创建前的 OCR 开关、页码和页数上限校验。
- `backend/src/api/schemas.py`：OCR capability response。
- `backend/src/main.py`：注册 capability router，保持 health 行为。
- `backend/tests/services/test_ocr.py`、`backend/tests/workflows/test_single_report_workflow.py`、`backend/tests/api/test_reports_api.py`、`backend/tests/services/test_analysis_runner.py`、`backend/tests/test_settings.py`：相应回归。
- `README.md`、`docs/DESIGN.md`、`docs/DEVELOPMENT.md`、`docs/plan/ocr-production-readiness-deferred-plan.md`：验收后更新能力状态和限制。

### 禁止修改

- `backend/src/db/models.py` 和所有 migration。
- `backend/src/standards/`、GRI manifest 和报告 profile 内容。
- `backend/src/services/ai_assessment_service.py`、LLM client 和 Prompt。
- `frontend/` 产品代码。
- export schema、review snapshot 和 risk rule。

---

## Task 1：冻结实施前基线

**Files:**

- Read: `docs/plan/ocr-controlled-pilot-design.md`
- Read: `backend/src/services/ocr.py`
- Read: `backend/src/services/document_parser.py`
- Read: `backend/src/workflows/single_report_workflow.py`
- Read: `backend/src/api/routes/reports.py`

- [ ] **Step 1：确认 Git 和提交边界**

```powershell
git status --short --branch
git log -8 --oneline
git rev-parse HEAD
```

Expected：工作区无未分类改动；起点包含设计提交 `3383163`；本地 ahead 状态只记录、不 push。

- [ ] **Step 2：记录 PDF 与依赖只读基线**

```powershell
Get-FileHash -Algorithm SHA256 "backend/data/reports/Envision Energy 2024-zh.pdf"
Set-Location backend
uv run --no-sync ocrmypdf --version
$tesseractCommand = if ($env:TESSERACT_CMD) { $env:TESSERACT_CMD } else { (Get-Command tesseract -ErrorAction Stop).Source }
& $tesseractCommand --list-langs
Get-Command gs,gswin64c,gswin32c -ErrorAction SilentlyContinue
```

Expected：OCRmyPDF 为 17.8.0；`chi_sim`、`eng` 可用；Ghostscript 当前不可用；不得打印密钥、数据库 URL 或本机用户目录。

- [ ] **Step 3：运行安装前 focused baseline**

```powershell
Set-Location backend
uv run --no-sync pytest `
  tests/services/test_ocr.py `
  tests/workflows/test_single_report_workflow.py `
  tests/api/test_reports_api.py `
  tests/services/test_analysis_runner.py `
  tests/test_settings.py `
  -q `
  --basetemp ../tmp/pytest-ocr-pilot-baseline
```

Expected：PASS，不产生真实 OCR 或外部模型调用。若基线失败，停止并先区分已有缺陷。

- [ ] **Step 4：记录全量测试发现范围**

```powershell
Set-Location backend
uv run --no-sync pytest --collect-only -q
uv run --no-sync pytest -q --basetemp ../tmp/pytest-ocr-pilot-full-baseline
uv run --no-sync ruff check src tests
```

Expected：测试数不少于当前记录的 792，pytest 与 Ruff 通过。该步骤只建立解冻前证据，不安装系统依赖。

---

## Task 2：用失败测试固定错误与 preflight 契约

**Files:**

- Create: `backend/src/services/ocr_errors.py`
- Create: `backend/src/services/ocr_capability.py`
- Create: `backend/tests/services/test_ocr_capability.py`
- Modify: `backend/src/config/settings.py`
- Modify: `backend/tests/test_settings.py`

- [ ] **Step 1：先写 settings 失败测试**

在 `backend/tests/test_settings.py` 增加：

```python
def test_ocr_defaults_remain_disabled_and_bounded():
    settings = Settings(_env_file=None)

    assert settings.ocr_enabled is False
    assert settings.ocr_lang == "chi_sim+eng"
    assert settings.ocr_max_pages == 5
    assert settings.ocr_timeout_seconds == 300
    assert settings.ghostscript_cmd == ""


def test_ocr_timeout_rejects_out_of_range_values():
    with pytest.raises(ValueError):
        Settings(_env_file=None, ocr_timeout_seconds=0)
    with pytest.raises(ValueError):
        Settings(_env_file=None, ocr_timeout_seconds=1801)
```

- [ ] **Step 2：写 preflight 参数化失败测试**

`backend/tests/services/test_ocr_capability.py` 至少包含：

```python
@pytest.mark.parametrize(
    ("missing_command", "expected_code"),
    [
        ("ocrmypdf", "ocrmypdf_missing"),
        ("ghostscript", "ghostscript_missing"),
        ("tesseract", "tesseract_missing"),
    ],
)
def test_inspect_ocr_capability_reports_each_missing_dependency(
    monkeypatch, missing_command, expected_code
):
    install_fake_commands(monkeypatch, missing=missing_command)

    result = inspect_ocr_capability(make_settings(ocr_enabled=True))

    assert result.enabled is True
    assert result.available is False
    assert expected_code in result.dependency_codes


def test_inspect_ocr_capability_reports_missing_requested_language(monkeypatch):
    install_fake_commands(monkeypatch, languages="eng\nosd\n")

    result = inspect_ocr_capability(make_settings(ocr_enabled=True))

    assert result.available is False
    assert result.dependency_codes == ("tesseract_language_missing",)


def test_require_ocr_capability_raises_only_safe_message(monkeypatch):
    install_fake_commands(
        monkeypatch,
        missing="ghostscript",
        diagnostic="[private-path] secret-token",
    )

    with pytest.raises(OcrPreflightError) as exc_info:
        require_ocr_capability(make_settings(ocr_enabled=True))

    assert exc_info.value.code == "ghostscript_missing"
    assert "Ghostscript" in str(exc_info.value)
    assert "private-path" not in str(exc_info.value)
    assert "secret-token" not in str(exc_info.value)
```

测试 helper 必须 monkeypatch `shutil.which` 和 `subprocess.run`，不访问本机真实命令。

- [ ] **Step 3：运行测试确认 RED**

```powershell
Set-Location backend
uv run --no-sync pytest `
  tests/test_settings.py `
  tests/services/test_ocr_capability.py `
  -q `
  --basetemp ../tmp/pytest-ocr-preflight-red
```

Expected：因 `ocr_timeout_seconds`、`ghostscript_cmd`、`ocr_errors` 和 `ocr_capability` 尚不存在而失败。

- [ ] **Step 4：实现稳定错误类型**

`backend/src/services/ocr_errors.py` 固定公开接口：

```python
OCR_ERROR_MESSAGES = {
    "ocr_feature_disabled": "OCR 功能当前未启用。",
    "ocr_page_out_of_range": "OCR 页码超出报告范围。",
    "ocr_page_limit_exceeded": "OCR 页数超过单报告处理上限。",
    "ocrmypdf_missing": "OCRmyPDF 不可用。",
    "ghostscript_missing": "Ghostscript 不可用。",
    "tesseract_missing": "Tesseract 不可用。",
    "tesseract_language_missing": "OCR 所需语言包不完整。",
    "ocr_execution_timeout": "OCR 执行超时。",
    "ocr_execution_failed": "OCR 执行失败。",
}


class OcrError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(OCR_ERROR_MESSAGES[code])


class OcrPreflightError(OcrError):
    pass


class OcrExecutionError(OcrError):
    pass
```

异常字符串只能来自固定消息表，不能拼接路径、命令行、stdout 或 stderr。

- [ ] **Step 5：实现只读 capability**

`backend/src/services/ocr_capability.py` 的公开类型固定为：

```python
@dataclass(frozen=True)
class OcrCapability:
    enabled: bool
    available: bool
    dependency_codes: tuple[str, ...]
    language: str
    max_pages: int
```

公开函数签名固定为 `inspect_ocr_capability(settings: Settings) -> OcrCapability` 和 `require_ocr_capability(settings: Settings) -> OcrCapability`。前者依次检查功能开关、OCRmyPDF、Ghostscript、Tesseract 和请求语言包并返回全部固定错误码；后者在功能未启用或存在依赖错误码时抛出 `OcrPreflightError`，否则返回 capability。

实现约束：

- 配置为绝对文件时检查该文件；配置为命令名时使用 `shutil.which`。
- Ghostscript 未显式配置时按 `gswin64c`、`gswin32c`、`gs` 顺序查找。
- 可执行文件存在后用参数数组执行 `--version`；Tesseract 用 `--list-langs`。
- 所有检查 `timeout=10`、`check=False`、不使用 shell。
- `dependency_codes` 按 OCRmyPDF、Ghostscript、Tesseract、语言包顺序稳定输出。
- `available = settings.ocr_enabled and not dependency_codes`。

- [ ] **Step 6：扩展 settings**

在 `Settings` 中增加：

```python
ghostscript_cmd: str = ""
ocr_timeout_seconds: int = Field(default=300, ge=1, le=1800)
```

保留 `ocr_enabled=False`、`ocr_max_pages=5` 和现有 OCR 默认值。

- [ ] **Step 7：运行 GREEN 与 Ruff**

```powershell
Set-Location backend
uv run --no-sync pytest `
  tests/test_settings.py `
  tests/services/test_ocr_capability.py `
  -q `
  --basetemp ../tmp/pytest-ocr-preflight-green
uv run --no-sync ruff check `
  src/config/settings.py `
  src/services/ocr_errors.py `
  src/services/ocr_capability.py `
  tests/test_settings.py `
  tests/services/test_ocr_capability.py
```

Expected：PASS，测试不调用真实依赖。

- [ ] **Step 8：提交 preflight 工作包**

```powershell
git add -- `
  backend/src/config/settings.py `
  backend/src/services/ocr_errors.py `
  backend/src/services/ocr_capability.py `
  backend/tests/test_settings.py `
  backend/tests/services/test_ocr_capability.py
git commit -m "feat: add OCR dependency preflight"
```

---

## Task 3：约束 OCR 执行、超时和派生哈希

**Files:**

- Modify: `backend/src/services/ocr.py`
- Modify: `backend/src/services/document_parser.py`
- Modify: `backend/tests/services/test_ocr.py`
- Modify: `backend/tests/services/test_document_parser.py`

- [ ] **Step 1：先写 timeout、失败脱敏和哈希测试**

扩展 `backend/tests/services/test_ocr.py`：

```python
def test_run_ocr_for_pages_uses_timeout_and_returns_derived_hash(monkeypatch, tmp_path):
    completed = install_successful_fake_ocr(monkeypatch, tmp_path, text="德勤 鉴证结论")

    results = run_ocr_for_pages(
        tmp_path / "report.pdf",
        [77],
        report_id="report-1",
        derived_dir=tmp_path / "derived",
        ocrmypdf_cmd="ocrmypdf",
        ghostscript_cmd="gswin64c",
        tesseract_cmd="tesseract",
        timeout_seconds=300,
    )

    assert completed["timeout"] == 300
    assert results[0].page_number == 77
    assert len(results[0].derived_file_sha256) == 64


def test_run_ocr_for_pages_timeout_removes_partial_output(monkeypatch, tmp_path):
    install_timeout_fake(monkeypatch, tmp_path)

    with pytest.raises(OcrExecutionError) as exc_info:
        run_ocr_for_pages(
            tmp_path / "report.pdf",
            [77],
            report_id="report-1",
            derived_dir=tmp_path / "derived",
            ocrmypdf_cmd="ocrmypdf",
            ghostscript_cmd="gswin64c",
            tesseract_cmd="tesseract",
            ocr_lang="chi_sim+eng",
            timeout_seconds=300,
        )

    assert exc_info.value.code == "ocr_execution_timeout"
    assert not list((tmp_path / "derived").rglob("*.pdf"))


def test_run_ocr_for_pages_failure_does_not_expose_stderr(monkeypatch, tmp_path):
    install_failed_fake(monkeypatch, stderr="[private-path] token=abc")

    with pytest.raises(OcrExecutionError) as exc_info:
        run_ocr_for_pages(
            tmp_path / "report.pdf",
            [77],
            report_id="report-1",
            derived_dir=tmp_path / "derived",
            ocrmypdf_cmd="ocrmypdf",
            ghostscript_cmd="gswin64c",
            tesseract_cmd="tesseract",
            ocr_lang="chi_sim+eng",
            timeout_seconds=300,
        )

    assert exc_info.value.code == "ocr_execution_failed"
    assert str(exc_info.value) == "OCR 执行失败。"
    assert "secret" not in str(exc_info.value)
```

- [ ] **Step 2：先写 parser metadata 失败测试**

在 `backend/tests/services/test_document_parser.py` 增加 fake `OcrResult`：

```python
OcrResult(
    page_number=2,
    text="德勤 独立有限鉴证报告 鉴证结论",
    derived_file_sha256="a" * 64,
)
```

断言 OCR chunk：

```python
assert ocr_chunk.source_method is EvidenceSourceMethod.OCR
assert ocr_chunk.quality_flags == [PageQualityFlag.NEEDS_MANUAL_REVIEW]
assert ocr_chunk.metadata == {
    "ocr_page": 2,
    "derived_file_sha256": "a" * 64,
    "ocr_text_length": len("德勤 独立有限鉴证报告 鉴证结论"),
}
```

- [ ] **Step 3：运行测试确认 RED**

```powershell
Set-Location backend
uv run --no-sync pytest `
  tests/services/test_ocr.py `
  tests/services/test_document_parser.py `
  -q `
  --basetemp ../tmp/pytest-ocr-execution-red
```

Expected：缺少新参数、结构化错误和派生哈希导致失败。

- [ ] **Step 4：实现受控 runner**

`OcrResult` 改为：

```python
@dataclass(frozen=True)
class OcrResult:
    page_number: int
    text: str
    derived_file_sha256: str
```

`run_ocr_for_pages()` 增加：

```python
ghostscript_cmd: str = ""
timeout_seconds: int = 300
```

并实现：

```python
try:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        env=_subprocess_env(tesseract_cmd, ghostscript_cmd),
        timeout=timeout_seconds,
    )
except subprocess.TimeoutExpired as exc:
    output_path.unlink(missing_ok=True)
    raise OcrExecutionError("ocr_execution_timeout") from exc

if completed.returncode != 0:
    output_path.unlink(missing_ok=True)
    raise OcrExecutionError("ocr_execution_failed")

derived_hash = sha256(output_path.read_bytes()).hexdigest()
```

不得把 `completed.stderr` 或 `completed.stdout` 写入异常。

- [ ] **Step 5：扩展子进程环境与 parser metadata**

`_subprocess_env()` 同时接受 Tesseract 和 Ghostscript 配置，只把各命令父目录前置到子进程 PATH，不修改系统 PATH。`DocumentParser` 将 `derived_file_sha256` 和 `ocr_text_length` 写入 OCR chunk metadata，不把派生绝对路径写入数据库。

- [ ] **Step 6：运行 GREEN 与 Ruff**

```powershell
Set-Location backend
uv run --no-sync pytest `
  tests/services/test_ocr.py `
  tests/services/test_document_parser.py `
  -q `
  --basetemp ../tmp/pytest-ocr-execution-green
uv run --no-sync ruff check `
  src/services/ocr.py `
  src/services/document_parser.py `
  tests/services/test_ocr.py `
  tests/services/test_document_parser.py
```

- [ ] **Step 7：提交 runner 工作包**

```powershell
git add -- `
  backend/src/services/ocr.py `
  backend/src/services/document_parser.py `
  backend/tests/services/test_ocr.py `
  backend/tests/services/test_document_parser.py
git commit -m "fix: bound and audit OCR execution"
```

---

## Task 4：实现确定性 OCR 页选择器

**Files:**

- Create: `backend/src/services/ocr_page_selector.py`
- Create: `backend/tests/services/test_ocr_page_selector.py`
- Modify: `backend/src/services/ocr_errors.py`

- [ ] **Step 1：写优先级和边界失败测试**

`backend/tests/services/test_ocr_page_selector.py` 覆盖：

```python
def test_explicit_pages_override_profile_and_quality_pages():
    selection = select_ocr_pages(
        explicit_pages=[77, 77],
        parsed_pages=[page(78, "low_text_density", "scanned")],
        report_profile=profile_with_required_ocr_page(77),
        page_count=78,
        max_pages=5,
    )

    assert selection.pages == (77,)
    assert selection.sources == ((77, "explicit"),)


def test_automatic_selection_prioritizes_profile_then_page_quality():
    selection = select_ocr_pages(
        explicit_pages=[],
        parsed_pages=[page(78, "low_text_density", "scanned")],
        report_profile=profile_with_required_ocr_page(77),
        page_count=78,
        max_pages=5,
    )

    assert selection.pages == (77, 78)
    assert selection.sources == ((77, "profile_requires_ocr"), (78, "page_quality"))


@pytest.mark.parametrize("pages", [[0], [-1], [79]])
def test_explicit_page_out_of_range_is_rejected(pages):
    with pytest.raises(OcrPageSelectionError) as exc_info:
        select_ocr_pages(
            explicit_pages=pages,
            parsed_pages=[],
            report_profile=None,
            page_count=78,
            max_pages=5,
        )
    assert exc_info.value.code == "ocr_page_out_of_range"


def test_explicit_page_limit_is_rejected():
    with pytest.raises(OcrPageSelectionError) as exc_info:
        select_ocr_pages(
            explicit_pages=[1, 2, 3, 4, 5, 6],
            parsed_pages=[],
            report_profile=None,
            page_count=78,
            max_pages=5,
        )
    assert exc_info.value.code == "ocr_page_limit_exceeded"
```

- [ ] **Step 2：运行测试确认 RED**

```powershell
Set-Location backend
uv run --no-sync pytest `
  tests/services/test_ocr_page_selector.py `
  -q `
  --basetemp ../tmp/pytest-ocr-selector-red
```

Expected：模块不存在。

- [ ] **Step 3：实现纯函数接口**

`backend/src/services/ocr_page_selector.py`：

```python
@dataclass(frozen=True)
class OcrPageSelection:
    pages: tuple[int, ...]
    sources: tuple[tuple[int, str], ...]


class OcrPageSelectionError(OcrError):
    pass
```

纯函数签名固定为 `select_ocr_pages(*, explicit_pages: list[int] | None, parsed_pages: list[PageExtraction], report_profile: ReportProfile | None, page_count: int, max_pages: int) -> OcrPageSelection`。

实现顺序：

1. 显式页存在时去重排序，验证范围和上限，直接返回。
2. 收集 profile 中 `requires_ocr=true` 的 assurance 页，验证范围。
3. 追加带 `LOW_TEXT_DENSITY` 或 `SCANNED` 的解析页。
4. 按 profile、页质量顺序去重，截取 `max_pages`。
5. 不根据公司名、固定页码、正文关键词或 requirement ID 做选择。

- [ ] **Step 4：运行 GREEN 与 Ruff**

```powershell
Set-Location backend
uv run --no-sync pytest tests/services/test_ocr_page_selector.py -q `
  --basetemp ../tmp/pytest-ocr-selector-green
uv run --no-sync ruff check `
  src/services/ocr_errors.py `
  src/services/ocr_page_selector.py `
  tests/services/test_ocr_page_selector.py
```

---

## Task 5：正式化 API 门禁与 capability

**Files:**

- Create: `backend/src/api/routes/capabilities.py`
- Create: `backend/tests/api/test_capabilities_api.py`
- Modify: `backend/src/api/schemas.py`
- Modify: `backend/src/api/routes/reports.py`
- Modify: `backend/src/main.py`
- Modify: `backend/tests/api/test_reports_api.py`

- [ ] **Step 1：写 capability API 失败测试**

```python
async def test_ocr_capability_is_non_blocking_and_safe(api_client, monkeypatch):
    monkeypatch.setattr(
        "src.api.routes.capabilities.inspect_ocr_capability",
        lambda settings: OcrCapability(
            enabled=True,
            available=False,
            dependency_codes=("ghostscript_missing",),
            language="chi_sim+eng",
            max_pages=5,
        ),
    )

    response = await api_client.get("/api/capabilities/ocr")

    assert response.status_code == 200
    assert response.json() == {
        "enabled": True,
        "available": False,
        "dependency_codes": ["ghostscript_missing"],
        "language": "chi_sim+eng",
        "max_pages": 5,
    }
    assert ":\\" not in response.text


async def test_core_health_remains_ok_when_ocr_is_unavailable(api_client):
    response = await api_client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

- [ ] **Step 2：写 analyze 门禁失败测试**

在 `test_reports_api.py` 增加：

```python
async def test_analyze_rejects_ocr_when_global_feature_is_disabled(api_client, api_session):
    report_id = await ready_report(api_client)
    get_settings().ocr_enabled = False

    response = await api_client.post(
        f"/api/reports/{report_id}/analyze",
        json={"confirm_llm": False, "enable_ocr": True, "ocr_pages": [1]},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ocr_feature_disabled"
    assert Repository(api_session).list_runs() == []


@pytest.mark.parametrize("ocr_pages", [[0], [-1], [2]])
async def test_analyze_rejects_out_of_range_ocr_pages_before_run(
    api_client, api_session, ocr_pages
):
    report_id = await ready_one_page_report(api_client)
    get_settings().ocr_enabled = True

    response = await api_client.post(
        f"/api/reports/{report_id}/analyze",
        json={"confirm_llm": False, "enable_ocr": True, "ocr_pages": ocr_pages},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "ocr_page_out_of_range"
    assert Repository(api_session).list_runs() == []
```

另增加 6 个唯一显式页触发 `ocr_page_limit_exceeded` 的测试。每个测试恢复 `get_settings().ocr_enabled`，避免污染其他 API 用例。

- [ ] **Step 3：运行测试确认 RED**

```powershell
Set-Location backend
uv run --no-sync pytest `
  tests/api/test_capabilities_api.py `
  tests/api/test_reports_api.py `
  -q `
  --basetemp ../tmp/pytest-ocr-api-red
```

- [ ] **Step 4：增加 response schema 与 router**

`backend/src/api/schemas.py`：

```python
class OcrCapabilityResponse(BaseModel):
    enabled: bool
    available: bool
    dependency_codes: list[str]
    language: str
    max_pages: int
```

`backend/src/api/routes/capabilities.py`：

```python
router = APIRouter(prefix="/api/capabilities", tags=["capabilities"])


@router.get("/ocr", response_model=OcrCapabilityResponse)
def ocr_capability() -> OcrCapabilityResponse:
    capability = inspect_ocr_capability(get_settings())
    return OcrCapabilityResponse(
        enabled=capability.enabled,
        available=capability.available,
        dependency_codes=list(capability.dependency_codes),
        language=capability.language,
        max_pages=capability.max_pages,
    )
```

在 `main.py` 注册 router；不得让 `/api/health` 调用 preflight。

- [ ] **Step 5：实现 run 创建前门禁**

`AnalyzeRequest.ocr_pages` 改用 `Field(default_factory=list)`。在 `analyze_report()` 读取 report 后、检查 active run 和创建 run 前执行：

```python
settings = get_settings()
if request.enable_ocr and not settings.ocr_enabled:
    raise HTTPException(
        status_code=409,
        detail={
            "code": "ocr_feature_disabled",
            "message": OCR_ERROR_MESSAGES["ocr_feature_disabled"],
        },
    )

if request.enable_ocr:
    unique_pages = sorted(set(request.ocr_pages))
    if any(page < 1 or report.page_count is None or page > report.page_count for page in unique_pages):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "ocr_page_out_of_range",
                "message": OCR_ERROR_MESSAGES["ocr_page_out_of_range"],
            },
        )
    if len(unique_pages) > settings.ocr_max_pages:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "ocr_page_limit_exceeded",
                "message": OCR_ERROR_MESSAGES["ocr_page_limit_exceeded"],
                "max_pages": settings.ocr_max_pages,
            },
        )
```

`enable_ocr=false` 的行为完全保持；不因 capability 不可用阻止普通分析。

- [ ] **Step 6：运行 GREEN、OpenAPI 和 Ruff**

```powershell
Set-Location backend
uv run --no-sync pytest `
  tests/api/test_capabilities_api.py `
  tests/api/test_reports_api.py `
  -q `
  --basetemp ../tmp/pytest-ocr-api-green
uv run --no-sync ruff check `
  src/api/routes/capabilities.py `
  src/api/routes/reports.py `
  src/api/schemas.py `
  src/main.py `
  tests/api/test_capabilities_api.py `
  tests/api/test_reports_api.py
```

再用测试 app 的 OpenAPI 断言 `/api/capabilities/ocr` 存在，`/api/health` schema 未改变。

- [ ] **Step 7：提交 selector 与 API 工作包**

```powershell
git add -- `
  backend/src/services/ocr_errors.py `
  backend/src/services/ocr_page_selector.py `
  backend/src/api/routes/capabilities.py `
  backend/src/api/routes/reports.py `
  backend/src/api/schemas.py `
  backend/src/main.py `
  backend/tests/services/test_ocr_page_selector.py `
  backend/tests/api/test_capabilities_api.py `
  backend/tests/api/test_reports_api.py
git commit -m "feat: gate and expose OCR capability"
```

---

## Task 6：接入 workflow、runner 和安全审计

**Files:**

- Modify: `backend/src/services/analysis_runner.py`
- Modify: `backend/src/workflows/single_report_workflow.py`
- Modify: `backend/tests/services/test_analysis_runner.py`
- Modify: `backend/tests/workflows/test_single_report_workflow.py`

- [ ] **Step 1：更新既有调用顺序测试并确认 RED**

将显式 OCR 用例预期从一次 OCR parse 改为基础解析加 OCR 二次解析：

```python
assert parser.calls == [None, [77]]
```

保留以下不变量：

```python
assert default_parser.calls == [None]
assert low_quality_parser.calls == [None, [2]]
```

增加 fake preflight 调用计数：默认关闭和零目标页为 0，目标页非空为 1。

- [ ] **Step 2：写 profile 选择、成功审计和失败审计测试**

```python
def test_workflow_selects_profile_required_ocr_page_before_low_quality_page(
    repo_session, tmp_path
):
    profile_path = write_profile(
        tmp_path,
        assurance_pages=[{"pdf_page": 77, "requires_ocr": True}],
        total_pdf_pages=78,
    )
    parser = ProfileAndLowQualityParser(low_quality_page=78)
    preflight_calls = []
    workflow = SingleReportWorkflow(
        Repository(repo_session),
        parser,
        FakeAdapter(),
        DisclosureAgent(),
        report_profile_path=profile_path,
        ocr_max_pages=5,
        ocr_preflight=lambda: preflight_calls.append(True) or available_capability(),
    )

    run = workflow.run(
        "report-1",
        Path("report.pdf"),
        "hash-1",
        confirm_llm=False,
        enable_ocr=True,
        ocr_pages=[],
    )

    assert run.status is RunStatus.COMPLETED
    assert parser.calls == [None, [77, 78]]
    assert preflight_calls == [True]
    assert audit_event("ocr_pages_selected").event_payload["pages"] == [77, 78]
    assert audit_event("ocr_completed").event_payload["ocr_page_count"] == 2


def test_workflow_persists_safe_preflight_failure(repo_session):
    workflow = workflow_with_preflight_error("ghostscript_missing")

    run = workflow.run(
        "report-1",
        Path("report.pdf"),
        "hash-1",
        confirm_llm=False,
        enable_ocr=True,
        ocr_pages=[77],
    )

    assert run.status is RunStatus.FAILED
    assert run.failure_summary["error_code"] == "ghostscript_missing"
    assert run.error_message == "Ghostscript 不可用。"
    assert "stderr" not in str(audit_event("analysis_failed").event_payload)
```

增加 `ocr_completed` payload 断言：只包含页码、每页文字长度、耗时、派生 SHA-256，不含路径、正文或命令行。

- [ ] **Step 3：运行 workflow 测试确认 RED**

```powershell
Set-Location backend
uv run --no-sync pytest `
  tests/workflows/test_single_report_workflow.py `
  tests/services/test_analysis_runner.py `
  -q `
  --basetemp ../tmp/pytest-ocr-workflow-red
```

- [ ] **Step 4：注入 runner 参数与 preflight**

`analysis_runner.py` 的 OCR closure 传递：

```python
ghostscript_cmd=settings.ghostscript_cmd,
timeout_seconds=settings.ocr_timeout_seconds,
```

并向 workflow 传入：

```python
ocr_preflight=lambda: require_ocr_capability(settings),
```

`enable_ocr=false` 时不得调用 closure。

- [ ] **Step 5：重排 workflow 的解析顺序**

固定流程：

```python
parsed = self.parser.parse_pdf(
    pdf_path,
    report_id=report_id,
    source_file_hash=source_file_hash,
    ocr_pages=None,
)
if enable_ocr:
    selection = select_ocr_pages(
        explicit_pages=ocr_pages,
        parsed_pages=parsed.pages,
        report_profile=self.report_profile,
        page_count=parsed.page_count,
        max_pages=self.ocr_max_pages,
    )
    self._audit_ocr_selection(run_id, selection)
    if selection.pages:
        capability = self.ocr_preflight()
        self._audit_ocr_preflight(run_id, capability)
        started = perf_counter()
        parsed = self.parser.parse_pdf(
            pdf_path,
            report_id=report_id,
            source_file_hash=source_file_hash,
            ocr_pages=list(selection.pages),
        )
        self._audit_ocr_completed(run_id, parsed, perf_counter() - started)
```

`ocr_preflight` 未配置但有目标页时抛出安全 `ocr_feature_disabled`，不能继续 OCR。

- [ ] **Step 6：让 failure_summary 保留 OCR code**

workflow 顶层异常处理改用：

```python
error_code = getattr(exc, "code", "analysis_execution_failed")
```

异常字符串来自固定 `OcrError` 消息；已有 `UnsupportedScannedPdfError.code` 继续兼容。不得扩大其他异常的 API 语义。

- [ ] **Step 7：扩展 parse_completed 与 OCR audit**

`parse_completed` 增加白名单字段：

```text
ocr_enabled
ocr_page_count
ocr_pages
```

`ocr_completed` 的每页统计从 OCR chunk metadata 读取，只保存：

```text
page_number
text_length
derived_file_sha256
```

不保存 OCR 正文。

- [ ] **Step 8：运行纵向 GREEN 与 Ruff**

```powershell
Set-Location backend
uv run --no-sync pytest `
  tests/services/test_ocr.py `
  tests/services/test_ocr_capability.py `
  tests/services/test_ocr_page_selector.py `
  tests/services/test_document_parser.py `
  tests/services/test_analysis_runner.py `
  tests/workflows/test_single_report_workflow.py `
  tests/api/test_capabilities_api.py `
  tests/api/test_reports_api.py `
  -q `
  --basetemp ../tmp/pytest-ocr-pilot-focused
uv run --no-sync ruff check src tests
```

Expected：全部 fake 测试通过，真实 OCR 调用仍为 0。

- [ ] **Step 9：提交 workflow 工作包**

```powershell
git add -- `
  backend/src/services/analysis_runner.py `
  backend/src/workflows/single_report_workflow.py `
  backend/tests/services/test_analysis_runner.py `
  backend/tests/workflows/test_single_report_workflow.py
git commit -m "feat: route selected OCR pages with audit"
```

---

## Task 7：安装前代码门禁与范围审计

- [ ] **Step 1：运行后端全量与 Ruff**

```powershell
Set-Location backend
uv run --no-sync pytest -q --basetemp ../tmp/pytest-ocr-pilot-preinstall-full
uv run --no-sync ruff check src tests
```

Expected：测试数量不少于 Task 1 发现范围，0 failure、0 Ruff error。

- [ ] **Step 2：运行前端保护门禁**

```powershell
Set-Location frontend
pnpm lint
pnpm test -- --run
pnpm typecheck
pnpm build
```

Expected：0 lint error；测试数量不少于当前 39 个文件、149 项；typecheck 和 production build 通过。前端 diff 必须为空。

- [ ] **Step 3：执行静态保护区审计**

```powershell
git diff 3383163..HEAD --name-only
git diff 3383163..HEAD --check
rg -n "OCR_ENABLED|enable_ocr|ocr_pages|assess_explicit_candidates\(" backend/src
```

Expected：没有 migration、数据库模型、standards、AI、frontend 或 export schema 差异；`confirm_llm=True` 没有进入产品路径；密钥未进入 diff。

任何门禁失败均在 Ghostscript 安装前停止。

---

## Task 8：Ghostscript 系统依赖门禁

**系统影响：** 该任务会通过 Chocolatey 安装 Ghostscript 10.7.1，并可能增加系统级程序目录和 PATH/shim。卸载命令为 `choco uninstall ghostscript -y`。执行本任务前必须具有用户对本计划和系统安装的明确批准。

- [ ] **Step 1：重新确认包和安装前状态**

```powershell
choco search ghostscript --exact --limit-output
choco info ghostscript --version=10.7.1 --limit-output
Get-Command gs,gswin64c,gswin32c -ErrorAction SilentlyContinue
```

Expected：包版本 10.7.1 可用，安装前 Ghostscript 命令不存在。若版本或来源发生变化，停止并重新报告，不自动改装其他包。

- [ ] **Step 2：安装 Ghostscript**

```powershell
choco install ghostscript --version=10.7.1 -y
```

Expected：Chocolatey 成功退出。不得同时安装其他 OCR、PDF 或图像工具。

- [ ] **Step 3：刷新当前会话并验证命令**

```powershell
$env:PATH = [Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [Environment]::GetEnvironmentVariable("PATH", "User")
Get-Command gswin64c,gs -ErrorAction SilentlyContinue
gswin64c --version
```

Expected：至少一个 Ghostscript CLI 可用且版本为 10.7.1。

- [ ] **Step 4：运行真实只读 preflight**

在 `backend` 目录使用隔离设置实例调用 `inspect_ocr_capability()`，设置：

```text
OCR_ENABLED=true
OCRMYPDF_CMD=ocrmypdf
GHOSTSCRIPT_CMD=gswin64c
TESSERACT_CMD=<已配置 Tesseract 命令>
OCR_LANG=chi_sim+eng
```

Expected：`enabled=true`、`available=true`、`dependency_codes=[]`；输出不含绝对路径。

安装失败、版本不符或 preflight 不可用时，执行卸载回滚并停止：

```powershell
choco uninstall ghostscript -y
```

---

## Task 9：执行 Envision 第 77 页真实 OCR 试点

**Inputs:**

- Read-only: `backend/data/reports/Envision Energy 2024-zh.pdf`
- Baseline run: `run-debd7c6af0ed494bbb6c8b5f73d99188`
- Output: demo runtime 派生目录和新 report/run

- [ ] **Step 1：记录原始哈希和 baseline**

```powershell
Get-FileHash -Algorithm SHA256 "backend/data/reports/Envision Energy 2024-zh.pdf"
```

通过 API 重新读取 baseline run，确认 499 assessment、`577/499/78/0`、失败 0、AI 调用 0，并保存终端输出。不得修改 baseline。

- [ ] **Step 2：启动隔离 OCR demo 后端**

在独立终端或统一 exec session 中设置 demo 数据库和 demo runtime，额外设置：

```powershell
$env:OCR_ENABLED = "true"
$env:OCRMYPDF_CMD = "ocrmypdf"
$env:GHOSTSCRIPT_CMD = "gswin64c"
$env:TESSERACT_CMD = if ($env:TESSERACT_CMD) { $env:TESSERACT_CMD } else { (Get-Command tesseract -ErrorAction Stop).Source }
$env:OCR_LANG = "chi_sim+eng"
$env:OCR_MAX_PAGES = "5"
$env:OCR_TIMEOUT_SECONDS = "300"
uv run --no-sync uvicorn src.main:app --host 127.0.0.1 --port 8012
```

数据库 URL 从本地 `.env` 读取并只替换数据库名为 demo；不得打印 URL。上传和派生目录必须位于 demo runtime。启动后检查 `/api/health` 和 `/api/capabilities/ocr`。

- [ ] **Step 3：通过正式 API 创建新 report/run**

流程固定为：

```text
POST /api/reports/upload?duplicate_policy=create_new
POST /api/reports/{report_id}/confirm-metadata
POST /api/reports/{report_id}/analyze
```

analyze body：

```json
{
  "confirm_llm": false,
  "enable_ocr": true,
  "ocr_pages": [77]
}
```

Expected：创建新的 report/run；不覆盖历史；DeepSeek、SiliconFlow 和 VLM 调用均为 0。

- [ ] **Step 4：轮询 run 并核验 OCR 审计**

每 5 秒读取：

```text
GET /api/runs/{run_id}
GET /api/runs/{run_id}/stages
GET /api/reports/{report_id}/audit
```

Expected：run completed；`ocr_pages_selected` 为显式第 77 页；preflight available；`ocr_completed` 成功页数 1；无路径和 stderr。

- [ ] **Step 5：只读核验 OCR chunk 与锚点**

使用 demo 数据库只读事务查询新 report 的 `document_chunks`：

```sql
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SELECT source_page, source_method, length(text), quality_flags, metadata
FROM document_chunks
WHERE report_id = :report_id
  AND source_method = 'ocr';
```

在进程内检查 OCR 文本是否命中“德勤”“独立有限鉴证报告”“鉴证结论”至少两个锚点；终端只输出锚点布尔值、文字长度、页码、质量标记和派生哈希，不输出完整 OCR 正文。

Expected：仅 OCR PDF 第 77 页；文字长度显著高于 46；至少两个锚点命中；chunk 带 `needs_manual_review`。

- [ ] **Step 6：逐项比较 baseline 与 OCR run**

按 `requirement_id` 对齐两个 run 的 499 assessments，比较：

```text
system verdict
rationale
missing items
evidence count
source PDF pages
source method
risk level
evidence status
applicability status
risk reason codes
```

Expected：

- `GRI 2-5-a`、`GRI 2-5-b-i`、`GRI 2-5-b-ii`、`GRI 2-5-b-iii` 可以产生可解释差异，并继续需要人工复核；
- 其余 495 项上述字段差异均为 0；
- 新增 false disclosed、wrong source page 和 global fallback 均为 0。

若 OCR chunk 成功但 GRI 2-5 没有引用 OCR evidence，判定试点未完成并停止；不得临时修改 Prompt、规则或 profile 制造通过。

- [ ] **Step 7：确认原始报告不变**

```powershell
Get-FileHash -Algorithm SHA256 "backend/data/reports/Envision Energy 2024-zh.pdf"
git status --short
```

Expected：SHA-256 与 Step 1 相同；原始报告无 Git 变化；派生 PDF 只位于 demo derived 目录。

---

## Task 10：完整回归、文档与重新冻结

**Files:**

- Modify: `README.md`
- Modify: `docs/DESIGN.md`
- Modify: `docs/DEVELOPMENT.md`
- Modify: `docs/plan/ocr-production-readiness-deferred-plan.md`
- Modify: `docs/plan/ocr-controlled-pilot-implementation-plan.md`
- Create: `docs/product/ocr-controlled-pilot-acceptance.md`

- [ ] **Step 1：执行 Envision v3 regeneration gate**

使用 `docs/DEVELOPMENT.md` 当前固定命令重新生成 Envision 499 assessment review、scope summary、diff summary 和 audit，保持 `confirm_llm=false` 与 `enable_ocr=false`。

Expected：`577/499/78/0`；global fallback、新增 false disclosed、新增 wrong source page、audit error 和 audit warning 均为 0。

- [ ] **Step 2：执行最终后端门禁**

```powershell
Set-Location backend
uv run --no-sync pytest -q --basetemp ../tmp/pytest-ocr-pilot-final-full
uv run --no-sync ruff check src tests
```

Expected：测试发现范围不少于 Task 1，0 failure、0 Ruff error。

- [ ] **Step 3：执行最终前端门禁**

```powershell
Set-Location frontend
pnpm lint
pnpm test -- --run
pnpm typecheck
pnpm build
```

Expected：前端无代码 diff，全部 gates 通过。

- [ ] **Step 4：完成验收报告**

`docs/product/ocr-controlled-pilot-acceptance.md` 必须记录：

1. 设计与实施提交；
2. 依赖版本和 capability 结果；
3. 新 report/run ID；
4. 第 77 页 OCR 文字长度、锚点命中、来源页和派生哈希；
5. GRI 2-5 四项差异；
6. 495 项保护字段差异；
7. 后端、前端和 Envision gates；
8. 外部模型/OCR/VLM 实际调用次数；
9. 原始 PDF 哈希前后对比；
10. 限制、失败项和是否建议扩大到通用扫描报告。

不得写入完整 OCR 正文、系统路径、数据库 URL、密钥或原始 stderr。

- [ ] **Step 5：更新主文档能力表述**

固定表述：

```text
OCR 已通过单页受控试点，默认关闭，仅在全局和请求双重启用后按目标页运行；当前不构成通用扫描 PDF 生产能力。
```

记录 Ghostscript、OCRmyPDF、Tesseract 版本和回滚方式；VLM 继续延期。

- [ ] **Step 6：计划与文档自检**

```powershell
rg -n "T[B]D|TO[D]O|待[补]充[:：]|待[确]认[:：]" `
  docs/plan/ocr-controlled-pilot-design.md `
  docs/plan/ocr-controlled-pilot-implementation-plan.md `
  docs/product/ocr-controlled-pilot-acceptance.md `
  README.md docs/DESIGN.md docs/DEVELOPMENT.md
rg -n "(^|[^A-Za-z])[A-Za-z]:[/\\]" `
  docs/plan/ocr-controlled-pilot-design.md `
  docs/plan/ocr-controlled-pilot-implementation-plan.md `
  docs/product/ocr-controlled-pilot-acceptance.md `
  README.md docs/DESIGN.md docs/DEVELOPMENT.md
git diff --check
```

Expected：无占位符、无本机绝对路径、无尾随空格或冲突标记。

- [ ] **Step 7：提交文档和验收结果**

```powershell
git add -- `
  README.md `
  docs/DESIGN.md `
  docs/DEVELOPMENT.md `
  docs/plan/ocr-production-readiness-deferred-plan.md `
  docs/plan/ocr-controlled-pilot-design.md `
  docs/plan/ocr-controlled-pilot-implementation-plan.md `
  docs/product/ocr-controlled-pilot-acceptance.md
git commit -m "docs: record controlled OCR pilot acceptance"
```

- [ ] **Step 8：最终提交检查**

```powershell
git status --short --branch
git log -8 --oneline
git diff 3383163..HEAD --stat
```

Expected：形成 4 个代码 commit 和 1 个文档 commit；工作区干净；不 push。

---

## 2. 终止条件

出现任一情况立即停止，不继续扩大范围：

1. 需要数据库 migration、API 结论字段、run 新状态或 export schema。
2. 需要修改 GRI profile 内容、规则、ontology、risk rule、AI 模型或 Prompt 才能让 OCR evidence 生效。
3. Ghostscript 包来源或版本与计划不一致。
4. capability 与 workflow 对依赖可用性的判断不同。
5. `enable_ocr=false` 运行 preflight、生成 OCR 文件或改变 Envision 结果。
6. OCR 失败信息泄露路径、命令行、stderr、环境变量或证据正文。
7. OCR 第 77 页错页、锚点不足、原始 PDF 哈希变化或派生目录越界。
8. GRI 2-5 以外任一独立判断项发生规则、证据页、风险、适用性或 missing items 差异。
9. 新增 false disclosed、wrong source page、global fallback、audit error 或 audit warning。
10. 需要接入 VLM、Docling、PaddleOCR、Celery/RQ 或 ParserBackend 大抽象。

## 3. 完成定义

只有同时满足以下条件，OCR 受控试点才完成：

- 默认 OCR 路径完全保持关闭；
- capability、preflight 和 workflow 共用一套依赖检查；
- 请求页校验、最大页数、超时和错误脱敏全部有测试；
- Envision 第 77 页真实 OCR 成功，来源页正确，至少两个验收锚点命中；
- OCR evidence 保持人工复核标记；
- GRI 2-5 差异可解释，其他 495 项差异为 0；
- 原始 PDF 哈希不变；
- 后端、Ruff、前端和 Envision v3 gates 全部通过；
- 文档只表述单页受控试点，不宣称通用扫描 PDF 生产能力；
- 分批 commit 完成，未 push。

## 4. 宏观下一步

试点完成后重新冻结 OCR 后端。只有新增至少两类真实扫描报告、形成页级 gold、记录 OCR 召回与错页率并证明同步执行不可接受时，才讨论通用 OCR、VLM 或后台队列；RAG Phase 2 与本计划继续独立。
