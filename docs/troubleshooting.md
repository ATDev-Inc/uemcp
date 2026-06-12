# Troubleshooting

Start with `ue_status`. It reports what UEMCP can see and includes a hint when nothing answers.

## "No Unreal Editor instances found"

Checklist, in order of likelihood:

1. **Is the editor actually running with a project open?** The project browser screen does not answer discovery.
2. **Is the Python Editor Script Plugin enabled?** `Edit > Plugins`, search "Python". Restart the editor after enabling.
3. **Is remote execution on?** `Edit > Project Settings`, search "Python", check **Enable Remote Execution**. This is per project, not per engine install. No restart needed for this one, but it does not hurt.
4. **Firewall.** On Windows, the first time the editor binds the multicast socket, Windows Defender asks to allow `UnrealEditor.exe` network access. If that prompt was dismissed, allow it manually: Windows Security > Firewall > Allow an app. The MCP server process (python/uvx) may need the same.
5. **VPN or virtual adapters.** Multicast discovery binds `0.0.0.0` by default, but some VPN clients swallow multicast. Try setting `UEMCP_MULTICAST_BIND` to your loopback or LAN interface IP on both sides (the editor has a matching setting in Project Settings > Python).
6. **Changed defaults.** If the editor's multicast group or port were customized, mirror them with `UEMCP_MULTICAST_GROUP` / `UEMCP_MULTICAST_PORT`.

Quick manual probe from a clone:

```sh
uv run python -c "from uemcp.remote_exec import RemoteExecutionClient; print(RemoteExecutionClient().discover(5.0))"
```

## "Did not connect back to the command endpoint"

Discovery worked, but the editor could not open the TCP connection back to UEMCP. Almost always a firewall blocking inbound TCP to the Python process. If you need a fixed port for a firewall rule, set `UEMCP_COMMAND_PORT=6776` and allow that.

## "Timed out waiting for a result from Unreal"

The command reached the editor but no reply came back within `UEMCP_COMMAND_TIMEOUT` (default 120s).

- A **modal dialog** in the editor blocks the Python session. Dismiss it. Commands run unattended, which suppresses most dialogs, but not all (plugin update prompts, crash reporter).
- Heavy operations (importing a huge FBX, shader compiles triggered by a new material) can legitimately exceed the timeout. Raise `UEMCP_COMMAND_TIMEOUT`.
- The editor may be frozen or compiling shaders at 100% CPU. Check it.

## Wrong editor instance

Multiple projects open: UEMCP picks the first responder. Pin with `--project MyGame` or `UEMCP_PROJECT`. `ue_status` lists everything it can see.

## Tool errors with a Python traceback

That traceback comes from inside the editor and names the exact `unreal` API call that failed. Common ones:

- `No actor found with label '...'`: labels are the World Outliner names, case-sensitive. `ue_list_actors` shows them.
- `Could not load class /Script/...`: typo in the module or class name, or the class lives in a different module (many gameplay classes are in `/Script/Engine`, UMG in `/Script/UMG`).
- `set_editor_property` type errors: the property may expect a struct or enum. Check spelling against the [Unreal Python API](https://docs.unrealengine.com/PythonAPI/), and remember properties are snake_case. Component-level properties need `ue_python`.
- `does it already exist?` when creating assets: Unreal will not overwrite an existing asset of the same name. Pick a new name or delete the old one.

## `ue_screenshot` times out

- The editor viewport must be visible. A minimized editor produces no frames.
- The MCP server must run on the same machine as the editor (it reads the PNG from the Saved/Screenshots folder).
- Very large resolutions can take longer than the 20 second polling window on weak GPUs. Try the default 1280x720 first.

## Output looks stale or the connection dropped

The bridge reconnects automatically once per command. If the editor was closed and reopened, the first tool call after that pays a couple of seconds for rediscovery, then everything resumes. If it still fails twice in a row, you get the discovery error above; fix that and retry.

## Still stuck

Open an issue with the output of `ue_status`, your engine version, OS, and how the server is launched: https://github.com/ATDev-Inc/uemcp/issues
