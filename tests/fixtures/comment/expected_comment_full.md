### HarnessProbe: 2 bug classes caught (3 findings)

- **tool call dropped** (2)
  - Tool call silently dropped on partial stream — (browser_use/agent/service.py:412) [evidence](https://github.com/10xdev4u-alt/harnessprobe/issues/101)
  - Second tool call in one message ignored — [evidence](https://github.com/10xdev4u-alt/harnessprobe/issues/102)
- **secret leaked in saved history** (1)
  - API key written into saved history file — (browser_use/agent/message_manager/service.py:88) [evidence](docs/research/03-bug-classes.md)

### LDH coverage

`81.82%` of LDH scope lines covered (9/11; 8 not measured) — **+2.10pp** vs previous report
Branches: 1 full / 1 partial / 1 missing

<details><summary>Top uncovered LDH lines</summary>

- `mini_repo/agent.py:21` — `return response.choices[0].message.content`
- `mini_repo/agent.py:34`
- `mini_repo/parsing.py:6` — `if not tool_calls:`

</details>

_harnessprobe · report harnessprobe.report/v1_
