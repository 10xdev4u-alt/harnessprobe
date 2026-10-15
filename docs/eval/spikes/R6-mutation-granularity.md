# R6: Python mutation granularity, mutmut vs libcst

Spike for HarnessProbe technical risk #3 (LDH-scoped mutation). Date: 2026-10-16.
Environment: Python 3.14.7, mutmut 3.8.0, libcst 1.9.0, pytest 9.1.1 (pinned in
`artifacts/r6/requirements.freeze.txt`). Both mutmut and libcst install and run on
Python 3.14; no compatibility blockers. One quirk: mutmut loads its config at import
time, so even `mutmut --version` or `mutmut run --help` raises `FileNotFoundError` when
run outside a directory with `[tool.mutmut]` config.

Subject: `artifacts/r6/sample_harness.py`, 130 lines, synthetic LDH shape (parse tool
call, validate params, dispatch, recursive redaction, retry with backoff). 55 lines carry
a trailing `# LDH` marker (42%). `ldh_map.py` maps marked lines to the 7 enclosing
functions out of 9; the two handlers are non-LDH. 15 pytest tests, all green in 0.08 s.

## Experiment A: whole module, mutmut defaults

`mutmut run --max-children 2`, cache cleared, fresh run: **166 runnable mutants, 125
killed (75.3%), 41 survived, 0 timeout, 0 suspicious, 17.0 s wall** (12.4 mutants/s,
per-mutant cost about 75 ms plus about 4 s fixed overhead for stats and clean-test
phases).

The raw libcst generator produces 189 mutations; the difference of 23 sits in the
three module-level constants (lines 11, 13, 49), which mutmut never turns into runnable
mutants because its trampoline arrangement only rewrites top-level functions. Verified
with `mutant_line_stats.py` and `gap_check.py`.

## Experiment B: scoping to LDH

Knob surface, read from the installed 3.8.0 source and confirmed by runs
(`configuration.py` L157-163, `pragma_handling.py` L82-88, `file_mutation.py` L270+):

| knob | scope | verdict |
|---|---|---|
| `source_paths` | files or directories | file granularity |
| `only_mutate` / `do_not_mutate` | file globs only, must end `.py` or `*` | no function or line targeting |
| `mutate_only_covered_lines` | coverage.py lines, not LDH-aware | wrong signal |
| `# pragma: no mutate` comments | hand-placed line or node exclusions | manual, not derived from LDH analysis |
| `do_not_mutate_patterns` | regex matched against source lines; expressions starting on matching lines are excluded | the only programmable fine-grained knob |

B1 attempt, function targeting: `only_mutate = ["sample_harness.py::parse_tool_call"]`
produced a `UserWarning` ("glob patterns ... likely invalid") and a run with **0 files
mutated**, stopping after 2.3 s. Mutmut cannot target functions by name.

B2, line exclusion driven by the markers:
`do_not_mutate_patterns = ["^(?!.*# LDH)"]` (negative lookahead: every line without the
marker is excluded). Result: **120 runnable mutants, all on marked lines (0 on unmarked
lines, verified with mutmut's own generator, `mutant_line_stats_output.txt`); 91 killed
(75.8%), 29 survived, 12.1 s wall.** Survivors by function: `parse_tool_call` 15 of 57
(74% killed), `dispatch` 6 of 11 (45% killed), `process_response` 5 of 27, `validate_params`
3 of 8; redaction, backoff, and retry left no survivors. The A-only survivors in the two
handler functions and on the unmarked `try`/`except`/`raise` lines disappear by
construction.

## Cost table

| variant | scope | mutants | killed | killed % | wall time | notes |
|---|---|---|---|---|---|---|
| A, defaults | whole file | 166 | 125 | 75.3% | 17.0 s | 46 mutants in non-LDH handler functions |
| B1, function-name glob | none | 0 | n/a | n/a | 2.3 s | pattern rejected with warning |
| B2, marker regex | LDH-marked lines | 120 | 91 | 75.8% | 12.1 s | zero mutants on unmarked lines |
| C, libcst ranges | lines [107,109] and [53,71] | 2 and 10 sites | n/a | n/a | under 1 s | prototype, no kill bookkeeping |

Scoping removes 46 of 166 mutants (28%) and 29% of wall time; the fraction held by fixed
overhead is why time falls less than mutants would suggest. The LDH subset is not easier:
75.8% killed versus 75.3% on the whole file.

## Experiment C: libcst line-range mutator

`line_range_mutator.py` swaps binary, comparison, and boolean operators and removes `not`
negations, only for nodes fully inside `[start, end]`. It applied 2 sites in
`backoff_delay` lines [107,109] (`base * (2 ** attempt)` became `base / (2 * attempt)`)
and 10 sites in `parse_tool_call` lines [53,71] (8 negations and boolean swaps, plus
comparison support that had no sites to hit). Both mutated copies compile
(`py_compile`), diffs are saved, originals reverted (sha256 before and after match).
Integration cost: this prototype applies every site at once, so it is a location-control
demonstration, not a mutant runner. A usable side-mutator must emit one site per mutant
and then reimplement what mutmut already has: per-mutant test selection, timeouts,
survivor bookkeeping, cache and resume. That bookkeeping, not the rewrite, is the work.

## Verdict

Confirmed with a correction. The v1 strategy of "weekly sliced function-granular" works,
but mutmut 3.8.0 does not need file slicing to get there: `do_not_mutate_patterns` plus
in-source LDH markers gives line granularity (finer than function) in one config line,
same kill signal, 29% less wall time, no module surgery, no new bookkeeping. The cost
moves to keeping markers and the exclusion regex in sync with the LDH analyzer; the
toolkit should generate a marked copy before each run and assert that zero unmarked-line
mutants were generated. Fallback if marker maintenance proves fragile: split LDH
functions into their own module and point `source_paths` at it (function granularity,
more invasive). Keep libcst for later, when custom operator sets or single-site shedding
below line granularity are needed; do not rebuild mutmut's scheduler now.

## Caveats

- Wall times come from single runs on a machine at load 5.2 to 9.5 on 4 cores; mutant
  counts are deterministic, times are indicative only. Both timed runs used
  `--max-children 2`.
- Kill rates are properties of this 15-test synthetic suite on a 130-line module, not
  the rates a real repo will show.
- The marker regex was exercised with one marker style and single-line statements;
  multi-line statements spanning marked and unmarked lines are untested.
- Experiment C proves location control and compilation, not mutant kill behavior.
