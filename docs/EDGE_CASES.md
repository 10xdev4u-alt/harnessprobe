# Edge cases and mitigation

1. False positive taint edges from provider setup code: filter to invocation results only; source catalog explicit.
2. Streaming/chunked LLM outputs: treat async iterators and SSE frames as sources; fuzz partial frames.
3. Indirect LLM values after serialization: taint survives JSON; mark serializer boundaries.
4. Tool sequences with no tool calls: ensure predicate branches for empty lists.
5. Malformed JSON arguments: test parser failure paths.
6. Missing optional fields and unknown provider fields: shape checks.
7. Out-of-order tool results: pairing invariants.
8. Duplicate tool calls: idempotency.
9. Concurrent tool execution: race tests.
10. Retries/timeouts: state rollback.
11. Provider-specific error objects: contract variants.
12. Unicode/empty content: boundaries.
13. Nested lists in redaction: recursive invariants.
14. Stateful agents across turns: context accumulation and reset.
15. Environment fakes (filesystem, network): contract for paths and creds.
16. Flaky tests from shared state: isolation with forks/shuffle.
17. Mutation tool timeouts: partition mutants.
18. Coverage gaps due to dynamic imports: annotation fallback.
19. Generated tests over-asserting unsupported behavior: contract checker.
20. Cost runaway in LLM generator: cache, budget, template mode.
21. Security of executing generated tests: containerized sandbox, no secrets.
22. Cross-language inconsistency: shared schema tests.
23. Provider SDK version drift: compatibility matrix + refresh CI.
24. Large repos performance: sampling and sharding.
25. Oracles for semantic outputs: use structural checks before text assertions.
