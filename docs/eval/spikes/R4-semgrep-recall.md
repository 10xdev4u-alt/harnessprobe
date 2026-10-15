# R4: Semgrep-CE static taint recall/precision for LDH extraction on browser-use

Date: 2026-10-16. Status: spike, complete.

## Context

HarnessProbe needs an LDH scope source (the set of lines that consume model output:
parsing, dispatch, state mutation, retry, redaction). Research decision 2026-10-15
(docs/research/03-tech-feasibility.md sec. 1, 7) picked "Semgrep CE + our own
source/sink taint rules" as the default Python engine, with the known limit that OSS
taint is intraprocedural. This spike measures what that choice actually buys on
browser-use, against hand-annotated ground truth.

## Method

Repo: browser-use at HEAD a71d5478e4187cbe5295aab6403dfe7e4a6861a4 (2026-10-15), cloned
shallow to /tmp/hp-eval/repos/browser-use-semgrep. Note the field study used df1e215;
HEAD moved.

Selected files (7): browser_use/agent/service.py, browser_use/agent/views.py,
browser_use/agent/message_manager/service.py, browser_use/agent/message_manager/utils.py,
browser_use/tools/registry/service.py, browser_use/tools/registry/views.py,
browser_use/tools/service.py. Harness-central per field study: agent loop, output
parsing, message manager, tool registry dispatch, tool execution.

LDH definition used for annotation: a line that (1) consumes a model-output-derived
value (LLM response object, parsed action, ActionResult from a model-chosen action),
(2) branches on one, or (3) mutates persistent state from one. Statement-start line is
the unit. Exclusions: logging-only lines, propagation-only local assignments, counter
increments, outbound schema construction, exception-derived error strings. Borderline
calls and inter-annotator uncertainty are in artifacts/r4/rules.md.

Annotation: 170 lines across the 7 files (artifacts/r4/ground-truth.json). The two
large files are annotated only inside read windows (listed in windows.json, chosen and
written before the Semgrep run); scoring is restricted to those windows. This is the
spike's main methodological concession: 133 of 256 hit lines fall outside windows and
are unscored.

Rules: artifacts/r4/ldh-rules.yaml, 10 rules, config validation 0 errors. Four taint
rules (sources: `$LLM.ainvoke/invoke`, `$CLIENT.chat.completions.create`,
`litellm.completion/acompletion`, harness calls `get_model_output/multi_act`; sinks:
response attribute access, `json.loads`, keyed dispatch, `self.state.*` assignment).
Six name-heuristic pattern rules for parsed-action variables, ActionResult fields,
dispatch lookups, and validated param fields. The heuristics exist because CE taint is
intraprocedural and cannot see values that arrive as parameters, which is most of the
harness.

Command (from repo root):

```
semgrep scan --config /tmp/hp-eval/artifacts/r4/ldh-rules.yaml --metrics=off --json \
  -o /tmp/hp-eval/artifacts/r4/hits.json \
  browser_use/agent/service.py browser_use/agent/views.py \
  browser_use/agent/message_manager/service.py browser_use/agent/message_manager/utils.py \
  browser_use/tools/registry/service.py browser_use/tools/registry/views.py \
  browser_use/tools/service.py
```

Semgrep 1.175.0, exit 0, 0 errors. 302 raw hits (256 distinct hit lines).

## Numbers

Scoring: each match collapsed to its start line; metrics on distinct hit lines within
annotation windows. Run: python3 artifacts/r4/score.py.

| Metric | +-0 (strict) | +-2 (formatting-tolerant) |
|---|---|---|
| Recall (annotated lines hit) | 81/170 = 47.6% | 103/170 = 60.6% |
| Precision (hit lines annotated) | 78.6% (81 TP / 103 lines) | 82.1% |

Honest headline: the strict +/-0 row. The +/-2 row absorbs Semgrep's statement spans
and my statement-start convention (for example the FPs at service.py:1680 and
views.py:563 are continuation lines of statements that are annotated). +/-2 is the
best-case reading; +/-0 is what the annotation claims literally.

Per file (recall +/-0 / +/-2, annotated): agent/service.py 14/31, 17/31; agent/views.py
31/51, 43/51; message_manager/service.py 15/30, 18/30; message_manager/utils.py 1/1,
1/1; tools/registry/views.py 2/9, 3/9; tools/registry/service.py 3/23, 4/23;
tools/service.py 15/25, 17/25.

Rule contribution: the taint rules produced 16 of 302 hits (ainvoke rule 9,
harness-call rule 7; openai and litellm rules 0 hits, those entry points do not appear
in the selected files). The 6 name-heuristic pattern rules produced 286. On this
corpus, Semgrep CE taint was a rounding error next to the heuristic layer.

Runtime: Semgrep internal profiling total_time 11.20 s (config 0.87 s, core 10.26 s).
Wall clock about 14 s on a machine at load average 7.2 on 4 cores, so treat the wall
time as noisy; the internal number is the one to quote.

Limiter for recall: intraprocedural scope plus my sink vocabulary. Not file size:
parsing 7 files took under a second.

## Miss taxonomy (67 misses at +/-2)

1. Value arrives as a parameter or state read (interprocedural), about 35 lines.
   Examples: agent/service.py:2782 (action passed to tools.act), service.py:1142
   (model_output passed into message manager), registry/service.py:395
   (`params=validated_params` executed), registry/views.py:71-76 (ActionModel methods
   where the object is `self`), message_manager/service.py:209. CE cannot bridge
   caller to callee; the heuristic rules only match receiver names, not arguments.
2. Sink vocabulary too narrow for bare scalars and chained expressions, about 20
   lines. Examples: message_manager/service.py:282,285,286,288 (`summary` is locally
   tainted from `llm.ainvoke`, but no rule matches a scalar read, `len(summary)`, or
   `self.state.X = summary`), message_manager/service.py:365-370, agent/service.py:1246
   (`self.state.last_result[-1].success`), tools/service.py:604-607 (`seconds`),
   tools/service.py:618 (`llm_x`). This class is a rule-authoring gap, not a CE limit.
3. Callee-argument consumption, about 4 lines. Examples: agent/service.py:1960
   (`_recursive_process_all_strings_inside_pydantic_model(parsed, ...)`),
   agent/service.py:1968 (`_broadcast_model_state(parsed)`). The callee consumes the
   model output; no receiver-name pattern can express that.
4. Redaction inside nested closures, about 8 lines. registry/service.py:470-494
   (`recursively_replace_secrets` searching model-authored param strings) and
   message_manager/service.py:594,598. The model text enters as a closure parameter;
   nothing taints it.

## FP taxonomy (22 scored, +/-2 basis)

1. Name collisions in non-LDH plumbing, 12 lines. views.py:119-147 (`params` inside
   loop-detector hashing; note these lines are plausibly LDH and were probably omitted
   from my annotation, so this is partly a ground-truth gap), registry/service.py:54
   and 147 (`action_name`/`action_params` in registry administration and signature
   handling, developer-chosen names), registry/views.py:50 (`params` list of schema
   descriptions).
2. Annotation scope the rules cannot know, 8 lines. Logging-only lines the rules
   rightly match but my scope excludes (message_manager:328, service.py:1674,2866,2867,
   2874), and propagation-only writes (service.py:1702,2845).
3. Statement-span artifacts beyond +/-2, 2 lines. service.py:1680, views.py:563 are
   continuation lines of annotated multi-line statements.

## Reproduce

```
git clone --depth 1 https://github.com/browser-use/browser-use /tmp/hp-eval/repos/browser-use-semgrep
cd /tmp/hp-eval/repos/browser-use-semgrep && git checkout a71d5478e4187cbe5295aab6403dfe7e4a6861a4
semgrep scan --config /tmp/hp-eval/artifacts/r4/ldh-rules.yaml --metrics=off --json \
  -o /tmp/hp-eval/artifacts/r4/hits.json <7 files listed above>
python3 /tmp/hp-eval/artifacts/r4/score.py
```

## Verdict

Semgrep-CE alone is not defensible as the v1 LDH scope source: 47.6% strict recall and
78.6% strict precision on hand-annotated ground truth, and the taint engine itself
contributed only 16/302 hits, so the "static taint" label oversells what ran. The
research plan holds as written: heuristic scope first (AST plus naming rules) and use
Semgrep-CE as one candidate generator in a union with the runtime tagging ledger, fail
open at interprocedural boundaries. If we keep Semgrep in the stack, the honest framing
is "pattern-based LDH candidate generator with a small taint assist", tuned per repo
vocabulary, never the scope of record.

Caveats that bound these numbers:

- Ground truth is my single-annotator reading of one commit; the stated definition the
  boundary calls in rules.md could move the set by roughly +-15 lines (~9%).
- 133 of 256 hit lines lie outside the two partial-file windows and were not scored;
  precision is a within-window number.
- The clear FP at views.py:119-147 is probably an annotation omission, which means
  precision is somewhat understated and recall slightly overstated.
- One run, one repo, one commit, one rule set the author also used to pick the file
  set. Treat the ratios as an interval, not a point.
