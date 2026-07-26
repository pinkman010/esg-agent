import argparse
import hashlib
from collections.abc import Sequence

from src.config.settings import get_settings
from src.db.repositories import Repository
from src.db.session import SessionLocal
from src.domain.embedding_models import ChunkEmbedding
from src.tools.embedding_client import EmbeddingCallBlocked, EmbeddingClient


def normalize_embedding_input(text: str, *, max_chars: int) -> str:
    normalized = " ".join(text.split()).strip()
    if not normalized:
        raise ValueError("embedding input must not be empty")
    return normalized[:max_chars]


def chunk_embedding_input_hash(
    text: str,
    *,
    provider: str,
    model: str,
) -> str:
    payload = f"{provider}\n{model}\n{text}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def embed_pending_chunks(
    *,
    report_id: str,
    limit: int = 128,
) -> dict[str, int]:
    settings = get_settings()
    if not settings.embedding_enabled:
        raise EmbeddingCallBlocked(
            "external embedding call requires EMBEDDING_ENABLED=true"
        )
    client = EmbeddingClient(
        model=settings.embedding_model,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_api_base,
        expected_dim=settings.embedding_dim,
        timeout_seconds=settings.embedding_timeout_seconds,
        max_retries=settings.embedding_max_retries,
        retry_delay_seconds=settings.embedding_retry_delay_seconds,
    )
    succeeded = 0
    failed = 0
    with SessionLocal() as session:
        repo = Repository(session)
        chunks = repo.list_chunks_missing_embeddings(
            provider=settings.embedding_provider,
            model=settings.embedding_model,
            report_id=report_id,
            limit=limit,
        )
        for start in range(0, len(chunks), settings.embedding_batch_size):
            batch = chunks[start : start + settings.embedding_batch_size]
            texts = [
                normalize_embedding_input(
                    chunk.text,
                    max_chars=settings.embedding_max_input_chars,
                )
                for chunk in batch
            ]
            try:
                result = client.embed_texts(
                    texts,
                    embedding_enabled=settings.embedding_enabled,
                )
                for chunk, normalized_text, vector in zip(
                    batch,
                    texts,
                    result.embeddings,
                    strict=True,
                ):
                    repo.upsert_chunk_embedding(
                        ChunkEmbedding(
                            chunk_id=chunk.chunk_id,
                            provider=settings.embedding_provider,
                            model=settings.embedding_model,
                            embedding_dim=len(vector),
                            embedding=vector,
                            input_hash=chunk_embedding_input_hash(
                                normalized_text,
                                provider=settings.embedding_provider,
                                model=settings.embedding_model,
                            ),
                            status="succeeded",
                            usage=result.usage,
                            latency_ms=result.latency_ms,
                            retry_count=result.retry_count,
                        )
                    )
                    succeeded += 1
            except Exception as exc:
                for chunk, normalized_text in zip(batch, texts, strict=True):
                    repo.upsert_chunk_embedding(
                        ChunkEmbedding(
                            chunk_id=chunk.chunk_id,
                            provider=settings.embedding_provider,
                            model=settings.embedding_model,
                            embedding_dim=settings.embedding_dim,
                            embedding=None,
                            input_hash=chunk_embedding_input_hash(
                                normalized_text,
                                provider=settings.embedding_provider,
                                model=settings.embedding_model,
                            ),
                            status="failed",
                            error_code=getattr(
                                exc,
                                "error_code",
                                "embedding_batch_failed",
                            ),
                            error_message=str(exc),
                            usage={},
                            latency_ms=None,
                            retry_count=getattr(exc, "retry_count", 0),
                        )
                    )
                    failed += 1
    return {"succeeded": succeeded, "failed": failed}


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-id", required=True)
    parser.add_argument("--limit", type=int, default=128)
    args = parser.parse_args(argv)
    result = embed_pending_chunks(
        report_id=args.report_id,
        limit=args.limit,
    )
    print(result)


if __name__ == "__main__":
    main()
