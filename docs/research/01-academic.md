# 01 — Academic Deep Dive: HarnessTester / "Complex Agents, Shallow Tests" (arXiv:2610.04921)

All sources accessed 2026-10-15. Local copies: paper text at `/tmp/research/paper.txt`, artifact shallow clone at `/tmp/research/ht-artifact` (blob-filtered).

## 0. Paper metadata

- **Title:** Complex Agents, Shallow Tests: Demystifying and Enhancing Test Adequacy of Agent Harness in the Wild
- **Authors:** Yifan Xiong, Jingyi Ge, Zhenpeng Chen, Yiling Lou. **v1 submitted 4 Oct 2026**, cs.SE/cs.AI, arXiv nonexclusive license.
- Sources: https://arxiv.org/abs/2610.04921 (abs), https://arxiv.org/html/2610.04921v1 (full text; all section/line refs below are to this HTML text).

## 1. LDH definition and extraction

- **Definition (verbatim-ish):** LDH is "the harness code that has data dependency or control dependency on the outputs of LLM invocations." Formally `LDH(A) = {h ∈ H(A) | ∃s ∈ S_LLM. s →_d h}`, where `S_LLM ⊆ Stmt(A)` are LLM invocation statements producing model outputs, `H(A)` the harness statements, and `→_d` is direct or transitive dependence. (paper §3.1)
- **Rationale:** LDH "interprets diverse and nondeterministic LLM outputs" and errors propagate through the agent workflow; the paper cites Chen et al. 2026 for agent bugs at the LLM–harness boundary. (paper §1, §3.1)
- **Extraction:** an interprocedural harness analysis tool that "models LLM invocations as sources and propagates the corresponding data- and control dependency facts throughout the program until a fixed point is reached." Counts all **explicit dependency** through assignments, field/container accesses, parameter and return flows, and "other taint-preserving transformations." Sources include values returned from LiteLLM's `completion` and OpenAI client provider provenance (Listing 1). Methods are left in the artifact. (paper §3.1)
- **Artifact implementation:** `src/llm_dependent/` — Python (`flow/analysis.py`, `facts.py`, `indexing.py`, `resolver.py`, `providers.py`, `source_rules.py`) and TypeScript (`flow/fact_analysis/worklist.mjs`, `resolver/*`, `indexing/*`) implementations; TS uses an explicit worklist/fixed-point scheme. Entry: `python3 run.py llm-dependent --project X` → `regions.json`. (artifact README; https://github.com/yifanxiong272/harnesstester_artifact)

## 2. HarnessTester technique

Coverage-driven paradigm: iteratively targets **LDH code uncovered by existing tests** and generates new tests for the target. Two mechanisms augment general LLM test generation. (paper §6)

### 2.1 Agent-harness contracts and contract guidance (prompt level)

- **Definition:** agent-harness contracts are "the requirements that must hold across interactions among harness components for valid execution, such as expected data structures, execution preconditions, and interaction protocols" — grounded in classic software contracts (Meyer 1992; Beugnard et al. 1999). (paper §4, §6)
- **Guidance principles (paper):** preserve runtime representations of provider responses, tool actions, and observations; construct the agent state/interaction history needed to reach the target; respect cross-component invocation contracts (sync/async conventions, return shapes); install contract-faithful test doubles at the actual bindings/injection points used by code under test; prioritize distinct behavioral partitions (diversity) over variants of exercised behavior. (paper §6)
- **Guidance verbatim in artifact** (`src/augment/python/prompt/prompts.py`): "You must account for agentic contracts when they are relevant: - preserve provider, tool, action, message, and observation payload shapes; - construct the state or history needed to reach the branch; - match sync or async call signatures and return shapes exactly; - patch the symbol where the code under test resolves it; - avoid live models, network access, external services, and real API keys." The **contract-agnostic** variant keeps only the last bullet (`--strategy contract_agnostic`).

### 2.2 Contract context retriever (tool level)

- LLM calls the retriever on demand with a **source file + exact symbol name** (often inferred from imports, e.g. `from pkg.actions import Action` → `pkg/actions.py`).
- Retriever resolves deterministically via **AST-based matching for symbol definitions with bounded extraction of surrounding module context**; returned definitions expose fields/types so the LLM can build contract-faithful mocks. Complements high-level guidance with repository-specific context. (paper §6; artifact `augment/python/prompt/context.py`, `input/`)

### 2.3 Iteration loop and prompts (artifact-visible)

- Round-based generation with a 120-min/`--time-budget-seconds` budget (or `--rounds N`); per round it reads exact missing lines/branches from a packet, then the model returns a JSON `propose_test` (test_file, append_code, expected_nodeids, targeted_objective_ids, targeted_lines, mocking_strategy, oracle). Rejected candidates get a **feedback prompt** (diagnosis + minimal repair + optional context requests; `--repair-context-requests N`, default 0). Accepted tests/coverage deltas in `results.json`/`coverage.json`. (`src/augment/python/templates/frozen_coverage_segment_prompt.md`, `..._feedback_prompt.md`, `src/augment/README.md`)
- Separate **Probe** flow for bug reproduction: plan → implement → minimize prompts, plus a repair/decision prompt that can request exact context (`filepath` + AST `qualname`) and forbids using issue text/diffs/official tests/live models. (`src/probe/*/prompt/templates/target_harness_repair*.md`)

## 3. Evaluation numbers

**Subjects:** 10 agents — Python: OpenHands, Aider, SWE-agent, PR-Agent, GPT Researcher, Browser Use, RD-Agent; TS: OpenClaw, Roo Code, Kimi Code. Selection: studied by prior work + ≥10,000 GitHub stars + release within 18 months + reproducible test suite + domain/language diversity. OpenClaw: 346K stars, harness >196K LOC. (paper §3.2, Table 1)

**RQ1 (test adequacy):** LDH share avg **22.35% lines / 31.71% branches** (branch share 1.10–1.75× line share). LDH coverage avg **44.27% line / 41.18% branch**; project-wide **49.48% / 36.84%**; mutation score over LDH avg **33.60%** (3.58% RD-Agent … 70.94% Kimi Code). ~38.36% of surviving mutants never executed; 25.92% executed but undetected. Tools: coverage.py / Vitest providers; mutmut / StrykerJS. (paper §4, Table 2)

**RQ2 (semantics):** 700 sampled LDH branch predicates, κ=0.96. 6 component-intention categories (Provider I/O Normalization 29.14%, Tool Action Handling 23.57%, +); 47.14% are presence/shape checks; 5 value forms (generated content 25.00%, provider response signals 6.57%, agent context state 21.71%, tool action payloads 21.71%, observation feedback 25.00%). Coverage: **25.57% fully / 24.57% partially / 49.86% uncovered**; gaps concentrate in dynamic-context, open value-space categories (e.g. orchestration). (paper §5)

**RQ3 (improvement):** backbones **GPT-5-mini**, **120-min budget per project**; baselines CoverUp + TestTailor (Python), Qodo Cover + TestPilot 2 (TS), plus contract-agnostic variant; general vs scoped-LDH settings. HarnessTester at 120 min: macro-averaged LDH gains **+25.84 / +25.41 pp** (line/branch; up to +68.77 pp line on GPT Researcher); vs strongest *scoped* baseline **82.27% / 94.36% larger**; vs strongest *general external* baselines **95.29% / 109.22% larger**; headline (abstract/intro) **75.95% / 84.76% larger mean line/branch gains and 69.89% larger mean mutation-score gain** vs the strongest baseline selected per agent/metric. Mutation: best gain on every agent (SWE-agent +43.01 pp vs CoverUp +22.15; OpenClaw +0.39 pp = 185 kills over 46,967 mutants vs 147 Qodo / 141 agnostic). Ablations: contract-agnostic gets 96.51%/96.24% smaller gains; guidance-only −43.26%/−45.98% and retriever-only −37.38%/−41.00% on OpenHands. Project-wide gains 13.90/17.30 pp vs best general 10.36/11.58. (paper §7, abstract)

**RQ4.a — H-Bench (historical bugs):** benchmark of **250 real-world harness bugs** (140 across 7 Python agents, 110 across 3 TS agents) mined from bug-fixing commits whose patch touches LDH; only bugs *not* exposed by any existing test in the buggy revision (leakage control). Per case the buggy location is given as target; detection = test fails on buggy and passes on fixed; all plausible detections manually reviewed. **HarnessTester 43 TP / 7 FP at $77.58 total ($1.80 per revealed bug) vs best baseline 2 TP / 0 FP at $21.68 ($10.84/bug); contract-agnostic 15 TP / 5 FP at $64.92**, FP share 14.00% vs 25.00%. Detection rate 17.20% vs 0.80%. (paper §8.1, Table 4)

**RQ4.b — previously-unknown bugs:** latest releases; OpenHands split into Canvas + SDK; 100 LDH functions per agent targeted; failures manually triaged and reported. **122 true harness bugs = 88 previously unknown + 34 known; 69 confirmed by developers, 64 fixed or with open fixes, one assigned a CVE number**; total cost **$81.64** (per-agent $5.80–9.16). Roo Code repo was archived (no issues could be filed). Example: Browser Use sensitive-data leakage (nested-list values bypass `redact_dict`/`redact_list`). (paper §8.2, Table 5)

## 4. Threats to validity (paper §9, verbatim-ish)

- **External:** "The generality of our findings can be scoped to our studied agents." Mitigations: diverse, actively developed systems; representative baseline set; "other techniques or models may yield different results"; benchmark + implementation released for replication.
- **Internal:** RQ2 semantic analysis relies on manual labeling; mitigated by two annotators with an explicit codebook (κ=0.96, third reviewer for disagreements). Metric calculation/implementation may have errors; mitigated by validating intermediate results, manual inspection of representative cases, established coverage/mutation tools.
- No construct-validity paragraph exists.

## 5. Artifact assessment (github.com/yifanxiong272/harnesstester_artifact)

- **Presence:** real, substantial code — 33,572 tree entries, ~400 MB. **Created 2026-09-30; last push 2026-10-06** (commit `b13057e` "Restore public bug reports and tests"); 0 stars / 0 forks. GitHub API reports `license: null` and **no top-level LICENSE file** (only bundled third-party licenses under `resources/subjects/`). Primary language per GitHub: TypeScript (because of vendored checkouts). (GitHub API + tree, accessed 2026-10-15)
- **Architecture:** `src/llm_dependent/` (LDH extraction; Python + TS), `src/augment/` (HarnessTester generation; prompts/strategy/validation; Python + TS), `src/probe/` (historical & latest-revision bug probing), `src/collect_coverage/`, `src/cli/`, `src/common/`. Single entry point **`run.py` with `setup | llm-dependent | augment | probe`**; per-component READMEs; module + CLI tests under `src/*/tests` and `tests/`.
- **Data:** `resources/inputs/<project>/` includes `regions.json`, coverage, base inputs; `resources/benchmark/cases/` holds the **250 H-Bench cases** (matching Table 4 counts: OpenClaw 88, OpenHands 42, Browser Use 41, Aider 19, Roo Code 16, RD-Agent 16, PR-Agent 11, SWE-agent 7, Kimi Code 6, GPT Researcher 4) plus dependency ZIPs; `dataset/` contains RQ1–RQ4 results (coverage/mutation CSVs, generated tests, figures, rq2 annotations, `rq4/roots.csv` = 119 public bug records of the 122, `submitted_issues.csv`, `historical/records.csv`).
- **Environments:** Ubuntu 22.04, Python 3.12.13 via uv 0.12.3, Node 24.15.0 + pnpm 10.32.1; needs `OPENAI_API_KEY` for augment/probe (`.env.example` default `gpt-5-mini`); extraction is fully static (no key needed).
- **Reusability:** CLI-first but packaged like a library (`src/common`, programmatic runners per component); prompt templates are plain Markdown files, easy to adapt; extraction can run on new projects via `projects.json` registration. **Caveat: no license → reuse terms unclear.**

## 6. Related-work scan (only sources actually opened)

- **Chen et al. 2026** (the paper's "agent bugs at the LLM–harness boundary" citation): arXiv:2607.15684, "Understanding Agent-Reactive Bugs at the Model-Harness Boundary" (255 issue reports; silent errors without oracles; LLM stochasticity complicates reproduction). https://arxiv.org/abs/2607.15684 — motivates LDH as a testing target.
- **Pan et al. 2026b = "Tangent"** (the paper's citation under Pan et al. 2026b): arXiv:2608.08413 / ASE'26 DOI 10.1145/3832783.3837414 — 2,572 labeled test methods from 240 modules; 61.8% unit-level; 23 test patterns; heavy mocking, shallow validation, low complexity; used to argue current practice leaves interaction behavior untested. (No paper literally titled "How are agentic systems tested" was found; see Uncertainties.)
- **Hasan et al. 2026**: EMSE 31(5), DOI 10.1007/s10664-026-10857-9 (arXiv:2509.19185) — 39 agent frameworks + 439 applications; testing-effort inversion (tools/workflows >70%, FM Plan Body <5%, prompts ~1%); complements HarnessTester's "harness undertested" claim.
- **Kohl et al. 2026**: arXiv:2601.18827 (IEEE BigData 2025) — structural testing of agents via OpenTelemetry traces + LLM mocking + assertions (awslabs/generative-ai-toolkit); closest prior "test the harness, not just acceptance" line of work.
- **Baselines:** CoverUp (arXiv:2403.16218; PACMSE/FSE DOI 10.1145/3729398; repo plasma-umass/coverup), TestTailor (PACMSE/FSE 2026, DOI 10.1145/3797140; path-proximal tests + symbolic constraints), Qodo Cover (github.com/qodo-ai/qodo-cover, AGPL-3.0, 5,662★, last push 2026-04-05), TestPilot 2 (github.com/neu-se/testpilot2, TypeScript, 33★; original TSE'24 TestPilot by Schäfer et al.).
- **Follow-ups citing HarnessTester:** **none found** as of 2026-10-15 — Semantic Scholar citations endpoint for arXiv:2610.04921 returned `{"offset": 0, "data": []}`; OpenAlex `cited_by_count = 0`; arXiv API full-text search for "HarnessTester" returned no hits. Paper is 11 days old.
- **Harness evolution/optimization (motivation only):** Self-Harness (arXiv:2606.09498) — self-improving harness loop whose Proposal Validation gate is regression testing; HarnessDev (arXiv:2609.01437) — LLM-created harnesses lag human references on code/search, evolution gains unstable; arXiv:2604.07236 — harness layers carry much of a planning agent's competence, framing the harness itself as reliability-critical.

## 7. What is reproducible / What is not

| Capability | Verdict | Why / what it needs |
|---|---|---|
| LDH extraction (regions) | ✅ Cheap, local | Static analysis, no API key; Python 3.12 + Node; bundled checkouts + `run.py llm-dependent` |
| Coverage methodology (RQ1) | ✅ Cheap, local | `collect_coverage/*` + bundled `coverage.json`; coverage.py / Vitest; no LLM |
| RQ2 taxonomy data | ✅ Data yes, ⚠️ labels manual | `dataset/rq2` has annotated 700-branch set + figures; re-labeling needs weeks of human effort |
| H-Bench execution (RQ4.a) | ⚠️ Paid + env-heavy | 250 cases bundled with dependency ZIPs; per-case buggy/fixed build + LLM calls; ~$77 was HarnessTester-only, baselines extra |
| RQ3 generation campaign | ⚠️ Paid + ~120 h+ | 6 techniques × 10 projects × 120-min budget with GPT-5-mini; total API cost never reported |
| RQ4.b unknown-bug discovery | ❌ Not reproducible | Targets latest revisions (moving), needs manual triage + issue reporting; outcome record only |
| Full mutation campaign | ⚠️ Compute/time | StrykerJS pools up to 46,967 mutants (OpenClaw); no GPU, but heavy CPU time |
| Anything GPU-based | N/A | Whole evaluation is API + local test execution; cost is **$ and wall-clock, not GPU** |

## 8. Uncertainties (could not verify)

1. **Two headline aggregates don't reconcile cleanly:** abstract/intro "75.95%/84.76% larger line/branch gains, 69.89% mutation gain" vs §7 "82.27%/94.36%" (scoped) and "95.29%/109.22%" (general). The 75.95/84.76 likely means mean gains vs per-agent best baseline across mixed settings, but the paper does not spell out the aggregation.
2. **No exact "How are agentic systems tested" paper by Pan:** the harness paper's Pan et al. 2026b is Tangent; the task's title may conflate it with Pan et al. 2026a ("Measuring agents in production", arXiv:2512.04123), which I did not open.
3. **Artifact has no license** (GitHub API null; no LICENSE file at root) — legal reuse/redistribution status unknown.
4. **Repo history shows a restore** ("Restore public bug reports and tests", 2026-10-06): earlier force/removal history not inspected; data completeness vs a hypothetical first version unverified.
5. **Prompt coverage not exhaustive:** I read the Python augment guidance/templates and one Probe repair template; TS variant and all Probe prompts were not line-by-line verified.
6. **RQ3 total API cost not reported** (only RQ4 costs) — full replication budget is unknown.
7. **The single CVE is unnamed** in the paper and in the repository data I inspected; not identified.
8. **Citation search limits:** Semantic Scholar search endpoint rate-limited (429); Google Scholar not queried; "no follow-ups" rests on S2 citations API + OpenAlex + arXiv full-text search on 2026-10-15.
