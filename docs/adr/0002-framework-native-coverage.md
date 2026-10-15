# ADR-0002: Framework-native coverage over standalone

## Context
Adoption requires appearing inside developers' existing pytest/Vitest workflows.

## Decision
Provide pytest and Vitest plugins that consume a precomputed LDH map and report
LDH coverage and mutants.

## Consequences
+ Low friction + CI integration.
- Per-framework maintenance burden.
- Coverage provider API churn.
