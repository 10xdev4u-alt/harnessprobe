# Quickstart

Five minutes, one toy agent, real numbers. The example lives in
`examples/toy-agent/`; every transcript below was captured from an actual run.
The transcripts show the capture directory `/tmp/toy-run2`; the path varies
with your checkout.

## The toy agent

`toy_agent/agent.py` is a minimal agent loop: a scripted model client, a
tool dispatch, error truncation, and a step limit. One method carries the
`# harness:llm-source` annotation, which marks it as the model boundary:

```python
    def complete(self, prompt: str) -> dict:  # harness:llm-source
        return self._responses.pop(0)
```

The tests in `tests/test_agent.py` cover only the happy path, on purpose.

## 1. Install

HarnessProbe is not on PyPI yet; install it from the repository:

```console
$ pip install git+https://github.com/10xdev4u-alt/harnessprobe
```

## 2. Scope the repo

```console
$ cd examples/toy-agent
$ harnessprobe init .
HarnessProbe scope for /tmp/toy-run2 (tier B: on)
sources: 0 model-call sites, 1 annotation sites
candidates: 1 files, 9 lines
confidence: authoritative=1, allowlisted=0, heuristic-high=0, heuristic-low=0
note: annotations are user-declared; treated as authoritative
wrote /tmp/toy-run2/harnessprobe.scope.json
```

Commit `harnessprobe.scope.json`. It pins the LDH line set the plugin measures.

## 3. Measure

Run the suite the way you already do, with coverage:

```console
$ coverage run --branch -m pytest tests -q
.                                                                        [100%]harnessprobe: LDH scope coverage 6/9 lines (66.67%), 3 uncovered samples
harnessprobe: report written to /tmp/toy-run2/harnessprobe.report.json

1 passed in 0.05s
```

The plugin activates on the scope file and writes `harnessprobe.report/v1`.
No test changes were needed.

## 4. Read the report

```console
$ harnessprobe comment --report harnessprobe.report.json
### HarnessProbe: no bug classes caught

No findings were attached to this run. HarnessProbe v1 ships LDH coverage subsetting; differential bug detection lands in later phases.

### LDH coverage

`66.67%` of LDH scope lines covered (6/9; 0 not measured)
Branches: 2 full / 4 partial / 3 missing

<details><summary>Top uncovered LDH lines</summary>

- `toy_agent/agent.py:36` — `if action == "add":`
- `toy_agent/agent.py:50` — `result = run_tool(action)`
- `toy_agent/agent.py:54` — `history.append("ok:" + action)`

</details>

_harnessprobe · report harnessprobe.report/v1_
```

The verdict is narrow and explicit: 66.67% of the LDH lines ran. The uncovered
lines are the tool dispatch and the success path of the loop — exactly the
decisions a happy-path test skips.

## 5. Close the gaps

Replace `tests/test_agent.py` with the full suite:

```python
"""The agent suite after the walkthrough closes the uncovered LDH branches."""

from __future__ import annotations

from toy_agent.agent import FakeClient, run_agent, truncate


def test_agent_finishes() -> None:
    client = FakeClient([{"action": "finish"}])
    assert run_agent(client, "hi") == {"status": "done", "history": []}


def test_agent_reports_missing_action() -> None:
    client = FakeClient([{}])
    assert run_agent(client, "hi") == {"status": "no_action", "history": []}


def test_agent_truncates_unknown_action_errors() -> None:
    client = FakeClient([{"action": "explode"}, {"action": "finish"}])
    result = run_agent(client, "hi")
    assert result["status"] == "done"
    assert result["history"] == [truncate("unknown action: " + "x" * 100)]


def test_agent_stops_at_max_steps() -> None:
    client = FakeClient([{"action": "add"}, {"action": "add"}, {"action": "add"}])
    result = run_agent(client, "hi")
    assert result["status"] == "max_steps"
    assert result["history"] == ["ok:add", "ok:add", "ok:add"]


def test_truncate_keeps_short_errors() -> None:
    assert truncate("short") == "short"
```

Rerun:

```console
$ coverage erase && coverage run --branch -m pytest tests -q
.....                                                                    [100%]harnessprobe: LDH scope coverage 9/9 lines (100.00%), 0 uncovered samples
harnessprobe: report written to /tmp/toy-run2/harnessprobe.report.json

5 passed in 0.06s
```

```console
$ harnessprobe comment --report harnessprobe.report.json
### HarnessProbe: no bug classes caught

No findings were attached to this run. HarnessProbe v1 ships LDH coverage subsetting; differential bug detection lands in later phases.

### LDH coverage

`100.00%` of LDH scope lines covered (9/9; 0 not measured)
Branches: 6 full / 3 partial / 0 missing

_harnessprobe · report harnessprobe.report/v1_
```

## 6. Gate it in CI

```console
$ harnessprobe gate --report harnessprobe.report.json --min-coverage 60
harnessprobe gate: passed
```

The composite action runs the same gate on every pull request and keeps one
sticky comment current; see `docs/GITHUB_ACTION.md`.

## What the numbers mean, and do not

- The scope is a superset by design. Here the annotation makes it precise;
  without annotations, heuristics guess (see `docs/SCOPE_FILE.md`).
- 66.67% is not "the tests are bad"; it is "of the lines this product calls
  LDH, this run executed two thirds". The uncovered list names exactly what
  was skipped.
- The after-run reports 6 full / 3 partial branches at 100% lines. The three
  partials are arcs the parser knows (straight-line fallthrough, the loop
  back-edge) that coverage.py does not instrument; no conditional direction is
  untaken. The classification is tracked for tightening in #96.
- `not_measured` lines are scope lines absent from the coverage data entirely
  (never-imported files). They are reported, never counted as uncovered.
- v1 measures coverage and renders findings; it detects no bugs. The comment
  says so in its first line.

## Next steps

- `docs/SCOPE_FILE.md` — scope format, confidence classes, allowlists.
- `docs/PR_COMMENT.md` — findings format and the comment contract.
- `docs/GITHUB_ACTION.md` — the action, inputs, and gate semantics.
