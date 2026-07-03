import json
from collections.abc import Callable
from typing import Any

from openai import OpenAI


class ModelCallBlocked(RuntimeError):
    pass


CompletionFactory = Callable[[str], dict[str, Any]]


class LLMClient:
    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        completion_factory: CompletionFactory | None = None,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.completion_factory = completion_factory

    def complete_json(self, prompt: str, confirm_llm: bool) -> dict[str, Any]:
        if not confirm_llm:
            raise ModelCallBlocked("external model call requires confirm_llm=true")

        if self.completion_factory is not None:
            return self.completion_factory(prompt)

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)