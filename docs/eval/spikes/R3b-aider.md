# R3b: LDH-scoped coverage subsetting on Aider

## Context

Spike R3b of the HarnessProbe evaluation. It measures how much of Aider's
LLM-dependent harness (LDH) code its own unit suite executes, using the same
Tier A/B scope algorithm as spike R3 (browser-use) so the per-repo numbers can
be compared. Prior knowledge from `docs/research/05-field-study.md`: Aider tests
patch `litellm.completion` directly and assert call kwargs
(`tests/basic/test_sendchat.py`), the repo ships no coverage tooling, and its
HEAD is stale (2026-05-22) relative to the other studied repos.

## Method

Pinned commit: `5dc9490bb35f9729ef2c95d00a19ccd30c26339c` (shallow clone of
`https://github.com/Aider-AI/aider`, `git rev-parse HEAD`).

Environment: Python 3.14.7 (pyproject allows `>=3.10,<3.15`), venv at
`/tmp/hp-eval/venvs/aider`, `uv pip install -e .` plus pytest and coverage.
The full editable install worked; no fallback needed. Machine load during the
run was 2-7 on 4 cores from unrelated processes. Coverage values are
deterministic; load only affects wall time.

Test selection: `tests/basic` is the largest offline unit subset (477 tests;
`tests/browser`, `tests/scrape`, `tests/help` are network/e2e and were
excluded). Result on the first attempt: 476 passed, 1 skipped, 67 subtests
passed, 148.69 s, exit 0. No test failed, so no fallback subset was needed.

LDH scope, extracted with the shared script
(`/tmp/hp-eval/artifacts/r3bc/ldh_scope.py`) from the package directory
`aider/` only. The scope semantics match the R3 implementation
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

Commands (from `/tmp/hp-eval/repos/aider`):

```
COVERAGE_FILE=/tmp/hp-eval/artifacts/r3bc/.coverage-aider \
  /tmp/hp-eval/venvs/aider/bin/python -m coverage run --branch --source=aider -m pytest tests/basic -q
COVERAGE_FILE=/tmp/hp-eval/artifacts/r3bc/.coverage-aider \
  /tmp/hp-eval/venvs/aider/bin/python -m coverage json -o coverage-aider.json
python /tmp/hp-eval/artifacts/r3bc/ldh_scope.py extract /tmp/hp-eval/repos/aider aider scope-aider.json
python /tmp/hp-eval/artifacts/r3bc/ldh_scope.py analyze scope-aider.json coverage-aider.json /tmp/hp-eval/repos/aider stats-aider.json
```

## Numbers

| Tier | AST stmt lines | Measured lines | Executed | Covered % | Branches full/partial/missing |
|---|---|---|---|---|---|
| Tier A | 1391 | 1381 | 527 | 38.16% | 81 / 76 / 175 |
| Tier B | 37 | 34 | 23 | 67.65% | 6 / 0 / 2 |
| Whole repo (reference) | 10885 | 10885 | 6202 | 54.4% | 1935 / 4060 branches = 47.7% |

"Measured lines" = scope lines that coverage counts as statements (10 AST lines
are not statements, for example `else:` and docstring continuations).

Per-file Tier A executed/measured, the input to the aggregate:

| File | Executed/measured | Note |
|---|---|---|
| aider/main.py | 263/412 | CLI wiring; entered scope via R3 attr-name matching, mostly executed |
| aider/io.py | 78/118 | console IO; mixed (shell-completion code plus response reads) |
| aider/coders/base_coder.py | 88/160 | response handling in the base coder |
| aider/models.py | 69/126 | litellm seam: `send_completion`, `simple_send_with_retries` |
| aider/onboarding.py | 23/119 | provider onboarding; entry paths tested, later branches not |
| aider/openrouter.py | 6/11 | model metadata HTTP |
| aider/coders/patch_coder.py | 0/244 | parsed-patch handling, executed by nothing in tests/basic |
| aider/args_formatter.py | 0/93 | naming false positive (`argparse` `action.*`) |
| aider/scrape.py | 0/47 | non-LLM HTTP scrape code |
| aider/versioncheck.py | 0/32 | non-LLM HTTP version check |
| aider/commands.py | 0/19 | shell-completion code (`completion.*`) |

Sensitivity, same coverage data, excluding the five files whose scope matches
are naming false positives (args_formatter, io, commands, scrape,
versioncheck): Tier A = 449/1072 = 41.9%. The primary 38.16% keeps the shared
R3 algorithm untouched for cross-repo comparability.

## Samples

Uncovered Tier A lines (capped at 2 per file so one noisy file cannot fill the
list):

```
aider/args_formatter.py:42        if not action.option_strings:
aider/args_formatter.py:43        return ""
aider/coders/base_coder.py:1343   if not self.num_cache_warming_pings:
aider/coders/base_coder.py:1344   return
aider/coders/patch_coder.py:225   content = self.partial_response_content
aider/coders/patch_coder.py:226   if not content or not content.strip():
aider/commands.py:704             text = document.text_before_cursor
aider/commands.py:707             after_command = text.split()[-1]
aider/io.py:187                   self.tokenize()
aider/io.py:189                   text = document.text_before_cursor
```

## What broke and caveats

- Nothing blocked the suite. First try was green on Python 3.14.7
  (476 passed, 1 skipped, 67 subtests, 148.69 s).
- The Tier A base-name regex misfires on Aider naming conventions:
  `parsed_args` (argparse namespace), `action.*` (argparse Action objects),
  `completion.*` (Aider's shell completion), and `response` in non-LLM HTTP
  code (versioncheck, scrape). 309 of 1381 measured Tier A lines (22%) sit in
  five such files. Sensitivity number above; the false positives are naming
  collisions, not extractor bugs.
- Aider obtains model output mainly as free text
  (`partial_response_content`, `md`, edit blocks). Those names do not match the
  R3 regex, so the editblock/udiff parsing code exercised by
  `test_editblock.py` and `test_udiff.py` stays largely outside this scope. The
  38.16% mixes a well-covered CLI/IO surface with a mostly untouched
  `patch_coder`; it is a scope reading, not a statement that Aider tests little
  LDH code.
- `aider/coders/patch_coder.py` (244 measured scope lines) is executed by
  nothing in the whole repo: `grep -rln "patch_coder\|PatchCoder" tests/`
  returns no file and coverage shows 0/244. This is the largest single LDH gap
  observed.
- One serial run per repo within the timebox; coverage percentages do not
  depend on load, so no repeats were taken. Wall times on this box (load 2-7
  of 4 cores) are upper bounds.
- Scope covers package code only; test code was not scanned.

## Reproduce

```
git clone --depth 1 https://github.com/Aider-AI/aider /tmp/hp-eval/repos/aider
git -C /tmp/hp-eval/repos/aider rev-parse HEAD   # expect 5dc9490bb35f9729ef2c95d00a19ccd30c26339c
uv venv --python 3.14 /tmp/hp-eval/venvs/aider
uv pip install --python /tmp/hp-eval/venvs/aider/bin/python -e /tmp/hp-eval/repos/aider pytest coverage
# then the four commands in Method (from the repo root)
```

Artifacts: `run-aider.log`, `coverage-aider.json`, `scope-aider.json`,
`stats-aider.json`, `requirements-aider.txt`, `ldh_scope.py`, `decisions.tsv`
(all under `/tmp/hp-eval/artifacts/r3bc/`).

## Verdict

Method runs end to end with zero barriers on Aider. The measured number is
trustworthy for what it is (38.16% of R3-scoped Tier A lines executed by
`tests/basic`), with a 41.9% sensitivity reading after removing argparse and
shell-completion false positives. The scope still misses Aider's text-edit
parsing paths, so the number needs that caveat before it is used as a quality
gate.
