# Scope file

`harnessprobe init` writes a scope file. The file is a JSON inventory of the
files and statement lines that may contain LLM-dependent harness (LDH) code,
with the evidence behind each guess. Review the file and commit it, so later
runs can diff scope changes. Run `init` against a repository root:

```console
harnessprobe init path/to/repo --out harnessprobe.scope.json
```

- `path` is the repository root to scan. It defaults to `.`.
- `--allowlist PATTERN` scopes every file that matches the glob pattern whole.
  Repeat the option for multiple patterns.
- `--no-tier-b` disables tier B reachability and lowers the candidate count.
- `--out PATH` sets the output path. The default is
  `<path>/harnessprobe.scope.json`.

The command prints a summary and exits 0. Warnings go to standard error. A
missing path, a path that is not a directory, or a write failure exits 1 with
an `error:` line on standard error.

## Schema: harnessprobe.scope/v2

```json
{
  "schema": "harnessprobe.scope/v2",
  "generated_by": "harnessprobe",
  "allowlist": ["legacy/agent.py"],
  "include_tier_b": true,
  "sources": [{"kind": "model_call", "path": "agent.py", "line": 14}],
  "files": [
    {
      "path": "agent.py",
      "scope_kind": "pinned-lines",
      "ldh_lines": 3,
      "lines": [14, 18, 21],
      "confidence": "heuristic-high",
      "reasons": ["heuristic:tier-a"]
    },
    {
      "path": "legacy/agent.py",
      "scope_kind": "whole-file",
      "ldh_lines": 42,
      "lines": null,
      "confidence": "allowlisted",
      "reasons": ["allowlist"]
    }
  ],
  "confidence_notes": ["annotations are user-declared; treated as authoritative"],
  "warnings": []
}
```

| Field | Type | Meaning |
| --- | --- | --- |
| `schema` | string | Format identifier. The only value is `harnessprobe.scope/v2`. |
| `generated_by` | string | Tool that wrote the file. |
| `allowlist` | list of strings | The `--allowlist` patterns, echoed in order. |
| `include_tier_b` | boolean | Whether tier B reachability ran. |
| `sources` | list of objects | Every model-call and annotation site found, with `kind`, `path`, and `line`. |
| `files` | list of objects | Candidate files, each with `path`, `scope_kind`, `ldh_lines` (count), `lines`, `confidence`, and `reasons`. |
| `confidence_notes` | list of strings | Legend for the confidence classes present, in fixed order. |
| `warnings` | list of strings | Files skipped during the scan, with the reason. |

`files` is sorted by `path`. `sources` is sorted by `path`, `line`, then
`kind`. Both orderings are deterministic across runs.

`scope_kind` records how the entry was scoped. A `pinned-lines` entry lists
the scoped line numbers in `lines`, and `ldh_lines` equals `len(lines)`. A
`whole-file` entry records `lines: null`: the file is scoped whole by
declaration, and its lines resolve from the current source when the scope file
is loaded. `v2` replaced the flat line list of `v1`; regenerate an older file
with `harnessprobe init`.

## Confidence vocabulary

Confidence describes the evidence for one file. The strongest evidence wins,
in the order below.

| Confidence | Reason | Meaning |
| --- | --- | --- |
| `authoritative` | `annotation` | A `# harness:llm-source` comment marks the site. |
| `allowlisted` | `allowlist` | An `--allowlist` pattern scopes the file whole. |
| `heuristic-high` | `heuristic:tier-a` | A model call, or a statement consuming one, inside the same function. |
| `heuristic-low` | `heuristic:tier-b` only | A one-hop call into a tier-A function. |

## Freshness

Scope entries age in two different ways.

Whole-file entries come from `--allowlist` patterns. They carry no pinned
lines: the plugin resolves their lines from the current source when it loads
the scope file, so edits that add, remove, or move lines cannot drop them from
measurement. They never need regeneration.

Pinned-lines entries record the line numbers seen at `init` time. When the
plugin loads a pinned entry whose lines no longer all resolve to statements,
it prints:

```
harnessprobe: warning: agent.py: pinned scope lines no longer resolve to statements; rerun harnessprobe init to refresh the scope file
```

An entry whose file cannot be read or parsed warns `pinned scope not
verifiable` instead. Warnings print before the coverage summary, so they are
visible in CI logs; they do not fail the session. Rerun `harnessprobe init`
and commit the refreshed file when the warning appears.

## Limits

The scope is a heuristic, not a proof. A call shape the matcher does not know
is not discovered. A consumer variable whose name does not match the prefix
list is dropped. Each file is read in isolation, so a call through an alias, a
wrapper two hops away, or a callback registered elsewhere is out of reach.
There is no data-flow or taint analysis, and a scoped line does not prove that
model output reaches it.

Tier A looks for model calls and for consumer names such as `response`,
`parsed`, and `tool_calls`. Tier B adds callers of tier-A functions one hop
out; expect false positives there and review them. `--no-tier-b` narrows the
candidate set and misses those callers.

Annotations are the only signal you control directly. Put `# harness:llm-source`
on a `def` line to scope its whole body, or on a single statement to scope that
statement. The file keeps the annotation site in `sources` either way.

## Using the scope file in pytest

Install the package and the pytest plugin loads on its own. It resolves a scope
file in this order:

1. `--harnessprobe-scope PATH`
2. the `harnessprobe_scope` ini option
3. `harnessprobe.scope.json` in the pytest rootdir

When none of these resolves, the plugin stays inert. A scope file you configure
explicitly that is missing or unreadable fails the session with a usage error.
Whole-file entries resolve against the pytest rootdir, so the scope file's
`path` values are relative to that directory.

Session end writes `harnessprobe.report.json` in the rootdir, holding the
`harnessprobe.report/v1` subset document and printed as a two-line summary. Send
the report elsewhere with `--harnessprobe-report PATH`, or keep the summary and
skip the file with `--harnessprobe-no-report`.

Coverage data must exist when the session ends:

```console
coverage run --branch -m pytest
```

pytest-cov works too. Without coverage data the plugin prints
`harnessprobe: no coverage data found` and writes nothing. Opt out of the whole
plugin with `-p no:harnessprobe`.
