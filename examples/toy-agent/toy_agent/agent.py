"""A tiny agent loop whose decisions depend on model output.

Used by the quickstart walkthrough in docs/QUICKSTART.md.
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_ERROR = 80


@dataclass
class ToolResult:
    ok: bool
    error: str = ""


class FakeClient:
    """Stands in for a chat model; replays scripted responses."""

    def __init__(self, responses: list[dict]) -> None:
        self._responses = list(responses)

    def complete(self, prompt: str) -> dict:  # harness:llm-source
        return self._responses.pop(0)


def truncate(error: str) -> str:
    if len(error) > MAX_ERROR:
        return error[:MAX_ERROR] + "..."
    return error


def run_tool(action: str) -> ToolResult:
    if action == "add":
        return ToolResult(ok=True)
    return ToolResult(ok=False, error="unknown action: " + "x" * 100)


def run_agent(client: FakeClient, prompt: str, max_steps: int = 3) -> dict:
    history: list[str] = []
    for _ in range(max_steps):
        response = client.complete(prompt)
        action = response.get("action")
        if action is None:
            return {"status": "no_action", "history": history}
        if action == "finish":
            return {"status": "done", "history": history}
        result = run_tool(action)
        if not result.ok:
            history.append(truncate(result.error))
            continue
        history.append("ok:" + action)
    return {"status": "max_steps", "history": history}
