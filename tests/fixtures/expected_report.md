# HarnessProbe LDH scope coverage

Totals: 9/11 scope lines covered (81.82%), 8 not measured; branches 1 full, 1 partial, 1 missing.

| File | Scope lines | Executed | Covered | Not measured | Branches F/P/M | Samples |
| --- | --- | --- | --- | --- | --- | --- |
| mini_repo/agent.py | 3 | 2 | 66.67% | 0 | 0/1/0 | 1 |
| mini_repo/parsing.py | 6 | 5 | 83.33% | 0 | 0/0/1 | 1 |
| mini_repo/dispatch.py | 2 | 2 | 100.00% | 0 | 1/0/0 | 0 |
| mini_repo/text_tools.py | 0 | 0 | n/a | 5 | 0/0/0 | 0 |
| mini_repo/unrelated.py | 0 | 0 | n/a | 3 | 0/0/0 | 0 |

## Top uncovered scope lines

- mini_repo/agent.py:21: return response.choices[0].message.content
- mini_repo/parsing.py:6: if not tool_calls:
