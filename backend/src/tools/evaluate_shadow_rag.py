import argparse
import csv
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from src.config.settings import get_settings
from src.tools.build_shadow_rag_contexts import SHADOW_PROMPT_VERSION
from src.tools.evaluate_shadow_retrieval import parse_page_list
from src.tools.llm_client import (
    LLMClient,
    LLMCompletionError,
    ModelCallBlocked,
)
from src.tools.shadow_vector_retrieval import resolve_shadow_output


VALID_VERDICTS = {
    "disclosed",
    "partially_disclosed",
    "unknown",
}


def build_shadow_messages(
    context: dict[str, Any],
) -> list[dict[str, str]]:
    evidence = [
        {
            "shadow_evidence_id": item["shadow_evidence_id"],
            "source_page": item["source_page"],
            "score": item["score"],
            "text": item["text"],
        }
        for item in context.get("evidence", [])
    ]
    system = (
        "你是 ESG 报告分析辅助模型。只能根据给定 requirement 和影子证据回答。"
        "输出 JSON 对象，字段必须为 suggested_verdict、rationale、"
        "cited_evidence_ids、cited_pdf_pages、missing_items。"
        "suggested_verdict 只能是 disclosed、partially_disclosed、unknown。"
        "不得引用输入之外的证据；证据不足时使用 unknown。"
    )
    user = json.dumps(
        {
            "prompt_version": SHADOW_PROMPT_VERSION,
            "requirement_id": context["requirement_id"],
            "requirement_text": context["requirement_text"],
            "evidence": evidence,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _schema_failure(
    code: str,
    *,
    content: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "shadow_status": "schema_failed",
        "shadow_suggested_verdict": None,
        "shadow_rationale": "",
        "shadow_cited_evidence_ids": [],
        "shadow_cited_pdf_pages": [],
        "shadow_missing_items": [],
        "shadow_guardrail_codes": [code],
        "shadow_raw_response": content,
    }


def validate_shadow_response(
    context: dict[str, Any],
    content: dict[str, Any],
) -> dict[str, Any]:
    verdict = content.get("suggested_verdict")
    rationale = content.get("rationale")
    cited_ids = content.get("cited_evidence_ids")
    cited_pages = content.get("cited_pdf_pages")
    missing_items = content.get("missing_items")
    if (
        verdict not in VALID_VERDICTS
        or not isinstance(rationale, str)
        or not rationale.strip()
        or not isinstance(cited_ids, list)
        or not all(isinstance(item, str) for item in cited_ids)
        or not isinstance(cited_pages, list)
        or not all(
            isinstance(item, int) and not isinstance(item, bool)
            for item in cited_pages
        )
        or not isinstance(missing_items, list)
        or not all(isinstance(item, str) for item in missing_items)
    ):
        return _schema_failure(
            "shadow_response_schema_invalid",
            content=content,
        )

    evidence_page_by_id = {
        str(item["shadow_evidence_id"]): int(item["source_page"])
        for item in context.get("evidence", [])
    }
    guardrails: list[str] = []
    if any(
        evidence_id not in evidence_page_by_id
        for evidence_id in cited_ids
    ):
        guardrails.append("invalid_shadow_citation")
    if len(cited_ids) != len(cited_pages):
        guardrails.append("shadow_citation_page_cardinality_mismatch")
    else:
        for evidence_id, page in zip(
            cited_ids,
            cited_pages,
            strict=True,
        ):
            expected_page = evidence_page_by_id.get(evidence_id)
            if expected_page is not None and page != expected_page:
                guardrails.append("shadow_citation_page_mismatch")
                break
    if verdict == "disclosed" and not cited_ids:
        guardrails.append("shadow_disclosed_without_evidence")
    if verdict == "partially_disclosed" and not missing_items:
        guardrails.append("shadow_partial_without_missing_items")
    guardrails = list(dict.fromkeys(guardrails))
    if guardrails:
        return {
            "shadow_status": "guardrail_failed",
            "shadow_suggested_verdict": None,
            "shadow_rationale": rationale.strip(),
            "shadow_cited_evidence_ids": cited_ids,
            "shadow_cited_pdf_pages": cited_pages,
            "shadow_missing_items": missing_items,
            "shadow_guardrail_codes": guardrails,
            "shadow_raw_response": content,
        }
    return {
        "shadow_status": "succeeded",
        "shadow_suggested_verdict": verdict,
        "shadow_rationale": rationale.strip(),
        "shadow_cited_evidence_ids": cited_ids,
        "shadow_cited_pdf_pages": cited_pages,
        "shadow_missing_items": missing_items,
        "shadow_guardrail_codes": [],
        "shadow_raw_response": content,
    }


def _evaluation_flags(row: dict[str, Any]) -> dict[str, bool]:
    manual_verdict = str(
        row.get("manual_suggested_verdict") or ""
    )
    shadow_verdict = row.get("shadow_suggested_verdict")
    gold_pages = set(parse_page_list(row.get("gold_pages")))
    cited_pages = set(
        parse_page_list(row.get("shadow_cited_pdf_pages"))
    )
    exact = bool(
        manual_verdict in VALID_VERDICTS
        and shadow_verdict == manual_verdict
    )
    false_disclosed = bool(
        shadow_verdict == "disclosed"
        and manual_verdict != "disclosed"
    )
    wrong_source_page = bool(
        shadow_verdict in {"disclosed", "partially_disclosed"}
        and shadow_verdict == manual_verdict
        and gold_pages
        and cited_pages
        and bool(cited_pages - gold_pages)
    )
    unknown_leakage = bool(
        shadow_verdict == "unknown"
        and manual_verdict in {"disclosed", "partially_disclosed"}
    )
    invalid_citation = bool(
        {
            "invalid_shadow_citation",
            "shadow_citation_page_cardinality_mismatch",
            "shadow_citation_page_mismatch",
        }
        & set(row.get("shadow_guardrail_codes") or [])
    )
    return {
        "exact_verdict_agreement": exact,
        "false_disclosed": false_disclosed,
        "wrong_source_page": wrong_source_page,
        "unknown_leakage": unknown_leakage,
        "invalid_shadow_citation": invalid_citation,
    }


def evaluate_shadow_contexts(
    contexts: list[dict[str, Any]],
    *,
    client: LLMClient,
    confirm_llm: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not confirm_llm:
        raise ModelCallBlocked(
            "external model call requires confirm_llm=true"
        )

    rows: list[dict[str, Any]] = []
    for context in contexts:
        base = {
            "report_id": context["report_id"],
            "requirement_id": context["requirement_id"],
            "context_hash": context["context_hash"],
            "prompt_version": SHADOW_PROMPT_VERSION,
            "manual_suggested_verdict": context.get(
                "manual_suggested_verdict",
                "",
            ),
            "manual_applicability": context.get(
                "manual_applicability",
                "",
            ),
            "gold_pages": context.get("gold_pages", []),
        }
        try:
            completion = client.complete_json(
                messages=build_shadow_messages(context),
                confirm_llm=True,
            )
            validated = validate_shadow_response(
                context,
                completion.content,
            )
            row = {
                **base,
                **validated,
                "shadow_model": completion.model,
                "shadow_usage": completion.usage,
                "shadow_latency_ms": completion.latency_ms,
                "shadow_retry_count": completion.retry_count,
                "shadow_error_code": "",
            }
        except LLMCompletionError as exc:
            row = {
                **base,
                **_schema_failure(exc.error_code),
                "shadow_status": "model_failed",
                "shadow_model": client.model,
                "shadow_usage": {},
                "shadow_latency_ms": None,
                "shadow_retry_count": exc.retry_count,
                "shadow_error_code": exc.error_code,
            }
        flags = _evaluation_flags(row)
        rows.append({**row, **flags})

    evaluable = [
        row
        for row in rows
        if row["manual_suggested_verdict"] in VALID_VERDICTS
    ]
    summary = {
        "evaluated_count": len(rows),
        "verdict_evaluable_count": len(evaluable),
        "exact_verdict_agreement_count": sum(
            row["exact_verdict_agreement"] for row in evaluable
        ),
        "exact_verdict_agreement_rate": (
            sum(row["exact_verdict_agreement"] for row in evaluable)
            / len(evaluable)
            if evaluable
            else 0.0
        ),
        "false_disclosed_count": sum(
            row["false_disclosed"] for row in rows
        ),
        "wrong_source_page_count": sum(
            row["wrong_source_page"] for row in rows
        ),
        "unknown_leakage_count": sum(
            row["unknown_leakage"] for row in rows
        ),
        "invalid_shadow_citation_count": sum(
            row["invalid_shadow_citation"] for row in rows
        ),
        "schema_failure_count": sum(
            row["shadow_status"] == "schema_failed"
            for row in rows
        ),
        "model_failure_count": sum(
            row["shadow_status"] == "model_failed"
            for row in rows
        ),
        "guardrail_failure_count": sum(
            row["shadow_status"] == "guardrail_failed"
            for row in rows
        ),
    }
    return rows, summary


def load_contexts(path: Path) -> list[dict[str, Any]]:
    contexts: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError(
                    f"context line {line_number} must be an object"
                )
            contexts.append(item)
    return contexts


def write_evaluation_outputs(
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    output_prefix: str,
) -> dict[str, str]:
    jsonl_path = resolve_shadow_output(
        f"{output_prefix}_results.jsonl"
    )
    csv_path = resolve_shadow_output(f"{output_prefix}_results.csv")
    summary_path = resolve_shadow_output(
        f"{output_prefix}_summary.json"
    )
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )
    fields = list(rows[0]) if rows else []
    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        if fields:
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        key: (
                            json.dumps(
                                value,
                                ensure_ascii=False,
                                sort_keys=True,
                            )
                            if isinstance(value, (list, dict))
                            else value
                        )
                        for key, value in row.items()
                    }
                )
    summary_path.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "results_jsonl": str(jsonl_path),
        "results_csv": str(csv_path),
        "summary_json": str(summary_path),
    }


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contexts", required=True)
    parser.add_argument("--confirm-llm", action="store_true")
    parser.add_argument(
        "--output-prefix",
        default="tmp/embedding/envision_shadow_rag",
    )
    args = parser.parse_args(argv)
    context_path = resolve_shadow_output(args.contexts)
    contexts = load_contexts(context_path)
    settings = get_settings()
    if args.confirm_llm and not settings.openai_compatible_api_key.strip():
        raise ValueError(
            "OPENAI_COMPATIBLE_API_KEY is not configured"
        )
    client = LLMClient(
        model=settings.llm_model,
        api_key=settings.openai_compatible_api_key,
        base_url=settings.openai_compatible_api_base,
        thinking_type=settings.llm_thinking_type,
        reasoning_effort=settings.llm_reasoning_effort,
        response_format=settings.llm_response_format,
        max_tokens=settings.llm_max_tokens,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        retry_delay_seconds=settings.llm_retry_delay_seconds,
    )
    rows, summary = evaluate_shadow_contexts(
        contexts,
        client=client,
        confirm_llm=args.confirm_llm,
    )
    outputs = write_evaluation_outputs(
        rows,
        summary,
        output_prefix=args.output_prefix,
    )
    print(
        json.dumps(
            {**summary, **outputs},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
