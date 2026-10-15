# R3 spike: LDH-scoped coverage subsetting on browser-use

Status: completed. Date: 2026-10-16. Timebox respected (~15 min wall clock used).
All artifacts under `/tmp/hp-eval/artifacts/r3/`. Nothing in the workspace repo was touched.

## Context

Spike R3 for HarnessProbe. Question: can we take a static LDH (LLM-dependent harness) line
set, intersect it with a normal coverage.py run, and produce honest, reproducible subset
numbers on a real agent repo?

Target: `github.com/browser-use/browser-use`, clone depth 1, HEAD
`a71d5478e4187cbe5295aab6403dfe7e4a6861a4` (2026-10-15, version 0.13.11). Chosen per
`docs/research/05-field-study.md` as the best MVP target: smallest and cleanest seam
(scripted `BaseChatModel` mock, typed provider builders, no coverage tooling of its own).

Constraints taken as given: 4 cores, tests serial, every run wrapped in `timeout 900`,
machine load average was 5.9 at start (other work on the box). Coverage correctness does
not depend on load; the load number is recorded per the benchmark checklist.

## Method

Environment (Python 3.14.7 from `/usr/bin/python3.14`, uv venv; uv's default was 3.13.12
and was overridden on purpose):

```
git clone --depth 1 https://github.com/browser-use/browser-use /tmp/hp-eval/repos/browser-use
git -C /tmp/hp-eval/repos/browser-use rev-parse HEAD   # a71d5478e4187cbe5295aab6403dfe7e4a6861a4
~/.local/bin/uv venv --python /usr/bin/python3.14 /tmp/hp-eval/venvs/bu
~/.local/bin/uv pip install --python /tmp/hp-eval/venvs/bu/bin/python \
    pytest pytest-asyncio pytest-httpserver pydantic openai httpx coverage
~/.local/bin/uv pip install --python /tmp/hp-eval/venvs/bu/bin/python -e /tmp/hp-eval/repos/browser-use
~/.local/bin/uv pip install --python /tmp/hp-eval/venvs/bu/bin/python \
    "pytest==9.0.2" "pytest-asyncio==1.3.0" "pytest-httpserver==1.1.3" "pytest-xdist==3.8.0" "pytest-timeout==2.4.0"
```

Editable install succeeded; no fallback to a minimal dependency set was needed.

Test selection: 62 of 120 `tests/ci` files, chosen by excluding any file whose text
references `browser_session`, `BrowserSession(`, `agent_with_cloud`, `playwright`,
`cdp_client`, or `CloudSync(`. Selection is in `artifacts/r3/candidates.txt`; collect-only
found 555 tests. Browser-dependent files (watchdogs, actor, beta, cloud) are out of scope.

```
cd /tmp/hp-eval/repos/browser-use
unset OPENAI_API_KEY     # deterministic, harness-only baseline
timeout 900 /tmp/hp-eval/venvs/bu/bin/coverage run --branch -m pytest \
  $(cat /tmp/hp-eval/artifacts/r3/candidates.txt) -q \
  -o addopts="--strict-markers --tb=line" -o log_cli=false -o timeout=60
timeout 900 /tmp/hp-eval/venvs/bu/bin/coverage json -o /tmp/hp-eval/artifacts/r3/coverage.json
```

The repo's `addopts` (`-svx --strict-markers --tb=short --dist=loadscope`) was overridden:
`-x` would abort the run at the first failure and lose coverage for every later test, and
the xdist flags are not needed for a serial run. This is the only deviation from the
prescribed command line.

Scope extraction (`artifacts/r3/ldh_scope.py`, deterministic, stdlib `ast`, source only):

- Tier A: statement lines in functions whose subtree contains (a) a call on an attribute
  chain matching `chat.completions.create` / `litellm.(a)completion` / `.invoke` /
  `.ainvoke` / `.generate`, or (b) an attribute or subscript read whose attr name or base
  identifier matches `^(parsed|action|tool_call|model_output|response|completion|tool_calls|function_call)`,
  case-insensitive, in either direction (`response.content` and `x.action` both match).
- Tier B: statement lines in functions that call a Tier-A function by bare name, same
  file, 1 hop. Attribute calls such as `self.run(...)` do not match, per the spec.
- Detection walks the whole function subtree, including nested defs. Line collection
  descends through control flow but stops at nested def/class bodies, which are scored as
  their own functions. Tier A wins over Tier B for a function that qualifies for both.
- Output `artifacts/r3/scope.json`: `{file: {tierA_lines, tierB_lines}}`, repo-relative keys.

Intersection (`artifacts/r3/subset_analysis.py`): a scope line is a statement only if it
appears in coverage.py's executable set (`executed_lines | missing_lines`); scope lines
absent from that set are reported as `not_measured` rather than silently dropped or counted
as uncovered. Branch arcs are classified per line as full, partial, or missing (all, some,
or none of the arcs leaving that line were executed). Whole-package percentages are over
the 129 package files the run imported (175 `.py` files exist in the package).

## Numbers

Primary run, exit 0: 549 passed, 6 skipped, 0 failed in 56.6s. (Six skips are
live-provider tests gated on missing API keys in `tests/ci/models/model_test_helper.py`.)

| Metric | Value |
|---|---|
| Package files imported / total | 129 / 175 |
| Package statements (imported files) | 22,903 |
| Whole-package line coverage (imported files) | 10,160 / 22,903 = 44.4% |
| Whole-package branch coverage (imported files) | 2,285 / 8,374 = 27.3% |
| Files with any scope | 61 |
| Tier A lines (raw, extractor) | 5,236 (22.9% of package statements) |
| Tier A statement lines (coverage-executable) | 4,357 (19.0% of package statements) |
| Tier A executed | 1,154 / 4,357 = 26.5% |
| Tier A branch arcs executed | 517 / 2,126 = 24.3% |
| Tier A branch-bearing lines: full / partial / missing | 134 (12.6%) / 249 (23.4%) / 680 (64.0%) |
| Tier B statement lines | 37 (54.1% executed, from 3 files) |
| Tier B raw lines | 348, of which 311 `not_measured` |
| Tier A `not_measured` lines | 879, of which 745 sit in 9 never-imported files |
| Extract / analysis runtime | 3.3s / 0.3s |

Per-file rows for every scope file are in `artifacts/r3/subset_table.csv`. Notable rows:
`agent/service.py` Tier A 241/705 (34.2%), `agent/message_manager/service.py` 84/118
(71.2%), `tools/registry/service.py` 106/179 (59.2%), `tools/service.py` 41/679 (6.0%),
`browser/watchdogs/har_recording_watchdog.py` 0/205.

Why Tier A coverage is not higher, explained with the data: the test selection is
deliberately browser-free (62 of 120 CI files), the CI shards the rest per file with a real
Chromium. The largest Tier A blocks that stay near zero are the action-dispatch path in
`tools/service.py` (6.0%: it runs under a live browser session), the browser watchdogs, and
`beta/service.py` which no selected test imports at all (its 497 Tier A lines dominate the
745 not-measured figure). Conversely the harness-heaviest files the selection hits score
34% to 71%, which shows the intersection machinery finds real execution where it exists.

Tier B is nearly vacuous on this codebase: only 5 files get any Tier B lines, and 311 of
348 raw lines are in files the run never imported. The bare-name rule misses the dominant
call shape, `self.method(...)` and `obj.method(...)`. This is a property of the specified
rule, not of the intersection.

Heuristic breadth check: the Tier A read pattern scores whole functions, so broad files
look over-included. `tools/service.py` scores 66% of the file, `llm/openai/chat.py` 49%,
`agent/service.py` 36%. Tier A is an over-approximation, which suits a subsetting product
(report on a superset) but caps how precisely the subset can be defended as "the LDH".

## Samples

First 10 uncovered Tier A statement lines (sorted, deterministic):

```
browser_use/actor/page.py:416  await self._ensure_session()
browser_use/actor/page.py:417  llm = llm or self._llm
browser_use/actor/page.py:419  if not llm:
browser_use/actor/page.py:420  raise ValueError('LLM not provided')
browser_use/actor/page.py:422  dom_service = self.dom_service
browser_use/actor/page.py:425  enhanced_dom_tree, _ = await dom_service.get_dom_tree(target_id=self._target_id, all_frames=None)
browser_use/actor/page.py:427  session_id = self._browser_session.id
browser_use/actor/page.py:428  serialized_dom_state, _ = DOMTreeSerializer(
browser_use/actor/page.py:432  llm_representation = serialized_dom_state.llm_representation()
browser_use/actor/page.py:434  system_message = SystemMessage(
```

Full uncovered count: 3,203 Tier A lines.

## What broke and caveats

1. A live-API test ran on the first attempt. `OPENAI_API_KEY` was set in the shell, so
   `tests/ci/models/test_llm_openai.py::test_openai_gpt_4_1_mini` (which launches a real
   browser and calls OpenAI) ran and failed: 549 passed, 1 failed, 5 skipped, 117s, log kept
   as `pytest-run-withkeys.log`. The primary baseline unset the key; the same test then
   skipped itself. Anyone reproducing this must unset provider keys, or they will measure a
   different, network-dependent run.
2. `-x` in the repo's `addopts` would have aborted the first run at that failure and
   silently truncated coverage for all later tests. Overriding `addopts` was necessary, and
   it is the only change to the prescribed pytest command line.
3. The whole-package percentages are over the 129 files this test set imported, not all 175
   package files. 46 files never imported are absent from the denominator; treating them as
   0% would lower the whole-package figure. The 745 Tier A lines in never-imported files are
   counted as `not_measured` in the scope numbers, so the Tier A "covered %" is honest on
   its denominator (4,357 executable scope statements).
4. The numbers are conditional on this 62-file test selection. Enabling browser tests
   (`tests/ci/browser`, interactions, watchdogs) would raise Tier A coverage; a reader must
   not read 26.5% as "browser-use's CI covers 26.5% of its LDH", because our run does not
   include the browser shards.
5. Extractor interpretation choices (recursive detection, nested-def boundary, either-side
   attribute matching, bare-name-only Tier B) are documented above; a different reading
   moves the scope by hundreds of lines. `litellm` is not installed in the venv, so
   `browser_use/llm/litellm/*` cannot be imported and those two files are unmeasured.
6. No flakiness observed: the selected set passed twice (with and without the live-key
   failure); the clean run repeated the same counts. One run per configuration was taken,
   per the spike's timebox; this is a coverage measurement, not a timing benchmark, and
   coverage.py is deterministic for a deterministic test set.

## Reproduce

```
mkdir -p /tmp/hp-eval/{repos,venvs,reports,artifacts/r3}
git clone --depth 1 https://github.com/browser-use/browser-use /tmp/hp-eval/repos/browser-use
git -C /tmp/hp-eval/repos/browser-use rev-parse HEAD    # expect a71d5478e4187cbe5295aab6403dfe7e4a6861a4
~/.local/bin/uv venv --python /usr/bin/python3.14 /tmp/hp-eval/venvs/bu
~/.local/bin/uv pip install --python /tmp/hp-eval/venvs/bu/bin/python pytest pytest-asyncio pytest-httpserver pydantic openai httpx coverage
~/.local/bin/uv pip install --python /tmp/hp-eval/venvs/bu/bin/python -e /tmp/hp-eval/repos/browser-use
# run from the repo, selection list needed first (grep rule in Method)
unset OPENAI_API_KEY
timeout 900 /tmp/hp-eval/venvs/bu/bin/coverage run --branch -m pytest $(cat /tmp/hp-eval/artifacts/r3/candidates.txt) -q -o addopts="--strict-markers --tb=line" -o log_cli=false -o timeout=60
/tmp/hp-eval/venvs/bu/bin/coverage json -o /tmp/hp-eval/artifacts/r3/coverage.json
/tmp/hp-eval/venvs/bu/bin/python /tmp/hp-eval/artifacts/r3/ldh_scope.py /tmp/hp-eval/repos/browser-use /tmp/hp-eval/repos/browser-use/browser_use /tmp/hp-eval/artifacts/r3/scope.json
/tmp/hp-eval/venvs/bu/bin/python /tmp/hp-eval/artifacts/r3/subset_analysis.py /tmp/hp-eval/artifacts/r3/coverage.json /tmp/hp-eval/artifacts/r3/scope.json /tmp/hp-eval/repos/browser-use /tmp/hp-eval/artifacts/r3
```

Artifacts: `candidates.txt`, `pytest-run.log`, `pytest-run-withkeys.log`, `coverage.json`,
`ldh_scope.py`, `scope.json`, `subset_analysis.py`, `subset_table.csv`, `r3_summary.json`,
`requirements.txt`, `decisions.tsv`.

## Verdict

Proceed with adjustments. The subsetting pipeline works end to end on a real repo: a
deterministic AST extractor plus `coverage json` intersection produces per-file, per-tier
line and branch numbers in seconds, and every number above is traceable to a script and a
log in this directory. Two adjustments before product use: the Tier B rule as specified
(bare-name, 1 hop) is nearly vacuous on real call shapes and should include attribute calls;
the Tier A read pattern over-includes whole large functions and should be narrowed or
reported as a deliberate superset. The numbers would be invalidated by a different commit,
a different test selection (especially enabling the browser shards), or a changed extractor
interpretation; each is pinned in the artifacts above.
