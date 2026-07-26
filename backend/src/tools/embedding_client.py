import time
from collections.abc import Callable
from typing import Any

from openai import APIConnectionError, APITimeoutError, OpenAI
from pydantic import BaseModel


class EmbeddingCallBlocked(RuntimeError):
    pass


class EmbeddingClientError(RuntimeError):
    def __init__(self, *, error_code: str, retry_count: int):
        super().__init__(f"Embedding request failed ({error_code})")
        self.error_code = error_code
        self.retry_count = retry_count


class EmbeddingResult(BaseModel):
    embeddings: list[list[float]]
    model: str
    usage: dict[str, Any]
    latency_ms: int
    retry_count: int


EmbeddingFactory = Callable[..., Any]


class EmbeddingClient:
    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        embedding_factory: EmbeddingFactory | None = None,
        *,
        expected_dim: int = 1024,
        timeout_seconds: int = 60,
        max_retries: int = 2,
        retry_delay_seconds: float = 2,
        sleep_fn: Callable[[float], None] = time.sleep,
        clock_fn: Callable[[], float] = time.monotonic,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.embedding_factory = embedding_factory
        self.expected_dim = expected_dim
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.sleep_fn = sleep_fn
        self.clock_fn = clock_fn

    def embed_texts(
        self,
        texts: list[str],
        *,
        embedding_enabled: bool,
    ) -> EmbeddingResult:
        if not embedding_enabled:
            raise EmbeddingCallBlocked(
                "external embedding call requires EMBEDDING_ENABLED=true"
            )
        if not texts or any(not text.strip() for text in texts):
            raise EmbeddingClientError(
                error_code="embedding_empty_input",
                retry_count=0,
            )

        embedding_create = self.embedding_factory
        if embedding_create is None:
            client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout_seconds,
            )
            embedding_create = client.embeddings.create

        request = {
            "model": self.model,
            "input": texts,
            "encoding_format": "float",
        }
        started_at = self.clock_fn()
        retry_count = 0
        while True:
            try:
                response = embedding_create(**request)
                return self._parse_response(
                    response,
                    retry_count,
                    started_at,
                    expected_count=len(texts),
                )
            except Exception as exc:
                error_code, retryable = self._classify_error(exc)
                if not retryable or retry_count >= self.max_retries:
                    raise EmbeddingClientError(
                        error_code=error_code,
                        retry_count=retry_count,
                    ) from None
                retry_count += 1
                if self.retry_delay_seconds:
                    self.sleep_fn(self.retry_delay_seconds)

    def _parse_response(
        self,
        response: Any,
        retry_count: int,
        started_at: float,
        *,
        expected_count: int,
    ) -> EmbeddingResult:
        data = sorted(
            getattr(response, "data", None) or [],
            key=lambda item: getattr(item, "index", 0),
        )
        embeddings = [
            list(getattr(item, "embedding", []) or [])
            for item in data
        ]
        if not embeddings:
            raise EmbeddingClientError(
                error_code="embedding_empty_response",
                retry_count=retry_count,
            )
        if len(embeddings) != expected_count:
            raise EmbeddingClientError(
                error_code="embedding_count_mismatch",
                retry_count=retry_count,
            )
        if any(len(vector) != self.expected_dim for vector in embeddings):
            raise EmbeddingClientError(
                error_code="embedding_dimension_mismatch",
                retry_count=retry_count,
            )
        return EmbeddingResult(
            embeddings=embeddings,
            model=str(getattr(response, "model", None) or self.model),
            usage=self._usage_dict(getattr(response, "usage", None)),
            latency_ms=max(
                0,
                round((self.clock_fn() - started_at) * 1000),
            ),
            retry_count=retry_count,
        )

    @staticmethod
    def _usage_dict(usage: Any) -> dict[str, Any]:
        if usage is None:
            return {}
        if isinstance(usage, dict):
            return usage
        if hasattr(usage, "model_dump"):
            return usage.model_dump(exclude_none=True)
        return {
            name: getattr(usage, name)
            for name in (
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
            )
            if getattr(usage, name, None) is not None
        }

    @staticmethod
    def _classify_error(exc: Exception) -> tuple[str, bool]:
        if isinstance(exc, EmbeddingClientError):
            return exc.error_code, False
        if isinstance(
            exc,
            (
                APIConnectionError,
                APITimeoutError,
                TimeoutError,
                ConnectionError,
            ),
        ):
            return "embedding_connection_error", True
        status_code = getattr(exc, "status_code", None)
        if status_code == 429:
            return "embedding_rate_limited", True
        if status_code in {500, 503, 504}:
            return "embedding_server_error", True
        if status_code in {400, 401, 402, 403, 404, 422}:
            return "embedding_request_rejected", False
        return "embedding_call_failed", False
