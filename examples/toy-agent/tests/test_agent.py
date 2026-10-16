"""The agent suite as it stands before the quickstart walkthrough."""

from __future__ import annotations

from toy_agent.agent import FakeClient, run_agent


def test_agent_finishes() -> None:
    client = FakeClient([{"action": "finish"}])
    assert run_agent(client, "hi") == {"status": "done", "history": []}
