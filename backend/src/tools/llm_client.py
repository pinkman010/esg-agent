import json
import time
from collections.abc import Callable
from typing import Any

from openai import APIConnectionError, APITimeoutError, OpenAI
from pydantic import BaseModel


class ModelCallBlocked(RuntimeError):
    pass


class LLMCompletionError(RuntimeError):
    def __init__(self, *, error_code: str, retry_count: int):
        super().__init__(f"LLM completion failed ({error_code})")
        self.error_code = error_code
        self.retry_count = retry_count


class LLMCompletionResult(BaseModel):
    content: dict[str, Any]
    model: str
    finish_reason: str | None
    usage: dict[str, Any]
    latency_ms: int
    retry_count: int


class _RetryableCompletionError(RuntimeError):
    def __init__(self, error_code: str):
        super().__init__(error_code)
        self.error_code = error_code


CompletionFactory = Callable[..., Any]


class LLMClient:
    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        completion_factory: CompletionFactory | None = None,
        *,
        thinking_type: str = "enabled",
        reasoning_effort: str = "high",
        response_format: str = "json_object",
        max_tokens: int = 4096,
        timeout_seconds: int = 120,
        max_retries: int = 2,
        retry_delay_seconds: float = 2,
        sleep_fn: Callable[[float], None] = time.sleep,
        clock_fn: Callable[[], float] = time.monotonic,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.completion_factory = completion_factory
        self.thinking_type = thinking_type
        self.reasoning_effort = reasoning_effort
        self.response_format = response_format
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.sleep_fn = sleep_fn
        self.clock_fn = clock_fn

    def complete_json(
        self,
        *,
        messages: list[dict[str, str]],
        confirm_llm: bool,
    ) -> LLMCompletionResult:
        if not confirm_llm:
            raise ModelCallBlocked("external model call requires confirm_llm=true")

        completion = self.completion_factory
        if completion is None:
            client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout_seconds,
            )
            completion = client.chat.completions.create

        request: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": self.response_format},
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        if self.thinking_type:
            request["extra_body"] = {"thinking": {"type": self.thinking_type}}
        if self.thinking_type == "enabled":
            request["reasoning_effort"] = self.reasoning_effort

        started_at = self.clock_fn()
        retry_count = 0
        while True:
            try:
                response = completion(**request)
                result = self._parse_response(response, retry_count, started_at)
                return result
            except Exception as exc:
                error_code, retryable = self._classify_error(exc)
                if not retryable or retry_count >= self.max_retries:
                    raise LLMCompletionError(
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
    ) -> LLMCompletionResult:
        choices = getattr(response, "choices", None) or []
        if not choices:
            raise _RetryableCompletionError("llm_empty_content")
        choice = choices[0]
        finish_reason = getattr(choice, "finish_reason", None)
        if finish_reason == "length":
            raise _RetryableCompletionError("llm_response_truncated")
        content = getattr(getattr(choice, "message", None), "content", None)
        if not content or not str(content).strip():
            raise _RetryableCompletionError("llm_empty_content")
        try:
            parsed = json.loads(content)
        except (TypeError, json.JSONDecodeError):
            raise _RetryableCompletionError("llm_invalid_json") from None
        if not isinstance(parsed, dict):
            raise _RetryableCompletionError("llm_invalid_json")

        return LLMCompletionResult(
            content=parsed,
            model=str(getattr(response, "model", None) or self.model),
            finish_reason=finish_reason,
            usage=self._usage_dict(getattr(response, "usage", None)),
            latency_ms=max(0, round((self.clock_fn() - started_at) * 1000)),
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
            for name in ("prompt_tokens", "completion_tokens", "total_tokens")
            if getattr(usage, name, None) is not None
        }

    @staticmethod
    def _classify_error(exc: Exception) -> tuple[str, bool]:
        if isinstance(exc, _RetryableCompletionError):
            return exc.error_code, True
        if isinstance(exc, (APIConnectionError, APITimeoutError, TimeoutError, ConnectionError)):
            return "llm_connection_error", True

        status_code = getattr(exc, "status_code", None)
        if status_code == 429:
            return "llm_rate_limited", True
        if status_code in {500, 503}:
            return "llm_server_error", True
        if status_code in {400, 401, 402, 422}:
            return "llm_request_rejected", False
        return "llm_call_failed", False
