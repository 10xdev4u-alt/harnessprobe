# SPEC — HarnessProbe

> Revised 2026-10-15 after research: see `research/06-RESEARCH-SYNTHESIS.md`.
> Original decisions below kept for history; current ordering is fixtures-first,
> taint second, no mutation/LLM-generator gates in v1.

## Problem Statement
Developers of agent systems test prompts and end-to-end tasks, but rarely
exercise LLM-dependent harness branches. LDH bugs survive because fixtures
rarely preserve provider/tool contracts while exploring boundary values.

## Solution
A taint-aware, contract-faithful, framework-native testing utility that (a)
identifies LDH, (b) measures LDH coverage/mutation, (c) generates boundary
inputs and adversarial tool sequences, and (d) detects differential bugs.

## User Stories
1. As an agent developer, I want LDH coverage in my existing pytest run, so
   I can see untested LLM-dependent branches.
2. As a TS agent developer, I want Vitest to report LDH branch coverage.
3. As a maintainer, I want mutations confined to LDH, so scores reflect
   LLM boundary robustness.
4. As a security engineer, I want adversarial tool outputs (injection, bad
   schema, nested secrets) to be replayed into redaction/normalization.
5. As an OSS contributor, I want contract builders to make valid fixtures.
6. As a CI owner, I want deterministic, sandboxed test execution.

## Implementation Decisions
- Monorepo with language-specific packages.
- Source-of-truth LDH map is JSON (`harness.taint.json`) with AST node ids.
- Contracts are versioned; generators mutate them via property-based libs.
- Generator is optional; core value works template-driven without LLM.
- CLI: `harnessprobe init|coverage|fuzz|mutate|bench`.

## Testing Decisions
- Prefer seams at public module boundaries.
- Oracles: branch coverage, mutation kill, invariant checks, differential fail/pass.
- No live LLM in PR checks.
