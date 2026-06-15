# Proposal: batch editing (`ue_batch_edit`)

Status: draft spec (not implemented)

## Problem

UEMCP's actor tools are one-actor-at-a-time: `ue_set_actor_property`, `ue_set_actor_transform`, `ue_assign_material`, `ue_destroy_actor`. To change many actors the client must loop, and **each call is a separate remote-execution round trip** (TCP command + log parse). Editing 50 actors is 50 round trips.

Two gaps:

1. **Latency.** N edits should be one editor call, not N.
2. **Relative transforms.** `ue_set_actor_transform` is absolute only. "Nudge every selected actor +100 in Z" or "rotate them all 90 degrees" is not expressible today. That is a genuinely new capability, not just a faster loop.

## Proposed tool

```python
@mcp.tool()
def ue_batch_edit(
    operations: list[dict],
    filter_class: str | None = None,
    name_contains: str | None = None,
    labels: list[str] | None = None,
    limit: int = 500,
    continue_on_error: bool = True,
    dry_run: bool = False,
) -> dict: ...
```

### Selection

Actors are selected by the union of:

- `labels` - explicit outliner labels (exact match), and/or
- `filter_class` + `name_contains` - same semantics as `ue_list_actors`.

If none are given it is an error (refuse to edit "everything" implicitly). `limit` caps the match count; if exceeded the tool errors rather than silently truncating (consistent with the no-silent-caps principle). `dry_run=True` resolves the selection and validates operations but applies nothing, returning the actors that would be touched.

### Operations

`operations` is an ordered list applied to each matched actor:

| op | fields | meaning |
|---|---|---|
| `set_property` | `property`, `value` | `set_editor_property`, with the same list -> Vector/LinearColor coercion as `ue_set_actor_property` |
| `set_transform` | `location?`, `rotation?`, `scale?`, `mode` | `mode: "absolute"` (set) or `"relative"` (add location/rotation, multiply scale) |
| `set_material` | `material_path`, `slot?` | assign to the first mesh component (reuses `build_assign_material` logic) |
| `destroy` | - | delete the actor (applied last regardless of list position) |

### Return

```json
{
  "matched": 12,
  "applied": 12,
  "failed": 0,
  "dry_run": false,
  "results": [
    {"label": "Crate_03", "ops": ["set_property", "set_transform"], "ok": true},
    {"label": "Crate_07", "ok": false, "error": "RuntimeError: ..."}
  ]
}
```

With `continue_on_error=True` a per-actor failure is recorded and the loop continues; with `False` the first failure raises after reporting what was already applied.

## Implementation notes

- One new snippet builder `build_batch_edit(operations, selection, ...)` in `src/uemcp/snippets.py`, returning a single body that:
  1. Collects matched actors with the `ue_list_actors` filter loop (reuse that logic).
  2. Iterates actors, applies ops inside a per-actor `try/except`, collects results.
  3. Returns the summary dict.
- Reuse existing in-editor logic: the property coercion block from `build_set_actor_property` and the mesh-component lookup from `build_assign_material`. Factor those into shared snippet fragments, the way `_FIND_ACTOR` and `_ACTOR_INFO_RETURN` already are.
- Values interpolate via `repr()` (existing convention), so operations arrive as JSON literals safely.
- Tests: add `build_batch_edit` cases to `tests/test_snippets.py` (compile + has-return) covering each op type and both transform modes. No live editor needed.

## Why not "blueprint from description" instead

It is appealing, but it is mostly a **client-side** concern: the model already composes `ue_create_blueprint` + `ue_add_component` + `ue_set_blueprint_default` from a description today, so the server-side gap is small. Batch editing, by contrast, removes round trips and adds relative transforms, which the client genuinely cannot do over the current API. Batch editing is the higher-leverage server addition; a Blueprint-from-description helper can come later as a thin convenience wrapper or an MCP prompt.

## Open questions

- Operation ordering vs `destroy`: force `destroy` last (proposed) or honor list order?
- Should `set_material` cover all slots / all mesh components, not just the first?
- Relative rotation: compose as Euler add (simple) or quaternion (correct under gimbal cases)? Start with Euler add and document the limitation.
- Add a companion `ue_batch_spawn` (spawn N actors from a list) in the same proposal, or keep it separate?
