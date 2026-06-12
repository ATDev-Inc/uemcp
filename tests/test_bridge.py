"""Result parsing: sentinel extraction, error propagation, missing payloads."""

import json

import pytest

from uemcp.bridge import SENTINEL, UnrealToolError, parse_result, wrap_body
from uemcp.remote_exec import CommandResult


def _result_with_output(*lines: str) -> CommandResult:
    return CommandResult(
        success=True,
        output=[{"type": "Info", "output": line} for line in lines],
    )


def test_parse_ok_payload():
    payload = SENTINEL + json.dumps({"ok": True, "data": {"count": 3}})
    result = _result_with_output("LogTemp: something unrelated", payload)
    assert parse_result(result) == {"count": 3}


def test_parse_uses_last_sentinel_line():
    old = SENTINEL + json.dumps({"ok": True, "data": "old"})
    new = SENTINEL + json.dumps({"ok": True, "data": "new"})
    assert parse_result(_result_with_output(old, new)) == "new"


def test_parse_sentinel_with_log_prefix():
    payload = "LogPython: " + SENTINEL + json.dumps({"ok": True, "data": [1, 2]})
    assert parse_result(_result_with_output(payload)) == [1, 2]


def test_parse_error_payload_raises_with_traceback():
    payload = SENTINEL + json.dumps(
        {"ok": False, "error": "RuntimeError: no actor", "traceback": "Traceback ..."}
    )
    with pytest.raises(UnrealToolError, match="no actor"):
        parse_result(_result_with_output(payload))


def test_parse_missing_sentinel_raises_with_editor_output():
    with pytest.raises(UnrealToolError, match="SyntaxError"):
        parse_result(_result_with_output("LogPython: Error: SyntaxError: bad"))


def test_executed_harness_emits_ok_payload(capsys):
    code = wrap_body("return {'value': 41 + 1}")
    # The harness imports unreal; stub it so the wrapped code runs here.
    import sys
    import types

    sys.modules.setdefault("unreal", types.ModuleType("unreal"))
    try:
        exec(compile(code, "<harness>", "exec"), {})
    finally:
        sys.modules.pop("unreal", None)
    out = capsys.readouterr().out
    payload = json.loads(out.split(SENTINEL, 1)[1])
    assert payload == {"ok": True, "data": {"value": 42}}


def test_executed_harness_emits_error_payload(capsys):
    code = wrap_body("raise ValueError('boom')")
    import sys
    import types

    sys.modules.setdefault("unreal", types.ModuleType("unreal"))
    try:
        exec(compile(code, "<harness>", "exec"), {})
    finally:
        sys.modules.pop("unreal", None)
    out = capsys.readouterr().out
    payload = json.loads(out.split(SENTINEL, 1)[1])
    assert payload["ok"] is False
    assert "ValueError: boom" in payload["error"]
    assert "Traceback" in payload["traceback"]
