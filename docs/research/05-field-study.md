# 05 — Field study: how real agent harnesses test LLM-dependent logic

Date: 2026-10-15. Method: read-only, sparse shallow clones (`--depth 1 --filter=blob:none`,
sparse-checkout of test dirs + selected sources) into `/tmp/research/agent-repos/`.
No tests were run. Test counts are approximations (file counts, `rg -c 'def test_'`,
`find`), not collected results. LDH is interpreted as line/branch/mutation coverage instrumentation.

## Repo summary

| Repo (commit, date) | Tests live in / framework | ~Test files / fns | Primary LLM faking |
|---|---|---|---|
| OpenHands `cb835dd` (2026-10-15) | `__tests__/**` + colocated specs (vitest); `tests/e2e/mock-llm/**` (Playwright); `src/mocks/*` (MSW) | ~860 ts/tsx spec files; 51 e2e files | Local OpenAI-compatible HTTP/SSE server built on `openhands.sdk.testing.TestLLM`; MSW handlers for app API |
| Aider `5dc9490` (2026-05-22) | `tests/basic`, `tests/browser`, `tests/help`, `tests/scrape`; unittest-style under pytest | 36 files / 489 fns | `unittest.mock.patch("litellm.completion")` + `MagicMock` model responses |
| browser-use `df1e215` (2026-10-15) | `tests/ci/**` (+ `tests/ci/models`, `security`, `integrations`); pytest | 120 files / 1168 fns | `AsyncMock(spec=BaseChatModel)` fake with scripted actions; `httpx.MockTransport`; `pytest_httpserver` |
| Roo-Code `b867ec9` (2026-05-15) | `src/**/__tests__/*.spec.ts`, `webview-ui`, `packages/*`; vitest per package | 424 `.ts` + 91 `.tsx` test files | `vi.mock("openai")`-style SDK stubs; hand-rolled `MockApiHandler extends BaseProvider` yielding fake streams |
| SWE-agent `3ea751c` (2026-07-16) | `tests/**`; pytest (markers: slow, ctf; xfail_strict) | 31 files / 133 fns | litellm `mock_response` kwarg; `patch("litellm.completion")` + MagicMock `ModelResponse`; in-product scripted models + recorded `.traj` replay |

## OpenHands — `cb835dd`

- Two fake-LLM layers. E2E: `tests/e2e/mock-llm/scripts/mock-llm-server.py` is a real local
  HTTP server speaking OpenAI `/v1/chat/completions` (streaming SSE + `[DONE]`), backed by the
  SDK's `TestLLM.from_messages(build_trajectory())`; exceptions map to provider-style HTTP errors.
  The server itself is unit-tested in-process (`test_mock_llm_server.py` binds `MockLLMHandler`
  with a fresh `TestLLM` per test). Unit: MSW node handlers in `src/mocks/*-handlers.ts`
  (conversation, settings, auth, MCP, workspaces, …) plus `__tests__/mocks/` fixtures.
- Representative excerpt (`tests/e2e/mock-llm/scripts/mock-llm-server.py:44`):
  ```python
  ERROR_MAP: dict[type, tuple[int, str]] = {
      LLMAuthenticationError: (401, "invalid_api_key"),
      LLMRateLimitError: (429, "rate_limit_exceeded"),
      LLMContextWindowExceedError: (400, "context_length_exceeded"),
      LLMBadRequestError: (400, "invalid_request_error"),
      LLMTimeoutError: (408, "timeout"),
      LLMServiceUnavailableError: (503, "server_error"),
  }
  ```
- Reusable helpers: `tests/e2e/mock-llm/utils/mock-llm-helpers.ts` (known tokens like
  `MOCK_LLM_E2E_BASH_OK`, backend/session seeding, minimal-PNG fixture); `test-mapping.json`
  maps changed source paths → e2e subsets (`scripts/resolve-affected-tests.mjs`); MSW handler
  modules export `reset*/seed*` helpers for test isolation.
- Assertion style: MSW-backed unit/integration tests assert API contracts and store behavior;
  agent-loop behavior is mostly end-to-end through one scripted trajectory (server docstring says
  "extend TRAJECTORY" for multi-turn/errors), so provider retry/redaction branches live in the
  external `openhands-sdk`/agent-server, not here.
- LDH: vitest v8 coverage (`vite.config.ts:521`, `include: ["src/**/*.{ts,tsx}"]`,
  `test:coverage` script) and **Stryker mutation testing** (`stryker.config.mjs`, mutates
  `src/**` excluding tests/fixtures/mocks).
- Gaps: provider I/O normalization is split across two systems (TS app + Python SDK); tool-action
  dispatch and redaction of the core loop aren't tested in-repo; only a single happy-path trajectory.

## Aider — `5dc9490`

- Tests patch litellm's completion entrypoint directly and assert constructed call kwargs —
  strong branch-level testing of request normalization and retry behavior.
- Representative excerpt (`tests/basic/test_sendchat.py:25`):
  ```python
  @patch("litellm.completion")
  @patch("builtins.print")
  def test_simple_send_with_retries_rate_limit_error(self, mock_print, mock_completion):
      mock = MagicMock()
      mock.status_code = 500
      mock_completion.side_effect = [
          litellm.RateLimitError("rate limit exceeded", response=mock, llm_provider="llm_provider", model="model"),
          None,
      ]
      Model(self.mock_model).simple_send_with_retries(self.mock_messages)
      assert mock_print.call_count == 3
  ```
- Helpers: none shared; every test builds its own `MagicMock` IO/model. `tests/basic/test_models.py`
  asserts `num_ctx`/`tools` construction; `tests/fixtures/` holds text fixtures (chat history,
  editblock goldens), not provider-response builders.
- Assertion style: branch-oriented (`test_editblock.py`, `test_udiff.py`, `test_wholefile.py`
  cover edit-format parsing; `test_sendchat.py` covers retry/exceptions). No recorded cassettes.
- LDH: none found — CI just runs bare `pytest` (`.github/workflows/ubuntu-tests.yml`), no
  pytest-cov/coverage config, no mutation tooling.
- Gaps: no reusable fake-server or response builder; tool-calling path is thin (Aider is
  text/edit-format based); observation-feedback and orchestration semantics barely exercised.

## browser-use — `df1e215`

- Reusable fake model in `tests/ci/conftest.py:75` — a scripted `BaseChatModel`, the closest
  thing to a "fake LLM SDK" among the repos:
  ```python
  def create_mock_llm(actions: list[str] | None = None) -> BaseChatModel:
      llm = AsyncMock(spec=BaseChatModel)
      llm.model = 'mock-llm'
      async def mock_ainvoke(*args, **kwargs):
          action_json = get_next_action()          # JSON action per call, then default done
          output_format = kwargs.get('output_format') or (args[1] if len(args) >= 2 else None)
          if output_format is None:
              return ChatInvokeCompletion(completion=action_json, usage=None)
          return ChatInvokeCompletion(
              completion=output_format.model_validate_json(action_json), usage=None)
      llm.ainvoke.side_effect = mock_ainvoke
      return llm
  ```
- Provider-level tests inject transports: `httpx.MockTransport(handle_request)` with typed
  builders (`tests/ci/models/test_llm_openrouter.py:31`), `AsyncMock` + `patch.object(...'create')`,
  and `pytest_httpserver.HTTPServer` for HTTP surfaces (cloud sync, reruns, bedrock serializers).
- Helpers: `mock_llm`, `agent_with_cloud`, real `browser_session` fixtures; conftest sets
  `SKIP_LLM_API_KEY_VERIFICATION` and pins cloud URLs to the local httpserver.
- Assertion style: strongly branch-oriented — `test_llm_retries.py` (503 backoff timing),
  `test_fallback_llm.py`, provider key precedence, `test_anthropic_serialized_tool_input.py`,
  security suite (`tests/ci/security/*`: domain filtering, IP blocking, sensitive data).
- LDH: no coverage flags found (dev deps are pytest/asyncio/httpserver/xdist/timeout; CI
  `test.yaml` runs sharded plain pytest); no mutation config.
- Gaps: orchestration semantics (multi-step planning/observation feedback) rely on scripted
  single actions; memory/compaction has only `test_message_compaction.py`.

## Roo-Code — `b867ec9`

- Vitest everywhere (`src/vitest.config.ts`, `webview-ui/vitest.config.ts`, `packages/*/vitest.config.ts`;
  root `npm test` = turbo). `packages/vscode-shim` fakes the VS Code host API for extension tests.
- Dominant fake is a local subclass of the real provider base (`src/core/condense/__tests__/condense.spec.ts:15`):
  ```ts
  class MockApiHandler extends BaseProvider {
      createMessage(): any {
          const mockStream = {
              async *[Symbol.asyncIterator]() {
                  yield { type: "text", text: "Mock summary of the conversation" }
                  yield { type: "usage", inputTokens: 100, outputTokens: 50, totalCost: 0.01 }
              },
          }
          return mockStream
      }
      // getModel(), countTokens() faked too
  }
  ```
  Provider transport tests instead stub SDK modules: `vi.mock("openai", () => ({ default: vi.fn(() => ({ chat: { completions: { create: mockCreate } } })) }))`
  (`src/api/providers/__tests__/base-openai-compatible-provider.spec.ts:13`).
- Helpers: no shared fake-LLM package; each spec re-declares MockApiHandler/streams (44 provider
  spec files, ~104 specs under `src/core`, incl. `task/__tests__/grace-retry-errors.spec.ts`,
  `duplicate-tool-use-ids.spec.ts`, `flushPendingToolResultsToHistory.spec.ts`).
- Assertion style: mixed but branch-heavy in core — tool use filtering, tool-result formatting
  (`src/core/tools/helpers/__tests__/toolResultFormatting.spec.ts`), apply-patch parser/apply,
  condense/summarize history.
- LDH: no coverage config found in checked vitest configs/package scripts; no mutation tooling
  (knip is used for dead-code, not coverage).
- Gaps: no redaction-specific suite (only `anthropic-filter`/`networkProxy` tangentially);
  stream normalization is per-provider ad hoc rather than fixture-driven.

## SWE-agent — `3ea751c`

- Ships its own scripted models in product code (`sweagent/agent/models.py:529`), used directly by
  agent tests — unique among the five:
  ```python
  class PredeterminedTestModel(AbstractModel):
      def __init__(self, outputs: list[dict | str]):
          """Model that outputs a predetermined sequence of messages. Useful for testing."""
          self._outputs = outputs
          self._idx = -1
      def query(self, *args, **kwargs) -> dict:
          self._idx += 1
          output = self._outputs[self._idx]
          if isinstance(output, str):
              return {"message": output}
          result = {"message": output["message"]}
          if "tool_calls" in output:
              result["tool_calls"] = output["tool_calls"]
          return result
  ```
- Other fakes: litellm's built-in `completion_kwargs={"mock_response": ...}` exercised for real
  (`tests/test_models.py:19`); `_make_mock_response()` MagicMock builder + `patch("litellm.completion")`
  for header/kwarg branches. Recorded trajectories under `tests/test_data/trajectories/**.traj`
  drive `tests/test_run_replay.py` (`sweagent run-replay`) and history-processor tests.
- Helpers: conftest fixtures (`test_trajectories_path`, `swe_agent_test_repo_traj`, `dummy_env`
  with `DummyRuntime`), `tests/utils.py` script-import helper.
- Assertion style: parser/dispatch is pure branch testing (`tests/test_parsing.py` 8 fns with
  `pytest.raises(FormatError)`; `test_tools_command_parsing.py` 7; `test_history_processors.py` 3,
  asserting observation elision via "Old environment output" markers); orchestration tested via
  replay + CLI smoke.
- LDH: CI `.github/workflows/pytest.yaml` runs `pytest --junitxml=test-results.xml --cov -n auto -s`
  and uploads coverage XML to Codecov; pytest-cov is a dev dep.
- Gaps: no HTTP/SSE-level provider normalization tests (only mock_response/MagicMock); no retry
  injection fixtures; long-horizon observation feedback only via `.traj` replay.

## Patterns we should support first

1. **Scripted fake model implementing the harness's own model interface** — browser-use's
   `create_mock_llm(actions)`, OpenHands SDK `TestLLM`, SWE-agent `PredeterminedTestModel`.
   The toolkit should offer an "action/trajectory script → model adapter" generator per SDK shape.
2. **Typed provider-response builders + transport injection** — `httpx.MockTransport` + pydantic
   `ChatCompletion` builders (browser-use); openai-module `vi.mock` chains (Roo). Second-tier:
   litellm `patch`/`mock_response` helpers (Aider, SWE-agent).
3. **Local OpenAI-compatible server with SSE streaming and error mapping** — OpenHands
   `mock-llm-server.py` (`_send_streaming`, `ERROR_MAP`) is the strongest integration-tier
   pattern; the toolkit should ship a configurable mock provider server (trajectory DSL + fault
   injection), since Aider/browser-use/SWE-agent all lack one.
4. **Fault-injection schedules** — `side_effect` sequences (Aider rate-limit→success), 503
   backoff timing (browser-use), exception→HTTP-status maps (OpenHands). Retry/error recovery is
   the category with most per-repo duplication and least shared tooling.
5. **Recorded trajectory replay as fixtures** — SWE-agent `.traj` + `run-replay` (and OpenHands
   `test-mapping.json` for test subsetting). Cassette/replay support with source→test mapping is
   directly reusable.
6. **Handler registries with seed/reset** — MSW-style domain handlers (OpenHands `src/mocks/*`)
   and Roo's per-suite `MockApiHandler`: give fake backends deterministic resettable state.

Overall, best-covered today: provider request construction (Aider/browser-use) and parser/tool
branch behavior (SWE-agent/Roo). Least-covered: error-recovery policy beyond simple retries,
observation-feedback formatting/elision semantics, long-horizon orchestration, and secret
redaction (no repo has a dedicated redaction suite).

## Uncertainties

- At this commit OpenHands is a TypeScript/Electron app; the Python agent core lives in external
  `openhands-sdk`/agent-server, so `TestLLM` internals were only observed via its in-repo server.
- Counts are file/`def test_`-based; parametrization and `subTest` loops mean true case counts differ.
- No suites were executed; framework/coverage claims come from configs, imports and CI workflows.
- LDH was read as line/branch/mutation coverage; only OpenHands (v8+Stryker) and SWE-agent
  (pytest-cov+Codecov) showed instrumentation; absence elsewhere is "not found", not disproof.
- Partial checkouts: parts of Roo-Code/OpenHands src were inspected via `git show` rather than
  checkout; selected 5 repos omit PR-Agent/GPT Researcher/RD-Agent/Kimi Code/OpenClaw.
- Aider's HEAD is 2026-05-22 (stale relative to others) and its repo has no coverage tooling by design.

## Best first MVP target

**browser-use**: smallest/cleanest seam. One `create_mock_llm` fixture + typed
`BaseChatModel`/`ChatInvokeCompletion` protocol + `httpx.MockTransport` give a complete
provider→agent-loop test loop in one repo, and its retry/fallback/security tests are exactly the
branch behavior an MVP toolkit must reproduce. Second target: OpenHands' mock-LLM server pattern
for the HTTP/SSE tier; third: SWE-agent for replay fixtures + scripted models.
