"""Synthetic LDH-shaped harness for the R6 spike. Throwaway, not production code.

LDH scope for this spike: statements that consume the raw model response
(unparsed) or raw tool output, dispatch on model-chosen names, and apply retry
or redaction policy. Lines in that scope carry a trailing `# LDH` marker.
"""

import json
import time

SECRET_KEYS = ("api_key", "token", "password", "secret")

TOOL_SCHEMAS = {"get_weather": {"city": str}, "send_email": {"to": str}}


class HarnessError(Exception):
    """Base class for harness failures."""


class ToolCallParseError(HarnessError):
    """Model response could not be parsed."""


class ParamValidationError(HarnessError):
    """Model-provided params failed validation."""


class UnknownToolError(HarnessError):
    """Model asked for a tool that is not registered."""


class TransientToolError(HarnessError):
    """Tool failed in a retryable way."""


def handle_get_weather(args):
    return {
        "city": args["city"],
        "units": args.get("units", "metric"),
        "temp_c": 21,
        "api_key": "sk-synthetic-123",
    }


def handle_send_email(args):
    return {"to": args["to"], "status": "queued", "token": "tok-synthetic-abc"}


TOOL_REGISTRY = {"get_weather": handle_get_weather, "send_email": handle_send_email}


def parse_tool_call(response):  # LDH
    choices = response.get("choices") if isinstance(response, dict) else None  # LDH
    if not choices:  # LDH
        raise ToolCallParseError("no choices in response")  # LDH
    message = choices[0].get("message") or {}  # LDH
    calls = message.get("tool_calls") or []  # LDH
    if not calls:  # LDH
        raise ToolCallParseError("no tool calls in message")  # LDH
    function = calls[0].get("function") or {}  # LDH
    name = function.get("name")  # LDH
    raw_args = function.get("arguments") or "{}"  # LDH
    if not isinstance(name, str) or not name:  # LDH
        raise ToolCallParseError("missing tool name")  # LDH
    try:
        args = json.loads(raw_args)  # LDH
    except (TypeError, ValueError) as exc:
        raise ToolCallParseError("arguments are not JSON") from exc
    if not isinstance(args, dict):  # LDH
        raise ToolCallParseError("arguments are not an object")  # LDH
    return {"name": name, "args": args}  # LDH


def validate_params(name, args):  # LDH
    schema = TOOL_SCHEMAS.get(name)  # LDH
    if schema is None:  # LDH
        raise UnknownToolError(name)  # LDH
    for key, expected in schema.items():  # LDH
        if key not in args:  # LDH
            raise ParamValidationError(f"missing param: {key}")  # LDH
        if not isinstance(args[key], expected):  # LDH
            raise ParamValidationError(f"bad type for param: {key}")  # LDH
    return args


def dispatch(call):  # LDH
    handler = TOOL_REGISTRY.get(call["name"])  # LDH
    if handler is None:  # LDH
        raise UnknownToolError(call["name"])  # LDH
    return handler(call["args"])  # LDH


def redact_secrets(value):  # LDH
    if isinstance(value, dict):  # LDH
        out = {}
        for key, item in value.items():  # LDH
            if key.lower() in SECRET_KEYS:  # LDH
                out[key] = "[REDACTED]"  # LDH
            else:
                out[key] = redact_secrets(item)
        return out
    if isinstance(value, list):  # LDH
        return [redact_secrets(item) for item in value]  # LDH
    return value


def backoff_delay(attempt, base=0.05, cap=2.0):  # LDH
    delay = base * (2 ** attempt)  # LDH
    return min(delay, cap)


def call_with_retry(handler, args, max_attempts=3, sleep=time.sleep):  # LDH
    last_error = None
    for attempt in range(max_attempts):  # LDH
        try:
            return handler(args)  # LDH
        except TransientToolError as exc:  # LDH
            last_error = exc
            sleep(backoff_delay(attempt))  # LDH
    raise last_error  # LDH


def process_response(response, sleep=time.sleep):  # LDH
    call = parse_tool_call(response)  # LDH
    args = validate_params(call["name"], call["args"])  # LDH
    handler = TOOL_REGISTRY.get(call["name"])  # LDH
    if handler is None:  # LDH
        raise UnknownToolError(call["name"])  # LDH
    output = call_with_retry(handler, args, sleep=sleep)  # LDH
    return redact_secrets(output)  # LDH
