"""Model client abstraction.

The crew talks to a model through this narrow interface, so the loop can run
fully offline in tests with a deterministic client, or against a real model in
production. Dependency injection keeps the deterministic core and the loop free
of hard external calls.
"""

from __future__ import annotations

from typing import Protocol


class ModelClient(Protocol):
    def generate(self, system: str, prompt: str) -> str: ...


class DeterministicModelClient:
    """An offline client that returns parseable, scripted reasoning.

    It is enough to exercise the full Understudy Loop without an API key. The
    planner role gets a short ReAct trace that ends in a final proposal. The
    scribe role gets a small ordered playbook. A real client (see
    AnthropicModelClient) replaces this in production.
    """

    def generate(self, system: str, prompt: str) -> str:
        if "ROLE: planner" in system:
            return (
                "THOUGHT: follow the confirmed playbook for this task class\n"
                "FINAL: proceed with the planned action using the playbook steps"
            )
        if "ROLE: scribe" in system:
            return (
                "STEP: read the request and gather the relevant context\n"
                "STEP: apply the team standard for this task class\n"
                "STEP: produce the result and record the decision"
            )
        return "FINAL: ok"


class AnthropicModelClient:
    """A thin real client. It is optional and only imported when used.

    It is kept out of the offline path on purpose, so the core and the loop run
    with no network and no key. Provide a model id and an api key to use it.
    """

    def __init__(self, model: str = "claude-sonnet-4-6", api_key: str = "", client: object = None) -> None:
        self.model = model
        self.api_key = api_key
        self._client = client

    def _ensure_client(self) -> None:
        if self._client is None:
            try:
                import anthropic
            except ImportError as error:
                raise RuntimeError(
                    "the anthropic package is required for AnthropicModelClient"
                ) from error
            self._client = anthropic.Anthropic(api_key=self.api_key or None)

    def generate(self, system: str, prompt: str) -> str:
        self._ensure_client()
        message = self._client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in message.content if block.type == "text")
