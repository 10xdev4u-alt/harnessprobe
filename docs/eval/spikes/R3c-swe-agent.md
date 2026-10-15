# R3c: LDH-scoped coverage subsetting on SWE-agent

## Context

Spike R3c of the HarnessProbe evaluation. It measures how much of SWE-agent's
LLM-dependent harness (LDH) code its own unit suite executes, using the same
Tier A/B scope algorithm as spike R3 (browser-use) so the per-repo numbers can
be compared. Prior knowledge from `docs/research/05-field-study.md`: SWE-agent
ships scripted models in product code (`PredeterminedTestModel`), uses litellm
`mock_response` and `patch("litellm.completion")`, drives recorded `.traj`
replays through `run-replay`, and its CI already runs pytest-cov (SWE-agent and
OpenHands are the only repos in the field study with coverage instrumentation).

## Method

Pinned commit: `3ea751c087f32b16e039a2233dd6eefecef325d5` (shallow clone of
`https://github.com/SWE-agent/SWE-agent`, `git rev-parse HEAD`).

Environment: Python 3.14.7 (pyproject requires `>=3.11`), venv at
`/tmp/hp-eval/venvs/swe`, `uv pip install -e .` plus pytest and coverage. The
full editable install worked; no fallback needed. Machine load during the run
was roughly 2-5 on 4 cores from unrelated processes. Coverage values are
deterministic; load only affects wall time.

Test selection: `tests/` with `-m "not slow"`, the largest offline unit subset
(131 collected, 111 selected, 20 deselected by the `slow` marker). Network-
looking tests (`test_problem_statement_multimodal.py`, `test_swesmith.py`)
patch `requests.get` or mock GitHub URLs and do not leave the machine. First
run: 105 passed, 4 failed, 2 xfailed, 226.35 s. All 4 failures were
`FileNotFoundError` from `subprocess.run(["sweagent", ...])` in
`tests/test_run.py` and `tests/test_run_replay.py` because the venv `bin` was
not on `PATH`. Rerunning exactly those 4 tests with
`PATH=/tmp/hp-eval/venvs/swe/bin:$PATH` and `coverage run --append` passed all
4 in 16.90 s, so the final measurement has zero unexplained failures and the
failure was an environment artifact, not a repo barrier.

LDH scope, extracted with the shared script
(`/tmp/hp-eval/artifacts/r3bc/ldh_scope.py`) from the package directory
`sweagent/` only. The scope semantics match the R3 implementation
(`reports/R3-browser-use.md`, Method section):

- Tier A: statement lines of functions whose subtree contains (a) a call on an
  attribute chain matching
  `chat.completions.create|litellm.(a)?completion|.invoke(|.ainvoke(|.generate(`,
  or (b) an attribute/subscript read whose attr name or leftmost base
  identifier matches
  `^(parsed|action|tool_call|model_output|response|completion|tool_calls|function_call)`,
  case-insensitive, in either direction.
- Tier B: statement lines of functions calling a Tier A function by bare name
  in the same file, 1 hop; Tier A wins for a function that qualifies for both.
- Detection walks the whole function subtree including nested defs; line
  collection descends through control flow but stops at nested def/class
  bodies, which count as their own functions.

Commands (from `/tmp/hp-eval/repos/swe-agent`):

```
COVERAGE_FILE=/tmp/hp-eval/artifacts/r3bc/.coverage-swe \
  /tmp/hp-eval/venvs/swe/bin/python -m coverage run --branch --source=sweagent -m pytest tests -q -m "not slow"
PATH=/tmp/hp-eval/venvs/swe/bin:$PATH COVERAGE_FILE=/tmp/hp-eval/artifacts/r3bc/.coverage-swe \
  /tmp/hp-eval/venvs/swe/bin/python -m coverage run --append --branch --source=sweagent -m pytest \
  tests/test_run.py::test_run_cli_no_arg_error tests/test_run.py::test_run_cli_main_help \
  tests/test_run.py::test_run_cli_subcommand_help tests/test_run_replay.py::test_run_cli_help -q
COVERAGE_FILE=/tmp/hp-eval/artifacts/r3bc/.coverage-swe \
  /tmp/hp-eval/venvs/swe/bin/python -m coverage json -o coverage-swe.json
python /tmp/hp-eval/artifacts/r3bc/ldh_scope.py extract /tmp/hp-eval/repos/swe-agent sweagent scope-swe-agent.json
python /tmp/hp-eval/artifacts/r3bc/ldh_scope.py analyze scope-swe-agent.json coverage-swe.json /tmp/hp-eval/repos/swe-agent stats-swe-agent.json
```

One analysis bug surfaced and was fixed mid-spike: for SWE-agent, coverage
7.16.2 wrote repo-relative paths into `coverage json` (its working directory
was the repo root), while for Aider the paths were absolute. The analyzer now
normalizes both forms; the fix changes no covered/executed counts, it only made
the measured lines resolvable at all.

## Numbers

| Tier | AST stmt lines | Measured lines | Executed | Covered % | Branches full/partial/missing |
|---|---|---|---|---|---|
| Tier A | 597 | 583 | 278 | 47.68% | 26 / 47 / 51 |
| Tier B | 22 | 22 | 10 | 45.45% | 1 / 2 / 0 |
| Whole repo (reference) | 6077 | 6077 | 3246 | 53.4% | 556 / 1582 branches = 35.1% |

"Measured lines" = scope lines that coverage counts as statements (14 AST
lines are not statements, for example `else:` lines).

Per-file Tier A executed/measured, the input to the aggregate:

| File | Executed/measured | Note |
|---|---|---|
| sweagent/agent/agents.py | 81/110 | agent loop and parser selection, mostly executed |
| sweagent/agent/models.py | 70/143 | litellm seam, query and raise-command handling |
| sweagent/tools/parsing.py | 40/46 | tool-call parsing; best-covered LDH file |
| sweagent/agent/problem_statement.py | 29/38 | issue image fetching and conversion |
| sweagent/run/run_replay.py | 16/20 | `.traj` replay path, exercised by tests |
| sweagent/run/run_single.py | 14/27 | single-run setup |
| sweagent/run/run.py | 11/55 | false positive: `parsed_args.*` (argparse namespace) |
| sweagent/tools/tools.py | 9/11 | block-action guard |
| sweagent/tools/utils.py | 8/21 | `_guard_multiline_input` env-output handling |
| sweagent/agent/action_sampler.py | 0/52 | duplicate filtering and action selection unexecuted |
| sweagent/agent/reviewer.py | 0/33 | reviewer preselection unexecuted |
| sweagent/inspector/server.py | 0/21 | inspector server unexecuted |
| sweagent/run/inspector_cli.py | 0/6 | inspector CLI entry unexecuted |

Sensitivity, same coverage data, excluding the two files whose scope matches
are naming false positives (`run.py`, `inspector_cli.py`, both from
`parsed_args` in argparse setup): Tier A = 267/522 = 51.1%. The primary 47.68%
keeps the shared R3 algorithm untouched for cross-repo comparability.

## Samples

Uncovered Tier A lines (capped at 2 per file):

```
sweagent/agent/action_sampler.py:213     thoughts: list[str] = []
sweagent/agent/action_sampler.py:214     actions: list[str] = []
sweagent/agent/agents.py:468             self.tools.config.parse_function = ThoughtActionParser()
sweagent/agent/agents.py:470             self.tools.config.parse_function = ActionOnlyParser()
sweagent/agent/models.py:336             parts = shlex.split(action)
sweagent/agent/models.py:337             error_code = parts[1]
sweagent/agent/problem_statement.py:243  content_type = "image/jpeg"
sweagent/agent/problem_statement.py:256  logger.warning(f"Image too large (>{max_size} bytes) for URL: {url}")
sweagent/agent/reviewer.py:249           if not response:
sweagent/agent/reviewer.py:250           self.logger.warning("No response from preselector")
```

## What broke and caveats

- Nothing blocked the suite. The one failure cluster was the PATH artifact
  described in Method; the 4 affected CLI tests pass with the venv on PATH and
  their coverage was merged into the final data file.
- The 20 deselected `slow` tests were not run; `test_env.py` alone holds 8 of
  them. Environment-execution paths may move the numbers.
- The Tier A base-name regex misfires on `parsed_args` (argparse) in `run.py`
  and `inspector_cli.py`, adding 61 false-positive scope lines. Sensitivity
  number above. One genuine borderline: `problem_statement.py` reads HTTP
  `response` objects for issue images, which is input handling rather than
  model-output consumption; it was left in Tier A because the shared regex
  covers it.
- action_sampler (0/52) and reviewer (0/33) are the biggest genuine LDH gaps:
  duplicate-action filtering and reviewer preselection run only in e2e flows or
  replays not exercised by the unit subset, even though replay fixtures exist
  in the repo.
- One serial run per repo within the timebox; coverage percentages do not
  depend on load, so no repeats were taken. Wall times on this box (load 2-5 of
  4 cores) are upper bounds.
- Scope covers package code only; test code was not scanned.

## Reproduce

```
git clone --depth 1 https://github.com/SWE-agent/SWE-agent /tmp/hp-eval/repos/swe-agent
git -C /tmp/hp-eval/repos/swe-agent rev-parse HEAD   # expect 3ea751c087f32b16e039a2233dd6eefecef325d5
uv venv --python 3.14 /tmp/hp-eval/venvs/swe
uv pip install --python /tmp/hp-eval/venvs/swe/bin/python -e /tmp/hp-eval/repos/swe-agent pytest coverage
# then the five commands in Method (from the repo root)
```

Artifacts: `run-swe.log`, `run-swe-cli-retry.log`, `coverage-swe.json`,
`scope-swe-agent.json`, `stats-swe-agent.json`, `requirements-swe.txt`,
`ldh_scope.py`, `decisions.tsv` (all under `/tmp/hp-eval/artifacts/r3bc/`).

## Verdict

Method runs end to end; after the PATH fix there are zero unexplained
failures. SWE-agent's unit subset executes 47.68% of R3-scoped Tier A lines
(51.1% after removing argparse false positives), clearly ahead of Aider's 38.2%
(41.9%), and the uncovered half clusters in clearly named files (action_sampler,
reviewer, inspector). The method gives an actionable, trustworthy reading here;
the scope regex still needs precision work before numbers act as gates.
