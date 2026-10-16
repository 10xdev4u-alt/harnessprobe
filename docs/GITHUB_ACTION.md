# GitHub Action

The composite action installs HarnessProbe, runs your pytest suite under
coverage, subsets the result to the LDH scope file, writes a gate summary to the
job summary, and posts a sticky PR comment. It never calls a model.

## Quickstart

1. Generate and commit a scope file once:

   ```console
   $ uvx harnessprobe init . --out harnessprobe.scope.json
   ```

2. Add `.github/workflows/harnessprobe.yml`:

   ```yaml
   name: HarnessProbe
   on: [pull_request]
   permissions:
     contents: read
     pull-requests: write
   jobs:
     harnessprobe:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: 10xdev4u-alt/harnessprobe@main
           with:
             min-coverage: "60"
   ```

A copy-paste version with comments is in
`examples/github-workflows/harnessprobe.yml`. This repository runs the same
action on itself (`uses: ./`), so the workflow in `.github/workflows/` is a
working reference.

## Inputs

| Input | Default | Meaning |
|---|---|---|
| `scope-file` | `harnessprobe.scope.json` | Scope file from `harnessprobe init`. |
| `pytest-args` | `tests` | pytest arguments, split on whitespace. |
| `coverage-args` | `--branch` | `coverage run` arguments, split on whitespace. |
| `run-tests` | `true` | Set `false` when the report already exists. |
| `report-file` | `harnessprobe.report.json` | Report path the plugin writes. |
| `harnessprobe-package` | action checkout | Package spec to install. |
| `extra-packages` | `pytest` | Additional pip packages (for example `pytest pytest-xdist`). |
| `python-version` | runner default | When set, installs it with `actions/setup-python`. |
| `min-coverage` | off | Minimum LDH coverage percent. |
| `max-uncovered` | off | Maximum uncovered LDH scope lines. |
| `fail-on-findings` | `false` | Fail when any findings are attached. |
| `findings-file` | off | Findings JSON for the gate and the comment. |
| `previous-report` | off | Older report JSON for the trend line. |
| `comment` | `true` | Create or update the sticky PR comment. |

## Outputs

`covered-pct`, `scope-lines`, `executed`, `uncovered`, `not-measured`,
`findings-count`, `gate-passed`, `gate-reasons`, and `report-path`. Downstream
steps read them as `${{ steps.<id>.outputs.<name> }}` when the action is used
through a step id.

## Gate

The gate runs `harnessprobe gate` and exits non-zero when a configured
threshold fails, after writing the job summary and the outputs. Every threshold
is off by default; an action call with no thresholds always passes the gate and
still writes the summary, outputs, and comment.

- `min-coverage` fails when `covered_pct < min-coverage`, and also when the
  report measured nothing.
- `max-uncovered` fails when uncovered lines exceed the limit. Uncovered means
  measured scope lines that did not execute; `not-measured` lines are excluded.
- `fail-on-findings` fails when the findings file contains at least one finding.

The comment step uses `if: always()`, so a failed gate still gets its comment
and its summary. A skipped or failed test run is surfaced by the missing-report
guard instead of a silent pass.

## Sticky comment

The action renders the comment documented in `docs/PR_COMMENT.md` and posts it
through `gh api`. When a comment carrying the HarnessProbe footer already exists
on the pull request, the action updates that comment instead of adding another.
One comment per pull request, every push.

The comment step needs `pull-requests: write` (the workflow above shows it) and
runs only on `pull_request` events; `push` runs gate and summarize without
commenting. Pull requests from forks are skipped automatically: their token is
read-only, so the action posts no comment there and still gates and summarizes.

## Findings

`findings-file` points at a `harnessprobe.findings/v1` document, the same
format `harnessprobe comment --findings` accepts (see `docs/PR_COMMENT.md`).
Findings lead the comment; coverage follows. The gate counts them for
`fail-on-findings`, and the `findings-count` output carries the number.

## Security notes

- Inputs reach the shell through `env`, not through `${{ }}` interpolation in
  `run:` blocks, so an input value cannot inject shell syntax.
- No live model or network call is made by the action. The only network use is
  pip and `gh api` for the comment.
- The token is the workflow's `github.token`; the action never persists or logs
  it. Grant only `contents: read` and `pull-requests: write`.
- The job runs pull request code, so check out with
  `persist-credentials: false` (shown in the example) to keep the token out of
  `.git/config` where the tests could read it.
- `harnessprobe-package` is installed with pip. Point it at a pinned ref when
  you override it.

## Limitations

- The scope is derived heuristically and is a superset, mostly by design. Tier
  B lines are one-hop guesses and should not be used as an absolute quality
  signal; `docs/SCOPE_FILE.md` documents the confidence classes.
- Coverage path matching follows coverage.py: files imported from the source
  tree match, files imported from a non-editable install do not. If your
  project uses a `src/` layout and installs non-editable in CI, add
  `pythonpath = ["src"]` to pytest settings or install editable.
- v1 measures coverage and renders findings; it does not detect bugs. The
  differential work lands in later phases (`docs/ROADMAP.md`).
- `pytest-args` and `coverage-args` split on whitespace; arguments containing
  spaces are not supported.
- `gh` must be available on the runner. GitHub-hosted runners ship it.
