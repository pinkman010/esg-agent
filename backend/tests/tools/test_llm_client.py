import json
from types import SimpleNamespace

import pytest

from src.tools.llm_client import LLMClient, LLMCompletionError, ModelCallBlocked


MESSAGES = [
    {
        "role": "system",
        "content": (
            "Return json only. Example JSON output: "
            '{"verdict":"disclosed","confidence":0.9}'
        ),
    },
    {"role": "user", "content": "Judge the supplied disclosure evidence."},
]


def _response(
    content: str | None = '{"verdict":"disclosed"}',
    *,
    finish_reason: str = "stop",
    model: str = "deepseek-v4-flash",
):
    return SimpleNamespace(
        model=model,
        choices=[
            SimpleNamespace(
                finish_reason=finish_reason,
                message=SimpleNamespace(content=content),
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        ),
    )


class FakeAPIError(RuntimeError):
    def __init__(self, status_code: int, message: str = "provider error"):
        super().__init__(message)
        self.status_code = status_code


def test_llm_client_blocks_external_call_without_confirmation():
    calls = []
    client = LLMClient(
        model="deepseek-v4-flash",
        completion_factory=lambda **kwargs: calls.append(kwargs),
    )

    with pytest.raises(ModelCallBlocked):
        client.complete_json(messages=MESSAGES, confirm_llm=False)

    assert calls == []


def test_llm_client_sends_deepseek_json_and_thinking_parameters():
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return _response()

    client = LLMClient(
        model="deepseek-v4-flash",
        completion_factory=fake_completion,
        sleep_fn=lambda _seconds: None,
    )

    result = client.complete_json(messages=MESSAGES, confirm_llm=True)

    assert result.content == {"verdict": "disclosed"}
    assert len(calls) == 1
    request = calls[0]
    assert request["response_format"] == {"type": "json_object"}
    assert request["extra_body"] == {"thinking": {"type": "enabled"}}
    assert request["reasoning_effort"] == "high"
    assert request["max_tokens"] == 4096
    assert "temperature" not in request
    assert [message["role"] for message in request["messages"]] == ["system", "user"]
    assert "json" in request["messages"][0]["content"].lower()
    assert "example" in request["messages"][0]["content"].lower()


@pytest.mark.parametrize(
    ("first_result", "expected_error_code"),
    [
        (_response(finish_reason="length"), "llm_response_truncated"),
        (_response(content=""), "llm_empty_content"),
        (_response(content="not-json"), "llm_invalid_json"),
        (FakeAPIError(429), "llm_rate_limited"),
        (FakeAPIError(500), "llm_server_error"),
        (FakeAPIError(503), "llm_server_error"),
        (TimeoutError("connect timeout"), "llm_connection_error"),
    ],
)
def test_llm_client_retries_transient_failures_twice(first_result, expected_error_code):
    calls = []

    def always_fail(**kwargs):
        calls.append(kwargs)
        if isinstance(first_result, Exception):
            raise first_result
        return first_result

    client = LLMClient(
        model="deepseek-v4-flash",
        completion_factory=always_fail,
        max_retries=2,
        retry_delay_seconds=0,
        sleep_fn=lambda _seconds: None,
    )

    with pytest.raises(LLMCompletionError) as exc_info:
        client.complete_json(messages=MESSAGES, confirm_llm=True)

    assert exc_info.value.error_code == expected_error_code
    assert exc_info.value.retry_count == 2
    assert len(calls) == 3


@pytest.mark.parametrize("status_code", [400, 401, 402, 422])
def test_llm_client_does_not_retry_terminal_http_errors(status_code):
    calls = []

    def reject(**kwargs):
        calls.append(kwargs)
        raise FakeAPIError(status_code, "secret-key-must-not-leak")

    client = LLMClient(
        model="deepseek-v4-flash",
        api_key="secret-key-must-not-leak",
        completion_factory=reject,
        max_retries=2,
        retry_delay_seconds=0,
    )

    with pytest.raises(LLMCompletionError) as exc_info:
        client.complete_json(messages=MESSAGES, confirm_llm=True)

    assert exc_info.value.error_code == "llm_request_rejected"
    assert exc_info.value.retry_count == 0
    assert len(calls) == 1
    assert "secret-key-must-not-leak" not in str(exc_info.value)


def test_llm_client_returns_response_metadata_after_retry():
    responses = [TimeoutError("connect timeout"), _response()]

    def complete(**_kwargs):
        result = responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    client = LLMClient(
        model="deepseek-v4-flash",
        completion_factory=complete,
        max_retries=2,
        retry_delay_seconds=0,
        sleep_fn=lambda _seconds: None,
    )

    result = client.complete_json(messages=MESSAGES, confirm_llm=True)

    assert result.model == "deepseek-v4-flash"
    assert result.finish_reason == "stop"
    assert result.usage == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }
    assert result.latency_ms >= 0
    assert result.retry_count == 1
    assert json.loads(result.model_dump_json())["content"]["verdict"] == "disclosed"
