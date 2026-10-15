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

## Packages

- `harnessprobe-core`: LDH taint graph, contract schemas, fixtures
- `harnessprobe-pytest`: pytest plugin + LDH coverage reporter
- `harnessprobe-vitest`: Vitest plugin/reporter
- `harnessprobe-fuzz`: adversarial response & tool-sequence generators
- `harnessprobe-mutation`: mutmut/Stryker runners scoped to LDH
- `harnessprobe-bench`: H-Bench-style differential bug detector
- `harnessprobe-gen`: optional LLM-driven test generator wrapper

## Status

Design/spec-only in this workspace drop. Implementation follows tracer-bullet
milestones in `docs/roadmap.md`.
