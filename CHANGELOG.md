# Changelog

All notable changes to UEMCP are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [semantic versioning](https://semver.org/).

## [Unreleased]

### Added

- Asset-library providers: `ue_search_sketchfab` and `ue_import_sketchfab` find and import downloadable Sketchfab models (search is public; download needs `SKETCHFAB_API_TOKEN`), plus `ue_asset_providers` to report which providers have credentials configured. Providers share a dependency-free interface (`src/uemcp/assets.py`) that further providers plug into.
- AI generation via Meshy: `ue_generate_model` starts a text-to-3D task, `ue_generation_status` polls it, and `ue_import_generated` imports the finished model (needs `MESHY_API_KEY`).
- `unreal_workflow_strategy` MCP prompt that guides the orient, place relative to the scene, then screenshot to verify loop.
- Movie Render Queue: `ue_render_sequence` renders a Level Sequence to an image sequence (`png`/`jpg`/`bmp`/`exr`), `prores` video, or `mp4` (renders frames then runs the project's command-line ffmpeg encoder). In-editor mode builds the Movie Pipeline config from the parameters and blocks until the render finishes; headless mode renders in a separate offscreen `UnrealEditor-Cmd` process, auto-authoring a config preset from the parameters when no `config_path` is given (`UEMCP_EDITOR_CMD` sets the executable). Needs the Movie Render Queue plugin enabled.
- `ue_batch_edit` applies an ordered list of operations (set_property, set_transform, set_material, destroy) to many actors selected by label or filter in a single editor round trip. Supports relative transforms (add to location/rotation, multiply scale), a dry-run mode, a match limit, and per-actor error collection.
- `ue_release_mouse` frees the cursor from a play session without stopping it: play mode can capture and lock the mouse to the viewport, and the built-in escapes (Esc, Shift+F1) are keyboard-only, which strands mouse-only users. Shows the cursor and switches the player controller to game-and-UI input with the viewport lock disabled. Handles the UE 5.7 rename of `WidgetBlueprintLibrary` to `WidgetLibrary`.

### Changed

- Discovery now retries (`UEMCP_DISCOVERY_ATTEMPTS`, default 3), so a single dropped multicast round-trip no longer fails a connect.
- Verified support through Unreal Engine 5.7.
- Screenshot wait raised to 30s to tolerate a cold first capture.

### Fixed

- `ue_stop_play` failed on UE 5.7 with `AttributeError: editor_request_end_play_map`: the entry point was renamed across engine releases. The snippet now tries `editor_request_end_play` (5.7), then `editor_request_end_play_map`, then falls back to `EditorLevelLibrary.editor_end_play`. This tool doubles as the keyboard-free escape from a play session that has captured the mouse, so its failure was an accessibility regression, not just an API break.

### Security

- Asset downloads are restricted to https (blocks `file://` and SSRF via URLs that arrive in third-party API responses), zip extraction is capped by size and entry count (zip-bomb guard), partial downloads are removed on failure, and upstream HTTP error bodies are no longer echoed back to the client.
- `ue_render_sequence` validates its `sequence_path`, `config_path`, and `map_path` arguments against a `/Game/...` content-path shape before building the headless `UnrealEditor-Cmd` command line. Unreal rebuilds and re-tokenizes its command line on whitespace, so this prevents a crafted path from injecting extra editor switches.
- Snippet builders reject non-finite numbers (`inf`/`nan`) in vector and rotation inputs with a clear error instead of emitting bare `inf`/`nan` tokens that would raise `NameError` inside the editor.
- CI/release workflows hardened: GitHub Actions pinned to commit SHAs, `GITHUB_TOKEN` scoped to least privilege (`contents: read`), checkout credential persistence disabled, and a Dependabot config added to keep actions and dependencies current.

## [0.1.0] - 2026-06-12

Initial release.

### Added

- MCP server driving a live Unreal Engine 5 editor over the engine's built-in Python remote execution protocol. No Unreal-side plugin required.
- 31 tools: editor status and project info, arbitrary Python execution, console commands, actor lifecycle (list, spawn, destroy, transform, properties, inspect), asset management (search, info, import, folders, duplicate, delete, save), constant-based material creation, material instances, material assignment, Blueprint creation with components and class defaults, level open/new, viewport camera control, actor focus, viewport screenshots returned as images, and simulate start/stop.
- Self-healing connection: automatic rediscovery and reconnect when the editor restarts.
- In-editor harness that returns structured JSON with real Python tracebacks on failure.
- Configuration via environment variables and a `--project` flag for multi-editor setups.
- Test suite (87 tests) that runs without Unreal: socket-level protocol tests against a fake editor and compile checks for every in-editor snippet.
- CI on Ubuntu and Windows, Python 3.10 and 3.13.

[Unreleased]: https://github.com/ATDev-Inc/uemcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ATDev-Inc/uemcp/releases/tag/v0.1.0
