# Contributing to UEMCP

Thanks for helping out. The bar for a good PR here is simple: it should work against a vanilla Unreal 5.x editor with only the built-in Python plugin enabled.

## Setup

```sh
uv sync
uv run pytest
uv run ruff check .
```

Tests run without Unreal. If your change touches in-editor behavior, please also smoke-test it against a real editor and say which engine version you used in the PR description.

## Adding a tool

1. Add a builder to `src/uemcp/snippets.py`. Builders are pure functions that return a flush-left Python snippet body. The body runs inside a harness function in the editor, so use `return` to hand back JSON-serializable data and raise exceptions for failures.
2. Register the tool in `src/uemcp/server.py` with a clear docstring (it becomes the tool description Claude reads).
3. Add a compile case for the builder in `tests/test_snippets.py`.

Guidelines:

- Prefix in-snippet variables with `_` to avoid colliding with user state in the editor's Python session.
- Interpolate values with `repr()` (`{value!r}`), never with raw string formatting.
- Raise `RuntimeError` with actionable messages ("No actor found with label X") rather than letting `None` flow into a confusing attribute error.
- Keep tools editor-version tolerant: wrap newer-API calls in try/except with a fallback where reasonable.

## Style

- `ruff check .` must pass.
- No em dashes in docs or comments.
