"""Glue between MCP tools and the remote execution client.

Every tool builds a small Python snippet (the "body"). The bridge wraps that
body in a harness that runs inside Unreal, catches exceptions, and prints a
single sentinel-prefixed JSON line. The bridge then parses that line out of
the editor's log output so tools get structured data back, not log soup.
"""

from __future__ import annotations

import json
import textwrap

from .remote_exec import (
    MODE_EXEC_FILE,
    CommandResult,
    RemoteExecutionClient,
    RemoteExecutionConfig,
    RemoteExecutionError,
)

SENTINEL = "__UEMCP_RESULT__"

_HARNESS_HEADER = """\
import json as _json
import traceback as _tb
import unreal

def __uemcp_main():
"""

_HARNESS_FOOTER = """

try:
    _r = __uemcp_main()
    print("__UEMCP_RESULT__" + _json.dumps({"ok": True, "data": _r}, default=str))
except Exception as _e:
    print("__UEMCP_RESULT__" + _json.dumps({
        "ok": False,
        "error": "%s: %s" % (type(_e).__name__, _e),
        "traceback": _tb.format_exc(),
    }, default=str))
"""


class UnrealToolError(RuntimeError):
    """A tool failed inside the editor; the message carries the UE traceback."""


def wrap_body(body: str) -> str:
    """Wrap a flush-left snippet body into the in-editor harness."""
    indented = textwrap.indent(textwrap.dedent(body).strip("\n"), "    ")
    return _HARNESS_HEADER + indented + _HARNESS_FOOTER


def parse_result(result: CommandResult):
    """Pull the sentinel JSON line out of a command result."""
    for entry in reversed(result.output):
        text = entry.get("output", "")
        index = text.find(SENTINEL)
        if index < 0:
            continue
        payload = json.loads(text[index + len(SENTINEL):])
        if payload.get("ok"):
            return payload.get("data")
        error = payload.get("error", "Unknown error inside Unreal")
        traceback_text = payload.get("traceback", "")
        raise UnrealToolError(f"{error}\n{traceback_text}".rstrip())
    detail = result.output_text() or result.result or "(no output)"
    raise UnrealToolError(
        "Unreal did not return a result payload. Editor output was:\n" + detail
    )


class UnrealBridge:
    """Lazy, self-healing connection to the editor shared by all tools."""

    def __init__(self, config: RemoteExecutionConfig | None = None):
        self.config = config or RemoteExecutionConfig.from_env()
        self.client = RemoteExecutionClient(self.config)

    def ensure_connected(self) -> None:
        if not self.client.is_connected:
            self.client.connect()

    def run_raw(self, code: str, exec_mode: str = MODE_EXEC_FILE) -> CommandResult:
        """Run code in the editor, reconnecting once if the channel went stale."""
        self.ensure_connected()
        try:
            return self.client.run_command(code, exec_mode=exec_mode)
        except RemoteExecutionError:
            # The editor may have restarted since the last call; retry once.
            self.client.close()
            self.client.connect()
            return self.client.run_command(code, exec_mode=exec_mode)

    def run_json(self, body: str):
        """Run a snippet body inside the harness and return its structured result."""
        result = self.run_raw(wrap_body(body))
        if not result.success and not result.output:
            raise UnrealToolError(
                "Unreal rejected the command: " + (result.result or "(no detail)")
            )
        return parse_result(result)

    def close(self) -> None:
        self.client.close()
