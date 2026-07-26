import argparse
import csv
import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.tools.evaluate_shadow_retrieval import parse_page_list
from src.tools.shadow_vector_retrieval import resolve_shadow_output


SHADOW_PROMPT_VERSION = "shadow-rag-v1"


def build_shadow_context(
    *,
    report_id: str,
    requirement_id: str,
    requirement_text: str,
    hits: list[dict[str, Any]],
    gold_pages: list[int] | None = None,
    manual_suggested_verdict: str = "",
    manual_applicability: str = "",
    standard_verified: str = "",
    review_complete: str = "",
    provider: str = "siliconflow",
    model: str = "BAAI/bge-m3",
    max_chunk_chars: int = 1200,
) -> dict[str, Any]:
    if not report_id.strip():
        raise ValueError("report_id is required")
    if not requirement_id.strip():
        raise ValueError("requirement_id is required")
    if not requirement_text.strip():
        raise ValueError("requirement_text is required")

    evidence: list[dict[str, Any]] = []
    seen_chunk_ids: set[str] = set()
    for hit in hits:
        chunk_id = str(hit.get("chunk_id") or "").strip()
        if not chunk_id or chunk_id in seen_chunk_ids:
            raise ValueError("shadow hits require unique chunk_id values")
        source_page = int(hit.get("source_page") or 0)
        if source_page < 1:
            raise ValueError("shadow hit source_page must be positive")
        text = str(hit.get("text") or "").strip()
        if not text:
            raise ValueError("shadow hit text must not be empty")
        seen_chunk_ids.add(chunk_id)
        evidence.append(
            {
                "shadow_evidence_id": f"shadow-chunk:{chunk_id}",
                "chunk_id": chunk_id,
                "source_page": source_page,
                "score": float(hit.get("score") or 0.0),
                "text": text[:max_chunk_chars],
            }
        )

    hash_payload = {
        "report_id": report_id,
        "requirement_id": requirement_id,
        "requirement_text": requirement_text.strip(),
        "provider": provider,
        "model": model,
        "prompt_version": SHADOW_PROMPT_VERSION,
        "evidence": evidence,
    }
    context_hash = hashlib.sha256(
        json.dumps(
            hash_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        **hash_payload,
        "top_k": len(evidence),
        "context_hash": context_hash,
        "generated_at": datetime.now(UTC).isoformat(),
        "gold_pages": parse_page_list(gold_pages),
        "manual_suggested_verdict": manual_suggested_verdict,
        "manual_applicability": manual_applicability,
        "standard_verified": standard_verified,
        "review_complete": review_complete,
    }


def _json_list(value: object, *, field_name: str) -> list[Any]:
    if isinstance(value, list):
        return value
    text = str(value or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON list: {field_name}") from exc
    if not isinstance(parsed, list):
        raise ValueError(f"expected JSON list: {field_name}")
    return parsed


def load_shadow_contexts_from_cases(
    cases_path: Path,
    *,
    report_id: str,
    max_chunk_chars: int = 1200,
) -> list[dict[str, Any]]:
    contexts: list[dict[str, Any]] = []
    with cases_path.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            row_report_id = str(row.get("report_id") or "").strip()
            if row_report_id != report_id:
                raise ValueError(
                    "retrieval case report_id does not match requested report"
                )
            chunk_ids = _json_list(
                row.get("vector_chunk_ids"),
                field_name="vector_chunk_ids",
            )
            source_pages = _json_list(
                row.get("vector_source_pages"),
                field_name="vector_source_pages",
            )
            scores = _json_list(
                row.get("vector_scores"),
                field_name="vector_scores",
            )
            texts = _json_list(
                row.get("vector_texts"),
                field_name="vector_texts",
            )
            lengths = {
                len(chunk_ids),
                len(source_pages),
                len(scores),
                len(texts),
            }
            if len(lengths) != 1:
                raise ValueError(
                    "retrieval hit fields must have matching lengths"
                )
            hits = [
                {
                    "chunk_id": chunk_id,
                    "source_page": source_page,
                    "score": score,
                    "text": text,
                }
                for chunk_id, source_page, score, text in zip(
                    chunk_ids,
                    source_pages,
                    scores,
                    texts,
                    strict=True,
                )
            ]
            contexts.append(
                build_shadow_context(
                    report_id=report_id,
                    requirement_id=str(
                        row.get("requirement_id") or ""
                    ),
                    requirement_text=str(row.get("query_text") or ""),
                    hits=hits,
                    gold_pages=parse_page_list(row.get("gold_pages")),
                    manual_suggested_verdict=str(
                        row.get("manual_suggested_verdict") or ""
                    ),
                    manual_applicability=str(
                        row.get("manual_applicability") or ""
                    ),
                    standard_verified=str(
                        row.get("standard_verified") or ""
                    ),
                    review_complete=str(
                        row.get("review_complete") or ""
                    ),
                    max_chunk_chars=max_chunk_chars,
                )
            )
    return contexts


def write_shadow_contexts(
    contexts: list[dict[str, Any]],
    *,
    output: str,
) -> Path:
    output_path = resolve_shadow_output(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for context in contexts:
            file.write(
                json.dumps(
                    context,
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )
    return output_path


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-id", required=True)
    parser.add_argument("--retrieval-cases", type=Path, required=True)
    parser.add_argument(
        "--output",
        default="tmp/embedding/envision_shadow_rag_contexts.jsonl",
    )
    parser.add_argument("--max-chunk-chars", type=int, default=1200)
    args = parser.parse_args(argv)
    contexts = load_shadow_contexts_from_cases(
        args.retrieval_cases,
        report_id=args.report_id,
        max_chunk_chars=args.max_chunk_chars,
    )
    output_path = write_shadow_contexts(
        contexts,
        output=args.output,
    )
    print(
        json.dumps(
            {
                "contexts": len(contexts),
                "output": str(output_path),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
