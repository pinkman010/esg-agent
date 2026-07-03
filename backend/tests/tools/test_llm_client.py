import pytest

from src.tools.llm_client import LLMClient, ModelCallBlocked


def test_llm_client_blocks_external_call_without_confirmation():
    client = LLMClient(model="deepseek-v4-flash", completion_factory=lambda _prompt: {"ok": True})

    with pytest.raises(ModelCallBlocked):
        client.complete_json("judge disclosure", confirm_llm=False)


def test_llm_client_uses_injected_completion_factory_when_confirmed():
    calls = []

    def fake_completion(prompt):
        calls.append(prompt)
        return {"verdict": "disclosed"}

    client = LLMClient(model="deepseek-v4-flash", completion_factory=fake_completion)

    result = client.complete_json("judge disclosure", confirm_llm=True)

    assert result == {"verdict": "disclosed"}
    assert calls == ["judge disclosure"]