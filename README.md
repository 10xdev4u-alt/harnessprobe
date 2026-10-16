# HarnessProbe (open-source) — Testing and hardening LLM-dependent agent harness

HarnessProbe is an open, framework-native toolkit for finding undertested
decision logic in LLM-dependent harness (LDH): the code that parses, validates,
dispatches, mutates state from, and reacts to LLM/tool outputs. It complements
prompt/eval suites by targeting white-box branch coverage, mutation score, and
differential bug detection around the LLM boundary.

## Why

The HarnessTester study (arXiv:2610.04921) found <50% LDH line/branch coverage
and 33.6% mutation score across 10 real agents, plus 122 real harness bugs.
promptfoo tests prompts/outputs; vcr.py/respx mock HTTP. Neither asks:
"did every branch that depends on an LLM value actually run, and survive a mutation?"

## What works today

One package, `harnessprobe`:

- `harnessprobe init` derives a heuristic LDH scope file (`harnessprobe.scope/v1`)
  with per-file confidence classes.
- A pytest plugin subsets session coverage to that scope and writes
  `harnessprobe.report/v1` JSON with uncovered LDH line samples.
- `harnessprobe comment` renders a bug-class-first PR comment, and
  `harnessprobe gate` enforces coverage thresholds for CI.
- A composite GitHub Action runs the suite, gates, summarizes, and keeps one
  sticky PR comment up to date (`docs/GITHUB_ACTION.md`).

## Quickstart

```console
$ pip install git+https://github.com/10xdev4u-alt/harnessprobe
$ harnessprobe init .                          # writes harnessprobe.scope.json
$ coverage run --branch -m pytest              # the plugin writes the report
$ harnessprobe comment --report harnessprobe.report.json
```

Use `harnessprobe gate --report harnessprobe.report.json --min-coverage 60` in
CI, or the action above. The walkthrough with before/after numbers is
`docs/QUICKSTART.md`; the format references are `docs/SCOPE_FILE.md`,
`docs/PR_COMMENT.md`, and `docs/GITHUB_ACTION.md`.

## Status

v0.1.0, in development, not yet on PyPI. Coverage subsetting, the pytest
plugin, the comment renderer, the gate, and the GitHub Action are built and
dogfooded on `browser-use`; taint graphs, fixtures, adversarial sequences,
mutation scoping, the Vitest reporter, and differential bug detection follow
the tracer-bullet milestones in `docs/ROADMAP.md`. This repository runs
HarnessProbe on itself in CI.
