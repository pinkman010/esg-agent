# Goldwind Holdout 修复计划

## 目标

修复 Goldwind 2024 holdout 暴露出的两个问题：

- `disclosed + needs_manual_review` 错配。
- `profile_builder` 只能识别 GRI 索引页，不能生成 requirement-level candidate routes。

本计划不新增 Goldwind per-ID contract，不把 GRI 索引页当作 substantive evidence。

## 当前事实

- holdout 报告：`backend/data/reports/Goldwind 2024-zh.pdf`
- first-pass 输出：`tmp/review/holdout_goldwind_2024_first_pass.csv`
- quality summary：`tmp/review/holdout_goldwind_2024_quality_summary.json`
- 当前 profile：`backend/data/reports/profiles/goldwind_2024.json`
- 当前 `global_fallback_count = 0`
- 当前 `profile_route_hit_count = 0`
- 当前 audit 被 `214` 行 `disclosed must be not_required` 阻断。
- Goldwind PDF 为双页拼版，`source_pdf_page` 是权威定位字段，`source_report_page` 只能作为近似阅读辅助字段。

## 人工复核口径

对 `verdict=disclosed` 且 `review_status=needs_manual_review` 的 214 行：

- 23 行、12 个唯一 requirement：保持 `disclosed`，改为 `not_required`。
- 27 行、13 个唯一 requirement：降为 `partially_disclosed + needs_manual_review`。
- 164 行、91 个唯一 requirement：降为 `unknown + needs_manual_review`。

可保持 `disclosed + not_required` 的 requirement：

- `GRI 2-1-a`
- `GRI 2-26-a-ii`
- `GRI 2-3-d`
- `GRI 2-5-b-ii`
- `GRI 2-6-b-ii`
- `GRI 2-7-d`
- `GRI 302-1-a`
- `GRI 305-1-e`
- `GRI 305-1-g`
- `GRI 305-4-a`
- `GRI 305-4-c`
- `GRI 305-5-a`

应降为 `partially_disclosed + needs_manual_review` 的 requirement：

- `GRI 2-1-d`
- `GRI 2-12-b`
- `GRI 2-12-b-i`
- `GRI 2-13-a-i`
- `GRI 2-25-e`
- `GRI 2-29-a`
- `GRI 2-29-a-i`
- `GRI 2-29-a-ii`
- `GRI 2-6-b`
- `GRI 2-6-b-i`
- `GRI 2-9-a`
- `GRI 2-9-b`
- `GRI 3-1-b`

其余本轮复核对象中被判为 `wrong_source_page`、`profile_mapping_issue` 或 `false_disclosed` 且未列入 partial 清单的 requirement，降为 `unknown + needs_manual_review`。

## Task 1：增强 Profile Builder 的 GRI 索引映射

修改文件：

- `backend/src/reports/profile_builder.py`
- `backend/tests/reports/test_profile_builder.py`

实现要求：

- 从 GRI 索引页抽取 `GRI disclosure -> report pages`。
- 支持范围页码：`P08-P11`、`P59-P60`。
- 支持离散页码：`P34, P64, P77`。
- 支持中英文逗号和空格噪声。
- 支持 Goldwind 双页拼版页码换算：
  - `report page P >= 2` 时，`source_pdf_page = floor(P / 2) + 2`
  - 该规则只能作为 profile builder 推断逻辑，不能写入通用 GRI 标准规则。
- 将 disclosure-level route 扩展到 leaf requirement route。
- 生成的 route 写入 `ReportProfile.requirement_routes`。
- 识别第三方审验声明页，写入 `assurance_pages`。

测试要求：

- `GRI 305-2 P46 -> PDF 25`
- `GRI 414-1 P59-P60 -> PDF 31, 32`
- `GRI 405-1 P34, P64, P77 -> PDF 19, 34, 40`
- `GRI 2-5 P91-P92 -> PDF 47, 48`
- 生成的 leaf route 至少覆盖 `GRI 305-2-a`、`GRI 414-1-a`、`GRI 405-1-a`。

## Task 2：重新生成 Goldwind Profile

输出文件：

- `backend/data/reports/profiles/goldwind_2024.json`

要求：

- `gri_index.pdf_pages = [50, 51]`
- `requirement_routes` 非空。
- `assurance_pages` 非空。
- `candidate_pdf_pages` 最大值不得超过 `52`。
- `source_report_page` 仍标记为近似辅助字段，不作为 Goldwind 的权威定位字段。

## Task 3：按人工复核结果生成 Holdout Fixed CSV

输入：

- `tmp/review/holdout_goldwind_2024_first_pass.csv`

输出：

- `tmp/review/holdout_goldwind_2024_reviewed.csv`

处理规则：

- 12 个 approved requirement：`disclosed + not_required`。
- 13 个 partial requirement：`partially_disclosed + needs_manual_review`。
- 其余本轮 `disclosed + needs_manual_review` 复核对象：`unknown + needs_manual_review`。
- 保留人工复核字段：
  - `manual_label`
  - `correct_pdf_pages`
  - `suggested_verdict`
  - `issue_type`
  - `review_note`

## Task 4：重新跑 Goldwind First-Pass

输出：

- `tmp/review/holdout_goldwind_2024_first_pass.csv`
- `tmp/review/holdout_goldwind_2024_quality_summary.json`
- `tmp/review/holdout_goldwind_2024_audit.json`

要求：

- 不启用 OCR。
- 不新增 Goldwind per-ID contract。
- 不把 GRI 索引页作为 substantive evidence。

## Task 5：质量门禁

必须满足：

- `global_fallback_count = 0`
- `profile_route_hit_count > 0`
- `profile_route_requirement_count > 0`
- `source_pdf_page` 与 `candidate_pdf_pages` 最大值不超过 `52`
- `disclosed + needs_manual_review = 0`
- omission note 不得升为 `disclosed` 或 `partially_disclosed`
- GRI index page evidence 不得作为 substantive evidence

人工复核指标：

- `false_disclosed_count = 0` 基于 `holdout_goldwind_2024_reviewed.csv` 统计。
- `wrong_source_page_count = 0` 基于 `correct_pdf_pages` 统计。
- `unknown_leakage_count` 单独报告，不作为本轮硬停止条件。

## 停止条件

出现任一情况必须暂停：

- `profile_route_hit_count` 仍为 `0`。
- 生成 route 页码越界。
- `global_fallback_count > 0`。
- `disclosed + needs_manual_review` 仍存在。
- GRI 索引页被当成 substantive evidence。
- Goldwind 双页拼版页码抽样失败。
- 测试失败且无法通过小范围修复解决。

## 验证命令

```powershell
cd backend
uv run --no-sync pytest tests/reports/test_profile_builder.py tests/reports/test_report_profile.py -q
```

```powershell
cd backend
uv run --no-sync python - <<'PY'
from src.tools.review_csv_audit import audit_review_csv
result = audit_review_csv("../tmp/review/holdout_goldwind_2024_first_pass.csv", report_total_pages=52)
print("ok=", result.ok)
print("errors=", result.errors[:20])
print("error_count=", len(result.errors))
PY
```
