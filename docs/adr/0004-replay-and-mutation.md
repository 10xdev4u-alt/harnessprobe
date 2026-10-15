# ADR-0004: Replay-plus-mutation over live LLMs in tests

## Context
Live LLMs make tests flaky, costly, non-deterministic. Yet we need realistic
nondeterministic inputs.

## Decision
Tests use captured/replayed HTTP cassettes plus systematic adversarial mutation
of those cassettes, never a live model in CI.

## Consequences
+ Deterministic, cheap, fast.
- Cassettes can become stale; add refresh job (nightly, optional).
- Misses provider behavior changes until refresh.
