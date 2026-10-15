# AGENTS.md — HarnessProbe Fleet Charter

Canonical operating rules for every human and agent working in this repository.
This charter is the upgraded form of the founding brief (verbatim in
`docs/APPENDIX-ORIGINAL-BRIEF.md`). It may be extended, clarified, and made more
precise; it may never be trimmed or have its meaning weakened.

## 1. Mission

HarnessProbe is an open-source toolkit that finds, exercises, and hardens the
LLM-dependent harness (LDH) code of agent systems: the parsing, dispatch,
state-mutation, retry, and redaction logic that consumes model and tool output.
We ship contract-faithful fixtures, framework-native coverage, adversarial
sequences, and differential bug detection. Research base: `docs/research/`.

The bar: enterprise-grade software, a clean history, and a workflow that reads
as a case study in disciplined agentic development.

## 2. Founding mandate (from the operator)

We are an enterprise team of elites. We run agentic, git-issue-PR-driven
development and push this project to our maximum. Concretely, as mandated:

- Make a new directory, initialize it under the identity `10xdev4u-alt` /
  `10xdev4u@gmail.com`, and create the GitHub repository under the
  `10xdev4u-alt` profile with `gh`.
- Before a single code commit and PR: dig in, research deeply, and raise the
  full issue backlog (60-70+ issues, more is welcome). Research and issues come
  first, not after.
- Use `the-ai-developer` as the co-author on every commit and as the reviewer.
- Follow conventional commits strictly with six-word commit messages.
- Every stage lands as a pull request: research, evaluate, issues, validate the
  idea against the issues, then start the idea.
- Local validation, commit, push, raise PR, review by `the-ai-developer` or
  `10xdev4u-alt`, validate, merge the PR (merge commit, never squash), then
  clean the local branch, the remote branch, and stale branches, and repeat for
  the next stage.
- Build world-class docs and READMEs, and a landing page with infinite
  creativity, unreal design, and zero innovation limits.
- All prose passes the `unslop` skill. All docs pass `technical-writing`.

Nothing in this charter overrides that mandate; everything in it operationalizes it.

## 3. Crew and roles

| Role | Identity | Responsibilities |
|---|---|---|
| Owner / author | `10xdev4u-alt <10xdev4u@gmail.com>` | Sole commit author; repo admin; merges. |
| Co-author / reviewer | `the-ai-developer` (GitHub + `the-ai-developer@users.noreply.github.com`) | Co-authors every commit; reviews every PR. |
| Agent fleet | opencode/Claude subagents | Research, planning, implementation, testing, review assistance. |
| Human operator | prince | Final authority; unblocks; approves exceptions. |

Attribution rules, non-negotiable:

- Every commit is authored by `10xdev4u-alt <10xdev4u@gmail.com>`.
- Every commit carries exactly one co-author trailer:
  `Co-authored-by: the-ai-developer <the-ai-developer@users.noreply.github.com>`.
- A PR is reviewed (approved) by an account that is not its author:
  `the-ai-developer` whenever possible, otherwise `10xdev4u-alt`.
- Merge commits record who merged; no bot merges.

## 4. Issue-first law

1. No code commit exists before the research and issue phases are complete.
2. Every branch, commit, and PR traces to at least one issue: PR body contains
   `Closes #<n>` (one per issue) or `Refs #<n>` when the issue stays open.
3. Issues are the backlog of record. Work discovered mid-flight becomes an
   issue first, then a branch.
4. Label vocabulary (created by `scripts/backlog.py`): `epic`, `stage`,
   `research`, `spike`, `fixtures`, `pytest-plugin`, `taint`, `adversarial`,
   `mutation`, `typescript`, `bench`, `docs`, `landing-page`, `ci`, `security`,
   `governance`, `good-first-issue`, `help-wanted`, `P0`, `P1`, `P2`, `blocked`.
5. Every issue has: context, acceptance criteria, references, and the owning
   epic. Vague issues are rejected in review.

## 5. Stage ladder (one PR per stage)

| Stage | Branch | Contents |
|---|---|---|
| R — Research | `stage/r-research` | Research corpus, synthesis, open questions. |
| E — Evaluate | `stage/e-evaluate` | Scorecards, go/no-go on spikes, thresholds. |
| I — Issues | `stage/i-issues` | Backlog manifest, labels, templates, scripts. |
| V — Validate | `stage/v-validate` | Spikes proving or killing the candidate solution. |
| B — Build | `stage/b-start` | First implementation slice (fixtures + pytest plugin). |
| F — Features | `feat/<slug>` | One epic slice per PR, indefinitely. |

Each stage follows the loop in section 6 exactly. A stage is done only when its
issue is closed, its PR merged, and branches are cleaned.

## 6. The loop (repeat forever)

1. Pick the next stage/issue from the board.
2. Branch from up-to-date `main`.
3. Research and plan; load the matching skills from
   `docs/SKILLS-INVENTORY.md`.
4. Write local validation first where practical (test, fixture, or proof script).
5. Commit small, conventional, six-word messages (section 7).
6. Validate locally: lint, typecheck, tests, unslop pass on prose.
7. Push the branch and open a PR with the stage template.
8. Request review from `the-ai-developer` (or `10xdev4u-alt` if conflict).
9. Address review comments with new commits; never force-push over an open PR
   unless the reviewer asks.
10. Reviewer approves; author merges with a merge commit (no squash).
11. Delete the local and remote branches; prune stale branches.
12. Update the board, close the issue, and start the next stage.

## 7. Commit discipline

Format: `<type>: <six words>` — the description must be exactly six words.

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`, `build`,
`revert`, `style`.

Rules:

- One logical change per commit; atomic and reviewable.
- Subject in imperative mood, lowercase, no trailing period.
- Body explains why, not what; wrap at 72 columns.
- Footer always ends with the co-author trailer (section 3).
- Reference issues in the body when not closing them.
- Never commit secrets, tokens, credentials, or generated artifacts that can be
  rebuilt.
- Example:
  ```
  docs: establish fleet charter operating rules

  Why: agents need one canonical workflow before any
  implementation commits land on main.

  Refs #1
  Co-authored-by: the-ai-developer <the-ai-developer@users.noreply.github.com>
  ```

## 8. Validation gates (local, then CI)

- Tests: unit, integration, and end-to-end where behavior exists; new behavior
  ships with tests; target 80%+ coverage on new code.
- Static: formatter, linter, typechecker — zero errors, warnings justified.
- Security: no secrets (`gitleaks` class check), inputs validated, sandboxed
  execution for anything that runs generated code.
- Determinism: no live LLM calls in CI; fixtures pinned; time/randomness frozen.
- Prose: `unslop` pass on every user-facing surface; `technical-writing` for
  docs, PR bodies, and commit bodies.
- Docs: change ships with docs; public APIs have examples.
- Review: PR template checklist complete before requesting review.

## 9. Skills routing (fleet)

Consult `docs/SKILLS-INVENTORY.md` for the full index (149 skills). Defaults:

| Job | Skill |
|---|---|
| Frame a large workstream | `wayfinder`, `figure-it-out` |
| Write specs and tickets | `to-spec`, `to-tickets`, `triage` |
| Implement a spec | `implement`, `implement-spec` |
| Tests | `tdd`, `create-verification-skill`, `run-smoke-tests` |
| Review | `code-review`, `interrogate`, `thermo-nuclear-code-quality-review` |
| Debug | `diagnosing-bugs`, `fix-ci`, `fix-merge-conflicts` |
| PR hygiene | `pr`, `make-pr-easy-to-review`, `get-pr-comments` |
| Prose | `unslop` (mandatory), `technical-writing`, `writing-for-agents` |
| Architecture | `codebase-design`, `domain-modeling`, `architect` |
| Evidence trail | `show-me-your-work`, `benchmark-checklist` |
| Decision stress-test | `grill-me`, `grilling`, `principle-attack-the-premise` |
| Landing page | `frontend-design`-class skills, `typescript-best-practices`, `control-ui` |

Subagents are spawned per the operator's harness rules; the fleet keeps context
lean by delegating heavy reading to subagents and keeping summaries in the main
thread.

## 10. Landing page and brand mandate

The landing page is a flagship artifact, not a brochure. Infinite creativity,
unreal design, zero innovation limits — subject to: real content (no lorem),
Core Web Vitals budget, WCAG 2.2 AA, no tracking, no dark patterns, unslopped
copy, and a build that stays reproducible. Design decisions are recorded as
ADRs; prototypes are welcome and expected (`prototype`, `architecture` skills).

## 11. Security and ethics

- Never call live models, external APIs, or paid services in CI.
- Generated tests and fixtures execute third-party code only inside sandboxes.
- Fixture secrets are synthetic, labeled, and scrubbed; treat captured payloads
  as untrusted input.
- Adversarial corpora are defensive-only; disclose exploitable findings to
  vendors before publication (coordinated, ~90 days).
- OWASP Top 10 for LLM/Agentic Applications and NIST AI RMF mappings are
  recorded in `docs/security/`.
- `security-reviewer` signs off before any release touching execution,
  credentials, or network paths.

## 12. Fleet operations

- One writer per file at a time; parallel agents work on disjoint scopes.
- Long-running or unattended work uses `show-me-your-work` decision logs.
- Architectural decisions land as ADRs under `docs/adr/`.
- Research lands under `docs/research/` with citations and access dates.
- Dead ends are recorded, not deleted: they become evaluation notes.
- Spike sandboxes: run third-party repo suites with a scrubbed environment
  (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `FX_*` and similar unset), an
  isolated `HOME` where practical, browser- and network-gated tests excluded by
  selection, and never open GUI applications on the operator's desktop.
- Context discipline: delegate bulk reading to subagents; main thread keeps
  decisions and diffs only.

## 13. Definition of done

An issue is done when: code merged with tests and docs, CI green, prose
unslopped, security gates passed, branches cleaned, issue closed, and the
changelog/board updated. A stage is done when every issue in it meets that bar
and the stage PR is merged with a merge commit.

## 14. Amendments

This charter grows. Add clarifications, tighten language, add rules — never
remove a mandate or change its meaning. Every amendment lands as a docs PR
reviewed by `the-ai-developer`, with the original brief preserved in
`docs/APPENDIX-ORIGINAL-BRIEF.md`.
