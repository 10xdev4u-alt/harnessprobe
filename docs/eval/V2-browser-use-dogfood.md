# V2 dogfood: pytest plugin and action on browser-use

Status: completed. Date: 2026-10-16. Issue: #36. Target pinned at
`a71d5478e4187cbe5295aab6403dfe7e4a6861a4` (browser-use 0.13.11), the same
commit as the R3 spike (`docs/eval/spikes/R3-browser-use.md`).

The claim under test: HarnessProbe works in a real agent repository without
touching that repository's tests or configuration.

## Environment

`/tmp/hp-eval` was rebuilt from scratch for this run (venv recipe from the R3
spike):

```console
$ git clone --depth 1 https://github.com/browser-use/browser-use /tmp/hp-eval/repos/browser-use
$ git -C /tmp/hp-eval/repos/browser-use fetch --depth 1 origin a71d5478e4187cbe5295aab6403dfe7e4a6861a4
$ git -C /tmp/hp-eval/repos/browser-use checkout a71d5478e4187cbe5295aab6403dfe7e4a6861a4
$ uv venv --python /usr/bin/python3.14 /tmp/hp-eval/venvs/bu
$ uv pip install --python /tmp/hp-eval/venvs/bu/bin/python pytest pytest-asyncio pytest-httpserver \
    pydantic openai httpx coverage "pytest==9.0.2" "pytest-asyncio==1.3.0" "pytest-httpserver==1.1.3" \
    "pytest-xdist==3.8.0" "pytest-timeout==2.4.0"
$ uv pip install --python /tmp/hp-eval/venvs/bu/bin/python -e /tmp/hp-eval/repos/browser-use
$ uv pip install --python /tmp/hp-eval/venvs/bu/bin/python /home/princetheprogrammerbtw/harnessprobe
```

HarnessProbe is installed from a source checkout **non-editable**, the shape the
GitHub Action uses; the plugin arrives through its `pytest11` entry point.
Python 3.14.7, serial run, no xdist.

## Scope derivation

```console
$ harnessprobe init /tmp/hp-eval/repos/browser-use --out /tmp/hp-eval/reports/bu-heuristic.scope.json
sources: 36 model-call sites, 0 annotation sites
candidates: 87 files, 1816 lines
confidence: heuristic-high=87
```

No allowlist: the scope is the product's heuristic verdict on the raw repo. 87
files and 1286 of the 1816 raw lines turn out to be coverage-executable.

## Test selection and run

The 62-file selection pinned by R3 (`docs/eval/spikes/scripts/r3-selected-tests.txt`)
runs with a scrubbed environment. Provider keys are unset so the six
live-provider tests skip themselves, as in R3.

```console
$ cd /tmp/hp-eval/repos/browser-use
$ env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u FX_OPENAI_BASE_URL \
    PATH="/tmp/hp-eval/venvs/bu/bin:$PATH" \
    coverage run --branch -m pytest $(cat .../r3-selected-tests.txt) -q \
      -o addopts= -o log_cli=false -o timeout=60 \
      --harnessprobe-scope /tmp/hp-eval/reports/bu-heuristic.scope.json \
      --harnessprobe-report /tmp/hp-eval/reports/bu-report.json
harnessprobe: LDH scope coverage 442/1286 lines (34.37%), 10 uncovered samples
549 passed, 6 skipped in 52.75s
```

`-o addopts=` clears the repo's own `-x --dist=loadscope` defaults for this
invocation only; the repo's files are untouched. Passing the scope and report
paths as CLI flags keeps browser-use's configuration free of HarnessProbe
entries.

## Results

| Metric | Value |
|---|---|
| Tests | 549 passed, 6 skipped, 0 failed (52.75s) |
| Scope measured lines | 1286 of 1816 raw |
| Executed scope lines | 442 (34.37%) |
| Uncovered scope lines | 844 |
| Not measured (never imported) | 530 |
| Branch arcs on scope lines | 138 full / 304 partial / 844 missing |
| Findings attached | 0 (v1 has no differential detection) |

The gate, run with the same flags the action passes:

```console
$ harnessprobe gate --report .../bu-report.json --min-coverage 30 --max-uncovered 1000 \
    --summary-out .../bu-gate.md --outputs .../bu-outputs.txt
HarnessProbe gate: passed
covered-pct=34.37  scope-lines=1286  executed=442  uncovered=844
not-measured=530   findings-count=0  gate-passed=true  gate-reasons=
```

Comment rendering (identical input goes into the action's sticky comment):

```console
$ harnessprobe comment --report .../bu-report.json
### HarnessProbe: no bug classes caught
### LDH coverage
`34.37%` of LDH scope lines covered (442/1286; 530 not measured)
- browser_use/actor/page.py:476 — llm_response = await llm.ainvoke(
- browser_use/agent/cloud_events.py:152 — first_action = model_output.action[0] if ...
```

The samples are real LDH decisions: `model_output.action` handling in
`cloud_events.py`, `action_result.error` truncation in the message manager.

## Zero host-repo changes

`git -C /tmp/hp-eval/repos/browser-use status --porcelain` shows exactly one
entry, `?? .coverage` — coverage.py's own data file, unavoidable for any
coverage run and absent from browser-use's `.gitignore`. No test file, config
file, or source file was touched. The selection file lives in our repository,
not in the host.

## Honest read

- The percentage is conditional on the 62-file browser-free selection, exactly
  as in R3. 530 not-measured lines sit mostly in never-imported files
  (`browser_use/beta/`); they are reported, not counted as uncovered.
- The previous plugin dogfood on this pin measured 449/1286 (34.91%). This run
  measured 442/1286 (34.37%): same denominator, seven fewer executed lines.
  The delta is plugin-version drift in line classification (scope derivation
  and the coordinates of the plugin's executable-line set), which is why this
  document pins its own run rather than quoting the older number.
- A 34% number on a heuristic superset is not "browser-use's tests are 34%
  good"; it is "of the lines this product calls LDH, this selection executed
  34%". The scope is a superset by design.
- v1 detects nothing, so the comment says so in its first section rather than
  implying a finding exists.

## Reproduce

The commands above run end to end in roughly three minutes on a 4-core box
(install ~60s, pytest 52.75s, gate and comment under a second). Artifacts
(`bu.scope.json`, `bu-report.json`, `bu-gate.md`, `bu-comment.md`) are
regenerated into `/tmp/hp-eval/reports/` and deliberately not committed.
