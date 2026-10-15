# 04 — Adoption & Portfolio (HarnessProbe working name)

Primary-source research. No code written. All URLs accessed **2026-10-15**.
Context: repo already has `docs/SPEC.md`; this doc is the independent evidence and portfolio critique that
should gate/reshape those decisions before build-out.

---

## 1. Who has the pain — verified incident evidence

### 1.1 Paper dossier (what is actually claimable)
Xiong, Ge, Chen, Lou, *"Complex Agents, Shallow Tests: Demystifying and Enhancing Test Adequacy of Agent
Harness in the Wild"*, arXiv:2610.04921v1, 2026-10-04 — verified from the full HTML, not the abstract:
<https://arxiv.org/abs/2610.04921> · <https://arxiv.org/html/2610.04921v1>
- 10 agents, ≥10K stars, Python + TS/JS, incl. Browser Use 70.9 KLOC, **OpenClaw 851.0 KLOC** (2,352 tests,
  386.4K stars), **Roo Code 3.54.0** 161.7 KLOC, Kimi Code 166.3 KLOC. LDH = code with data/control dependency
  on LLM outputs; avg share **22.35% lines / 31.71% branches** (branch share 1.10–1.75× line share).
- Avg LDH coverage **44.27% line / 41.18% branch**; avg LDH mutation score **33.60%** (3.58% RD-Agent →
  70.94% Kimi Code). Of 700 sampled LDH predicates: 25.57% fully covered, 49.86% uncovered.
- Core difficulty stated as contract-faithful setups (Finding 2); Kimi Code's reusable fake-LLM/SSE helpers are
  the counterexample, OpenClaw's ad-hoc fixtures the anti-pattern.
- RQ4.a: 43/250 historical bugs vs 2 for best baseline. RQ4.b: 122 bugs, 88 previously unknown, 69 confirmed,
  64 fixed/assigned, *"one of them is assigned a CVE number"* — **the paper never names the CVE**.

### 1.2 Browser Use secret-redaction bug (the paper's RQ4.b example) — fix exists
- Paper: "a sensitive value nested within a typed action parameter can bypass redaction and remain in the saved
  history." Matching real issue: **#5623**, "AgentHistory save_to_file does not redact sensitive values inside
  nested action lists", opened 2026-08-31 by **yifanxiong272** (paper's first author), closed as completed via
  **PR #5662** (also referenced by PR #5656): <https://github.com/browser-use/browser-use/issues/5623>
- Fix: <https://github.com/browser-use/browser-use/pull/5656> — recursive value filter + regression tests.
  Verdict: flagship bug is **real, confirmed, and fixed**.
- Same bug class kept recurring, which supports the thesis: #4609 substring leak
  (<https://github.com/browser-use/browser-use/issues/4609>), #5248 placeholder cascade
  (<https://github.com/browser-use/browser-use/issues/5248>), #2601 masking leaks by inference
  (<https://github.com/browser-use/browser-use/issues/2601>), #2226 raw password reaches the LLM
  (<https://github.com/browser-use/browser-use/issues/2226>).

### 1.3 "Roo Code CVE" claim — partially verifiable, attribution NOT
- The paper says exactly one of its 88 previously-unknown bugs got a CVE and notes Roo Code's repo **was
  archived** during the study. No CVE number appears in the full text; **cannot confirm which**. Best
  candidate for "the 1 CVE" in the paper's window: CVE-2026-30307 — treat as unverified.
- Roo Code's history is a dense stream of auto-approval-parser bugs — the same LDH shape (LLM-proposed shell
  command parsed by regex/allowlist that disagrees with the real shell):
  CVE-2025-58370 + CVE-2025-53536 (<https://github.com/RooCodeInc/Roo-Code/security>);
  **CVE-2026-30307**, CVSS 9.8, `$(...)`/backtick whitelist bypass (<https://nvd.nist.gov/vuln/detail/CVE-2026-30307>);
  CVE-2026-63108, CVE-2026-82536/82537, and the five-CVE batch CVE-2026-110202…110206 published 2026-10-13
  (<https://app.opencve.io/cve/?product=roo_code&vendor=roocode> ·
  <https://theagentictimes.org/vulnerabilities/five-flaws-let-roo-code-auto-approve-banned-shell-commands>).

### 1.4 OpenClaw harness bug stream (851 KLOC) — all "green health / broken turns" shaped
- #134304 configured-but-unregistered harness; every turn fails in ~27 ms while Gateway stays healthy:
  <https://github.com/openclaw/openclaw/issues/134304>
- #66260 startup skips Codex harness activation (fixed v2026.4.23): <https://github.com/openclaw/openclaw/issues/66260>
- #83984 missing export (`hasBeforeToolCallPolicy`) crashed all Codex-OAuth turns in a beta:
  <https://github.com/openclaw/openclaw/issues/83984>
- #135576 subagent requester-settle loses gateway binding; completion `deliveryStatus: failed`:
  <https://github.com/openclaw/openclaw/issues/135576>
- #135618 `codexPlugins` hot-reload invalidates the active harness until restart:
  <https://github.com/openclaw/openclaw/issues/135618>
- #131701 failed turns lose the primary provider error in empty-answer recovery: <https://github.com/openclaw/openclaw/issues/131701>
- #87063 `claude-cli` alias throws `MissingAgentHarnessError`; skill catalog double-injection blows the 1M
  context window: <https://github.com/openclaw/openclaw/issues/87063>

### 1.5 LangChain / LlamaIndex tool-call parsing + streaming bugs
- LangChain #35782 one malformed tool call silently drops **all** tool calls (`except KeyError: pass` around a
  whole batch comprehension): <https://github.com/langchain-ai/langchain/issues/35782>
- LangChain #33504 `create_agent` ignores `invalid_tool_calls`; agent silently exits instead of retrying:
  <https://github.com/langchain-ai/langchain/issues/33504> (fixes PR #35818/#35819)
- LangChain #36679 `default_tool_parser` crashes on malformed `function` dicts, dropping all valid calls:
  <https://github.com/langchain-ai/langchain/issues/36679>
- LangChain #36073 non-dict JSON args → `ValidationError` (<https://github.com/langchain-ai/langchain/pull/36073>);
  #34746 Ollama streaming `ResponseError: error parsing tool call` crashes the loop
  (<https://github.com/langchain-ai/langchain/issues/34746>)
- LlamaIndex #18760 Bedrock Converse merges consecutive streaming tool calls → `JSONDecodeError`:
  <https://github.com/run-llama/llama_index/issues/18760> (fix PR #18761)
- LlamaIndex #21579 streaming yields `tool_kwargs` as str, breaks cross-provider replay:
  <https://github.com/run-llama/llama_index/issues/21579> (fix PR #21580)
- LlamaIndex #15083 text+tool-call streaming stalls, tool call dropped:
  <https://github.com/run-llama/llama_index/issues/15083>; #11013 `stream_chat()` never triggers tool calling:
  <https://github.com/run-llama/llama_index/issues/11013>

**Verdict:** pain is real and recurring, dominated by the paper's top LDH categories (provider I/O normalization
29%, tool action handling 24%, orchestration/feedback/error recovery ~34%). It is currently fixed by reactive
one-off patches — not by test infrastructure.

---

## 2. Positioning: whose job is this?

**Jobs-to-be-done:** (1) framework maintainers (LangChain/LlamaIndex class) — "parser/dispatch regressions must
not ship; we can't hand-write 500 fixtures"; they already run big pytest/Vitest suites with heavy LLM mocks of
varying quality. (2) agent product teams (Browser Use/Roo Code class) — "our stall/leak bug only reproduced in
prod; turn it into a regression before merge." (3) AI infra/platform teams — standardize harness contracts
across N internal agents; satisfy OWASP/NIST security reviews.

**What they already run in CI:** pytest/Vitest + mocks; coverage.py thresholds; Codecov-style PR comments
(Codecov is the dominant coverage bot: 79–86% of coverage-monitoring PR comments in a 474-project study,
<https://arxiv.org/html/2409.05101v1>); live LLM calls fenced to nightly; Stryker/mutmut weekly, not per-PR
(Sentry: ~20–25 min per package, deliberately weekly, <https://blog.sentry.io/mutation-testing-js-sdks/>);
hand-rolled record/replay of parsed responses instead of SSE bytes
(<https://dev.to/galian/record-replay-assert-testing-llm-agents-in-ci-without-paying-for-every-run-4dfp>).

**Adoption triggers that measurably work:** a **failing status check + PR comment** is the single most
incentivizing coverage-tool feature (survey of 279 Codecov users, AST'24,
<https://doi.org/10.1145/3644032.3644444>); zero-config pytest plugin; a GitHub Action; file-glob/threshold
escape hatches. Pre-commit is the wrong shape for repo-wide metrics.

**Comparable adoption stories, with warning labels:** Codecov won via free OSS + PR comments (Sentry
acquisition) but >80% of surveyed devs admit ignoring failing coverage checks (small deltas, wrong results,
priorities). Stryker is defined by slowness: canonical issue "Why Stryker is so slow?" — 5.2K mutants ≈ **72h
estimate** on a 98%-covered project, <https://github.com/stryker-mutator/stryker-js/issues/3320>. Mutation
testing broadly: TSE'24 survey of 104 OSS practitioners — high satisfaction, **performance is overwhelmingly
the main limitation**, <https://dl.acm.org/doi/10.1109/TSE.2024.3377378>; Google ICST'18 — "mutation adequacy
is too expensive", prefer commit-level selective mutation,
<https://homes.cs.washington.edu/~rjust/publ/industrial_mutation_icst_2018.pdf>.

---

## 3. Portfolio options (critique, not enthusiasm)

**(a) LDH taint mapper CLI.** User: framework maintainers/platform teams. Scope: interprocedural data/control
dependency from LLM-call sources → `harness.taint.json`. Moat: hard engineering (Python decorators, TS
structural typing); the paper needed a bespoke analysis. Competition: none directly (semgrep-style tools don't
model LLM semantics). Adoption: CLI + JSON; low friction; vendored by (b). Risk: false negatives silently
undercount LDH; per-provider source modeling; TS interprocedural analysis is a swamp. Effort **L**. Enabler,
not a product.

**(b) pytest/Vitest LDH coverage plugin.** User: any agent team with existing tests. Scope: scope coverage to
LDH; PR comment/status check; thresholds. Moat: taint-aware scoping + harness-aware heuristics; thin
otherwise — reporting itself is commoditized by coverage.py/Vitest/Codecov. Adoption: **strong** (pip install,
own plugin runner, GH Action; the one CI affordance that works). Risk: metric indifference (§4.1); 2-ecosystem
maintenance. Effort **M**. Standalone: yes — best demoable wedge.

**(c) Contract-fixture library for provider responses/tool calls.** User: every dev hand-rolling mocks. Scope:
typed builders for OpenAI/Anthropic/Bedrock/generic tool-call streams; fake LLM + local SSE server;
record/replay with request fingerprints; versioned contracts. Moat: **the paper's actual insight** —
contract-faithful setups (Kimi Code proves in-repo value). Competition: pytest-recording/VCR (too low-level,
SSE churn), provider SDK test utils (niche), LangSmith/Braintrust (evals, not unit fixtures). Adoption: library
+ "known-ugly" fixture gallery (truncated JSON, invalid_tool_calls, merged calls, refusals, max_tokens).
Risk: provider drift; low willingness to pay. Effort **M**. Standalone: yes.

**(d) Adversarial tool-sequence fuzzer.** User: security-minded teams (OWASP ASI02/ASI05). Scope: generate
hostile-but-contract-valid sequences (injection inside tool outputs, nested secrets, schema drift,
reordered/duplicated calls) and replay into the harness. Moat: adversarial corpus breadth + contract fidelity.
Competition: generic fuzzers (no agent semantics), prompt-level red-team tools (Garak/PyRIT, promptfoo) — not
harness-level. Adoption: scary-real demos (browser-use leak class); sells security reviews; hard to gate CI.
Risk: corpus decay; dual-use ethics (§5). Effort **M**. Sibling of (c).

**(e) H-Bench-style differential bug bench.** User: maintainers benchmarking regressions; researchers. Scope:
replay recorded real histories, differential-detect harness behavior change across versions with pinned outputs.
Moat: bench data + upkeep; the paper's 250-bug set is an IP/timing gray zone. Competition: SWE-bench/
Terminal-Bench measure task success (black-box), not harness regressions. Adoption: leaderboard + nightly CI;
weak per-team pull. Risk: public-good maintenance with no model; oracle quality = recording quality. Effort
**L**. Separate repo.

**(f) LLM-driven test generator with contract guidance.** User: same as (a)/(b). Scope: generate
contract-faithful tests for under-covered LDH branches (the paper's HarnessTester itself). Moat: consumes
contract metadata from (a)+(c); without it, it's baseline LLM testgen. Competition: Qodo/CodiumAI-class
testgen. Adoption: hardest — generated tests in PRs are noisy; must be suggest-not-gate. Risk: nondeterministic
quality, review burden, the classic testgen adoption wall. Effort **L**. Only as premium feature later.

**Monorepo verdict:** one repo, layered `taint` → `fixtures` → `coverage` → `fuzz` → `gen`; (e) splits out.
Python and TS share a JSON contract schema, not code.

---

## 4. Tweaks, critiques, reasons this project might fail

1. **LDH coverage may be the wrong headline metric.** >80% of Codecov users ignore failing coverage checks
   (small deltas, wrong results, production-first priorities). Another percentage-bar gets ignored.
   *Tweak:* lead PR comments with bug classes caught ("secret leaked in saved history", "tool call dropped");
   keep LDH % for trends, not gates.
2. **Mutation at 851 KLOC is infeasible per-PR.** Stryker users report 72h full runs; TSE survey: performance
   is *the* blocker; Google: aim for "better tests", not mutation adequacy. *Tweak:* LDH-scoped, changed-lines
   only, sampled mutants, weekly job; ship no PR mutation gate until a slice runs <10 min.
3. **Nondeterminism does not kill this; unpinned recordings do.** LLM-as-judge evals are statistical (pass^k;
   <https://ai.zenoagi.com/harness/practice/evals-in-practice> ·
   <https://www.saumilsrivastava.ai/blog/agent-evaluation-is-a-distributed-systems-problem>), but harness tests
   with *recorded* outputs are deterministic (<https://www.tedwerbel.com/blog/deterministic-testing-for-ai>).
   Differential oracles are valid only if fingerprints are stable (timestamps, unsorted tools, request IDs are
   the four classic killers). Fail loudly on drift; never call live.
4. **"Maintainers prefer sandboxed e2e evals" is true but compatible.** Outcome evals are the regression
   backbone; unit/trajectory layers are diagnostics (ZenoAGI). Slot in as the unit/integration layer feeding
   the same CI — pitching it as an evals replacement loses.
5. **The taint lift is bigger than it looks.** Bespoke interprocedural analysis; Python `**kwargs`/decorators
   and TS structural typing hurt recall. A mapper that misses LDH reports comforting but wrong numbers.
   *Tweak:* publish recall/precision on ≥3 public repos before anything ships on top; manual annotation escape
   hatch.
6. **Framework absorption + OSS treadmill.** LangChain/LlamaIndex/Vercel AI SDK absorb point fixes; Kimi Code
   built fixtures in-house. Fixture builders may become table stakes — be the cross-provider/cross-language
   layer, and be fast. Meanwhile contract corpora rot with provider API churn; 2 languages × N providers × M
   runners is a maintenance tax a single maintainer will lose.
7. **The paper is 11 days old, v1, not peer-reviewed,** and one studied repo (Roo Code) is already archived.
   Reproduce its RQ1 numbers on the same 10 repos before quoting effect sizes publicly.

---

## 5. Ethics / security constraints (existing guidance)

- **OWASP Top 10 for LLM Applications 2026** — LLM01 Prompt Injection, LLM02 Sensitive Information Disclosure,
  LLM10 Improper Output Handling directly in scope; "Improper Output Handling" is the harness-parsing risk
  itself: <https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/>
- **OWASP Top 10 for Agentic Applications 2026** — ASI02 Tool Misuse, ASI05 Unexpected RCE, ASI08 Cascading
  Failures: <https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/> · **NIST AI RMF
  1.0 + NIST AI 600-1 (GenAI Profile, July 2024)** — map to MEASURE/MANAGE for enterprise buyers (crosswalk in
  the OWASP LLM 2026 appendix).
- Concrete constraints: (1) generated tests execute third-party code → sandbox (container, no network by
  default), never privileged CI; ship `--no-exec`. (2) Fixtures contain captured responses → untrusted input,
  scrub at record time, obviously-fake sentinels (browser-use's GitGuardian false positive on fixture literals,
  PR #5656). (3) Injected tool outputs are inert, labeled data — replayed against auto-approve agents they are
  live hazards (Roo Code CVE class). (4) Exploit-shaped findings → vendor-first coordinated disclosure (~90 days).

---

## 6. Recommended portfolio order + MVP wedge

**Order:** 1) (c) contract fixtures — the seam everything stands on. 2) (a) taint mapper with published
recall/precision on ≥3 repos — the gate for anything LDH-scoped. 3) (b) coverage plugin on top, PR-comment UX
with bug-class-first summaries. 4) (d) adversarial sequences as a corpus pack for (c). 5) (f) contract-guided
generator, suggest-not-gate, last. 6) (e) bench as a separate repo consuming recorded histories.

**MVP wedge:** **(c) + thin (b) for Python first** — a pytest plugin that (i) detects LDH heuristically
(decorator/module allowlist, upgradeable to taint), (ii) ships typed fake provider responses including §1.5's
ugly cases (truncated JSON, invalid tool calls, dropped batches, nested secrets), (iii) emits a Codecov-style
PR comment naming bug classes caught, not a bare percentage. Deterministic, needs no mutation engine or
perfect taint, exercises the full pipeline (contracts → tests → PR UX), and generates evidence for (a)/(d)/(f).
Vitest second; no mutation gating until a changed-lines slice runs <10 min.

**Reasons the project might fail (top 3):** gate fatigue vs ignored metrics; taint-analysis recall too low to
trust; fixture/contract maintenance treadmill — with framework absorption and unpinned-recording flakiness as
close runners-up.
