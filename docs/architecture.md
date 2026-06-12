# Architecture

## The big picture

```
Claude (MCP client)
   |  stdio (MCP protocol)
   v
uemcp server                              src/uemcp/server.py
   |
   |  builds a Python snippet             src/uemcp/snippets.py
   |  wraps it in a result harness        src/uemcp/bridge.py
   |  ships it over the wire              src/uemcp/remote_exec.py
   v
Unreal Editor (Python Editor Script Plugin, remote execution enabled)
```

There is intentionally **no Unreal-side plugin**. UEMCP talks to the remote execution feature that ships inside the engine's own Python plugin. That single decision drives everything else in the design: nothing to compile, no engine version matrix, and the whole test suite can run without Unreal.

## The wire protocol (`remote_exec.py`)

Unreal's Python remote execution uses two channels:

**Discovery (UDP multicast).** Every editor with remote execution enabled joins `239.0.0.1:6766`. Messages are single JSON objects with an envelope of `version: 1`, `magic: "ue_py"`, a `source` node UUID, and a `type`. The client sends a `ping`; editors answer with a `pong` carrying their engine version, project name, and project root.

**Commands (TCP).** Connection setup is inverted from what you might expect: the *client* opens a TCP listener, then multicasts an `open_connection` message telling a specific editor node where to connect back. UEMCP binds port 0 and advertises whatever the OS assigned, so there are no port conflicts. Once connected, each `command` message gets exactly one `command_result` reply:

```json
{"type": "command", "data": {"command": "<python source>", "unattended": true, "exec_mode": "ExecuteFile"}}
{"type": "command_result", "data": {"success": true, "result": "None", "output": [{"type": "Info", "output": "..."}]}}
```

Results can span multiple TCP segments, so `CommandChannel._receive` accumulates bytes and retries JSON parsing until a full object lands. `RemoteExecutionClient` owns discovery, instance selection, and connection lifecycle.

## The harness (`bridge.py`)

`exec_mode: ExecuteFile` gives us back log output, not return values. UEMCP gets structured data out anyway by wrapping every snippet body in a harness before sending it:

```python
import json as _json
import traceback as _tb
import unreal

def __uemcp_main():
    # ... the tool's snippet body, indented, ends with `return <payload>` ...

try:
    _r = __uemcp_main()
    print("__UEMCP_RESULT__" + _json.dumps({"ok": True, "data": _r}, default=str))
except Exception as _e:
    print("__UEMCP_RESULT__" + _json.dumps({"ok": False, "error": ..., "traceback": _tb.format_exc()}, default=str))
```

`parse_result` scans the editor's log output for the last sentinel-prefixed line and decodes it. Failures arrive as real Python tracebacks from inside the editor, which makes debugging a misbehaving tool dramatically less painful than grepping logs.

The bridge also self-heals: if a command fails at the transport level (editor restarted, socket died), it reconnects once and retries before giving up.

## Snippets (`snippets.py`)

Snippet builders are **pure functions from arguments to Python source strings**. Three rules keep them safe and testable:

1. **Interpolate with `repr()`** (`{value!r}`), never raw f-string interpolation. Anything that arrived as JSON (str, int, float, bool, None, list, dict) reprs to a valid Python literal, and quoting/escaping is handled for free.
2. **Prefix in-snippet variables with `_`.** Remote execution shares one Python session inside the editor; underscored names avoid trampling user state.
3. **Raise with actionable messages.** `raise RuntimeError("No actor found with label %r" % _LABEL)` beats letting `None.set_actor_location` produce an AttributeError two lines later.

Because builders are pure, `tests/test_snippets.py` compiles every builder's output (wrapped in the harness) with CPython's `compile()`. CI cannot run Unreal, but it can guarantee that no tool ever ships a snippet with a syntax error.

## Adding a tool, end to end

Say you want `ue_rename_actor`:

1. **Builder** in `snippets.py`:

```python
def build_rename_actor(label: str, new_label: str) -> str:
    return "\n".join([
        f"_LABEL = {label!r}",
        _FIND_ACTOR,
        f"_target.set_actor_label({new_label!r})",
        f'return {{"old": _LABEL, "new": {new_label!r}}}',
    ])
```

2. **Tool** in `server.py`, inside `create_server`:

```python
@mcp.tool()
def ue_rename_actor(label: str, new_label: str) -> dict:
    """Rename an actor's outliner label."""
    return bridge.run_json(snippets.build_rename_actor(label, new_label))
```

The docstring is what Claude reads when deciding whether and how to call the tool. Write it for the model: say what the parameters mean and what conventions apply.

3. **Compile case** in `tests/test_snippets.py`:

```python
("rename_actor", snippets.build_rename_actor, ("Old", "New")),
```

4. **Docs**: add a section to `docs/tools.md`.

5. Smoke-test against a real editor and note the engine version in your PR.

## Testing strategy

| Layer | How it is tested | Needs Unreal? |
|---|---|---|
| Protocol messages | encode/decode round trips, garbage rejection | No |
| TCP command channel | fake editor over `socket.socketpair`, including split-segment framing and dead sockets | No |
| Harness | executed in-process with a stubbed `unreal` module; asserts the sentinel JSON for both success and error paths | No |
| Snippets | every builder compiled via `compile()` | No |
| Tools against a live editor | manual smoke test, documented in PRs | Yes |

A future `tests/live/` suite gated behind an environment variable (pointing at a running editor) is welcome; see [issue tracker](https://github.com/ATDev-Inc/uemcp/issues).
