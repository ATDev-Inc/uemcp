# UEMCP

Open source MCP server that lets Claude drive a live Unreal Engine 5 editor with no plugin to compile. It speaks UE's built-in Python remote execution protocol (UDP multicast discovery + TCP command channel), builds Python snippets, runs them in the editor's shared Python session, and parses structured JSON back out.

## Key rules
- **Snippet interpolation MUST use `repr()` (`{value!r}`), never raw f-string interpolation.** This is the security boundary that keeps tool arguments from escaping into the editor's Python session as executable code. Reviewers reject raw interpolation.
- **Prefix every in-snippet variable with `_`** (e.g. `_target`, `_LABEL`). Remote execution shares ONE Python session inside the editor; unprefixed names trample user state.
- **Snippet builders in `snippets.py` are pure functions** (args -> Python source string): no I/O, no Unreal import. `tests/test_snippets.py` `compile()`s every builder, so any new builder needs a compile case there or CI cannot catch its syntax errors.
- **Reject non-finite floats** for any numeric snippet input: route vectors/rotations/coords through `_finite` / `_vector` / `_rotator`. `repr(inf)`/`repr(nan)` emit bare `inf`/`nan` tokens that `NameError` inside the editor.
- **Never add an Unreal-side plugin or non-stdlib runtime dependency.** "Nothing to install inside Unreal" is the whole premise; the only runtime dep is `mcp`. Asset providers in `assets.py` are stdlib-only (`urllib`/`zipfile`, with zip-bomb guards) and unit-tested with the HTTP layer monkeypatched.
- **A tool docstring is the model-facing spec.** Claude reads it to decide whether/how to call the tool; state what params mean and which conventions apply (see below).
- **Raise `RuntimeError` with actionable messages** ("No actor found with label X") instead of letting `None` flow into a confusing `AttributeError`. Wrap newer engine APIs in try/except with a fallback (support vanilla UE 5.0-5.7).
- **Adding a tool touches 5 places, keep them in sync:** builder in `src/uemcp/snippets.py`, registration in `src/uemcp/server.py`, compile case in `tests/test_snippets.py`, reference entry in `docs/tools.md`, and a real-editor smoke test naming the engine version in the PR.

## Stack & layout
- Python 3.10+, `mcp` / FastMCP. Built with `uv` + hatchling.
- `src/uemcp/server.py` - FastMCP tool definitions (the `ue_*` tools).
- `src/uemcp/snippets.py` - pure builders for in-editor Python bodies.
- `src/uemcp/bridge.py` - result harness (sentinel-prefixed JSON) + self-healing transport.
- `src/uemcp/remote_exec.py` - wire protocol: UDP multicast discovery, inverted TCP connection, split-segment reassembly.
- `src/uemcp/assets.py` - `AssetProvider` / generative providers; `render.py` - headless renders.
- `tests/` - protocol, bridge, snippets, assets, render (all run without Unreal). `docs/architecture.md` explains the layers and the add-a-tool walkthrough.

## Build, run, test
- Setup: `uv sync`
- Test: `uv run pytest` (CI uses `-v`; entire suite runs without Unreal via a fake editor over real sockets and `compile()`-checked snippets).
- Lint: `uv run ruff check .`
- Run the server: `uv run uemcp` (or `uvx uemcp`). Entry point is `uemcp.server:main`.
- Live check against a real editor: `uv run python -c "from uemcp.remote_exec import RemoteExecutionClient; print(RemoteExecutionClient().discover())"`

## Conventions
- Format/lint with ruff: line length 100, rules `E,F,W,I,UP,B`, target py310. `uv run ruff check .` must pass on Ubuntu and Windows.
- Tool arg conventions (state these in docstrings): content paths `/Game/Props/SM_Chair`, engine classes `/Script/Engine.PointLight`, distances in centimeters, rotations `[roll, pitch, yaw]` in degrees, colors `[r, g, b]` in 0..1.
- No em dashes in docs, comments, or commit messages (house style).
- Release: bump the version in BOTH `pyproject.toml` and `src/uemcp/__init__.py`, then move `[Unreleased]` notes in `CHANGELOG.md` and tag `vX.Y.Z`.

## When to ask
- Adding/renaming a `ue_*` tool or changing its parameters or return shape (public MCP surface Claude relies on).
- Anything that would require an Unreal-side plugin, a new runtime dependency, or code that only works on some engine versions.
- Touching the security boundary: interpolation, the escape-hatch `ue_python` tool, or the no-auth network defaults (localhost command channel, multicast TTL 0). Do not widen network exposure without explicit sign-off.
- Ambiguous spec, or changes to the release/publish workflow.
