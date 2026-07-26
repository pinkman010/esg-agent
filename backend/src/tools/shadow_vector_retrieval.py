import argparse
import csv
from collections.abc import Sequence
from pathlib import Path

from src.config.settings import PROJECT_ROOT, get_settings
from src.db.repositories import Repository
from src.db.session import SessionLocal
from src.tools.embed_document_chunks import normalize_embedding_input
from src.tools.embedding_client import EmbeddingClient


def resolve_shadow_output(output: str) -> Path:
    output_root = (PROJECT_ROOT / "tmp" / "embedding").resolve()
    resolved = (PROJECT_ROOT / output).resolve()
    if not resolved.is_relative_to(output_root):
        raise ValueError("shadow output must stay under tmp/embedding")
    return resolved


def shadow_search(
    query: str,
    *,
    report_id: str,
    top_k: int,
) -> list[dict]:
    if top_k < 1:
        raise ValueError("top_k must be positive")
    settings = get_settings()
    client = EmbeddingClient(
        model=settings.embedding_model,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_api_base,
        expected_dim=settings.embedding_dim,
        timeout_seconds=settings.embedding_timeout_seconds,
        max_retries=settings.embedding_max_retries,
        retry_delay_seconds=settings.embedding_retry_delay_seconds,
    )
    normalized_query = normalize_embedding_input(
        query,
        max_chars=settings.embedding_max_input_chars,
    )
    embedding_result = client.embed_texts(
        [normalized_query],
        embedding_enabled=settings.embedding_enabled,
    )
    query_embedding = embedding_result.embeddings[0]
    with SessionLocal() as session:
        repo = Repository(session)
        results = repo.search_chunk_embeddings(
            provider=settings.embedding_provider,
            model=settings.embedding_model,
            query_embedding=query_embedding,
            report_id=report_id,
            limit=top_k,
        )
    return [item.model_dump(mode="json") for item in results]


def write_csv(rows: list[dict], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "chunk_id",
        "report_id",
        "source_page",
        "score",
        "source_file_hash",
        "text",
    ]
    with output.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {name: row.get(name, "") for name in fieldnames}
            )


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--report-id", required=True)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument(
        "--output",
        default="tmp/embedding/shadow_vector_retrieval.csv",
    )
    args = parser.parse_args(argv)
    rows = shadow_search(
        args.query,
        report_id=args.report_id,
        top_k=args.top_k,
    )
    output = resolve_shadow_output(args.output)
    write_csv(rows, output)
    print({"rows": len(rows), "output": str(output)})


if __name__ == "__main__":
    main()
