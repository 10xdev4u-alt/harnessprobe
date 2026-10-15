# 03 — Technical Feasibility: LDH taint, LDH-scoped coverage, LDH-scoped mutation, contract-faithful adversarial generation

Status: research only. Date: 2026-10-15. All URLs accessed 2026-10-15 unless noted.
LDH (LLM-dependent harness) is used per repo Glossary: statements whose data/control flow depends on an LLM invocation result.
Methods: primary sources (official docs, source code read from shallow clones under /tmp/research), one cheap local experiment (Python 3.14 `sys.monitoring`).

## 1. Python static taint / call-graph options

| Tool | License (per [Refs]) | Programmatic source→sink output | Async / generators / dynamic attrs | Cost | Verdict for LDH extraction |
|---|---|---|---|---|---|
| CodeQL Python | CLI under GitHub CodeQL Terms (free: academic + OSS codebases; private/CI needs paid GHAS); queries MIT [R1][R2][R3] | Yes: `codeql database create/analyze`, custom `.ql` path queries (`flowPath`, `TaintTracking` config), SARIF/CSV out [R4][R5] | `await` and `yield` flows modeled; `getattr`/registry-style dynamic dispatch approximated via points-to → FN/FP at framework boundaries | DB build minutes for mid repos; query authoring + taint config = M effort | Strongest single tool for both languages; use only if target repos are OSS, else licensing blocks |
| Semgrep CE 1.x | Engine LGPL-2.1; interfile = proprietary Semgrep Code; registry rules under Semgrep Rules License (no redistribution product-embedded) [R6] | Yes: `semgrep --json/--sarif`; taint rules produce `dataflow_trace` (source, intermediate vars, sink) [R7] | OSS taint is intraprocedural (function scope); `--pro-intrafile` = interprocedural within one file (Pro engine); no type inference → dynamic attributes weak | Free; fast CI; rule authoring S–M | Best OSS default: write our own source/sink rules (no registry rules shipped) |
| Joern CPG (`pysrc2cpg`) | Apache-2.0 [R8] | Yes: `joern-parse --language PYTHONSRC`, CPGQL `reachableByFlows`; JVM + server mode scriptable [R8][R9] | Python frontend younger than C/Java; type propagation iterative; async/await and generators approximated — expect false paths | JVM install + Scala querying; M effort | Viable but heavier and weaker Python semantics than CodeQL/Pysa |
| PyCG | Apache-2.0, archived (no further dev) [R10][R11] | Call graph only (JSON adjacency/FASTEN); no taint [R10] | Paper: precision ~99.2%, recall ~69.9%; handles generators, closures, multiple inheritance; not async-focused [R11] | pip install; S effort | Use algorithm/code as reference for our own fixpoint CG, not as dependency (archived) |
| Scalpel | Apache-2.0, low activity [R12][R13] | Framework: CFG, call graph, SSA, type inference — taint is DIY [R12] | Research-grade; Python 3.10-era | M effort | Only if we need SSA/CFG beyond stdlib `ast` |
| Pysa (Meta; "Pyre taint") | MIT [R14] | Yes: `pyre analyze`, JSON results incl. flows, `--save-results-to` [R15] | Type-driven: needs Pyrefly clean run; async supported via models; dynamic attrs limited; every third-party SDK needs `.pysa` models/stubs [R15][R16] | Model writing for LLM SDKs = M–L | Excellent precision but setup burden; good reference model set |

Successor note: JARVIS (arXiv:2305.05949) claims ≥67% faster, +84% precision, +20% recall over PyCG, but is a research prototype [R17].

## 2. TypeScript/JavaScript static options

| Tool | License | Call graph | Taint | Effort |
|---|---|---|---|---|
| TS Compiler API | Apache-2.0 [R18] | Yes: `checker.getSymbolAtLocation`, `getResolvedSignature`, re-export/aliasing resolution [R18] | DIY fixpoint over def-use; no builtin taint | M–L |
| ts-morph | MIT [R19] | Wraps TS API; navigation/symbols, no call-graph helper | DIY; same as above with nicer API; best for AST-range work (mutation, LDH spans) | M |
| SWC | Apache-2.0/MIT [R20] | Parser only (no type checker) | Syntax-only approximations | S–M, weak |
| Babel | MIT [R21] | Parser/transform plugin API (what istanbul uses) | Syntax-only | S–M, weak |
| CodeQL JS/TS | see R1–R3 | Yes | Yes (full taint libs) | M; same licensing caveat |
| Semgrep CE | see R6 | Intra-function taint; no CG | Yes (intraprocedural; `--pro-intrafile` Pro) | S–M |

Verdict: for an OSS toolkit, ts-morph (LDH span extraction + local dataflow) is the pragmatic base; SWC/Babel are for speed, not semantics. CodeQL JS/TS if OSS-licensed targets allow it.

## 3. Runtime alternatives to static taint

- Python: `sys.monitoring` (3.12+) exposes `BRANCH` (and `LINE`, `CALL`, `JUMP`) events; verified locally on 3.14 (`sys.monitoring.events.BRANCH` present) [R22]. `sys.settrace` works everywhere but is slow unless C-implemented (coverage.py's ctrace is).
- LLM-value tagging without full taint: wrap the provider SDK client; return a `Proxy`/dict subclass that registers tagged leaves in a `WeakSet`/`WeakKeyDictionary`; then intersect "branches executed after a tagged value was live" with static LDH candidates. This is a *may-depend* signal, not may-flow taint.
- Prior art: dynamic taint for Node exists as research infrastructure — NodeMedic/NodeMedic-FINE (provenance graphs; Jalangi2 instrumentation ≈59% overhead), Augur/NodeProf [R23][R24][R25]; taint-spec extraction via library "membranes" (Taser, ICSE'20) [R26]. Python: pytaint (forked CPython), PyT (static), PolyTracker (LLVM binaries) [R27][R28][R29]. No turnkey runtime taint for LLM SDK responses exists.
- Node: `node:inspector` `Profiler.startPreciseCoverage({detailed:true})` (block ranges; what Vitest v8 uses) [R30][R31]; `async_hooks`/`AsyncLocalStorage` for context propagation; `diagnostics_channel` to emit tag events; `module.register()` loader hooks to rewrite imports [R32][R33][R34].

Feasibility: proxy tagging is S–M effort and language-agnostic; soundness is the catch (serialization to/from JSON and Pydantic/Zod coercion produce untagged copies; C-extension boundaries are opaque).

## 4. Coverage plumbing

- coverage.py 7.x: three cores — `ctrace`, `pytrace` (`sys.settrace`), `sysmon` (`sys.monitoring`). `sysmon` is much faster (often <5% overhead for line coverage) but "complex features like dynamic contexts are not supported yet" (as of 7.16.x); dynamic contexts and FileTracer plugins require the C tracer [R35][R36][R37]. For LDH subset reporting we do **not** need plugins: run normal coverage, then `coverage json` (executed_lines/executed_branches/contexts with `--show-contexts`) and intersect with the static LDH line/branch set — S effort. A `DynamicContext` plugin is only needed for live per-test attribution [R37].
- istanbul JSON: per-file `statementMap`/`branchMap` carry explicit `loc.start.line/column` → subsetting by source range is post-hoc trivial; merge/filter via `istanbul-lib-coverage` [R38][R39].
- Vitest: providers `v8` (default; raw ranges are UTF-16 offsets → must remap first) and `istanbul`; since v3.2 v8 uses AST-based remapping producing istanbul-identical reports [R40]. V8 "does not support limiting coverage collection to specific modules" [R40]. Custom reporter: extend `istanbul-lib-report` `ReportBase`; custom provider via `provider: 'custom'` + `customProviderModule` [R40].

## 5. Mutation tooling scoping (exact evidence)

| Tool | Scope control (verified) | Line-level? | Effort |
|---|---|---|---|
| mutmut 3 (read from clone) | `only_mutate`/`do_not_mutate` are **file globs only** (`must end with ".py" or "*"`) [R41]; internal filter uses `self._covered_lines` per-node line check (`file_mutation.py` L283) + config `mutate_only_covered_lines` [R42]; rewriting via libcst [R42] | Not via config; line filter exists internally, and mutants are function-granular (trampoline rewrite) → map LDH lines to enclosing functions or drive `FileMutationGenerator` directly | M |
| cosmic-ray | TOML: `module-path` (file/dir), `excluded-modules` globs, `[operators]` parameterized selection; session = SQLite work items (module_path, operator, occurrence) [R43][R44][R45] | No line ranges; occurrence/operator granularity | M |
| StrykerJS | `mutate: ["src/app.js:1-11"]`, `"src/app.js:5:4-6:4"` — exact ranges; cannot combine range with glob [R46]. Programmatic: `new Stryker(opts).runMutationTest()`; standalone `@stryker-mutator/instrumenter` [R47] | **Yes, first-class** | S |
| Own AST mutator | libcst (Python; mutmut 3 already depends on it) [R42]; ts-morph / Stryker instrumenter (TS) | Full control; reimplements mutant-kill bookkeeping | M–L; only if needed |

Verdict: TS → StrykerJS ranges directly. Python → mutmut with an LDH→function map (accept function granularity) or a libcst-based side-mutator; cosmic-ray only if its operator plugin API helps (it is parso-based [R43]).

## 6. Schema / contract generation tooling

- Python: pydantic v2 as single source of truth (JSON Schema via `model_json_schema`) [R48]; `instructor` for validated calls/retries over SDKs [R49]; `outlines` for constrained decoding (FSM/regex) [R50]; `guidance` for interleaved generation + tool calls [R51]. Boundary fuzzing: Hypothesis + `hypothesis-jsonschema.from_schema` for schema-valid instances, native shrinking [R52][R53].
- TS: `zod` (`safeParse`) [R54] or `typebox`+`TypeCompiler` (fast validation) [R55]; `ajv` for raw JSON Schema [R56]; `fast-check` for arbitraries + shrinking [R57].
- Best combination for provider responses + tool-call sequences: one schema per provider response/tool I/O; generate boundary variants from the schema (not from prose); encode tool-sequence invariants (call/result pairing, arg schema, state transitions) as an explicit state machine whose transitions are schema-validated; generate sequences via Hypothesis `RuleBasedStateMachine` (Py) / fast-check `commands` model (TS) [R52][R57]; validate every generated artifact with the same validator before replay so fixtures stay contract-faithful.

## 7. Recommended minimal stack per language

Python (all OSS, $0): Semgrep CE + our own source/sink taint rules (sources: openai/anthropic/google-genai/litellm/langchain entrypoints; sinks: every statement consuming the returned value) → transitive LDH closure via a stdlib `ast`+`symtable` fixpoint caller graph (PyCG-style; PyCG is archived) [R10][R11]; optional CodeQL Python as an OSS-repo cross-check [R1]. Runtime tagging: `wrapt`/Proxy wrapper on the provider client + `WeakKeyDictionary` ledger; pytest plugin reports LDH subset from `coverage json` vs static LDH spans [R35]. Mutation: mutmut (LDH→function mapping, `mutate_only_covered_lines` off) or a small libcst mutator [R41][R42]. Contracts: pydantic v2 + Hypothesis + hypothesis-jsonschema [R48][R52][R53].

TypeScript ($0): ts-morph for LDH spans + local dataflow [R19]; Proxy-based tagging of provider SDK clients (`openai`, `@anthropic-ai/sdk`, Vercel AI SDK); Vitest istanbul provider (or v8 with v3.2+ remap) + custom reporter doing LDH-range subsetting via istanbul-lib-report [R40][R39]; StrykerJS with `--mutate file:startLine-endLine` [R46][R47]; schema via zod or typebox; sequences/edge cases via fast-check command model [R55][R57].

## 8. Effort estimate (S ≤ ~1 wk, M ~2–4 wks, L > 1 month, per component, one strong engineer)

| Component | Python | TS | Notes |
|---|---|---|---|
| Source/sink discovery + LDH closure | M | M | rule authoring + fixpoint CG; framework indirection is the risk |
| Runtime tagging layer (Proxy + ledger) | S–M | S–M | soundness limited by serialization/coercion |
| LDH subset coverage + reporter | S | S–M | JSON subsetting either side; custom reporter needed for Vitest UX |
| LDH-scoped mutation runner | M | S | mutmut function-level mapping vs Stryker ranges |
| Contract generator (responses) | S | S–M | schema-of-truth + validator loop |
| Tool-sequence generator + shrinker | M | M | state machine over schemas; invariants are the work |
| Differential oracle harness (buggy vs fixed rev) | M | M | needs bench corpus (agent repos) |

## 9. Top failure modes and mitigations

1. Static taint misses LDH through dynamic dispatch: PyCG recall ~70% (precise but incomplete) [R11]; Joern Python approximated [R8]; PyCG archived [R10]. Mitigate: union static candidates with runtime tagging ledger; fail open (report uncertainty), never gate on static-only.
2. Runtime tagging false negatives at value boundaries: JSON round-trips and pydantic/zod coercions strip proxies; C extensions opaque. Mitigate: tag at the narrowest boundary (post-parse object) + AST checkpoints; Taser-style membrane approach for library calls [R26]; measure recall on 2–3 real repos before committing.
3. Mocking mismatch / heavy mocking is the norm in agent tests: 34.4% of tests mock agent or tool; shallow validation, simplistic inputs (Tangent, ASE'26) [R58]. Mitigate: our fixtures are contract-validated (schema-parse before replay), and a lint flags mocks that bypass the LDH harness under test.
4. Cassette staleness: VCR default `once` replays old episodes and errors on new requests; stale fixtures silently drift from provider contracts [R59]. Mitigate: schema-validated fixtures + periodic re-record mode (`all`) + contract diff job; treat cassettes as generated artifacts.
5. Non-determinism/flakiness: LLM classification non-determinism 0–25% Hamming distance even at temperature 0 [R60]; classic Python flakiness sources (order, network, time, randomness) [R61]. Mitigate: deterministic fixtures in CI, seeds recorded, retries only outside measurement (never mask mutation survivors with retries).
6. Adversarial tool outputs are themselves an attack surface: indirect prompt injection reaches agents through tool results; benchmarks show 24%+ attack success on ReAct-style agents (InjecAgent) and real tool-calling environments (AgentDojo) [R62][R63]. Mitigate: generator emits payloads into sandboxed sinks only; never feed generated tool output back into a live agent; delimit/inspect channels in test harness.
7. Subset coverage ≠ LDH coverage: a branch executed after a tagged value was live may not depend on it (may-depend vs may-flow). Mitigate: report two tiers (executed-with-tagged-live vs statically-LDH), and use mutation score on LDH as the stronger signal.
8. Mutation noise: equivalent mutants and function-granular trampolines in mutmut inflate survivors; Stryker mutator set differs. Mitigate: restrict operator sets (cosmic-ray `[operators]`, Stryker `excludedMutations`), triage survivors with differential oracle, accept documented noise floor.
9. Tooling licensing/version traps: CodeQL CLI ToS bars non-OSS/CI use without GHAS and bars redistribution [R2]; Semgrep registry rules can't ship in our product [R6]; coverage.py `sysmon` can't do dynamic contexts yet [R35]; Vitest v8 can't limit collection to modules and pre-3.2 branch data was remap-dependent [R40].

## 10. Riskiest unknowns (de-risk first)

1. Static taint recall on real agent repos (LangChain/LlamaIndex/Vercel AI SDK dispatch, wrappers, retries) — measure LDH recall vs runtime ledger on 5–10 repos before choosing engine.
2. Proxy-tagging survivability through async pipelines, caching layers, and schema coercion — spike on 2 repos per language; quantify tag loss.
3. Python mutation granularity: whether LDH→function mapping (mutmut) yields a usable signal or forces a libcst mutator; and whether contract-faithful fixtures can actually kill LDH mutants at acceptable cost.

## References

All URLs accessed 2026-10-15.
[R1] https://docs.github.com/en/code-security/concepts/code-scanning/codeql/codeql-cli
[R2] https://raw.githubusercontent.com/github/codeql-cli-binaries/main/LICENSE.md (GitHub CodeQL Terms and Conditions)
[R3] https://github.com/github/codeql/blob/main/LICENSE (MIT, queries)
[R4] https://codeql.github.com/docs/writing-codeql-queries/creating-path-queries
[R5] https://codeql.github.com/codeql-standard-libraries/python/codeql/dataflow/TaintTracking.qll/module.TaintTracking.html
[R6] https://semgrep.dev/docs/licensing
[R7] https://docs.semgrep.dev/writing-rules/data-flow/taint-mode/overview
[R8] https://docs.joern.io/frontends/python ; https://docs.joern.io/frontends/ (Apache-2.0)
[R9] https://docs.joern.io/cpgql/reference-card
[R10] https://github.com/vitsalis/pycg (archived)
[R11] https://arxiv.org/abs/2103.00587 (PyCG, ICSE'21)
[R12] https://github.com/SMAT-Lab/Scalpel (Apache-2.0)
[R13] https://arxiv.org/abs/2202.11840 (Scalpel)
[R14] https://github.com/facebook/Pysa (MIT)
[R15] https://pyre-check.org/docs/pysa-running
[R16] https://pyre-check.org/docs/pysa-advanced (broadening/widening)
[R17] https://arxiv.org/abs/2305.05949 (JARVIS)
[R18] https://github.com/microsoft/TypeScript/wiki/Using-the-Compiler-API ; https://github.com/microsoft/TypeScript/blob/main/LICENSE.txt
[R19] https://ts-morph.com/ ; https://www.npmjs.com/package/ts-morph
[R20] https://swc.rs/
[R21] https://babeljs.io/docs/
[R22] https://docs.python.org/3/library/sys.monitoring.html (verified locally: Python 3.14, `sys.monitoring.events.BRANCH` present)
[R23] https://www.andrew.cmu.edu/user/liminjia/research/papers/nodemedic-eurosp23.pdf
[R24] https://www.ndss-symposium.org/wp-content/uploads/2025-1636-paper.pdf (NodeMedic-FINE)
[R25] https://github.com/nuprl/augur (NodeProf dynamic taint)
[R26] https://github.com/cs-au-dk/taser ; https://dl.acm.org/doi/abs/10.1145/3377811.3380390 (membranes, ICSE'20)
[R27] https://github.com/felixgr/pytaint
[R28] https://pypi.org/project/python-taint/ (PyT, static, 2018)
[R29] https://pypi.org/project/polytracker/
[R30] https://v8.dev/blog/javascript-code-coverage
[R31] https://github.com/istanbuljs/v8-to-istanbul
[R32] https://nodejs.org/api/inspector.html
[R33] https://nodejs.org/api/async_context.html ; https://nodejs.org/api/diagnostics_channel.html
[R34] https://nodejs.org/api/module.html#moduleregister
[R35] https://coverage.readthedocs.io/en/latest/howitworks.html (cores; sysmon lacks dynamic contexts)
[R36] https://nedbatchelder.com/blog/202312/coveragepy_with_sysmonitoring (<5% overhead, experimental caveats)
[R37] https://coverage.readthedocs.io/en/latest/plugins.html ; https://coverage.readthedocs.io/en/latest/api_plugin.html
[R38] https://github.com/gotwarlost/istanbul/blob/master/coverage.json.md
[R39] https://github.com/istanbuljs/istanbuljs/blob/main/packages/istanbul-lib-coverage/index.js
[R40] https://vitest.dev/guide/coverage.html ; https://vitest.dev/config/coverage
[R41] https://github.com/boxed/mutmut/blob/master/src/mutmut/configuration.py (cloned 2026-10-15; `only_mutate` L157–164)
[R42] https://github.com/boxed/mutmut/blob/master/src/mutmut/mutation/file_mutation.py (cloned 2026-10-15; `_covered_lines` L283, libcst L17)
[R43] https://cosmic-ray.readthedocs.io/en/latest/reference/cli.html ; https://cosmic-ray.readthedocs.io/en/latest/concepts.html
[R44] https://cosmic-ray.readthedocs.io/en/latest/reference/api/cosmic_ray.html
[R45] https://github.com/sixty-north/cosmic-ray/blob/master/src/cosmic_ray/config.py (cloned 2026-10-15; `operators_config` → `operators` dict)
[R46] https://stryker-mutator.io/docs/stryker-js/configuration/ (mutation range syntax)
[R47] https://github.com/stryker-mutator/stryker-js/blob/master/packages/core/README.md (programmatic `Stryker`) ; packages/instrumenter
[R48] https://docs.pydantic.dev/latest/concepts/json_schema/
[R49] https://python.useinstructor.com/
[R50] https://dottxt-ai.github.io/outlines/
[R51] https://github.com/guidance-ai/guidance
[R52] https://hypothesis.readthedocs.io/en/latest/
[R53] https://hypothesis-jsonschema.readthedocs.io/en/stable/
[R54] https://zod.dev/
[R55] https://github.com/sinclairzx81/typebox
[R56] https://ajv.js.org/
[R57] https://fast-check.dev/docs/
[R58] https://arxiv.org/abs/2608.08413 (Tangent, ASE'26, Pan et al.; 2572 labeled tests, 34.4% mock agent/tool)
[R59] https://vcrpy.readthedocs.io/en/latest/usage.html (record modes once/new_episodes/none/all)
[R60] https://arxiv.org/abs/2602.05465 (LLM flaky-test classification non-determinism 0–25% at temp 0)
[R61] https://arxiv.org/html/2101.09077v1 (flaky tests in Python)
[R62] https://arxiv.org/abs/2403.02691 (InjecAgent)
[R63] https://arxiv.org/abs/2406.13352 (AgentDojo, NeurIPS'24 D&B)
