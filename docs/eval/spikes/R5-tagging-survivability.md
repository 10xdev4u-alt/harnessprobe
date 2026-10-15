# R5: proxy-tagging survivability through async and schema coercion

Spike for HarnessProbe technical risk #2 (proxy-tagging survivability). Date: 2026-10-16.
Environment: Python 3.14.7, wrapt 2.5.1, pydantic 2.14.1, openai 3.31.0 (all pinned, see
`artifacts/r5/requirements.freeze.txt`). Probe: `artifacts/r5/tag_probe.py`, raw output in
`artifacts/r5/probe_output.txt` and `probe_output_run2.txt`.

Method: wrap a pydantic v2 model in a `wrapt.ObjectProxy` subclass carrying a unique
sentinel (`TaggedProxy`, tag argument required so a lost tag cannot be masked by a
default). Push the proxy through each hop listed below and read the tag back. The openai
SDK rows use the real `openai.types.chat.ChatCompletionMessage` /
`ChatCompletionMessageToolCall` types, constructed offline (no client, no key, no
network).

## Survivability matrix

| case | survives | lost at | notes |
|---|---|---|---|
| a) direct attribute access | YES | - | reads forward through proxy (`role`, `tool_calls[0].function.name`) |
| a2) nested element via attribute | NO | never tagged | `tool_calls[0]` is the raw model; the proxy wraps only the top-level value |
| b) 3-hop sync pass | YES | - | same object identity at the end |
| c) 3-hop async chain | YES | - | same object identity at the end |
| d) model_validate from tagged dict | NO | model_validate | new `LocalMessage`; tag never enters validation |
| d3) model_validate from tagged instance [extra] | YES | - | pydantic v2 default `revalidate_instances='never'` returns the same proxy |
| e) model_dump + re-validate | NO | model_dump | dump is a plain dict; re-validation builds an untagged model |
| f) json dumps/loads + re-validate | NO | model_dump | `json.dumps(proxy)` raises TypeError; `dumps(model_dump())` works and drops the tag |
| g) copy.copy / copy.deepcopy | NO | raises | wrapt 2.5.1 raises `NotImplementedError: object proxy must define __copy__()` (`__deepcopy__()`) |
| g2) copy with overridden hooks [extra] | YES | - | two small methods on the proxy subclass keep the tag |
| h) dict-style passthrough | NO | flattening | rebuilding `{"role": ..., "tool_calls": [...]}` yields a plain dict |
| h2) mapping access on proxy [extra] | NO | mechanics | `proxy["role"]` raises TypeError; the proxy is not a mapping |
| i) tag inside list element | YES | - | indexing and `list(lst)` keep the same object |
| i3) deepcopy of containing list [extra] | NO | raises | same `NotImplementedError` from the element proxy |
| i4) list element through dump/validate [extra] | NO | model_dump | coercion rebuilds plain models |
| openai) attribute access on real SDK type | YES | - | `isinstance(proxy, ChatCompletionMessage)` is True; nested objects untagged |
| openai) model_validate from tagged dict | NO | model_validate | new object, tag gone |
| openai) deepcopy | NO | raises | same `NotImplementedError` |

## Where the tag dies

The tag survives exactly as long as the identity of the proxy object survives: returns
through sync and async calls, attribute reads, list indexing, shallow list copies.
It dies at every step that rebuilds the value:

1. `model_dump` (and any serialization) because it produces a fresh plain dict.
2. `model_validate` from a dict (including JSON round trips) because pydantic builds a
   new model from untrusted input.
3. Manual dict flattening, the most common shape in chat loops that re-append
   `{"role": ..., "tool_calls": ...}` to a message list.
4. `copy.copy` / `copy.deepcopy`, which raise by default: wrapt 2.5.1 requires proxy
   subclasses to define `__copy__` and `__deepcopy__`. A library built on tagging must
   ship those two methods (6 lines, verified in the `g2` rows), otherwise copies of a
   tagged object crash instead of losing the tag quietly.
5. Nested values are never tagged: the proxy is shallow. `tool_calls`, list elements
   inside the model, and function arguments come back as raw pydantic models. Leaf-level
   provenance requires wrapping leaves individually.

One notable survival: `model_validate(proxy_instance)` returns the same proxy (pydantic
v2 does not revalidate instances by default), so idempotent re-validation of an object
that already is a model keeps the tag. Whether real harness code hits this path depends
on the repo.

## Perf

Timeit, 10,000 attribute reads per sample, 5 interleaved samples per side, medians and
ranges from two full runs (run 2 shown; run 1 in `probe_output.txt`). The machine ran at
load ~9.5 on 4 cores (desktop Chromium/editor load, not stoppable), so ranges are wide;
the two runs agree on the order of magnitude.

| operation (per 10k) | median | min | max | run 1 median |
|---|---|---|---|---|
| raw attribute read | 1,224 us | 1,200 | 3,206 | 4,744 |
| proxy attribute read | 19,830 us | 18,531 | 46,054 | 30,972 |
| proxy tag read (`getattr`) | 6,036 us | 3,408 | 7,317 | 6,183 |
| raw `role` read | 1,640 us | 1,483 | 8,925 | 2,419 |
| proxy `role` read | 23,800 us | 17,482 | 35,555 | 23,709 |

Order of magnitude: one proxy attribute read costs about 2 microseconds versus about
0.1 to 0.5 microseconds raw, an 8x to 16x per-access overhead, with a floor near 0.6 us
for a tag read. Limiter: pure Python per-attribute dispatch through the wrapt C proxy on
one core, no I/O involved. At harness scale (tens to hundreds of reads per model
response) the total is microseconds per response, negligible next to an LLM call. The
cost of tagging is not the problem; the soundness loss documented above is.

## Verdict

Proxy tagging is usable as an optional second-tier truth source, meaning a may-depend
signal for "a tagged value was live here", never as a taint oracle. It survives the
paths that matter for cheap instrumentation (same-object returns across sync, async, and
callbacks; direct reads; list membership in the common case) and losses cluster at
exactly the boundaries the research doc predicted: pydantic coercion, JSON round trips,
and dict flattening. Two additions make it usable in practice: override `__copy__` /
`__deepcopy__` on the proxy subclass, and re-tag at the narrowest boundary after any
validation. For leaf-level provenance, wrap leaves, not the container. Recall on a real
repo is bounded by how often that repo re-validates or serializes between the SDK
boundary and the LDH code, which is a per-repo measurement (2 to 3 repos), not a
constant.

## Caveats

- The machine was under load (~9.5 on 4 cores); perf numbers are coarse (medians of 5
  timeit samples, interleaved sides, two runs, wide spread). Only the order of magnitude
  is claimed.
- openai types were exercised as constructible models only, not through a wrapped SDK
  client, no network calls were made.
- The probe tags the post-parse object directly; the planned architecture (wrapping the
  provider client) adds one more boundary that this spike did not model.
- `model_validate` behavior depends on pydantic v2 defaults (`revalidate_instances`);
  other configs would change the `d3` result.
