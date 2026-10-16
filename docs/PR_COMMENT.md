# PR comments

`harnessprobe comment` renders the PR comment for a coverage run. It leads with the
bug classes the run caught and links each one to its evidence, and reports LDH
coverage second. Reviewers read bug classes, and a bare percentage gets skipped.
The comment has up to four blocks, in this order.

1. Bug classes.
2. LDH coverage.
3. Top uncovered LDH lines.
4. Footer, `_harnessprobe · report harnessprobe.report/v1_`.

### Bug classes

With findings attached, the heading is `### HarnessProbe: N bug classes caught (M
findings)`. Each class gets a bullet, `- **<bug_class>** (k)`, ordered by finding
count (highest first, then class name). Each finding gets an indented bullet,
`<title> — [evidence](<evidence>)`, with `(<location>)` before the link when the
finding has one. With no findings, the heading is `### HarnessProbe: no bug classes
caught`, followed by one line that says so.

### LDH coverage

Always present. The first line reports the percentage of LDH scope lines covered,
the executed and total counts, and the not-measured count:

    `81.82%` of LDH scope lines covered (9/11; 8 not measured)

With `--previous`, the line ends with the trend value followed by `vs previous
report`: `+2.10pp`, `no change`, or `no comparable previous value` when a side has no
percentage. The second line, `Branches: F full / P partial / M missing`, reports
branch classification totals.

### Top uncovered LDH lines

Present only when the report has uncovered samples. A collapsed `<details>` block
lists up to 8 lines as `` - `path:line` — `text` ``, most-sampled files first.

## Findings file

Findings arrive as a `harnessprobe.findings/v1` JSON document:

```json
{"schema": "harnessprobe.findings/v1",
 "findings": [
   {"bug_class": "tool call dropped", "title": "Tool call silently dropped on partial stream",
    "evidence": "https://github.com/10xdev4u-alt/harnessprobe/issues/101",
    "location": "browser_use/agent/service.py:412"}]}
```

`evidence` is a URL or a repo path. `location` is optional and holds `file:line`.

## Usage

```console
$ uv run harnessprobe comment --report harnessprobe.report.json \
    --findings tests/fixtures/comment/sample-findings.json
### HarnessProbe: 2 bug classes caught (3 findings)
...
```

Without `--out`, the comment goes to stdout; with `--out comment.md`, it is written
there. A missing or invalid report, findings file, or previous report prints `error:`
on stderr and exits 1.

## Where findings come from

v1 renders findings; it does not detect them. Detection arrives with the differential
work in later phases (B3 and the P-series), so until then runs without findings render
the no-findings line plus the coverage sections and never claim bugs.
