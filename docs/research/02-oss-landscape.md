# 02 — OSS landscape: testing LLM-dependent agent code

Primary-source scan, **2026-10-15**. Method: GitHub REST (`api.github.com/repos/<repo>`, `/commits?per_page=1`) and Atom feeds; PyPI JSON; npm registry; Maven Central; READMEs via raw.githubusercontent.com; official doc sites. Unauthenticated API (rate-limited; search is partial). **All URLs below accessed 2026-10-15.** LDH = "LLM-dependent harness": branch coverage of app code + contract-faithful fixtures (project hypothesis under test, not an existing standard).

## 1. Comparison table (15 most relevant)

Columns: Replay = mocks/records/replays LLM HTTP · Cov = measures app-code coverage · Mut = mutates app code · Adv = generates adversarial inputs/sequences · Gap vs LDH positioning.

| Name | Stars | License | Last release / last commit | Replay | Cov | Mut | Adv | Gap vs LDH |
|---|---|---|---|---|---|---|---|---|
| promptfoo | 26,017 | MIT | npm 0.124.1 / 2026-10-15 | Partial (disk response cache) | No | No | Yes (redteam plugins/strategies incl. agents) | Black-box probes; no branch coverage, no request-contract fixtures |
| deepeval | 18,890 | Apache-2.0 | PyPI 4.3.0 / 2026-10-15 | No | No | No | Partial (README: "native red teaming" via platform; synthesizers) | Output judges only; cannot say which app branch executed |
| inspect_ai (UK AISI) | 3,011 | MIT | PyPI 0.3.280 / 2026-10-15 | Partial (model-output cache, key incl. tools) | No | No | Partial (Scanners) | Eval harness; nothing measures app branching; no HTTP cassettes |
| langsmith-sdk + openevals | 1,081 + 1,224 | MIT | langsmith 0.14.9 (2026-10-15); openevals 0.2.0 / 2026-10-14 | Yes (pytest plugin caches HTTP to disk: `LANGSMITH_TEST_CACHE`) | No | No | No (agentevals = trajectory evals) | Closest incumbent mechanic, but cache is a response blob: no branch attribution, no synthesized/contract-checked fixtures |
| braintrust | 22 + 29 (split SDK repos) | Apache-2.0 | PyPI 0.46.0 / 2026-10-15 | Partial (gateway/proxy response cache; base-URL swap) | No | No | No | Server-side cache only; no local fixtures, no coverage |
| ragas | 16,033 | Apache-2.0 | PyPI 0.4.3 / repo 2026-02-24 (slowing) | No | No | No | Synthetic testset generation (not adversarial sequences) | RAG metric suite; no repo instrumentation |
| PyRIT | 4,628 | MIT | PyPI 1.1.0 / 2026-10-15 | No | No | No | Yes (attack automation) | Model-safety attacks; nothing about app code paths or tool-branch coverage |
| vcrpy | 3,021 | MIT | PyPI 8.3.0 / 2026-10-13 | Yes (cassettes; httpx/httpcore support) | No | No | No | Golden-capture replay: stale fixtures pass silently; no contract validation, no branch mapping |
| pytest-recording | 616 | MIT | 0.14.0 / 2026-10-01 | Yes (vcrpy + network blocking) | No | No | No | Same as vcrpy, pytest-native |
| respx | 841 | BSD-3-Clause | 0.23.1 / 2026-04-23 | Mock-only (httpx routes/side effects) | No | No | No | No recording; fixtures hand-written |
| mutmut | 1,484 | BSD-3-Clause | 3.8.0 / 2026-09-12 | n/a | Optional coverage.py line filter for mutants | Yes | No | Scope = module/function wildcards + pragmas; no `file:line-range` CLI; not LLM-aware |
| StrykerJS | 3,228 | Apache-2.0 | core 10.0.0 / 2026-10-10 | n/a | perTest coverage analysis | Yes | No | Has `--mutate "src/app.js:1-11"` but no LLM-branch targeting |
| PIT (pitest) | 1,875 | Apache-2.0 | 1.30.1 (Maven, 2026-10-14) | n/a | Mutation + coverage export | Yes | No | Class/method/test globs only; no line-range in OSS (issue #794; arcmutate is commercial) |
| coverage.py | 3,420 | Apache-2.0 | 7.16.2 / 2026-10-15 | n/a | Yes (line+branch; dynamic contexts) | No | No | Can attribute lines→tests (`switch_context`); nothing wires it to LLM decision points |
| nyc / c8 | 5,759 / 2,122 | ISC | 18.0.0 (2026-02-22) / 12.0.0 (2026-07-14) | n/a | Yes (Istanbul/V8) | No | No | No dynamic contexts; report plumbing only (v8-to-istanbul 136★ bridges Vitest) |

## 2. Eval & red-team platforms — what they are, what they are not

- **promptfoo** (TS): eval + redteam; docs describe generating adversarial inputs (plugins, strategies, "LLM agent" targets). Does **not** run your app's coverage; response cache is a provider-response store (`fetch:v3:` keys, TTL 14d, `PROMPTFOO_CACHE_*`), not contract fixtures. Sources: github.com/promptfoo/promptfoo; promptfoo.dev/docs/red-team/; promptfoo.dev/docs/configuration/caching/.
- **deepeval** (Python): pytest-shaped LLM eval ("similar to Pytest but specialized for unit testing LLM apps"); local LLM-as-judge metrics; mentions synthesizers and "native red teaming" (platform-side). No HTTP mocking, no coverage. Source: github.com/confident-ai/deepeval (README).
- **inspect_ai** (Python, UK AISI): eval framework; local **model-output cache** keyed on model+prompt+epoch+generate-config+**tools** (`--cache`, `CachePolicy`) — determinism aid, explicitly not HTTP record/replay; Scanners analyze logs. Does not measure app coverage/mutation. Source: inspect.aisi.org.uk/caching.html.
- **LangSmith + openevals** (Python): pytest plugin (`@pytest.mark.langsmith`) with **HTTP caching to disk cassettes** (`LANGSMITH_TEST_CACHE=...`, selective `cached_hosts`); openevals = ready-made evaluators, agentevals for agent trajectories. No coverage/mutation; cache is opportunistic (no schema/contract check, no negative-case synthesis). Sources: docs.langchain.com/langsmith/pytest; github.com/langchain-ai/openevals.
- **Braintrust**: tracing/evals org; **AI proxy (deprecated) → Gateway** caches responses (`x-bt-use-cache auto|always|never`, `x-bt-cached: HIT/MISS`, TTL ≤7d; auto mode caches temp=0/seed). Server-side; requires pointing SDK base URL at proxy; not a test-cassette system. Sources: braintrust.dev/docs/deploy/ai-proxy; github.com/braintrustdata/braintrust-sdk-python.
- **ragas**: renamed from explodinggradients → **vibrantlabsai/ragas**; metrics for RAG; synthetic testset generation; activity slowed (PyPI 2026-01, repo 2026-02). Source: github.com/vibrantlabsai/ragas.
- **PyRIT**: canonical repo moved Azure/PyRIT (119★, archived tombstone) → **microsoft/PyRIT** (MIT, active). Adversarial risk identification; not a test harness for app branches. Source: github.com/microsoft/PyRIT.
- **garak** (NVIDIA, 9,581★, Apache-2.0, 0.17.0): LLM vulnerability scanner — adversarial probes at model layer. Source: github.com/NVIDIA/garak.
- **openai/evals**: 19,607★, **no detected license (NOASSERTION; LICENSE 404 at main)**, last push 2026-04-14 — benchmark registry orientation, stale. Source: github.com/openai/evals.

## 3. HTTP record/replay & mocking — the actual primitives

- **vcrpy**: cassettes + 4 record modes (`once`/`new_episodes`/`none`/`all`); changelog confirms **httpx support (via httpcore patching, #943)** and earlier httpx support (#784) — so OpenAI/Anthropic Python SDK traffic is replayable. Sources: vcrpy.readthedocs.io/en/latest/usage.html; vcrpy.readthedocs.io/en/latest/changelog.html.
- **pytest-recording**: vcrpy-powered, `vcr_config` fixture, record modes, "also provides network access blocking". Source: github.com/kiwicom/pytest-recording.
- **respx**: httpx router mocks (`routes`, side effects) — mock-only, no recording. Source: github.com/lundberg/respx.
- **nock**: `nock.recorder.rec()` recording (README "Recording" incl. `enable_reqheaders_recording`) → goldens feed mocks. Source: github.com/nock/nock.
- **MSW** (18,293★): handler/mock-server model; README does not advertise cassette record/replay. Source: github.com/mswjs/msw.
- **undici MockAgent**: "intercepts HTTP requests made through undici and replies with programmed mock responses"; docs warn `setGlobalDispatcher()` doesn't touch separately-created pools/clients. Source: raw.githubusercontent.com/nodejs/undici/HEAD/docs/docs/api/MockAgent.md.
- **Polly.js** (10,249★ Apache-2.0): record/replay/stub but dormant — npm @pollyjs/core 6.0.6 was **2023-07-20**; repo pushed 2025-05-31. Source: github.com/Netflix/pollyjs; registry.npmjs.org/@pollyjs%2fcore.
- **vitest-fetch-mock**: 90★, last release 0.4.5 **2025-03-03** (semi-dormant); forked from jest-fetch-mock (jefflau). Source: github.com/IanVS/vitest-fetch-mock.
- Pattern: all of these replay *bytes captured once*; none validate that a response is contract-legal, none synthesize unexercised contract states (tool_calls, refusals, 429/5xx, SSE partial frames), none connect fixtures to code branches.

## 4. pytest / Vitest / Jest ecosystem — the empty niche

- GitHub repo search (2026-10-15): `pytest-llm` → 2★ (codingjoe, BSD-2), `pytest-llmeval` → 1★, `pytest-llm-assert` → 1★, `pytest-langchain-openai` → 0★. No mature pytest plugin for LLM mocking/replay beyond vcrpy wrappers. Sources: api.github.com/search/repositories?q=pytest-llm etc.
- `openai` Python SDK README contains **no pytest-plugin mention** (the historical plugin is no longer advertised). Source: raw.githubusercontent.com/openai/openai-python/HEAD/README.md.
- Vitest/Jest: `vitest-ai` → only reporter/doc plugins; `jest-openai` → no such repo. LangSmith ships a **Vitest/Jest analogue** of its pytest plugin (docs language + caching). Sources: search API; docs.langchain.com/langsmith/pytest (JS/TS note).
- **vcr-langchain** (record/replay LLM interactions for LangChain): 81★, MIT, last push **2024-06-26** — abandoned. Source: github.com/amosjyng/vcr-langchain.
- LangChain core ships **fake chat models** for tests (`Fake chat models for testing purposes`). Source: raw.githubusercontent.com/langchain-ai/langchain/HEAD/libs/core/langchain_core/language_models/fake_chat_models.py.

## 5. Agent-framework testing today

- **LangGraph** (43,315★): no published testing-utils package (`langgraph-testing` → PyPI 404); testing routes through LangSmith pytest + fake models. Source: pypi.org/pypi/langgraph-testing/json (404); github.com/langchain-ai/langgraph.
- **autogen** (61,423★, last push 2026-04-15): LICENSE file reads **CC-BY-4.0** (unusual for code; API agrees); old `test/test_utils.py` path no longer exists (404) — no published test harness. Source: raw.githubusercontent.com/microsoft/autogen/main/LICENSE.
- **browser-use** (118,079★, MIT, active): references its `browser-harness` repo for connection/test setup; no LLM HTTP mocking story. Source: github.com/browser-use/browser-use.
- **Temporal** (agent durability): `ActivityEnvironment` (mock activity context), `WorkflowEnvironment.start_time_skipping()` (time-skip), `Replayer.replay_workflows()` (determinism CI). Mocks effects deterministically but nothing at the LLM/HTTP layer. Source: docs.temporal.io/develop/python/testing-suite.
- **AgentA/B correction**: "Netflix AgentA/B" is actually an **Amazon** paper (arXiv 2504.09723, Apr 2025, 1,000 simulated agents on Amazon.com); `github.com/Netflix/agent-ab` is **404**. Netflix's adjacent public artifact is the oci-agent causal-inference workflow (Netflix Tech Blog, Jun 2026). Sources: arxiv.org/abs/2504.09723; github.com/Netflix/agent-ab; netflixtechblog.com.

## 6. Mutation tooling — programmatic scoping (can we run only file/line mutants?)

- **mutmut** (Python, BSD-3): `mutmut run "my_module*"` / `"my_module.my_function*"` wildcards; `# pragma: no mutate [block|start/end]`; `mutate_only_covered_lines=true` reuses coverage.py lines; **no documented file:line-range CLI**; results/CLI-oriented (`export-cicd-stats`). Sources: mutmut.readthedocs.io/en/latest/; github.com/boxed/mutmut.
- **cosmic-ray** (Python, MIT, active 2026-10-15): filters are the scoping API — `cr-filter-git` skips everything except **edited/new lines vs a branch**, `cr-filter-pragma` skips `# pragma: no mutate` lines, `cr-filter-operators` excludes operators by regex; external `cosmic-ray-spor-filter` maps arbitrary line ranges via spor metadata. Closest OSS "line-set" scoping. Source: cosmic-ray.readthedocs.io/en/latest/how-tos/filters.html.
- **StrykerJS** (Apache-2.0): `--mutate` accepts **mutation ranges** `"src/app.js:1-11"` (and column forms); `coverageAnalysis: perTest` runs only tests covering a mutant. Source: stryker-mutator.io/docs/stryker-js/configuration/.
- **PIT** (Apache-2.0): scoping = `targetClasses` / `targetTests` / `excludedMethods` / `mutableCodePaths` globs; **no line-range parameter in OSS docs**; the request is open (issue #794) and satisfied only by **commercial arcmutate exclusions**. Sources: pitest.org/quickstart/maven/; pitest.org/quickstart/commandline/; github.com/hcoles/pitest/issues/794.

## 7. Coverage tooling APIs

- **coverage.py** (Apache-2.0): dynamic contexts — `dynamic_context = "test_function"` or tool-driven `Coverage.switch_context()` (pytest-cov `--cov-context=test` uses it); `.coverage` is a SQLite DB; reports filter/annotate by context. This is the machinery for "which test saw this line", not "which LLM decision caused this branch". Programmatic C tracer is internal; the public surface is the Coverage API + contexts. Source: coverage.readthedocs.io/en/latest/contexts.html.
- **nyc** (ISC): Istanbul CLI/report format (`coverage-final.json`-style outputs); no per-test dynamic contexts. Source: github.com/istanbuljs/nyc.
- **v8-to-istanbul** (136★, ISC): converts V8 coverage → Istanbul maps; **c8** (ISC) = native V8 coverage with Istanbul reporters; Vitest coverage flows through this path. Sources: github.com/istanbuljs/v8-to-istanbul; github.com/bcoe/c8.
- Consequence: on the JS side, per-test line attribution is weaker than coverage.py's contexts; a `vitest` LDH plugin cannot lean on per-test contexts the way pytest can.

## 8. Positioning takeaways (where the open space is)

1. **The core join has no owner**: evals measure outputs; coverage measures executions — nothing attributes app-code branches/paths to *LLM decisions* (tool choice, retry/fallback, refusal handling). "Which branch did this mock branch on, and which fixture would flip it?" is unserved.
2. **Replay is commoditized; fixtures are not**: vcr/nock/undici/MSW all replay goldens. Nobody validates fixtures against provider contracts or synthesizes unexercised contract states (tool_calls, refusals, 429/5xx, streaming frames). "Contract-faithful fixtures" is genuinely open.
3. **Managed caches prove the demand but not the product**: LangSmith test cache, promptfoo cache, Braintrust gateway, inspect cache all persist responses — none do coverage, none do contract checks, all are provider-response blobs.
4. **Adversarial generation is crowded at the security layer** (promptfoo, PyRIT, garak). The unclaimed variant is *coverage-guided* adversarial sequences that force uncovered agent branch edges.
5. **Mutation plumbing mostly exists**: Stryker has file:line ranges; cosmic-ray has git-diff/pragma line filters; mutmut has module/function wildcards + coverage filtering. Nobody scopes mutants to LLM-branch-decision code — an integration position, not a from-scratch build.
6. **pytest is the wedge**: LangSmith proved pytest + disk cache adoption; the LLM-mock plugin niche is empty (2★-scale repos only). Vitest/Jest is equally empty (vitest-fetch-mock dormant; no jest-openai).
7. **Don't fight the eval platforms on metrics**; they are quality-score tools. LDH's differentiation is engineering-rigor outputs (branch coverage %, mutation score on decision code, fixture contract validity) — CI-native, not judge-native.

## 9. Uncertainties

- **AgentA/B premise is wrong**: Amazon paper (arXiv), not Netflix; Netflix/agent-ab 404 on 2026-10-15 (maybe deleted/never public).
- **autogen license**: LICENSE file + API report **CC-BY-4.0**; could be a docs-relicense artifact — flagged, not resolved.
- **openai/evals**: NOASSERTION license detection; LICENSE not found at `main/LICENSE`.
- **PIT line scoping**: absence verified from docs + open issue #794 only; a plugin/feature flag could exist undocumented.
- **vcrpy httpx**: changelog confirms support, but streaming/SSE replay fidelity and cassette binary-format stability were not tested here.
- **inspect cache**: keyed on generate-config incl. tools; behavior when tool schemas drift is untested here (may invalidate or silently serve).
- **Braintrust adoption signal weak**: product lives on the hosted platform; public SDK repos have 22/29★.
- **Star counts** are unauthenticated REST snapshots on 2026-10-15; GitHub search results for niche plugins may miss renamed/private projects.
- **ragas/deepeval org & platform claims** ("native red teaming" extent in OSS) unverified beyond README text.
- **Temporal**: mocks Activity boundaries, not provider SDKs; LLM-specific replay unaddressed in docs read.
