# Setup guide

## Requirements

- Unreal Engine 5.0 through 5.7 (Epic Games Launcher or source builds both work)
- Python 3.10+ on the machine running the MCP server
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Unreal side

One-time, per project:

1. Open your project in Unreal Editor.
2. `Edit > Plugins`, search **Python Editor Script Plugin**, check **Enabled**, restart the editor when prompted.
3. `Edit > Project Settings`, search **Python** (under Plugins), check **Enable Remote Execution**.

Defaults you do not need to touch (but can): multicast group `239.0.0.1:6766`, multicast bind address `0.0.0.0`. These appear in the same Project Settings section.

> **On a machine with a VPN or virtual adapters (NordVPN, Tailscale, VirtualBox, Hyper-V, WSL; common on Windows):** discovery can silently fail because the multicast ping leaves on the wrong interface. Keep everything on loopback. Recent UE versions already default the **Multicast Bind Address** to `127.0.0.1`; match it on the server side by setting `UEMCP_MULTICAST_BIND=127.0.0.1`. See [troubleshooting](troubleshooting.md) for how to check which interface the editor actually bound.

To verify: the editor gives no visible sign that remote execution is on; it just silently joins the multicast group. The easiest check is to ask Claude for `ue_status` once the client is configured. To probe directly from a clone of this repo:

```sh
uv run python -c "from uemcp.remote_exec import RemoteExecutionClient; print(RemoteExecutionClient().discover())"
```

You should see your project listed.

## Client side

### Claude Code

```sh
claude mcp add unreal -- uvx uemcp
```

### Claude Desktop

Add to `claude_desktop_config.json` (Settings > Developer > Edit Config):

```json
{
  "mcpServers": {
    "unreal": {
      "command": "uvx",
      "args": ["uemcp"]
    }
  }
}
```

### Any other MCP client

UEMCP is a standard stdio MCP server. Point your client at the `uemcp` command. If you prefer pip over uv:

```sh
pip install uemcp
uemcp
```

### From a clone

```sh
git clone https://github.com/ATDev-Inc/uemcp
cd uemcp
uv sync
uv run uemcp
```

## Multiple editors open at once

UEMCP connects to the first editor that answers discovery. To pin it to one project:

```sh
uvx uemcp --project MyGame
```

or set `UEMCP_PROJECT=MyGame` in the MCP server's `env` block. The match is against the project name (the `.uproject` file name without extension), case-insensitive.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `UEMCP_PROJECT` | (first found) | Prefer a specific project |
| `UEMCP_MULTICAST_GROUP` | `239.0.0.1` | Must match the editor's Python settings |
| `UEMCP_MULTICAST_PORT` | `6766` | Must match the editor's Python settings |
| `UEMCP_MULTICAST_BIND` | `0.0.0.0` | Interface to bind for discovery; set to `127.0.0.1` to match an editor bound to loopback (see [troubleshooting](troubleshooting.md)) |
| `UEMCP_COMMAND_HOST` | `127.0.0.1` | Host the editor connects back to for commands |
| `UEMCP_COMMAND_PORT` | `0` (auto) | Fixed command port if you need one for firewall rules |
| `UEMCP_COMMAND_TIMEOUT` | `120` | Seconds to wait for a command result |
| `UEMCP_DISCOVERY_TIMEOUT` | `2` | Seconds to wait for editors to answer a ping |
| `UEMCP_DISCOVERY_ATTEMPTS` | `3` | How many discovery round-trips to try before giving up |

## Editor and server on different machines

Possible but not the default, because the protocol is unauthenticated (see [Security notes](../README.md#security-notes)):

1. Both machines must be on the same multicast-capable network segment.
2. Set `UEMCP_COMMAND_HOST` to an IP of the server machine that the editor machine can reach (the editor opens a TCP connection back to the server).
3. Allow inbound TCP to that host/port on the server machine, and outbound from the editor machine.
4. In the editor's Project Settings, the multicast TTL may need to be raised above 0 for packets to cross a switch.

Note that `ue_screenshot` reads the image file from disk and therefore only works when the server and editor share a filesystem.
