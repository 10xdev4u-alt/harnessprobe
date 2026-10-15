import json

import pytest

import sample_harness as h


def weather_response(args=None):
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "arguments": json.dumps(args or {"city": "Lyon"}),
                            },
                        }
                    ],
                }
            }
        ]
    }


def email_response():
    return {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "function": {
                                "name": "send_email",
                                "arguments": json.dumps({"to": "a@example.com"}),
                            }
                        }
                    ]
                }
            }
        ]
    }


def test_process_response_weather_redacts_api_key():
    result = h.process_response(weather_response(), sleep=lambda s: None)
    assert result == {
        "city": "Lyon",
        "units": "metric",
        "temp_c": 21,
        "api_key": "[REDACTED]",
    }


def test_process_response_email_redacts_token():
    result = h.process_response(email_response(), sleep=lambda s: None)
    assert result == {
        "to": "a@example.com",
        "status": "queued",
        "token": "[REDACTED]",
    }


def test_parse_missing_choices():
    with pytest.raises(h.ToolCallParseError):
        h.parse_tool_call({"choices": []})


def test_parse_no_tool_calls():
    with pytest.raises(h.ToolCallParseError):
        h.parse_tool_call({"choices": [{"message": {}}]})


def test_parse_arguments_not_json():
    response = weather_response()
    response["choices"][0]["message"]["tool_calls"][0]["function"][
        "arguments"
    ] = "{not json"
    with pytest.raises(h.ToolCallParseError):
        h.parse_tool_call(response)


def test_parse_arguments_not_object():
    response = weather_response()
    response["choices"][0]["message"]["tool_calls"][0]["function"][
        "arguments"
    ] = "[1, 2]"
    with pytest.raises(h.ToolCallParseError):
        h.parse_tool_call(response)


def test_validate_missing_param():
    with pytest.raises(h.ParamValidationError):
        h.validate_params("get_weather", {})


def test_validate_bad_type():
    with pytest.raises(h.ParamValidationError):
        h.validate_params("get_weather", {"city": 3})


def test_unknown_tool_validation():
    with pytest.raises(h.UnknownToolError):
        h.validate_params("delete_everything", {})


def test_dispatch_unknown_tool():
    with pytest.raises(h.UnknownToolError):
        h.dispatch({"name": "delete_everything", "args": {}})


def test_retry_succeeds_after_transient_failures():
    sleeps = []

    def flaky(args):
        if len(sleeps) < 2:
            raise h.TransientToolError("boom")
        return {"ok": True}

    result = h.call_with_retry(flaky, {"x": 1}, sleep=sleeps.append)
    assert result == {"ok": True}
    assert sleeps == [0.05, 0.1]


def test_retry_exhausts_attempts():
    sleeps = []

    def always_fails(args):
        raise h.TransientToolError("boom")

    with pytest.raises(h.TransientToolError):
        h.call_with_retry(always_fails, {}, sleep=sleeps.append)
    assert sleeps == [0.05, 0.1, 0.2]


def test_backoff_caps_at_cap():
    assert h.backoff_delay(0) == 0.05
    assert h.backoff_delay(1) == 0.1
    assert h.backoff_delay(10) == 2.0


def test_redact_nested_structures():
    payload = {
        "outer": {"api_key": "sk-x", "inner": [{"token": "t", "keep": 1}]},
        "list": ["plain", {"password": "p", "secret": "s"}],
    }
    assert h.redact_secrets(payload) == {
        "outer": {"api_key": "[REDACTED]", "inner": [{"token": "[REDACTED]", "keep": 1}]},
        "list": ["plain", {"password": "[REDACTED]", "secret": "[REDACTED]"}],
    }


def test_redact_scalar_passthrough():
    assert h.redact_secrets("plain") == "plain"
    assert h.redact_secrets(7) == 7
