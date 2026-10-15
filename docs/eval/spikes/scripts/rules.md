# R4 ground truth: annotation rules and borderline calls

## Annotation definition

An LDH line is a source line that does at least one of:

1. Consumes a model-output-derived value: attribute/subscript/index access, or
   passing it to a function that transforms or executes it (dispatch, parse,
   redact), where the value traces to an LLM response object, a parsed action
   object, or an ActionResult produced by executing a model-chosen action.
2. Branches on such a value (if / elif / while / ternary / comprehension filter
   whose condition tests it).
3. Mutates persistent state (`self.state.*`, history, message manager state) from
   such a value.

Primary unit: the starting line of the statement/expression. Multi-line
statements are annotated on the first line only; the scorer collapses each
Semgrep match to its start line so ±0 is strict and ±2 absorbs line-wrapping.

## Scope exclusions (chosen before running Semgrep)

- Logging-only lines (`logger.*`, `log_response`, `_log_action`,
  `_log_next_action_summary`): excluded even though they read the value.
- Pure local propagation (`result = await self.multi_act(...)` with no
  attribute access): excluded; the mutation of `self.state.*` is annotated.
- Counter increments driven only by control flow (e.g. `consecutive_failures += 1`):
  excluded.
- Schema construction sent to the model (`create_action_model`,
  `RegisteredAction.prompt_description`, `AgentOutput.model_json_schema`):
  excluded; that is outbound, not consumption.
- Error strings derived from exceptions (not response objects): excluded.

## Partial annotation windows

`browser_use/agent/service.py` (4163 lines) and `browser_use/tools/service.py`
(2327 lines) are annotated only inside windows listed in `windows.json`, chosen
by reading order before the Semgrep run. Hits outside windows are excluded from
scoring and reported separately as unscored extras.

## Borderline calls (kept in this file for honesty)

1. `service.py:1200` `self.state.last_model_output = model_output`: a pure
   assignment, but a persistent-state mutation from the fetched model output.
   Included under rule 3. A stricter reading (consumption only) would drop it.
2. `service.py:1217` `self.state.last_result = result`: `result` holds
   ActionResults, which derive from a model-chosen action, not from the model
   text directly. Included under interpretation "tool/action output is
   downstream of model output". A text-only reading would drop all ActionResult
   lines (message_manager 322-347, views.py 708/718-734) and recall would fall
   by roughly 20 lines.
3. `tools/registry/service.py:200` `params.model_dump()` in the registry
   wrapper: `params` is a validated action param model, i.e. parsed model
   output. Included. Semgrep taint does not model this flow (it enters as a
   parameter), so this line is a guaranteed CE miss.
4. `agent/service.py:1694-1701` `setattr(action_instance, 'done', {...})`: the
   payload is hardcoded; the branch above (1691) is LDH. The lines are excluded
   because they do not read model output. A control-dependence reading would
   include 1694-1702.
5. `message_manager/service.py:594` `message.content = replace_sensitive(...)`:
   the message is the state prompt, which embeds model text from prior steps.
   Included as redaction of model-derived content. If redaction of
   user-supplied-but-echoed text is not LDH, drop 593-599.

## Inter-annotator uncertainty

Single annotator (this agent). The knobs above (logging, propagation-only,
ActionResult-derived, counter mutations) plausibly move the annotated set by
±15 lines (~9%). A second annotator using the same stated definition would
land within that band; a different operationalization would not.
