# ADR-0001: Taint-based LDH extraction over name matching

## Context
LDH cannot be found by grepping provider SDK calls; outputs flow through
message objects, tool call structures, and state.

## Decision
Implement an interprocedural data/control dependency pass per language with
explicit source catalog and annotation fallback.

## Consequences
+ Precise LDH map.
- High initial cost; requires language-specific implementations.
- Need manual override for dynamic/reflection cases.
