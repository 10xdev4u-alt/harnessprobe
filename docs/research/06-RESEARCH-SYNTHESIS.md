# RESEARCH SYNTHESIS — idea verdict, tweaks, final plan (2026-10-15)

Inputs: `01-academic.md`, `02-oss-landscape.md`, `03-tech-feasibility.md`,
`04-adoption-and-portfolio.md`, `05-field-study.md`. This file is the decision record.

## 1. Verdict on the idea

The pain is real and verified independently of the paper: recurring harness bugs at
provider-normalization / tool-action / redaction / retry seams (Browser Use #5623 closed by
PR #5656; LangChain #35782/#33504/#36679; LlamaIndex #18760/#21579; OpenClaw turn-failure
stream; Roo Code parser CVEs). The paper's metrics (LDH share 22%/32%, coverage 44%/41%,
mutation 33.6%) are reproducible cheaply from the artifact's static pipeline.

But "implement HarnessTester" is the wrong first shape:

- LDH coverage % as a headline gate gets ignored (>80% of Codecov users ignore failing checks).
- Per-PR mutation is infeasible (Stryker 72h anecdotes; TSE'24: performance is the blocker).
- Static taint recall is unproven for real dispatch/wrapper stacks (PyCG ~70% recall; TS worse).
- The paper is 11 days old, v1, no follow-ups yet; its artifact is unlicensed and can't be reused.

The genuinely unowned space (all 5 research streams agree): **nothing joins LLM decisions to
app-code branches, and nobody validates/synthesizes fixtures against harness contracts.**
Replay is commoditized (vcr/respx/nock/MSW); evals score outputs, not executions.

## 2. What we tweak (vs the paper)

1. **Fixtures before taint.** Lead with contract-faithful fixtures (the paper's actual insight).
   Taint mapper ships later and cannot gate anything until recall/precision is published on ≥3 repos.
2. **Bug-class-first, not percentage-first.** PR comment names caught bug classes
   ("tool call dropped", "secret leaked in saved history"); LDH % is a trend line, not a gate.
3. **No LLM in CI.** Deterministic fixtures; record/replay is a commodity we consume, not rebuild.
   Differential oracles only on pinned recordings; fail loudly on drift.
4. **Mutation later, sliced.** LDH→function map (mutmut) or libcst side-mutator; weekly,
   changed-lines only; no gate until a slice runs <10 min. TS later gets Stryker ranges natively.
5. **No LLM test generator in v1.** Suggest-not-gate, premium/later; needs (1)+(2) as substrate.
6. **Clean-room everything.** The artifact has no license → no copying code or H-Bench data.
   H-Bench-style bench is a separate repo we build ourselves from public issue/PR history.
7. **Two tiers of truth, never one.** Static LDH set and runtime tagged-value ledger are reported
   separately; disagreement is signal, not something to hide behind one number.
8. **Heuristic scope first.** Decorator/module allowlist + explicit annotations, upgradeable to
   Semgrep-CE rules; don't block the wedge on interprocedural analysis.

## 3. Recommended portfolio order (revised)

1. `harnessprobe-fixtures` (Python) — typed provider-response/tool-call/observation builders,
   fake model adapter protocol, "known-ugly" corpus, compat checks vs SDK versions. **MVP core.**
2. `harnessprobe-pytest` (Python) — thin plugin: heuristic LDH scope, coverage.py JSON subsetting,
   bug-class-first PR comment. **MVP shell.**
3. `harnessprobe-taint` — Semgrep-CE + ast fixpoint; publish recall/precision vs runtime ledger.
4. `harnessprobe-adversarial` — sequence corpus pack (injection-in-observations, reordered/duplicated
   calls, truncation, nested secrets) replayed into fixtures.
5. `harnessprobe-gen` — contract-guided generator, suggest-only.
6. `hbench-open` — separate repo, clean-room differential bench from public bug history.
7. TS/Vitest mirror starts only after Python wedge shows adoption signals.

Monorepo for 1–5 (shared JSON schemas, not shared code); 6 splits out.

## 4. Verified stack (from 03)

- Python: pydantic v2 + Hypothesis/hypothesis-jsonschema; coverage.py `coverage json` subsetting
  (no plugin needed for static LDH spans); pytest; later Semgrep CE custom rules + stdlib `ast`
  fixpoint; later mutmut (LDH→function) or libcst mutator.
- TypeScript: ts-morph spans; Vitest istanbul provider + `istanbul-lib-report` `ReportBase`;
  Stryker `--mutate file:start-end`; zod/typebox + fast-check.
- Runtime tagging (de-risk spike, not day-1 dependency): `wrapt`/Proxy on provider clients +
  `WeakKeyDictionary` ledger; catches values static analysis misses.
- Licensing guardrails: CodeQL CLI terms forbid non-OSS/CI use; no Semgrep registry rules shipped.

## 5. Evidence-backed MVP shape

- **Target repo for dogfood:** browser-use (`tests/ci/conftest.py:75` `create_mock_llm`,
  `httpx.MockTransport`, retry/fallback/security suites). Runner-up: OpenHands mock-LLM server
  pattern for the HTTP/SSE tier; SWE-agent `.traj` replay for fixtures.
- **MVP = fixtures + pytest plugin**, validated by reproducing paper-style LDH coverage on
  browser-use/Aider/SWE-agent and by catching the bug classes above from recorded fixtures.
- **De-risk order (spikes before committing):** (a) fixture builders against real SDK versions,
  (b) coverage subsetting on 3 repos, (c) taint recall vs runtime ledger, (d) proxy-tag survivability
  through async/coercion, (e) Python mutation granularity.

## 6. Reasons this could still fail (tracked)

1. Gate fatigue — a metric nobody acts on; counter: bug-class demos, suggest-first.
2. Taint recall too low → comforting wrong numbers; counter: two-tier reporting, no gating.
3. Provider/SDK churn maintenance treadmill; counter: schema-from-SDK-tests, compat CI, community packs.
4. Framework absorption (LangChain/Kimi-style in-house fixtures); counter: cross-provider + cross-language layer.
5. Legal/ethical: no artifact reuse; sandbox generated tests; scrub fixture secrets; coordinated disclosure.

## 7. Immediate next actions (no implementation before spikes)

- S1: write `harness-taint.schema.json` + fixture-pack schema (the boundary format everything shares).
- S2: build the ugly-case fixture corpus from the verified public bug classes (issue-linked).
- S3: measure coverage subsetting on browser-use/Aider/SWE-agent (reproduce paper RQ1 subset).
- S4: spike Semgrep-CE LDH rules vs runtime ledger on one repo; report recall/precision.
- Everything else stays parked until S1–S4 report.
