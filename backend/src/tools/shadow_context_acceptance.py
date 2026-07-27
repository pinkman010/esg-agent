from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path
from typing import Any, Literal

from src.tools.evaluate_shadow_retrieval import parse_page_list


MethodName = Literal["rule", "vector", "hybrid"]


def _has_valid_rrf_evidence_fields(item: dict[str, Any]) -> bool:
    sources = tuple(item.get("retrieval_sources") or ())
    if sources not in {
        ("rule",),
        ("vector",),
        ("rule", "vector"),
    }:
        return False
    rule_rank = item.get("rule_rank")
    vector_rank = item.get("vector_rank")
    if "rule" in sources:
        if (
            not isinstance(rule_rank, int)
            or isinstance(rule_rank, bool)
            or rule_rank < 1
        ):
            return False
    elif rule_rank is not None:
        return False
    if "vector" in sources:
        if (
            not isinstance(vector_rank, int)
            or isinstance(vector_rank, bool)
            or not 1 <= vector_rank <= 10
        ):
            return False
    elif vector_rank is not None:
        return False
    expected_score = 0.0
    if rule_rank is not None:
        expected_score += 2.0 / (60 + rule_rank)
    if vector_rank is not None:
        expected_score += 1.0 / (60 + vector_rank)
    fusion_score = item.get("fusion_score")
    return (
        isinstance(fusion_score, (int, float))
        and not isinstance(fusion_score, bool)
        and math.isfinite(float(fusion_score))
        and math.isclose(
            float(fusion_score),
            expected_score,
            rel_tol=1e-12,
            abs_tol=1e-12,
        )
    )


def build_comparison_case(
    *,
    report_id: str,
    requirement_id: str,
    gold_pages: object,
    rule_pages: object,
    vector_pages: object,
    hybrid_pages: object,
    context_hash: str,
    unresolved_rule_pages: object,
) -> dict[str, Any]:
    if not report_id.strip():
        raise ValueError("report_id is required")
    if not requirement_id.strip():
        raise ValueError("requirement_id is required")
    if len(context_hash) != 64:
        raise ValueError("context_hash must be sha256")
    case: dict[str, Any] = {
        "report_id": report_id.strip(),
        "requirement_id": requirement_id.strip(),
        "gold_pages": parse_page_list(gold_pages),
        "rule_pages": parse_page_list(rule_pages)[:5],
        "vector_pages": parse_page_list(vector_pages)[:5],
        "hybrid_pages": parse_page_list(hybrid_pages)[:5],
        "context_hash": context_hash,
        "unresolved_rule_pages": parse_page_list(unresolved_rule_pages),
    }
    gold = set(case["gold_pages"])
    for method in ("rule", "vector", "hybrid"):
        pages = case[f"{method}_pages"]
        first_hit_rank = next(
            (rank for rank, page in enumerate(pages, start=1) if page in gold),
            None,
        )
        case[f"{method}_first_hit_rank"] = first_hit_rank if gold else None
        for k in (1, 3, 5):
            matched = set(pages[:k]) & gold
            case[f"{method}_hit_at_{k}"] = int(bool(matched)) if gold else None
            case[f"{method}_recall_at_{k}"] = (
                round(len(matched) / len(gold), 6) if gold else None
            )
    if not gold:
        case["comparison_bucket"] = "not_evaluated"
    else:
        rule_hit = bool(set(case["rule_pages"]) & gold)
        hybrid_hit = bool(set(case["hybrid_pages"]) & gold)
        if hybrid_hit and not rule_hit:
            case["comparison_bucket"] = "hybrid_gain"
        elif rule_hit and not hybrid_hit:
            case["comparison_bucket"] = "hybrid_loss"
        elif rule_hit and hybrid_hit:
            case["comparison_bucket"] = "both_hit"
        else:
            case["comparison_bucket"] = "neither_hit"
    return case


def compute_method_metrics(
    cases: list[dict[str, Any]],
    *,
    method: MethodName,
    k_values: tuple[int, ...] = (1, 3, 5),
) -> dict[str, int | float]:
    if method not in {"rule", "vector", "hybrid"}:
        raise ValueError("unsupported method")
    if not k_values or any(k < 1 for k in k_values):
        raise ValueError("k_values must contain positive integers")
    page_field = f"{method}_pages"
    evaluated = [case for case in cases if parse_page_list(case["gold_pages"])]
    denominator = len(evaluated)
    summary: dict[str, int | float] = {
        "case_count": len(cases),
        "evaluated_case_count": denominator,
        "no_gold_page_case_count": len(cases) - denominator,
    }
    reciprocal_rank_total = 0.0
    for k in sorted(set(k_values)):
        hit_total = 0
        recall_total = 0.0
        for case in evaluated:
            gold = set(parse_page_list(case["gold_pages"]))
            pages = parse_page_list(case[page_field])
            matched = set(pages[:k]) & gold
            hit_total += bool(matched)
            recall_total += len(matched) / len(gold)
        summary[f"hit_at_{k}"] = (
            round(hit_total / denominator, 6) if denominator else 0.0
        )
        summary[f"recall_at_{k}"] = (
            round(recall_total / denominator, 6) if denominator else 0.0
        )
    for case in evaluated:
        gold = set(parse_page_list(case["gold_pages"]))
        pages = parse_page_list(case[page_field])[:5]
        first_hit_rank = next(
            (rank for rank, page in enumerate(pages, start=1) if page in gold),
            None,
        )
        if first_hit_rank is not None:
            reciprocal_rank_total += 1 / first_hit_rank
    summary["mrr"] = (
        round(reciprocal_rank_total / denominator, 6) if denominator else 0.0
    )
    return summary


def audit_contexts(
    contexts: list[dict[str, Any]],
    *,
    report_id: str,
    report_total_pages: int,
    expected_count: int = 499,
    require_exact_context_size: bool = True,
) -> dict[str, int]:
    if len(contexts) != expected_count:
        raise ValueError("unexpected context count")
    if report_total_pages < 1:
        raise ValueError("report_total_pages must be positive")
    requirement_ids: set[str] = set()
    context_hashes: set[str] = set()
    duplicate_page_context_count = 0
    unresolved_rule_page_context_count = 0
    out_of_range_page_count = 0
    invalid_shadow_evidence_id_count = 0
    invalid_rrf_evidence_count = 0
    context_size_not_5_count = 0
    expected_rrf_metadata = {
        "retrieval_mode": "hybrid_rrf",
        "provider": "siliconflow",
        "model": "BAAI/bge-m3",
        "vector_pool_k": 10,
        "context_k": 5,
        "top_k": 5,
        "rrf_rule_weight": 2.0,
        "rrf_vector_weight": 1.0,
        "rrf_constant": 60,
    }

    for context in contexts:
        if context.get("report_id") != report_id:
            raise ValueError("context report_id mismatch")
        if any(
            context.get(field) != value
            for field, value in expected_rrf_metadata.items()
        ):
            raise ValueError("context RRF metadata mismatch")
        requirement_id = str(context.get("requirement_id") or "").strip()
        if not requirement_id or requirement_id in requirement_ids:
            raise ValueError("duplicate or empty requirement_id")
        requirement_ids.add(requirement_id)
        context_hash = str(context.get("context_hash") or "")
        if (
            re.fullmatch(r"[0-9a-f]{64}", context_hash) is None
            or context_hash in context_hashes
        ):
            raise ValueError("duplicate or invalid context_hash")
        context_hashes.add(context_hash)
        evidence = list(context.get("evidence") or [])
        pages = [int(item.get("source_page") or 0) for item in evidence]
        if len(pages) != len(set(pages)):
            duplicate_page_context_count += 1
        out_of_range_page_count += sum(
            page < 1 or page > report_total_pages for page in pages
        )
        invalid_shadow_evidence_id_count += sum(
            not str(item.get("chunk_id") or "").strip()
            or str(item.get("shadow_evidence_id") or "")
            != f"shadow-chunk:{str(item.get('chunk_id') or '').strip()}"
            for item in evidence
        )
        invalid_rrf_evidence_count += sum(
            not _has_valid_rrf_evidence_fields(item) for item in evidence
        )
        if len(evidence) != 5:
            context_size_not_5_count += 1
        if context.get("unresolved_rule_pages"):
            unresolved_rule_page_context_count += 1

    if duplicate_page_context_count:
        raise ValueError("duplicate source pages in context")
    if out_of_range_page_count:
        raise ValueError("context source page out of range")
    if invalid_shadow_evidence_id_count:
        raise ValueError("invalid shadow evidence id")
    if invalid_rrf_evidence_count:
        raise ValueError("invalid RRF evidence fields")
    if unresolved_rule_page_context_count:
        raise ValueError("unresolved rule pages remain")
    if require_exact_context_size and context_size_not_5_count:
        raise ValueError("context size must equal 5")
    return {
        "context_count": len(contexts),
        "unique_requirement_count": len(requirement_ids),
        "unique_context_hash_count": len(context_hashes),
        "duplicate_page_context_count": duplicate_page_context_count,
        "unresolved_rule_page_context_count": (unresolved_rule_page_context_count),
        "out_of_range_page_count": out_of_range_page_count,
        "invalid_shadow_evidence_id_count": (invalid_shadow_evidence_id_count),
        "invalid_rrf_evidence_count": invalid_rrf_evidence_count,
        "context_size_not_5_count": context_size_not_5_count,
    }


def load_comparison_inputs(
    retrieval_cases_path: Path,
    contexts_path: Path,
    *,
    report_id: str,
    expected_count: int = 499,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    with retrieval_cases_path.open(
        encoding="utf-8-sig",
        newline="",
    ) as file:
        retrieval_rows = list(csv.DictReader(file))

    contexts: list[dict[str, Any]] = []
    with contexts_path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                context = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid context JSON at line {line_number}") from exc
            if not isinstance(context, dict):
                raise ValueError(
                    f"context JSON at line {line_number} must be an object"
                )
            contexts.append(context)

    def index_by_requirement(
        rows: list[dict[str, Any]],
        *,
        source_name: str,
    ) -> dict[str, dict[str, Any]]:
        indexed: dict[str, dict[str, Any]] = {}
        for row in rows:
            row_report_id = str(row.get("report_id") or "").strip()
            if row_report_id != report_id:
                raise ValueError(f"{source_name} report_id mismatch")
            requirement_id = str(row.get("requirement_id") or "").strip()
            if not requirement_id:
                raise ValueError(f"{source_name} requirement_id is required")
            if requirement_id in indexed:
                raise ValueError(f"duplicate {source_name} requirement_id")
            indexed[requirement_id] = row
        return indexed

    retrieval_by_requirement = index_by_requirement(
        retrieval_rows,
        source_name="retrieval case",
    )
    contexts_by_requirement = index_by_requirement(
        contexts,
        source_name="context",
    )
    if len(retrieval_by_requirement) != expected_count:
        raise ValueError("unexpected retrieval case count")
    if len(contexts_by_requirement) != expected_count:
        raise ValueError("unexpected context count")

    retrieval_ids = set(retrieval_by_requirement)
    context_ids = set(contexts_by_requirement)
    if retrieval_ids != context_ids:
        missing_contexts = len(retrieval_ids - context_ids)
        missing_retrieval_cases = len(context_ids - retrieval_ids)
        raise ValueError(
            "requirement sets differ: "
            f"missing_contexts={missing_contexts}, "
            f"missing_retrieval_cases={missing_retrieval_cases}"
        )

    cases: list[dict[str, Any]] = []
    for requirement_id in sorted(retrieval_ids):
        row = retrieval_by_requirement[requirement_id]
        context = contexts_by_requirement[requirement_id]
        evidence = list(context.get("evidence") or [])
        evidence_pages = [int(item.get("source_page") or 0) for item in evidence]
        case = build_comparison_case(
            report_id=report_id,
            requirement_id=requirement_id,
            gold_pages=row.get("gold_pages"),
            rule_pages=row.get("rule_pages"),
            vector_pages=(row.get("vector_source_pages") or row.get("vector_pages")),
            hybrid_pages=evidence_pages,
            context_hash=str(context.get("context_hash") or ""),
            unresolved_rule_pages=context.get("unresolved_rule_pages"),
        )
        case["context_size"] = len(evidence)
        case["duplicate_page_count"] = len(evidence_pages) - len(set(evidence_pages))
        cases.append(case)
    return cases, contexts


def build_acceptance_summary(
    *,
    report_id: str,
    run_metadata: dict[str, Any],
    cases: list[dict[str, Any]],
    context_audit: dict[str, int],
    deterministic_hash_mismatch_count: int,
    formal_table_counts_before: dict[str, int],
    formal_table_counts_after: dict[str, int],
    embedding_enabled: bool,
    expected_count: int = 499,
    expected_evaluated_case_count: int = 119,
) -> dict[str, Any]:
    required_metadata = {
        "git_head",
        "input_manifest_path",
        "retrieval_mode",
        "provider",
        "model",
        "vector_pool_k",
        "context_k",
        "rrf_rule_weight",
        "rrf_vector_weight",
        "rrf_constant",
        "git_dirty",
        "git_status_sha256",
    }
    missing_metadata = sorted(required_metadata - set(run_metadata))
    if missing_metadata:
        raise ValueError("missing run metadata: " + ", ".join(missing_metadata))
    rule = compute_method_metrics(cases, method="rule")
    vector = compute_method_metrics(cases, method="vector")
    hybrid = compute_method_metrics(cases, method="hybrid")
    gain_count = sum(case["comparison_bucket"] == "hybrid_gain" for case in cases)
    loss_count = sum(case["comparison_bucket"] == "hybrid_loss" for case in cases)
    counts_unchanged = formal_table_counts_before == formal_table_counts_after
    gates = {
        "case_count_499": len(cases) == expected_count,
        "evaluated_case_count_matches_expected": (
            hybrid["evaluated_case_count"] == expected_evaluated_case_count
        ),
        "context_count_499": (context_audit["context_count"] == expected_count),
        "unique_requirement_count_499": (
            context_audit["unique_requirement_count"] == expected_count
        ),
        "unique_context_hash_count_499": (
            context_audit["unique_context_hash_count"] == expected_count
        ),
        "duplicate_page_context_count_zero": (
            context_audit["duplicate_page_context_count"] == 0
        ),
        "unresolved_rule_page_context_count_zero": (
            context_audit["unresolved_rule_page_context_count"] == 0
        ),
        "out_of_range_page_count_zero": (context_audit["out_of_range_page_count"] == 0),
        "invalid_shadow_evidence_id_count_zero": (
            context_audit["invalid_shadow_evidence_id_count"] == 0
        ),
        "invalid_rrf_evidence_count_zero": (
            context_audit["invalid_rrf_evidence_count"] == 0
        ),
        "context_size_not_5_count_zero": (
            context_audit["context_size_not_5_count"] == 0
        ),
        "deterministic_hash_mismatch_count_zero": (
            deterministic_hash_mismatch_count == 0
        ),
        "formal_table_counts_unchanged": counts_unchanged,
        "embedding_disabled": not embedding_enabled,
        "hybrid_hit_at_5_not_below_rule": (hybrid["hit_at_5"] >= rule["hit_at_5"]),
        "hybrid_recall_at_5_not_below_rule": (
            hybrid["recall_at_5"] >= rule["recall_at_5"]
        ),
        "hybrid_mrr_not_below_rule": (hybrid["mrr"] >= rule["mrr"]),
        "hybrid_gain_not_below_loss": gain_count >= loss_count,
    }
    return {
        "report_id": report_id,
        "run_metadata": run_metadata,
        "case_count": len(cases),
        "evaluated_case_count": hybrid["evaluated_case_count"],
        "no_gold_page_case_count": hybrid["no_gold_page_case_count"],
        **context_audit,
        "deterministic_hash_mismatch_count": (deterministic_hash_mismatch_count),
        "rule_metrics": rule,
        "vector_metrics": vector,
        "hybrid_metrics": hybrid,
        "hybrid_gain_case_count": gain_count,
        "hybrid_loss_case_count": loss_count,
        "formal_table_counts_before": formal_table_counts_before,
        "formal_table_counts_after": formal_table_counts_after,
        "formal_table_counts_unchanged": counts_unchanged,
        "gates": gates,
        "ok": all(gates.values()),
        "limitations": [
            "历史 correct_pdf_pages 只作为现有工程 gold。",
            "无 gold requirement 不进入召回指标分母。",
            "页码命中不等于披露充分。",
            ("本结果不构成 GRI 专家认证、外部鉴证或最终合规结论。"),
        ],
    }


def render_acceptance_report(summary: dict[str, Any]) -> str:
    metadata = dict(summary.get("run_metadata") or {})
    required_metadata = {
        "git_head",
        "input_manifest_path",
        "retrieval_mode",
        "provider",
        "model",
        "vector_pool_k",
        "context_k",
        "rrf_rule_weight",
        "rrf_vector_weight",
        "rrf_constant",
        "git_dirty",
        "git_status_sha256",
    }
    missing_metadata = sorted(required_metadata - set(metadata))
    if missing_metadata:
        raise ValueError("missing run metadata: " + ", ".join(missing_metadata))
    status = "通过" if summary["ok"] else "未通过"
    lines = [
        "# 混合影子 RAG Phase 1.5 自动工程验收",
        "",
        f"- 结论：{status}",
        f"- 报告 ID：`{summary['report_id']}`",
        f"- Git：`{metadata['git_head']}`",
        (f"- 工作区未提交变更：{'是' if metadata['git_dirty'] else '否'}"),
        (f"- Git 状态 SHA256：`{metadata['git_status_sha256']}`"),
        f"- Provider：`{metadata['provider']}`",
        f"- Model：`{metadata['model']}`",
        f"- 检索模式：`{metadata['retrieval_mode']}`",
        (
            "- 参数："
            f"`vector_pool_k={metadata['vector_pool_k']}`、"
            f"`context_k={metadata['context_k']}`、"
            f"`rrf_rule_weight={metadata['rrf_rule_weight']}`、"
            f"`rrf_vector_weight={metadata['rrf_vector_weight']}`、"
            f"`rrf_constant={metadata['rrf_constant']}`"
        ),
        (f"- 输入 manifest：`{metadata['input_manifest_path']}`"),
        "",
        "## 召回指标",
        "",
        "| 方法 | Hit@1 | Hit@3 | Hit@5 | Recall@1 | Recall@3 | Recall@5 | MRR |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, key in (
        ("规则", "rule_metrics"),
        ("向量", "vector_metrics"),
        ("混合", "hybrid_metrics"),
    ):
        metrics = summary[key]
        lines.append(
            f"| {label} | {metrics['hit_at_1']:.6f} | "
            f"{metrics['hit_at_3']:.6f} | "
            f"{metrics['hit_at_5']:.6f} | "
            f"{metrics['recall_at_1']:.6f} | "
            f"{metrics['recall_at_3']:.6f} | "
            f"{metrics['recall_at_5']:.6f} | "
            f"{metrics['mrr']:.6f} |"
        )
    lines.extend(
        [
            "",
            "## 差异与结构",
            "",
            (f"- Hybrid gain：{summary['hybrid_gain_case_count']}"),
            (f"- Hybrid loss：{summary['hybrid_loss_case_count']}"),
            f"- Context：{summary['context_count']}",
            (f"- 唯一 context hash：{summary['unique_context_hash_count']}"),
            "",
            "## 门禁",
            "",
            "| 门禁 | 结果 |",
            "| --- | --- |",
        ]
    )
    for gate, passed in summary["gates"].items():
        lines.append(f"| `{gate}` | {'通过' if passed else '失败'} |")
    lines.extend(
        [
            "",
            "## 正式业务表计数",
            "",
            "| 表 | Before | After |",
            "| --- | ---: | ---: |",
        ]
    )
    before = summary["formal_table_counts_before"]
    after = summary["formal_table_counts_after"]
    for table_name in sorted(set(before) | set(after)):
        lines.append(
            f"| `{table_name}` | {before.get(table_name, 0)} | "
            f"{after.get(table_name, 0)} |"
        )
    lines.extend(["", "## 限制", ""])
    lines.extend(f"- {limitation}" for limitation in summary["limitations"])
    lines.extend(
        [
            "",
            "## 后续边界",
            "",
            "- Phase 2 为可选增强，当前未启动。",
            "- Phase 3 保持关闭。",
            "",
        ]
    )
    return "\n".join(lines)
