# UEMCP

[![CI](https://github.com/ATDev-Inc/uemcp/actions/workflows/ci.yml/badge.svg)](https://github.com/ATDev-Inc/uemcp/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/uemcp)](https://pypi.org/project/uemcp/)
[![Python](https://img.shields.io/pypi/pyversions/uemcp)](https://pypi.org/project/uemcp/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Drive Unreal Engine 5 with Claude. Nothing to install inside Unreal.**

UEMCP is an open source [MCP](https://modelcontextprotocol.io) server by [ATDev](https://github.com/ATDev-Inc) that connects Claude (Claude Code, Claude Desktop, or any MCP client) to a live Unreal Engine 5 editor. Spawn actors, build materials, author Blueprints, manage assets, fly the viewport camera, take screenshots, and run arbitrary editor Python, all from a conversation.

## Why this one is different

Most Unreal MCP servers ship a C++ plugin you have to copy into your project and compile. UEMCP speaks Unreal's **built-in Python remote execution protocol** instead: the same multicast discovery and TCP command channel that ships with every copy of the engine. That means:

- **Zero install on the Unreal side.** No plugin to build, no project files to modify, no engine version matrix to chase.
- **Works with vanilla UE 5.0 through 5.6**, including Epic Games Launcher builds.
- **Structured results, not log scraping.** Every tool runs inside an error-capturing harness in the editor and returns clean JSON, with real Python tracebacks when something fails.
- **Self-healing connection.** Restart the editor mid-session and the next tool call reconnects automatically.
- **An escape hatch.** `ue_python` gives Claude the full `unreal` module for anything the 29 dedicated tools do not cover.

## Quickstart

### 1. Set up Unreal (one time, about 30 seconds)

1. Open your project in Unreal Editor.
2. `Edit > Plugins`, search for **Python Editor Script Plugin**, enable it, restart when prompted.
3. `Edit > Project Settings`, search for **Python**, check **Enable Remote Execution**.

That is the entire Unreal-side setup.

### 2. Add the server to Claude

With [uv](https://docs.astral.sh/uv/) installed:

**Claude Code**

```sh
claude mcp add unreal -- uvx uemcp
```

**Claude Desktop** (`claude_desktop_config.json`)

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

**pip, or from a clone of this repo**

```sh
pip install uemcp && uemcp
# or
git clone https://github.com/ATDev-Inc/uemcp && cd uemcp && uv run uemcp
```

More detail, including pinning to one project when several editors are open: [docs/setup.md](docs/setup.md).

### 3. Talk to your editor

> "Spawn a point light 300 units up, make it warm orange at 8000 intensity, then screenshot the viewport."

> "Find every static mesh asset with 'rock' in the name and scatter 20 of them in a rough circle around the origin."

> "Create a BP_Collectible blueprint with a static mesh component and a sphere collision, set its mesh to the gold coin asset."

## Tools

| Group | Tools |
|---|---|
| Editor | `ue_status`, `ue_python`, `ue_console_command`, `ue_project_info` |
| Actors | `ue_list_actors`, `ue_spawn_actor`, `ue_destroy_actor`, `ue_set_actor_transform`, `ue_set_actor_property`, `ue_get_actor` |
| Assets | `ue_search_assets`, `ue_asset_info`, `ue_import_asset`, `ue_create_folder`, `ue_duplicate_asset`, `ue_delete_asset`, `ue_save_all` |
| Materials | `ue_create_material`, `ue_create_material_instance`, `ue_assign_material` |
| Blueprints | `ue_create_blueprint`, `ue_add_component`, `ue_set_blueprint_default` |
| Levels | `ue_open_level`, `ue_new_level` |
| Viewport | `ue_set_camera`, `ue_get_camera`, `ue_focus_actor`, `ue_screenshot` |
| Play | `ue_play`, `ue_stop_play` |

Conventions: project content paths look like `/Game/Props/SM_Chair`, engine classes like `/Script/Engine.PointLight`. Distances are centimeters, rotations are `[roll, pitch, yaw]` in degrees, colors are `[r, g, b]` in 0..1.

Full parameter and return documentation for every tool: [docs/tools.md](docs/tools.md).

## How it works

```
Claude (MCP client)
   |  stdio (MCP)
   v
uemcp server (this package, plain Python)
   |  UDP multicast 239.0.0.1:6766  -> discovery ping/pong
   |  TCP command channel           -> JSON commands and results
   v
Unreal Editor (built-in Python remote execution)
```

Each tool builds a small Python snippet, wraps it in a harness that catches exceptions, runs it in the editor, and parses a sentinel-prefixed JSON line back out of the log output. The snippet builders are pure functions, so CI compiles every one of them without needing Unreal installed.

## Configuration

Everything works with defaults when the editor and server are on the same machine. Override with environment variables when needed:

| Variable | Default | Purpose |
|---|---|---|
| `UEMCP_PROJECT` | (first found) | Prefer a specific project when several editors are open |
| `UEMCP_MULTICAST_GROUP` | `239.0.0.1` | Discovery multicast group |
| `UEMCP_MULTICAST_PORT` | `6766` | Discovery port |
| `UEMCP_COMMAND_HOST` | `127.0.0.1` | Host the editor connects back to |
| `UEMCP_COMMAND_TIMEOUT` | `120` | Per-command timeout in seconds |
| `UEMCP_DISCOVERY_TIMEOUT` | `2` | Discovery wait in seconds |

`uemcp --project MyGame` is shorthand for `UEMCP_PROJECT=MyGame`.

## Security notes

UEMCP executes Python inside your editor process, by design. Treat it like giving Claude the editor's Python console:

- The remote execution protocol has **no authentication**. Keep the defaults (localhost command channel, multicast TTL 0) unless you fully control the network.
- Tools can modify and delete project content. Use source control on your project. You should be doing that anyway.
- Review what an agent did with `ue_save_all` withheld if you want a manual checkpoint before anything hits disk.

## Documentation

| Doc | What it covers |
|---|---|
| [docs/setup.md](docs/setup.md) | Detailed Unreal and client setup, multiple editors, remote machines |
| [docs/tools.md](docs/tools.md) | Full reference for all 31 tools: parameters, returns, examples |
| [docs/architecture.md](docs/architecture.md) | The wire protocol, the snippet harness, and how to add a tool |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Connection problems, firewalls, common tool errors |
| [docs/cookbook.md](docs/cookbook.md) | Prompt recipes: lighting rigs, greyboxing, asset audits |

## Development

```sh
git clone https://github.com/ATDev-Inc/uemcp
cd uemcp
uv sync
uv run pytest
uv run ruff check .
```

The test suite runs entirely without Unreal: protocol tests talk to a fake editor over real sockets, and every in-editor snippet is compile-checked.

## Roadmap

- Sequencer tools (create level sequences, bind actors, render movies)
- Niagara system spawning and parameter control
- Landscape sculpting primitives
- True PIE (play-in-editor) control with input injection
- Asset thumbnails as MCP resources

## Community

- **Contributing**: [CONTRIBUTING.md](CONTRIBUTING.md) has a contribution ladder from docs fixes up to new tools. If you keep reaching for the same `ue_python` snippet, that is a tool waiting to be born, and a working snippet pasted into an issue is 80% of the work.
- **Bugs**: use the [issue templates](https://github.com/ATDev-Inc/uemcp/issues/new/choose). The in-editor traceback from the tool error is the most useful thing you can include.
- **Security**: see [SECURITY.md](SECURITY.md). Report vulnerabilities privately, not in public issues.
- **Releases**: [CHANGELOG.md](CHANGELOG.md) and [GitHub releases](https://github.com/ATDev-Inc/uemcp/releases).
- **Conduct**: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## License

[MIT](LICENSE). Copyright (c) 2026 ATDev.
