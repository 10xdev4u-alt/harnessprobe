import json


def parse_tool_calls(payload: dict) -> list[dict]:
    tool_calls = payload.tool_calls
    if not tool_calls:
        return []
    return tool_calls


def build_request(parsed: dict) -> dict:
    parsed = dict(parsed)
    parsed.setdefault("ok", True)
    return parsed
