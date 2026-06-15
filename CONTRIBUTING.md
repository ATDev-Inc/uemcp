# Contributing to UEMCP

Thanks for helping out. The bar for a good contribution is simple: it should work against a vanilla Unreal 5.x editor with only the built-in Python plugin enabled, because "nothing to install inside Unreal" is the whole point of this project.

## Getting set up

```sh
git clone https://github.com/ATDev-Inc/uemcp
cd uemcp
uv sync
uv run pytest        # 114 tests, no Unreal needed
uv run ruff check .
```

To run against a real editor, open any UE5 project with the Python Editor Script Plugin enabled and remote execution on (see [docs/setup.md](docs/setup.md)), then:

```sh
uv run python -c "from uemcp.remote_exec import RemoteExecutionClient; print(RemoteExecutionClient().discover())"
```

Read [docs/architecture.md](docs/architecture.md) before touching code. It is short and explains the three layers (protocol client, harness/bridge, snippets) and walks through adding a tool end to end.

## Ways to contribute, easiest first

1. **Docs fixes.** Anything in `docs/` or the README that confused you probably confuses others.
2. **Cookbook recipes.** A prompt that produced a great result belongs in [docs/cookbook.md](docs/cookbook.md).
3. **Engine version reports.** Tested UEMCP against an engine version not listed in recent PRs? An issue saying "all good on 5.x.y" (or what broke) is genuinely useful.
4. **New tools.** If you keep reaching for the same `ue_python` snippet, that is a tool waiting to be born. A working snippet pasted into a feature request is 80% of the work.
5. **Asset providers.** The `AssetProvider` and `GenerativeProvider` interfaces in `src/uemcp/assets.py` are a clean place to add an asset catalog (like Sketchfab) or a generator (like Meshy). A provider only has to search or generate and return a local file; the existing import path takes it from there. Keep it stdlib-only, and unit-test it with the HTTP layer monkeypatched, the way `tests/test_assets.py` does.
6. **Roadmap items.** Sequencer, Niagara, landscape, true PIE control, asset thumbnails as resources. Comment on the tracking issue before starting anything large.

## Adding a tool

The full walkthrough with code is in [docs/architecture.md](docs/architecture.md#adding-a-tool-end-to-end). The short version:

1. Add a pure builder function to `src/uemcp/snippets.py` that returns the in-editor Python body.
2. Register the tool in `src/uemcp/server.py`. The docstring is what Claude reads; write it for the model.
3. Add a compile case to `tests/test_snippets.py`.
4. Document it in `docs/tools.md`.
5. Smoke-test against a real editor and name the engine version in your PR.

Snippet rules (enforced in review):

- Interpolate values with `repr()` (`{value!r}`), never raw f-string interpolation. This is also a security boundary: it is what prevents tool arguments from escaping into the editor's Python session as code.
- Prefix in-snippet variables with `_` so they cannot trample user state in the editor's shared Python session.
- Raise `RuntimeError` with actionable messages ("No actor found with label X") instead of letting `None` flow into a confusing AttributeError.
- Be version-tolerant: wrap newer engine APIs in try/except with a fallback where reasonable.

## Pull requests

- Keep PRs focused; one tool or one fix per PR reviews fastest.
- `uv run pytest` and `uv run ruff check .` must pass (CI runs both on Ubuntu and Windows).
- Fill in the PR template, including the smoke-test note.
- No em dashes in docs or comments (house style).

## Reporting bugs

Use the issue template. The single most useful thing you can include is the tool error text: UEMCP errors carry the Python traceback from inside the editor, which usually names the exact failing `unreal` call.

For security reports, see [SECURITY.md](SECURITY.md). Please do not open public issues for vulnerabilities.

## Release process (maintainers)

1. Update the version in `pyproject.toml` and `src/uemcp/__init__.py`.
2. Move the `[Unreleased]` notes in `CHANGELOG.md` under the new version with today's date.
3. Commit, tag `vX.Y.Z`, push the tag.
4. Create a GitHub release from the tag. The `Release` workflow builds and publishes to PyPI via trusted publishing.

## Code of conduct

Be kind. The long version: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
