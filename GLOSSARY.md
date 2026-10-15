# GLOSSARY

Agent harness: operational software surrounding an LLM (context/memory,
guardrails, orchestration, tool interfaces).

LLM-dependent harness (LDH): statements whose data or control flow depends,
directly or transitively, on an LLM invocation result.

LLM value: any value derived from an LLM invocation (content, tool calls, tokens,
provider signals, embedded in larger structures).

Agent-harness contract: obligations/guarantees that must hold across harness
components for valid execution: response shapes, tool call/result pairing,
state transitions, callback protocols.

Source: a statement producing LLM output (e.g. `completion(...)`,
`client.responses.create(...)`).

Sink/predicate: branch or decision whose outcome depends on an LLM value.

Contract-faithful fixture: test double that preserves production contracts
while varying one LLM value at a time.

LDH coverage: line/branch coverage restricted to LDH statements.

Differential oracle: test must fail on buggy revision and pass on fixed revision.

Tool sequence: ordered set of model-proposed calls and returned observations.

Adversarial response: schema-valid but boundary-stressing LLM output.
