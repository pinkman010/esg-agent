import argparse
import csv
import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.db.repositories import Repository
from src.db.session import SessionLocal
from src.tools.evaluate_shadow_retrieval import parse_page_list
from src.tools.shadow_vector_retrieval import resolve_shadow_output


SHADOW_PROMPT_VERSION = "shadow-rag-v1"
DEFAULT_VECTOR_POOL_K = 10
DEFAULT_CONTEXT_K = 5
DEFAULT_RRF_RULE_WEIGHT = 2.0
DEFAULT_RRF_VECTOR_WEIGHT = 1.0
DEFAULT_RRF_CONSTANT = 60


def _chunk_value(chunk: object, field_name: str) -> object:
    if isinstance(chunk, dict):
        return chunk.get(field_name)
    return getattr(chunk, field_name, None)


def fuse_shadow_hits(
    *,
    rule_pages: list[int],
    vector_hits: list[dict[str, Any]],
    report_chunks: Sequence[object],
    vector_pool_k: int = DEFAULT_VECTOR_POOL_K,
    context_k: int = DEFAULT_CONTEXT_K,
    rule_weight: float = DEFAULT_RRF_RULE_WEIGHT,
    vector_weight: float = DEFAULT_RRF_VECTOR_WEIGHT,
    rrf_constant: int = DEFAULT_RRF_CONSTANT,
) -> tuple[list[dict[str, Any]], list[int]]:
    if vector_pool_k < 1:
        raise ValueError("vector_pool_k must be positive")
    if context_k < 1:
        raise ValueError("context_k must be positive")
    if rule_weight <= 0 or vector_weight <= 0:
        raise ValueError("RRF weights must be positive")
    if rrf_constant < 1:
        raise ValueError("rrf_constant must be positive")

    chunks_by_page: dict[int, list[dict[str, Any]]] = {}
    for chunk in report_chunks:
        chunk_id = str(_chunk_value(chunk, "chunk_id") or "").strip()
        source_page = int(_chunk_value(chunk, "source_page") or 0)
        text = str(_chunk_value(chunk, "text") or "").strip()
        if not chunk_id or source_page < 1 or not text:
            raise ValueError("report chunks require id, page, and text")
        chunks_by_page.setdefault(source_page, []).append(
            {
                "chunk_id": chunk_id,
                "source_page": source_page,
                "text": text,
            }
        )
    for chunks in chunks_by_page.values():
        chunks.sort(
            key=lambda item: (-len(item["text"]), item["chunk_id"])
        )

    vector_by_page: dict[int, dict[str, Any]] = {}
    for vector_rank, hit in enumerate(
        vector_hits[:vector_pool_k],
        start=1,
    ):
        chunk_id = str(hit.get("chunk_id") or "").strip()
        source_page = int(hit.get("source_page") or 0)
        text = str(hit.get("text") or "").strip()
        if not chunk_id or source_page < 1 or not text:
            raise ValueError("vector hits require id, page, and text")
        vector_by_page.setdefault(
            source_page,
            {
                "chunk_id": chunk_id,
                "source_page": source_page,
                "text": text,
                "score": float(hit.get("score") or 0.0),
                "vector_rank": vector_rank,
            },
        )

    candidates: dict[int, dict[str, Any]] = {}
    unresolved_rule_pages: list[int] = []
    for rule_rank, source_page in enumerate(
        parse_page_list(rule_pages),
        start=1,
    ):
        page_chunks = chunks_by_page.get(source_page, [])
        vector_candidate = vector_by_page.get(source_page)
        if not page_chunks and vector_candidate is None:
            unresolved_rule_pages.append(source_page)
            continue
        representative = vector_candidate or page_chunks[0]
        candidates[source_page] = {
            **representative,
            "score": (
                float(vector_candidate["score"])
                if vector_candidate is not None
                else 0.0
            ),
            "rule_rank": rule_rank,
            "vector_rank": (
                vector_candidate["vector_rank"]
                if vector_candidate is not None
                else None
            ),
        }

    for source_page, vector_candidate in vector_by_page.items():
        candidates.setdefault(
            source_page,
            {
                **vector_candidate,
                "rule_rank": None,
            },
        )

    fused: list[dict[str, Any]] = []
    for candidate in candidates.values():
        rule_rank = candidate["rule_rank"]
        vector_rank = candidate["vector_rank"]
        fusion_score = 0.0
        retrieval_sources: list[str] = []
        if rule_rank is not None:
            retrieval_sources.append("rule")
            fusion_score += rule_weight / (rrf_constant + rule_rank)
        if vector_rank is not None:
            retrieval_sources.append("vector")
            fusion_score += vector_weight / (
                rrf_constant + vector_rank
            )
        fused.append(
            {
                **candidate,
                "retrieval_sources": retrieval_sources,
                "fusion_score": fusion_score,
            }
        )

    missing_rank = 10**9
    fused.sort(
        key=lambda item: (
            -float(item["fusion_score"]),
            item["rule_rank"]
            if item["rule_rank"] is not None
            else missing_rank,
            item["vector_rank"]
            if item["vector_rank"] is not None
            else missing_rank,
            item["source_page"],
            item["chunk_id"],
        )
    )
    return fused[:context_k], unresolved_rule_pages


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
    retrieval_mode: str = "vector",
    vector_pool_k: int | None = None,
    context_k: int | None = None,
    rrf_rule_weight: float | None = None,
    rrf_vector_weight: float | None = None,
    rrf_constant: int | None = None,
    unresolved_rule_pages: list[int] | None = None,
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
        item = {
            "shadow_evidence_id": f"shadow-chunk:{chunk_id}",
            "chunk_id": chunk_id,
            "source_page": source_page,
            "score": float(hit.get("score") or 0.0),
            "text": text[:max_chunk_chars],
        }
        for field_name in (
            "retrieval_sources",
            "rule_rank",
            "vector_rank",
            "fusion_score",
        ):
            if field_name in hit:
                item[field_name] = hit[field_name]
        evidence.append(item)

    hash_payload = {
        "report_id": report_id,
        "requirement_id": requirement_id,
        "requirement_text": requirement_text.strip(),
        "provider": provider,
        "model": model,
        "prompt_version": SHADOW_PROMPT_VERSION,
        "evidence": evidence,
    }
    if retrieval_mode == "hybrid_rrf":
        hash_payload.update(
            {
                "retrieval_mode": retrieval_mode,
                "vector_pool_k": vector_pool_k,
                "context_k": context_k,
                "rrf_rule_weight": rrf_rule_weight,
                "rrf_vector_weight": rrf_vector_weight,
                "rrf_constant": rrf_constant,
                "unresolved_rule_pages": parse_page_list(
                    unresolved_rule_pages
                ),
            }
        )
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
    retrieval_mode: str = "vector",
    report_chunks: Sequence[object] | None = None,
    vector_pool_k: int = DEFAULT_VECTOR_POOL_K,
    context_k: int = DEFAULT_CONTEXT_K,
    rrf_rule_weight: float = DEFAULT_RRF_RULE_WEIGHT,
    rrf_vector_weight: float = DEFAULT_RRF_VECTOR_WEIGHT,
    rrf_constant: int = DEFAULT_RRF_CONSTANT,
) -> list[dict[str, Any]]:
    if retrieval_mode not in {"vector", "hybrid_rrf"}:
        raise ValueError("unsupported retrieval_mode")
    if retrieval_mode == "hybrid_rrf" and report_chunks is None:
        raise ValueError("hybrid_rrf requires report_chunks")
    if retrieval_mode == "hybrid_rrf" and not report_chunks:
        raise ValueError("hybrid_rrf requires document chunks")
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
            vector_hits = [
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
            unresolved_rule_pages: list[int] = []
            if retrieval_mode == "hybrid_rrf":
                hits, unresolved_rule_pages = fuse_shadow_hits(
                    rule_pages=parse_page_list(row.get("rule_pages")),
                    vector_hits=vector_hits,
                    report_chunks=report_chunks or [],
                    vector_pool_k=vector_pool_k,
                    context_k=context_k,
                    rule_weight=rrf_rule_weight,
                    vector_weight=rrf_vector_weight,
                    rrf_constant=rrf_constant,
                )
            else:
                hits = vector_hits
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
                    retrieval_mode=retrieval_mode,
                    vector_pool_k=(
                        vector_pool_k
                        if retrieval_mode == "hybrid_rrf"
                        else None
                    ),
                    context_k=(
                        context_k
                        if retrieval_mode == "hybrid_rrf"
                        else None
                    ),
                    rrf_rule_weight=(
                        rrf_rule_weight
                        if retrieval_mode == "hybrid_rrf"
                        else None
                    ),
                    rrf_vector_weight=(
                        rrf_vector_weight
                        if retrieval_mode == "hybrid_rrf"
                        else None
                    ),
                    rrf_constant=(
                        rrf_constant
                        if retrieval_mode == "hybrid_rrf"
                        else None
                    ),
                    unresolved_rule_pages=unresolved_rule_pages,
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
    parser.add_argument(
        "--retrieval-mode",
        choices=("vector", "hybrid_rrf"),
        default="vector",
    )
    parser.add_argument(
        "--vector-pool-k",
        type=int,
        default=DEFAULT_VECTOR_POOL_K,
    )
    parser.add_argument(
        "--context-k",
        type=int,
        default=DEFAULT_CONTEXT_K,
    )
    parser.add_argument(
        "--rrf-rule-weight",
        type=float,
        default=DEFAULT_RRF_RULE_WEIGHT,
    )
    parser.add_argument(
        "--rrf-vector-weight",
        type=float,
        default=DEFAULT_RRF_VECTOR_WEIGHT,
    )
    parser.add_argument(
        "--rrf-constant",
        type=int,
        default=DEFAULT_RRF_CONSTANT,
    )
    args = parser.parse_args(argv)
    report_chunks = None
    if args.retrieval_mode == "hybrid_rrf":
        with SessionLocal() as session:
            report_chunks = Repository(session).list_document_chunks(
                report_id=args.report_id
            )
    contexts = load_shadow_contexts_from_cases(
        args.retrieval_cases,
        report_id=args.report_id,
        max_chunk_chars=args.max_chunk_chars,
        retrieval_mode=args.retrieval_mode,
        report_chunks=report_chunks,
        vector_pool_k=args.vector_pool_k,
        context_k=args.context_k,
        rrf_rule_weight=args.rrf_rule_weight,
        rrf_vector_weight=args.rrf_vector_weight,
        rrf_constant=args.rrf_constant,
    )
    output_path = write_shadow_contexts(
        contexts,
        output=args.output,
    )
    print(
        json.dumps(
            {
                "contexts": len(contexts),
                "retrieval_mode": args.retrieval_mode,
                "output": str(output_path),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
