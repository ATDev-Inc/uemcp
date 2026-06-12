# Changelog

All notable changes to UEMCP are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [semantic versioning](https://semver.org/).

## [Unreleased]

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
