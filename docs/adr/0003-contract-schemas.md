# ADR-0003: Contract schemas as canonical fixtures

## Context
The largest failure mode is fixtures that break agent-harness contracts.

## Decision
Ship versioned JSON Schemas/Zod/Pydantic contracts for provider responses,
tool calls/results, observations, and state; generate fakes from them.

## Consequences
+ Contract-faithful by default.
+ Cross-language consistency.
- Schemas can drift from SDKs; add compatibility tests.
