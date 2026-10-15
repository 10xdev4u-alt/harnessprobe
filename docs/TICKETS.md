# Tickets (research-revised order)

## Phase R — de-risk (do first, no product code)
R1. Define `harness.taint.json` schema + validator (Python + TS conformance fixtures).
R2. Fixture-pack schema + ugly-case corpus, each case linked to a real public bug/issue.
R3. Coverage subsetting spike: run coverage on browser-use / Aider / SWE-agent, subset to
    heuristic LDH scope, report numbers + confidence.
R4. Taint recall spike: Semgrep-CE rules vs runtime tagged-value ledger on one repo.
Gate: R3 + R4 reviews clean before Phase 1.

## Phase 1 — fixtures (MVP core)
F1. pydantic v2 provider-response builders (OpenAI/Anthropic/LiteLLM shapes).
F2. Tool call / tool result / observation builders with pairing invariants.
F3. Fake model adapter protocol + scripted trajectory DSL (browser-use/OpenHands/SWE-agent shapes).
F4. Fault-injection helpers (side_effect schedules, exception→status maps, SSE partials).
F5. SDK compat test matrix (pinned versions).
F6. Local OpenAI-compatible mock server (SSE + error mapping).

## Phase 2 — pytest plugin (MVP shell)
P1. `harnessprobe init` → heuristic LDH scope file.
P2. Coverage subsetting + report JSON.
P3. Bug-class-first PR comment / CI output.
P4. GitHub Action + example on browser-use.

## Phase 3 — taint
T1. Semgrep-CE source/sink rules (openai/anthropic/litellm/langchain).
T2. ast fixpoint caller graph; two-tier report.
T3. Recall/precision report + annotation escape hatch.

## Phase 4 — adversarial pack
A1. Sequence mutator: reorder/drop/duplicate/truncate; injection-in-observation corpus.
A2. Sandboxed replay runner.

## Phase 5 — mutation + TS
M1. LDH→function map for mutmut (or libcst side-mutator); weekly job, changed lines only.
M2. TS mirror: ts-morph spans, Vitest istanbul reporter, Stryker ranges.

## Phase 6 — separate repos
G1. `harnessprobe-gen` (suggest-only).
B1. `hbench-open` clean-room mining + differential oracle harness.
