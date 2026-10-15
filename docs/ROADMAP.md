# Roadmap (research-revised, 2026-10-15)

See `research/06-RESEARCH-SYNTHESIS.md` for evidence. Order changed from the original plan:
fixtures first, taint second, no LLM generator or mutation gates in v1.

## Phase R — De-risk spikes (before any build commitment)
- R1: shared schemas (`harness.taint.json`, fixture pack) + validators.
- R2: ugly-case fixture corpus from verified public bug classes (issue-linked).
- R3: LDH-scoped coverage subsetting measured on browser-use / Aider / SWE-agent.
- R4: Semgrep-CE LDH rules vs runtime ledger → recall/precision report.
- Decision gate: proceed only if R3 numbers are trustworthy and R4 recall is defensible.

## Phase 1 — Fixtures library (Python) [MVP core]
- Typed provider response / tool call / observation builders (pydantic v2).
- Fake model adapter protocol (SDK-shape-aware); scripted trajectory DSL.
- Known-ugly corpus: truncated JSON, invalid tool calls, dropped batches, merged calls,
  refusals, max_tokens, 429/5xx mapping, nested secrets, partial SSE frames.
- Contract compat tests against pinned SDK versions.

## Phase 2 — pytest plugin [MVP shell]
- Heuristic LDH scope (allowlist + annotations), upgradeable to taint map.
- `coverage json` subsetting → LDH coverage report.
- Bug-class-first PR comment / status output; LDH % as trend, not gate.

## Phase 3 — Taint mapper
- Semgrep-CE rules + stdlib ast fixpoint; two-tier reporting (static vs runtime-tagged).
- Published recall/precision on ≥3 public repos before anything gates on it.

## Phase 4 — Adversarial sequence pack
- Coverage-guided hostile-but-contract-valid sequences; sandbox-only replay.

## Phase 5 — Mutation (sliced) + TS mirror
- Python: LDH→function map (mutmut) or libcst side-mutator; weekly changed-lines only.
- TS: ts-morph + Vitest istanbul reporter + Stryker `--mutate file:start-end`.

## Phase 6 — Generator + bench (separate repos)
- `harnessprobe-gen`: contract-guided, suggest-not-gate.
- `hbench-open`: clean-room differential bench from public bug history (no artifact reuse).

## Explicitly parked
- Per-PR mutation gates; live LLM calls in CI; copying paper artifact code or H-Bench data.
