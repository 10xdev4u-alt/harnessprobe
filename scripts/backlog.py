#!/usr/bin/env python3
"""Raise the HarnessProbe research backlog on GitHub.

Idempotent: skips titles that already exist. Requires `gh` authenticated as
10xdev4u-alt with repo scope. Usage:

    python3 scripts/backlog.py [owner/repo]

Defaults to 10xdev4u-alt/harnessprobe.
"""

from __future__ import annotations

import json
import subprocess
import sys

REPO = sys.argv[1] if len(sys.argv) > 1 else "10xdev4u-alt/harnessprobe"

LABELS: dict[str, tuple[str, str]] = {
    "epic": ("5319e7", "Cross-cutting epic covering many issues"),
    "stage": ("0e8a16", "Stage-ladder work item (R/E/I/V/B)"),
    "research": ("1d76db", "Research, evidence gathering, citations"),
    "spike": ("fbca04", "Time-boxed technical experiment, may end in no-go"),
    "fixtures": ("bfd4f2", "Contract-faithful fixture library"),
    "pytest-plugin": ("c2e0c6", "pytest plugin and coverage subsetting"),
    "taint": ("d4c5f9", "LDH taint extraction and analysis"),
    "adversarial": ("e99695", "Adversarial response and sequence generation"),
    "mutation": ("f9d0c4", "Mutation testing scoped to LDH"),
    "typescript": ("2d76d0", "TypeScript / Vitest track"),
    "bench": ("6f42c1", "H-Bench-style differential bug benchmark"),
    "docs": ("0075ca", "Documentation and prose quality"),
    "landing-page": ("ff69b4", "Brand, landing page, design"),
    "ci": ("bfdadc", "Continuous integration and automation"),
    "security": ("b60205", "Security, sandboxing, disclosure"),
    "governance": ("c5def5", "Team process, templates, labels, boards"),
    "good-first-issue": ("7057ff", "Scoped for new contributors"),
    "help-wanted": ("008672", "Extra guidance available"),
    "P0": ("b60205", "Must land before anything else"),
    "P1": ("d93f0b", "High priority"),
    "P2": ("fbca04", "Normal priority"),
    "blocked": ("000000", "Blocked by another issue"),
}

ISSUES: list[tuple[str, list[str], str]] = [
    (
        "Establish fleet charter as single source truth",
        ["governance", "docs", "P0", "stage"],
        """**Why.** Agents and humans need one canonical playbook for identity, stages, commits, review, and merges before any code lands.

**Acceptance criteria**
- `AGENTS.md` covers crew roles, issue-first law, stage ladder, loop, commit format, gates.
- Charter amends only by adding; meanings never weaken.
- Linked from `README.md`.

**Refs.** `AGENTS.md`, `docs/APPENDIX-ORIGINAL-BRIEF.md`.""",
    ),
    (
        "Publish original founding brief appendix",
        ["governance", "docs", "P0"],
        """**Why.** Operator mandate must be preserved verbatim as the source of truth the charter upgrades.

**Acceptance criteria**
- Verbatim brief committed under `docs/APPENDIX-ORIGINAL-BRIEF.md`.
- Hard-requirement checklist extracted in the same file.
- Any future charter change links back here.

**Refs.** `docs/APPENDIX-ORIGINAL-BRIEF.md`.""",
    ),
    (
        "Add skills inventory and routing table",
        ["governance", "docs", "P0"],
        """**Why.** 149 skills across five libraries are unusable if agents cannot find the right one fast.

**Acceptance criteria**
- Generated `docs/SKILLS-INVENTORY.md` lists every skill with one-line purpose and source.
- Charter maps common jobs to default skills.
- Regeneration script committed and documented.

**Refs.** `docs/SKILLS-INVENTORY.md`.""",
    ),
    (
        "Create issue templates research spike bug feature",
        ["governance", "ci"],
        """**Why.** Backlog quality decides project quality; every issue must carry context, acceptance criteria, and references.

**Acceptance criteria**
- `.github/ISSUE_TEMPLATE/` holds research, spike, bug, and feature forms.
- Forms require context, acceptance criteria, and refs.
- Rendered templates verified on GitHub.

**Refs.** charter section 4.""",
    ),
    (
        "Create PR template with stage checklist",
        ["governance", "ci"],
        """**Why.** Every stage PR must prove research, validation, tests, prose, and security before review.

**Acceptance criteria**
- `.github/pull_request_template.md` with stage, issues closed, validation evidence, unslop pass, security notes.
- Reviewer checklist matches charter section 8.
- Used by every PR from now on.

**Refs.** `AGENTS.md` section 5-8.""",
    ),
    (
        "Define triage label vocabulary and board columns",
        ["governance"],
        """**Why.** Clear data starts with a stable vocabulary for labels, stages, and board states.

**Acceptance criteria**
- Labels created and described (see `scripts/backlog.py`).
- Project board columns: Inbox, Research, Validated, Building, Review, Done.
- Triage rules documented in `docs/governance/triage.md`.

**Refs.** `docs/governance/triage.md`.""",
    ),
    (
        "Set up CODEOWNERS and branch protection policy",
        ["governance", "ci"],
        """**Why.** main must stay releasable; only reviewed merges land.

**Acceptance criteria**
- `.github/CODEOWNERS` assigns review to the-ai-developer.
- Branch protection: required review, required CI, no force-push, merge commits only.
- Documented in `docs/governance/branching.md`.

**Refs.** charter section 5-6.""",
    ),
    (
        "Define six-word conventional commit lint",
        ["ci", "governance"],
        """**Why.** The six-word rule is a mandate; it must be enforced mechanically, not by memory.

**Acceptance criteria**
- Commit-msg hook and CI lint validate `<type>: <exactly six words>`.
- Allowed types from charter section 7.
- Co-author trailer presence validated.
- Tests for the linter itself.

**Refs.** `AGENTS.md` section 7.""",
    ),
    (
        "Set up project board milestones per stage",
        ["governance", "ci"],
        """**Why.** Stage ladder needs a visible board and milestones so progress is auditable.

**Acceptance criteria**
- Milestones R, E, I, V, B, F1.. created.
- Board view grouped by epic and stage.
- Automation links merged PRs to milestone items.

**Refs.** charter section 5.""",
    ),
    (
        "Add CI lint typecheck tests on pull requests",
        ["ci", "P0"],
        """**Why.** Nothing merges without a green gate; start with the pipeline skeleton.

**Acceptance criteria**
- Workflow runs on PRs: format check, lint, typecheck, tests.
- Fails fast, caches deps, uploads test artifacts.
- Status check required by branch protection.

**Refs.** charter section 8.""",
    ),
    (
        "Enforce coverage gate on new code",
        ["ci", "P1"],
        """**Why.** 80 percent on new code keeps quality from decaying as the toolkit grows.

**Acceptance criteria**
- Coverage diff gate on changed lines for Python and TS.
- Threshold configurable, default 80 percent.
- PR comment summarizes the delta.

**Refs.** charter section 8.""",
    ),
    (
        "Add secret scanning with gitleaks",
        ["security", "ci", "P0"],
        """**Why.** Fixtures will contain captured payloads; a leak would be catastrophic for trust.

**Acceptance criteria**
- gitleaks runs on PRs and pushes.
- Synthetic-only rule documented: fixture secrets must be labeled and fake.
- Failure blocks merge.

**Refs.** charter section 11.""",
    ),
    (
        "Add conventional commit message linter action",
        ["ci"],
        """**Why.** Enforce the six-word conventional rule at the PR level too.

**Acceptance criteria**
- Action validates every commit in a PR.
- Clear error shows the offending commit and expected format.
- Skips merge commits.

**Refs.** `AGENTS.md` section 7.""",
    ),
    (
        "Add stale branch reaper workflow",
        ["ci", "governance"],
        """**Why.** The loop deletes branches and prunes stale ones; automate it so it actually happens.

**Acceptance criteria**
- Weekly workflow deletes merged branches older than 7 days.
- Dry-run mode and allowlist.
- Report posted as workflow summary.

**Refs.** charter section 6 step 11.""",
    ),
    (
        "Add Dependabot and dependency review",
        ["ci", "security"],
        """**Why.** Fixture builders depend on fast-moving SDKs; drift must be surfaced weekly.

**Acceptance criteria**
- Dependabot for pip, npm, and GitHub Actions.
- Dependency review action on PRs.
- Grouped updates, no auto-merge.

**Refs.** charter section 11.""",
    ),
    (
        "Add release automation and changelog",
        ["ci", "docs", "P2"],
        """**Why.** Clean releases with generated changelogs signal enterprise quality.

**Acceptance criteria**
- release-please or equivalent configured for Python and TS packages.
- Changelog generated from conventional commits.
- Tag, release notes, and artifact publishing defined.

**Refs.** charter section 8.""",
    ),
    (
        "R1 define harness.taint.json schema contract",
        ["research", "spike", "P0"],
        """**Why.** The taint map is the contract every tool in the fleet shares; it must exist before extraction code.

**Acceptance criteria**
- JSON Schema draft 2020-12 at `schemas/harness-taint.schema.json`.
- Validators in Python and TS with shared conformance fixtures.
- Semantic checks beyond schema: unique ids, referential integrity of sourceIds.
- ADR recording the format decisions.

**Refs.** `docs/research/06-RESEARCH-SYNTHESIS.md` R1.""",
    ),
    (
        "R2 define fixture pack schema contract",
        ["research", "spike", "fixtures", "P0"],
        """**Why.** Fixtures must be machine-checkable against provider contracts or they rot silently.

**Acceptance criteria**
- Schema for fixture packs: provider responses, tool calls, observations, fault schedules.
- Validators Python + TS; every fixture validated before replay.
- Versioning field and compat matrix hooks.

**Refs.** `docs/research/03-tech-feasibility.md` section 6.""",
    ),
    (
        "R3 measure LDH coverage subsetting on browser-use",
        ["research", "spike", "pytest-plugin"],
        """**Why.** The MVP claim depends on honest LDH-scoped coverage numbers on a real repo.

**Acceptance criteria**
- Run coverage.py, subset executed lines/branches to heuristic LDH scope.
- Report LDH share, covered share, uncovered sample with file paths.
- Document method and caveats; compare with paper RQ1 shape.

**Refs.** `docs/research/05-field-study.md`.""",
    ),
    (
        "R3b measure LDH coverage subsetting on Aider",
        ["research", "spike", "pytest-plugin"],
        """**Why.** Second Python repo with a different mocking style (litellm patch) tests the methodology.

**Acceptance criteria**
- Same method as R3, applied to Aider tests.
- Cross-repo comparison table.
- Document failure modes found while subsetting.

**Refs.** `docs/research/05-field-study.md`.""",
    ),
    (
        "R3c measure LDH coverage subsetting on SWE-agent",
        ["research", "spike", "pytest-plugin"],
        """**Why.** Third repo adds recorded-trajectory replay and predicate-heavy parsing tests.

**Acceptance criteria**
- Same method as R3, applied to SWE-agent tests.
- Predicate-level full/partial/uncovered counts.
- Feed numbers into evaluation scorecard.

**Refs.** `docs/research/05-field-study.md`.""",
    ),
    (
        "R4 Semgrep-CE taint recall versus runtime ledger",
        ["research", "spike", "taint", "P0"],
        """**Why.** If recall is too low, LDH coverage numbers are comforting lies; measure before building on it.

**Acceptance criteria**
- Custom Semgrep rules for provider sources and downstream uses.
- Runtime tagged-value ledger on the same repo as reference.
- Recall/precision table with concrete missed cases.

**Refs.** `docs/research/03-tech-feasibility.md` section 1-3.""",
    ),
    (
        "R5 proxy tagging survivability async coercion spike",
        ["research", "spike", "taint"],
        """**Why.** Runtime tagging is the fallback truth source; serialization and schema coercion may strip it.

**Acceptance criteria**
- Proxy/wrapt tagging of provider clients on Python and TS samples.
- Quantify tag loss across async pipelines and pydantic/zod coercion.
- Recommendation: keep, drop, or narrow the technique.

**Refs.** `docs/research/03-tech-feasibility.md` section 3.""",
    ),
    (
        "R6 Python mutation granularity mutmut versus libcst",
        ["research", "spike", "mutation"],
        """**Why.** mutmut is function-granular; an LDH line set may need finer control than it offers.

**Acceptance criteria**
- Map LDH lines to functions, run mutmut sample, measure signal quality.
- Prototype libcst side-mutator for line ranges.
- Cost table: wall time per 100 mutants.

**Refs.** `docs/research/03-tech-feasibility.md` section 5.""",
    ),
    (
        "R7 provider SDK compat matrix research",
        ["research", "fixtures"],
        """**Why.** Fixtures must track OpenAI/Anthropic/LiteLLM response shapes without a treadmill.

**Acceptance criteria**
- Matrix of pinned SDK versions and our fixture compatibility.
- Strategy for detecting drift (schema snapshots from SDK tests).
- Weekly job spec to refresh.

**Refs.** `docs/research/04-adoption-and-portfolio.md`.""",
    ),
    (
        "R8 threat model generated tests and fixture secrets",
        ["research", "security", "P0"],
        """**Why.** Generated tests execute third-party code and fixtures carry captured payloads.

**Acceptance criteria**
- STRIDE-style threat model for toolkit and CI.
- Sandbox requirements (container, no network, no privileged CI).
- Fixture secret policy: synthetic sentinels, scrub at record time.
- Mapped to OWASP LLM/Agentic Top 10.

**Refs.** `docs/research/04-adoption-and-portfolio.md` section 5.""",
    ),
    (
        "R9 clean-room H-Bench mining feasibility",
        ["research", "spike", "bench"],
        """**Why.** The paper artifact is unlicensed; any bench must be mined independently from public history.

**Acceptance criteria**
- Mining method from public bug-fix commits whose patches touch harness logic.
- Leakage control: exclude bugs already exposed by existing tests.
- Legal note: no artifact data reused.

**Refs.** `docs/research/01-academic.md` section 5-7.""",
    ),
    (
        "R10 reproduce paper RQ1 methodology subset",
        ["research", "spike"],
        """**Why.** We must be able to reproduce the headline adequacy numbers on our own pipeline before quoting them.

**Acceptance criteria**
- Document exact paper methodology subset we reproduce.
- Run on 1-2 public repos; compare shape of numbers.
- Record divergences and likely causes.

**Refs.** `docs/research/01-academic.md` section 3.""",
    ),
    (
        "R11 survey agent repos test helper patterns",
        ["research"],
        """**Why.** The field study covered 5 repos; widen confidence across the paper's 10.

**Acceptance criteria**
- Add PR-Agent, GPT Researcher, RD-Agent, Kimi Code, OpenClaw to the study.
- Per-repo fake-LLM and fixture helper inventory.
- Update patterns list for MVP support.

**Refs.** `docs/research/05-field-study.md`.""",
    ),
    (
        "R12 evaluation scorecard template and thresholds",
        ["research", "governance"],
        """**Why.** Spikes must end in a scored decision, not a vibe.

**Acceptance criteria**
- Template: hypothesis, method, evidence, recall/precision, cost, verdict.
- Pre-agreed thresholds for go/no-go.
- Used by every Stage E decision.

**Refs.** `docs/research/06-RESEARCH-SYNTHESIS.md` section 7.""",
    ),
    (
        "E1 go no go scorecard for candidate MVP",
        ["stage", "P1"],
        """**Why.** The fixtures + pytest plugin wedge must be validated before build investment.

**Acceptance criteria**
- Scorecards for R3/R4/R5/R6 spikes.
- Decision recorded as ADR.
- Explicit kill criteria documented.

**Refs.** `docs/research/06-RESEARCH-SYNTHESIS.md` section 5.""",
    ),
    (
        "E2 recall precision acceptance thresholds",
        ["research"],
        """**Why.** Taint can only gate once its error rates are known and accepted.

**Acceptance criteria**
- Thresholds for reporting-only versus gating use.
- Manual annotation sample to estimate ground truth.
- Published in evaluation docs.

**Refs.** `docs/research/03-tech-feasibility.md` section 10.""",
    ),
    (
        "E3 two tier reporting trust model static versus runtime",
        ["research"],
        """**Why.** Static LDH set and runtime tagged ledger disagree; the product must surface that honestly.

**Acceptance criteria**
- Report format with both tiers and a disagreement section.
- Guidance on which tier to trust for which decision.
- Example report on a public repo.

**Refs.** `docs/research/03-tech-feasibility.md` section 9.""",
    ),
    (
        "E4 competitive re-scan cadence and diff log",
        ["research"],
        """**Why.** LangChain/promptfoo-class shifts can close our window; watch them on a schedule.

**Acceptance criteria**
- Monthly re-scan checklist for the 15 tools.
- Diff log in `docs/research/competitive-log.md`.
- Alert criteria for strategic changes.

**Refs.** `docs/research/02-oss-landscape.md`.""",
    ),
    (
        "V1 validate fixtures solve real bug classes",
        ["stage", "fixtures", "P0"],
        """**Why.** Fixture value is proven by catching real bugs, not by coverage theater.

**Acceptance criteria**
- Reproduce the browser-use nested-secret leak class from fixtures alone.
- Reproduce a LangChain dropped-tool-call class.
- Each validation documented with issue links.

**Refs.** `docs/research/04-adoption-and-portfolio.md` section 1.""",
    ),
    (
        "V2 validate pytest plugin on browser-use dogfood",
        ["stage", "pytest-plugin", "P0"],
        """**Why.** The plugin must work in a real repo unmodified before any release.

**Acceptance criteria**
- Install plugin in a browser-use checkout, run tests, produce report.
- Report names bug classes and LDH coverage honestly.
- Zero changes required to the host repo tests.

**Refs.** `docs/research/05-field-study.md`.""",
    ),
    (
        "V3 validate sandbox execution model",
        ["stage", "security"],
        """**Why.** Running generated tests without isolation is unacceptable for enterprise users.

**Acceptance criteria**
- Container/namespace sandbox spec; no network by default.
- Proof run of a hostile fixture in the sandbox.
- Documented escape hatches and warnings.

**Refs.** charter section 11.""",
    ),
    (
        "V4 validate determinism pinning time randomness sse",
        ["stage", "fixtures"],
        """**Why.** Deterministic replay is the product promise; prove it under stress.

**Acceptance criteria**
- Freeze time, seed randomness, pin fixture bytes.
- Repeated 100x replay produces identical results.
- Documented drift detection on cassette mismatch.

**Refs.** `docs/research/04-adoption-and-portfolio.md` section 4.""",
    ),
    (
        "F1 pydantic builders for OpenAI chat completions",
        ["fixtures", "P1"],
        """**Why.** The most common provider shape needs typed builders that cannot drift from the contract.

**Acceptance criteria**
- Builders for message, tool call, usage, refusal, finish reasons.
- Validated against pinned SDK version in tests.
- Ugly variants supported (truncation, missing fields).

**Refs.** `docs/research/03-tech-feasibility.md` section 6.""",
    ),
    (
        "F2 pydantic builders for Anthropic messages",
        ["fixtures", "P1"],
        """**Why.** Second provider; content blocks and tool use differ enough to justify first-class support.

**Acceptance criteria**
- Builders for content blocks, tool_use, stop reasons, usage.
- Compat tests against pinned anthropic SDK.
- Streaming variant builders.

**Refs.** `docs/research/03-tech-feasibility.md` section 6.""",
    ),
    (
        "F3 pydantic builders for LiteLLM model responses",
        ["fixtures", "P1"],
        """**Why.** LiteLLM fronts many providers and is how several studied agents call models.

**Acceptance criteria**
- ModelResponse builders with choices, tool calls, provider quirks.
- `mock_response` compatible shapes.
- Compat tests against pinned litellm.

**Refs.** `docs/research/05-field-study.md`.""",
    ),
    (
        "F4 tool call and result builders pairing invariants",
        ["fixtures", "P1"],
        """**Why.** The top bug class is mismatched or dropped call/result pairs.

**Acceptance criteria**
- Builders enforce id pairing, argument schema, result envelope contracts.
- Invariant tests for reorder, duplicate, missing result cases.
- Used by the adversarial sequence pack.

**Refs.** `docs/research/05-field-study.md` patterns 1-4.""",
    ),
    (
        "F5 observation feedback builders",
        ["fixtures", "P2"],
        """**Why.** Observation formatting and elision is one of the least-tested semantic categories.

**Acceptance criteria**
- Builders for tool observations, truncations, error feedback.
- Fixtures for long-horizon elision semantics.
- Tests against SWE-agent-style history processors.

**Refs.** paper RQ2 categories.""",
    ),
    (
        "F6 fake model adapter protocol across SDK shapes",
        ["fixtures", "P1"],
        """**Why.** Every repo hand-rolls a fake model against its own interface; one protocol ends the duplication.

**Acceptance criteria**
- Adapter protocol covering invoke/ainvoke/stream shapes.
- Reference adapters for browser-use, OpenHands, SWE-agent patterns.
- Docs with migration examples.

**Refs.** `docs/research/05-field-study.md` pattern 1.""",
    ),
    (
        "F7 scripted trajectory DSL for multi turn",
        ["fixtures", "P1"],
        """**Why.** Single-action mocks cannot reach orchestration and feedback branches.

**Acceptance criteria**
- Declarative script: model turns, tool calls, observations, state checkpoints.
- Runner drives any adapter from the DSL.
- Example trajectories reproducing retry and fallback loops.

**Refs.** `docs/research/05-field-study.md` patterns 1, 5.""",
    ),
    (
        "F8 fault injection helpers retries rate limits",
        ["fixtures", "P1"],
        """**Why.** Retry/error recovery is the most duplicated and least shared test code across repos.

**Acceptance criteria**
- Side-effect schedules, exception-to-status maps, backoff assertions.
- SSE fault frames and mid-stream disconnects.
- Tests proving schedules are deterministic.

**Refs.** `docs/research/05-field-study.md` pattern 4.""",
    ),
    (
        "F9 known ugly corpus of malformed responses",
        ["fixtures", "P1"],
        """**Why.** Real incidents are malformed JSON, invalid tool calls, merged streams, refusals.

**Acceptance criteria**
- Corpus entries each linked to a real public bug or PR.
- Cases: truncated JSON, non-dict args, dropped batch, merged calls, refusal, max_tokens empty.
- Every case validated as contract-legal input to the harness under test.

**Refs.** `docs/research/04-adoption-and-portfolio.md` section 1.5.""",
    ),
    (
        "F10 SSE partial frame fixtures",
        ["fixtures", "P2"],
        """**Why.** Streaming normalization bugs are frequent and under-tested.

**Acceptance criteria**
- Builders for split UTF-8, split JSON, doubled [DONE], interleaved events.
- Golden expectations for reassembly behavior.
- Tests against a local SSE mock server.

**Refs.** `docs/research/05-field-study.md` pattern 3.""",
    ),
    (
        "F11 nested secret redaction fixtures",
        ["fixtures", "security", "P2"],
        """**Why.** The flagship verified bug class is nested secrets surviving redaction.

**Acceptance criteria**
- Fixtures for nested lists/dicts, typed action params, history persistence.
- Recursive-redaction invariant helper.
- Tests modeled on browser-use issue #5623 / PR #5656.

**Refs.** `docs/research/04-adoption-and-portfolio.md` section 1.2.""",
    ),
    (
        "F12 local OpenAI compatible mock server",
        ["fixtures", "P2"],
        """**Why.** Integration-tier tests need a real HTTP/SSE provider; OpenHands proved the pattern.

**Acceptance criteria**
- Server with streaming SSE, error mapping, trajectory DSL backing.
- Self-tested in-process; configurable ports and delays.
- Drop-in for any OpenAI-compatible client.

**Refs.** `docs/research/05-field-study.md` pattern 3.""",
    ),
    (
        "F13 SDK compat matrix test suite",
        ["fixtures", "ci", "P2"],
        """**Why.** Provider churn silently invalidates fixtures; the matrix catches it.

**Acceptance criteria**
- Tests run fixture builders against pinned SDK versions.
- Matrix job on schedule and release.
- Failure report names the drift precisely.

**Refs.** `docs/research/04-adoption-and-portfolio.md` risk 3.""",
    ),
    (
        "P1 harnessprobe init heuristic scope file",
        ["pytest-plugin", "P1"],
        """**Why.** Scope discovery is the first user touch; it must be instant and explainable.

**Acceptance criteria**
- `harnessprobe init` writes a scope file from allowlists and annotations.
- Output lists sources, heuristic LDH candidates, confidence notes.
- No taint dependency required.

**Refs.** `docs/research/06-RESEARCH-SYNTHESIS.md` tweak 8.""",
    ),
    (
        "P2 coverage json subsetting engine",
        ["pytest-plugin", "P1"],
        """**Why.** LDH coverage is post-hoc subsetting, not a new tracer.

**Acceptance criteria**
- Consume `coverage json`, intersect with scope, emit LDH line/branch ratios.
- Predicate-level full/partial/uncovered classification.
- Unit tests on synthetic coverage fixtures.

**Refs.** `docs/research/03-tech-feasibility.md` section 4.""",
    ),
    (
        "P3 LDH report JSON schema and renderer",
        ["pytest-plugin", "P2"],
        """**Why.** Machine-readable reports enable CI gates and PR comments.

**Acceptance criteria**
- Versioned report schema; renderer for terminal and Markdown.
- Per-file, per-category breakdown.
- Golden tests for renderer output.

**Refs.** charter section 8.""",
    ),
    (
        "P4 bug class first PR comment renderer",
        ["pytest-plugin", "P1"],
        """**Why.** Percentages get ignored; bug classes get read.

**Acceptance criteria**
- Comment leads with caught bug classes and evidence links.
- LDH coverage trend shown second.
- Snapshot tests for comment rendering.

**Refs.** `docs/research/04-adoption-and-portfolio.md` tweak 1.""",
    ),
    (
        "P5 GitHub Action for pytest plugin",
        ["ci", "pytest-plugin", "P1"],
        """**Why.** Adoption needs a one-line CI affordance.

**Acceptance criteria**
- Action installs plugin, runs tests, posts comment, optional status gate.
- Config: scope file, thresholds, comment on/off.
- Example workflow in docs, dogfooded on browser-use.

**Refs.** `docs/research/04-adoption-and-portfolio.md` section 2.""",
    ),
    (
        "P6 plugin docs quickstart example",
        ["docs", "pytest-plugin", "P2"],
        """**Why.** Users decide in five minutes; the quickstart decides for them.

**Acceptance criteria**
- Quickstart on a toy agent repo with before/after report.
- Explains heuristic scope limits honestly.
- Passes unslop and technical-writing review.

**Refs.** charter section 8.""",
    ),
    (
        "T1 Semgrep CE source and sink rules",
        ["taint", "P2"],
        """**Why.** Rules are the cheapest path to interprocedural LDH candidates without CodeQL licensing.

**Acceptance criteria**
- Source rules for openai/anthropic/litellm/langchain entrypoints.
- Sink rules for consumed values; taint traces emitted as JSON.
- Rule tests with fixtures; no registry rules vendored.

**Refs.** `docs/research/03-tech-feasibility.md` section 1.""",
    ),
    (
        "T2 ast fixpoint caller graph closure",
        ["taint", "P2"],
        """**Why.** Real LDH spans cross functions; Semgrep CE alone is intraprocedural.

**Acceptance criteria**
- stdlib ast + symtable fixpoint caller graph.
- Closure from sources through callers to harness statements.
- Precision notes and annotation escape hatch.

**Refs.** `docs/research/03-tech-feasibility.md` section 1.""",
    ),
    (
        "T3 annotation escape hatch LDH markers",
        ["taint", "P2"],
        """**Why.** Dynamic dispatch will always defeat static analysis somewhere; users need an override.

**Acceptance criteria**
- `# harness:llm-source` and `// harness:llm-source` annotations.
- Scope file merges annotations with analysis output.
- Docs and tests for annotation resolution.

**Refs.** `docs/research/06-RESEARCH-SYNTHESIS.md` tweak 8.""",
    ),
    (
        "T4 two tier merge and disagreement report",
        ["taint", "P2"],
        """**Why.** Static and runtime tiers disagree; hiding that would betray the clear-data mandate.

**Acceptance criteria**
- Merge logic produces static-only, runtime-only, and agreed sets.
- Disagreement summary with file examples.
- Report consumed by pytest plugin.

**Refs.** `docs/research/03-tech-feasibility.md` section 9.""",
    ),
    (
        "T5 recall precision harness on public repos",
        ["taint", "research", "P1"],
        """**Why.** Published error rates are the precondition for any gating.

**Acceptance criteria**
- Harness runs annotation-based ground truth versus taint output.
- Recall/precision per repo and aggregate.
- Results published in docs with raw data.

**Refs.** `docs/research/03-tech-feasibility.md` section 10.""",
    ),
    (
        "A1 sequence mutator reorder drop duplicate",
        ["adversarial", "P2"],
        """**Why.** Orchestration bugs live in sequences, not single responses.

**Acceptance criteria**
- Mutators: reorder, drop, duplicate, delay, truncate turns.
- Contract validation after every mutation.
- Invariant tests for pairing and state consistency.

**Refs.** `docs/research/06-RESEARCH-SYNTHESIS.md` section 2.""",
    ),
    (
        "A2 injection in observation corpus",
        ["adversarial", "security", "P2"],
        """**Why.** Tool outputs are the indirect prompt-injection channel.

**Acceptance criteria**
- Corpus of injection payloads embedded in tool results and observations.
- Replayed only inside sandboxes against fixtures.
- Defensive-only policy documented.

**Refs.** `docs/research/03-tech-feasibility.md` section 9.""",
    ),
    (
        "A3 sandboxed replay runner",
        ["adversarial", "security", "P2"],
        """**Why.** Hostile fixtures must never touch the host network or filesystem.

**Acceptance criteria**
- Runner executes replays in a sandbox with no network.
- Resource limits and timeouts.
- Proof run documented in V3.

**Refs.** charter section 11.""",
    ),
    (
        "M1 LDH to function map mutmut runner",
        ["mutation", "P2"],
        """**Why.** Function-granular scoping is the pragmatic Python path today.

**Acceptance criteria**
- Map LDH lines to enclosing functions, run mutmut on those only.
- Report surviving mutants with LDH context.
- Cost measured per 100 mutants.

**Refs.** `docs/research/03-tech-feasibility.md` section 5.""",
    ),
    (
        "M2 libcst side mutator evaluation",
        ["mutation", "spike", "P2"],
        """**Why.** Line-precise mutants may be required to keep signal high.

**Acceptance criteria**
- Prototype line-range mutator on libcst.
- Compare kill signal versus mutmut function-level.
- Recommendation recorded as ADR.

**Refs.** `docs/research/03-tech-feasibility.md` section 5.""",
    ),
    (
        "M3 weekly changed lines mutation job",
        ["mutation", "ci", "P2"],
        """**Why.** Per-PR mutation is infeasible; changed-lines weekly is the workable compromise.

**Acceptance criteria**
- Weekly job mutates LDH lines changed in the last week.
- Budget cap and time limit; results posted.
- No PR gate until slice runs under 10 minutes.

**Refs.** `docs/research/04-adoption-and-portfolio.md` tweak 2.""",
    ),
    (
        "TS1 ts-morph LDH span extractor",
        ["typescript", "taint", "P2"],
        """**Why.** TypeScript agents (OpenClaw, Roo, Kimi) are half the population.

**Acceptance criteria**
- ts-morph based source detection and local dataflow.
- Emits the shared harness.taint.json contract.
- Fixture tests on a small TS agent sample.

**Refs.** `docs/research/03-tech-feasibility.md` section 2.""",
    ),
    (
        "TS2 Vitest istanbul LDH reporter",
        ["typescript", "pytest-plugin", "P2"],
        """**Why.** Vitest side needs report parity with the pytest plugin.

**Acceptance criteria**
- Custom reporter subsetting istanbul coverage to LDH spans.
- Terminal and Markdown output matching the Python report schema.
- Dogfood on Roo-Code or similar.

**Refs.** `docs/research/03-tech-feasibility.md` section 4.""",
    ),
    (
        "TS3 Stryker range scoped runner",
        ["typescript", "mutation", "P2"],
        """**Why.** Stryker ranges are first-class; wrap them for LDH scoping.

**Acceptance criteria**
- Runner consumes LDH spans and invokes Stryker with ranges.
- Programmatic API used; budget caps.
- Report normalized with Python side.

**Refs.** `docs/research/03-tech-feasibility.md` section 5.""",
    ),
    (
        "TS4 TS fixture builders zod and fast-check",
        ["typescript", "fixtures", "P2"],
        """**Why.** TS users need the same contract-faithful fixtures and edge generation.

**Acceptance criteria**
- zod/typebox schemas for provider responses and tool calls.
- fast-check arbitraries for boundary variants.
- Conformance with shared JSON schema fixtures.

**Refs.** `docs/research/03-tech-feasibility.md` section 6.""",
    ),
    (
        "B1 hbench-open repository bootstrap",
        ["bench", "P2"],
        """**Why.** A clean-room differential bench is a public good and a research magnet.

**Acceptance criteria**
- Separate repo skeleton with methodology doc.
- No data or code reused from the paper artifact.
- Contribution guide for new bug cases.

**Refs.** `docs/research/01-academic.md` section 5-7.""",
    ),
    (
        "B2 public bug history miner",
        ["bench", "P2"],
        """**Why.** Case mining must be reproducible and leakage-controlled.

**Acceptance criteria**
- Miner over public repos for harness-touching bug fix commits.
- Filter: not exposed by existing tests at buggy revision.
- Dataset card with provenance and licenses.

**Refs.** `docs/research/04-adoption-and-portfolio.md`.""",
    ),
    (
        "B3 differential oracle runner and triage",
        ["bench", "P2"],
        """**Why.** Detection claims require differential oracles and honest false-positive accounting.

**Acceptance criteria**
- Runner: test must fail on buggy, pass on fixed revision.
- Triage workflow with TP/FP evidence and cost tracking.
- Nightly job on the public case set.

**Refs.** paper RQ4 methodology.""",
    ),
    (
        "L1 define brand and design language",
        ["landing-page", "P1"],
        """**Why.** The landing page mandate demands a real design language, not a template.

**Acceptance criteria**
- Tokens: type scale, color, spacing, motion rules.
- Two reference directions prototyped and compared.
- Decision recorded as ADR.

**Refs.** charter section 10.""",
    ),
    (
        "L2 landing scaffold Astro or Next",
        ["landing-page", "P1"],
        """**Why.** The scaffold decides the performance budget and content model.

**Acceptance criteria**
- Static-first scaffold with docs integration.
- 100 Lighthouse performance/SEO targets documented.
- CI build and preview deploys.

**Refs.** charter section 10.""",
    ),
    (
        "L3 interactive LDH coverage visualizer demo",
        ["landing-page", "P1"],
        """**Why.** The story is branch-level; show it, do not describe it.

**Acceptance criteria**
- Animated diff of an agent file with LDH branches highlighted.
- Toggle: before/after adversarial fixtures; branch flips visible.
- Runs client-side on synthetic data.

**Refs.** charter section 10.""",
    ),
    (
        "L4 accessibility and performance budget",
        ["landing-page", "P2"],
        """**Why.** Unreal design still ships to real users; budgets keep it honest.

**Acceptance criteria**
- WCAG 2.2 AA audit with axe; keyboard and reduced-motion paths.
- Core Web Vitals budget enforced in CI.
- No tracking, no dark patterns.

**Refs.** charter section 10.""",
    ),
    (
        "L5 SEO meta OG and docs site",
        ["landing-page", "docs", "P2"],
        """**Why.** Discovery matters for an OSS project.

**Acceptance criteria**
- Meta, OG images, sitemap, robots, structured data.
- Docs site linked from landing with search.
- Lighthouse SEO >= 100.

**Refs.** charter section 10.""",
    ),
    (
        "L6 deploy pipeline preview and production",
        ["landing-page", "ci", "P2"],
        """**Why.** Preview per PR and one-click production deploy.

**Acceptance criteria**
- Preview URL on every PR affecting the landing page.
- Production deploy on main with rollback.
- Secrets scoped and documented.

**Refs.** charter section 10.""",
    ),
    (
        "D1 rewrite README quickstart with unslop",
        ["docs", "P1"],
        """**Why.** The README is the product to everyone who has not installed it.

**Acceptance criteria**
- Problem, proof, quickstart, architecture, status in that order.
- Every claim links to evidence or an issue.
- Passes unslop and technical-writing review.

**Refs.** charter section 8.""",
    ),
    (
        "D2 contributing guide and good first issues",
        ["docs", "governance", "good-first-issue", "P2"],
        """**Why.** A clean workflow is an invitation; contributors need the map.

**Acceptance criteria**
- CONTRIBUTING documents the stage ladder and commit rules.
- Ten good-first-issues curated with mentoring notes.
- Code of conduct in place.

**Refs.** charter section 4-7.""",
    ),
    (
        "D3 architecture docs and ADR index",
        ["docs", "P2"],
        """**Why.** Decisions must be discoverable, not folklore.

**Acceptance criteria**
- ADR index with statuses and links.
- Architecture overview with diagrams.
- Decision log format documented.

**Refs.** `docs/adr/`.""",
    ),
    (
        "D4 security policy and coordinated disclosure",
        ["docs", "security", "P2"],
        """**Why.** A testing tool that handles hostile fixtures needs an explicit security posture.

**Acceptance criteria**
- SECURITY.md with reporting channels and SLAs.
- Coordinated disclosure policy (~90 days).
- Sandbox and secrets guidance for contributors.

**Refs.** charter section 11.""",
    ),
    (
        "D5 provider fixture contribution guide",
        ["docs", "fixtures", "help-wanted", "P2"],
        """**Why.** Provider coverage scales through contributors, not the core team.

**Acceptance criteria**
- Guide: add a provider shape, pin a version, add compat tests.
- Checklist and example PR referenced.
- Linked from the fixtures docs.

**Refs.** `docs/research/03-tech-feasibility.md` section 6.""",
    ),
]


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def ensure_labels() -> None:
    for name, (color, desc) in LABELS.items():
        run(["gh", "label", "create", name, "--repo", REPO, "--color", color,
             "--description", desc, "--force"])


def existing_titles() -> set[str]:
    proc = run(["gh", "issue", "list", "--repo", REPO, "--state", "all",
                "--limit", "500", "--json", "title"])
    if proc.returncode != 0:
        print(proc.stderr.strip())
        sys.exit(1)
    return {item["title"] for item in json.loads(proc.stdout or "[]")}


def main() -> None:
    ensure_labels()
    seen = existing_titles()
    created = skipped = 0
    for title, labels, body in ISSUES:
        if title in seen:
            skipped += 1
            continue
        proc = run(["gh", "issue", "create", "--repo", REPO,
                    "--title", title, "--body", body] +
                   [arg for label in labels for arg in ("--label", label)])
        if proc.returncode != 0:
            print(f"FAILED: {title}\n{proc.stderr.strip()}")
            continue
        created += 1
        print(f"created: {title}")
    print(f"done: {created} created, {skipped} skipped, repo {REPO}")


if __name__ == "__main__":
    main()
