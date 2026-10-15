# Incident: live provider test opened a real browser

**Date:** 2026-10-16, 01:05 local (Asia/Kolkata).
**Severity:** low impact, high signal.
**Status:** resolved; guardrail landed with this record.

## What happened

During spike R3 (browser-use coverage subsetting), the first pytest run
executed `tests/ci/models/test_llm_openai.py::test_openai_gpt_4_1_mini`, a test
gated on `OPENAI_API_KEY` presence. The interactive shell had a live key and a
provider base URL exported, so the test launched system Chromium through
browser-use on the operator's desktop and attempted a live model call. It failed
with "Button was not clicked - SUCCESS not found in any page state". The browser
exited with the test.

## Evidence

- First-run log: 549 passed, 1 failed, 5 skipped in 117 s
  (`pytest-run-withkeys.log`, kept in the spike artifacts).
- `R3-browser-use.md`, "What broke" item 1, and
  `/tmp/hp-eval/artifacts/r3/decisions.tsv` (01:05 entry).
- `~/.config/browseruse/` created at 01:03 local with 63 MB of browser-use
  extensions and an empty profiles directory; removed during remediation.

## Impact

- One live-flagged test ran with real credentials against the configured base
  URL. The exact request count cannot be reconstructed from the kept artifacts.
- Chromium windows opened on the operator's desktop with unsupported-flag
  warnings. Operator-visible; no data loss.
- No key material was written to any artifact or commit (content scan clean).
- Official spike numbers come from a re-run with the key unset: 549 passed,
  6 skipped, 0 failed in 57 s.

## Root cause

Spike processes inherited the operator shell's API keys. browser-use gates live
tests on key presence and starts a real browser when keys are present. Test
selection alone was not a sufficient gate.

## Remediation

- Removed the spike-created `~/.config/browseruse` directory (63 MB).
- Amended charter section 12: spike sandboxes scrub key environment variables,
  isolate `HOME` where practical, exclude browser- and network-gated tests by
  selection, and never open GUI applications on the operator's desktop.
- Future spike instructions repeat the rule in their prompts.
