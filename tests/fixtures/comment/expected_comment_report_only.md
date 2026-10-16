### HarnessProbe: no bug classes caught

No findings were attached to this run. HarnessProbe v1 ships LDH coverage subsetting; differential bug detection lands in later phases.

### LDH coverage

`81.82%` of LDH scope lines covered (9/11; 8 not measured)
Branches: 1 full / 1 partial / 1 missing

<details><summary>Top uncovered LDH lines</summary>

- `mini_repo/agent.py:21` — `return response.choices[0].message.content`
- `mini_repo/agent.py:34`
- `mini_repo/parsing.py:6` — `if not tool_calls:`

</details>

_harnessprobe · report harnessprobe.report/v1_
