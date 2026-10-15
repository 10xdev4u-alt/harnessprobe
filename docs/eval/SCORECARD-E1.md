# Evaluation scorecard E1 — MVP go/no-go (2026-10-16)

Consumes spikes R3, R3b, R3c, R4, R5, R6 in `spikes/`. Framework per R12:
hypothesis, method, evidence, cost, verdict. Decisions are binding for Phase
1-2 scope and are recorded in `../adr/0005-mvp-scope-after-validation.md`.

## 1. Decisions

| # | Decision | Verdict | Basis |
|---|---|---|---|
| D1 | Coverage subsetting is viable as the MVP substrate | GO | R3/R3b/R3c: deterministic pipeline on three repos; LDH-scope coverage 26.5% / 38.2% / 47.7% against whole-repo 44.4% / 54.4% / 53.4% |
| D2 | Heuristic scope with fixes ships before any taint dependency | GO, v2 required | Tier B near-vacuous (37 measurable statements); Tier A over-includes whole functions (`tools/service.py` 66%); naming false positives move numbers 3-4 points |
| D3 | Semgrep-CE as the v1 scope source | NO-GO | R4 strict recall 47.6%, precision 78.6% on 170 annotated lines; 286 of 302 hits came from name heuristics, not taint |
| D4 | Runtime proxy tagging as a v1 dependency | NO-GO, parked as optional tier | R5: tags die at every rebuild boundary (dump, validate-from-dict, JSON, dict flattening); shallow wrapping; 8-16x access overhead |
| D5 | Marker-scoped weekly mutation in v1; libcst deferred | GO | R6: scoping keeps the kill rate (75.8% vs 75.3%) with 28% fewer mutants and 29% less wall time; the negative-lookahead marker regex is the mechanism |
| D6 | Two-tier trust reporting with an explicit disagreement section | ACCEPTED | R4 misses cluster at interprocedural boundaries; R5 losses are systematic; a single number would hide both |

## 2. E2 acceptance thresholds

Gate flips only when these are met. Until then everything is reporting-only.

- Scope heuristic: warn-only forever; scope coverage % never gates.
- Taint tier gating: recall >= 80% and precision >= 70% on the T5 harness
  across >= 3 public repos, two consecutive runs. Below that it reports,
  never blocks.
- Mutation: no PR gates; weekly job with a time budget; kill rate is
  trend data.
- Bug-class claims: at least one reproduced bug class per claim; zero caught
  in a report is allowed but stated plainly.

## 3. Scope heuristic v2 requirements (binding for P1/P2 build)

1. Negative patterns: exclude argparse-style names (`parsed_args`), shell
   completion, and similar collisions.
2. Tier B reachability uses attribute calls (`self.method(...)`,
   `obj.method(...)`), not bare names; must be non-vacuous on the R3 corpus
   before shipping.
3. Statement-level narrowing inside functions: whole-function inclusion
   overstates scope; narrow to model-output consumption statements.
4. Free-text output reads: Aider-family text tools (parsing
   `partial_response_content`-style content) are LDH and must be in scope.
5. One annotation vocabulary: `# harness:llm-source`, shared by scope
   extraction, the mutation marker, and future escape hatches.

## 4. Cost data for planning

- R3 pipeline: extract 3.3 s + intersect 0.3 s on 22.9k statements.
- R4 scan: ~14 s wall for 7 files (stays out of the v1 path).
- R5: ~2 us per proxy read; negligible per model response. Fine as opt-in.
- R6: 120 mutants / 12.1 s on a 130-line module; budget weekly slices from
  this ratio.

## 5. Risks updated

1. Scope over-approximation is measured, not hypothetical (R3). Section 3
   must land before public dogfood.
2. Ground truth is single-annotator today (+/- ~9%). T5 must use two
   annotators; R4 numbers stay intervals until then.
3. Python 3.14: every spike dependency (coverage, pydantic, wrapt, mutmut,
   libcst, semgrep) ran. Keep 3.14 in the CI matrix.

## 6. Stays open

- E4: competitive re-scan, monthly, independent of this scorecard.
- T5: recall/precision harness on >= 3 public repos.
- T1: Semgrep-CE rules as an optional union-only generator.
