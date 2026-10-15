# ADR 0005: MVP scope after validation spikes

Status: accepted — 2026-10-16.
Deciders: 10xdev4u-alt (owner), the-ai-developer (reviewer).

## Context

Spikes R3-R6 (`docs/eval/spikes/`) produced measured evidence. The scorecard
(`docs/eval/SCORECARD-E1.md`) converts it into decisions D1-D6. Two research
assumptions changed: static taint is weaker than hoped, and mutation scoping is
possible without file-level slicing.

## Decision

1. MVP = contract fixtures + pytest-visible coverage subsetting (roadmap
   phases 1-2). Order unchanged.
2. Scope extraction ships heuristic v2 (scorecard section 3) plus
   `# harness:llm-source` annotations. No Semgrep dependency in v1;
   Semgrep-CE becomes an optional union-only generator in T1 work.
3. Runtime proxy tagging stays parked as an optional second tier until T4/T5.
   It is not a v1 dependency.
4. Mutation is weekly and marker-scoped via mutmut
   `do_not_mutate_patterns`; libcst is deferred until sub-line control is
   needed.
5. Reporting contract: two tiers with an explicit disagreement section; no
   percentage gates in v1; thresholds per scorecard section 2.

## Consequences

- P1/P2/P3 build is unblocked; build starts here.
- T1 is demoted to a generator of scope candidates, reporting only.
- M1 becomes marker-based rather than function-map-based.
- One annotation vocabulary (`# harness:llm-source`) serves scope, mutation,
  and escape hatches.
