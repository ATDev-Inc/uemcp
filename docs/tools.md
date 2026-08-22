# Tool reference

Every UEMCP tool, with parameters, return shapes, and examples.

**Shared conventions**

- Content paths: `/Game/Folder/AssetName` (no extension, no `.AssetName` suffix needed).
- Engine classes: `/Script/ModuleName.ClassName`, for example `/Script/Engine.PointLight`.
- Locations are `[x, y, z]` in centimeters. Rotations are `[roll, pitch, yaw]` in degrees. Colors are `[r, g, b]` (and sometimes `[r, g, b, a]`) in the 0..1 range.
- Actors are addressed by their **outliner label** (the name you see in the World Outliner), which is not always the same as the internal object name.
- On failure, tools raise with the actual Python traceback from inside the editor, so you can see exactly which `unreal` API call rejected what.

---

## Editor

### `ue_status`

Discover running editor instances and report connection state. Call this first when anything else fails.

| Param | Type | Default | Notes |
|---|---|---|---|
| (none) | | | |

Returns `{connected, connected_to, instances: [{node_id, project, engine_version, machine}], hint}`. `hint` is non-null when no editors were found and explains the Unreal-side setup.

### `ue_python`

Run arbitrary Python inside the editor with full `unreal` module access. The escape hatch for everything not covered by a dedicated tool.

| Param | Type | Default | Notes |
|---|---|---|---|
| `code` | str | required | Multi-line scripts are fine. Use `print()` for output you want back. |

Returns `{success, output, result}` where `output` is everything the script logged.

### `ue_console_command`

Execute an Unreal console command.

| Param | Type | Default | Notes |
|---|---|---|---|
| `command` | str | required | For example `stat fps`, `r.ScreenPercentage 50`, `slomo 0.5` |

### `ue_project_info`

No parameters. Returns `{engine_version, project_file, project_dir, current_level}`.

---

## Actors

### `ue_list_actors`

| Param | Type | Default | Notes |
|---|---|---|---|
| `filter_class` | str | None | Substring match on class name, e.g. `Light` matches PointLight and SpotLight |
| `name_contains` | str | None | Substring match on outliner label, case-insensitive |
| `limit` | int | 100 | |

Returns `{count, actors: [{label, name, class, location}]}`.

### `ue_spawn_actor`

| Param | Type | Default | Notes |
|---|---|---|---|
| `class_path` | str | required | `/Script/Engine.PointLight` or an asset like `/Game/Props/SM_Chair` |
| `location` | [float, float, float] | [0,0,0] | |
| `rotation` | [float, float, float] | [0,0,0] | [roll, pitch, yaw] degrees |
| `scale` | [float, float, float] | None | |
| `label` | str | None | Outliner label to assign |

Returns the spawned actor's `{label, name, class, location, rotation, scale}`.

Spawning from a StaticMesh asset path creates a StaticMeshActor with that mesh assigned. Useful engine classes: `PointLight`, `SpotLight`, `DirectionalLight`, `RectLight`, `SkyLight`, `ExponentialHeightFog`, `PlayerStart`, `CameraActor`, `TriggerBox`.

### `ue_destroy_actor`

| Param | Type | Default |
|---|---|---|
| `label` | str | required |

### `ue_set_actor_transform`

| Param | Type | Default | Notes |
|---|---|---|---|
| `label` | str | required | |
| `location` | [float x3] | None | Omitted parts are left unchanged |
| `rotation` | [float x3] | None | |
| `scale` | [float x3] | None | |

Returns the actor's full transform after the change.

### `ue_set_actor_property`

Set any editor property on an actor. Property names are snake_case as in the Unreal Python API (`intensity`, `light_color`, `mobility`).

| Param | Type | Default | Notes |
|---|---|---|---|
| `label` | str | required | |
| `property_name` | str | required | snake_case |
| `value` | any | required | Lists of 3 or 4 numbers are coerced to Vector or LinearColor when the property needs one |

Note: many interesting properties live on a component, not the actor. For those, use `ue_python`, for example `actor.light_component.set_intensity(5000)`.

### `ue_get_actor`

| Param | Type | Default |
|---|---|---|
| `label` | str | required |

Returns transform, class, and the full component list `[{name, class}]`.

### `ue_batch_edit`

| Param | Type | Default |
|---|---|---|
| `operations` | list[dict] | required |
| `filter_class` | str | none |
| `name_contains` | str | none |
| `labels` | list[str] | none |
| `limit` | int | 500 |
| `continue_on_error` | bool | true |
| `dry_run` | bool | false |

Applies an ordered list of operations to every matched actor in a single editor round trip, instead of one tool call per actor. Select actors by `labels` (exact match) and/or `filter_class` + `name_contains` (same semantics as `ue_list_actors`); at least one selector is required, so it never edits the whole level by accident. If the match count exceeds `limit` the call errors rather than truncating.

Each entry in `operations` is a dict keyed by `op`:

| op | fields | meaning |
|---|---|---|
| `set_property` | `property`, `value` | `set_editor_property`, with the same list to Vector/LinearColor coercion as `ue_set_actor_property` |
| `set_transform` | `location?`, `rotation?`, `scale?`, `mode` | `mode: "absolute"` sets, `"relative"` adds to location/rotation and multiplies scale |
| `set_material` | `material_path`, `slot?` | assign to the actor's first mesh component |
| `destroy` | - | delete the actor (always applied last) |

`dry_run: true` resolves the selection and returns the actors that would be touched without changing anything. Relative transforms are the headline capability here: "nudge every selected actor +100 in Z" or "rotate them all 90 degrees" is not expressible through the per-actor tools. Returns `{matched, applied, failed, dry_run, results}`, where `results` is per-actor `{label, ops, ok, error?}`.

Relative rotation composes as a Euler add, which is fine for axis-aligned nudges but can behave unexpectedly near gimbal cases; set an absolute rotation when you need exactness.

---

## Assets

### `ue_search_assets`

| Param | Type | Default | Notes |
|---|---|---|---|
| `root` | str | `/Game` | Folder to search recursively. Use `/Engine` for engine content |
| `query` | str | None | Case-insensitive substring on asset name |
| `class_filter` | str | None | Exact class name: `StaticMesh`, `Material`, `Blueprint`, `World`, `Texture2D` |
| `limit` | int | 50 | |

Returns `{count, assets: [{path, name, class}]}`.

### `ue_asset_info`

| Param | Type | Default |
|---|---|---|
| `path` | str | required |

Returns `{path, name, class}` plus `num_lods` and `materials` for static meshes and `generated_class` for blueprints.

### `ue_import_asset`

| Param | Type | Default | Notes |
|---|---|---|---|
| `file_path` | str | required | Absolute path on the editor's machine: FBX, OBJ, PNG, TGA, WAV, ... |
| `destination` | str | `/Game/Imported` | Content folder to import into |

Returns `{imported: [object paths]}`. Imports run in automated mode with default import settings.

### `ue_create_folder` / `ue_duplicate_asset` / `ue_delete_asset`

Content-browser folder creation, asset duplication, and deletion. `ue_delete_asset` fails (on purpose) when the asset is still referenced by something else.

### `ue_save_all`

Saves all dirty packages: the open level plus every modified asset. UEMCP tools save the assets they create, but level edits (spawned actors, transforms) are only persisted after a save.

---

## Asset libraries

Pull assets from external catalogs and import them with the same path as `ue_import_asset`. Providers live in `src/uemcp/assets.py` behind a small `AssetProvider` interface; Sketchfab is the first one.

### `ue_asset_providers`

List the available providers and whether each one's download credentials are set.

| Param | Type | Default | Notes |
|---|---|---|---|
| (none) | | | |

Returns `{providers: [{name, kind, search, download_ready, token_env}]}`. `download_ready` is false until the provider's token env var is set.

### `ue_search_sketchfab`

Search [Sketchfab](https://sketchfab.com) for downloadable models. Search is public and needs no token.

| Param | Type | Default | Notes |
|---|---|---|---|
| `query` | str | required | Free-text search, e.g. `"wooden barrel"`. |
| `limit` | int | `12` | Capped at 24 by the Sketchfab API. |

Returns `{count, results: [{uid, name, author, license, face_count, downloadable}]}`. Check the `license` before using a model, and feed `uid` to `ue_import_sketchfab`.

### `ue_import_sketchfab`

Download a model by `uid` and import it into the project. Requires `SKETCHFAB_API_TOKEN` (create one under sketchfab.com > Settings > API). The model is fetched as glTF, unpacked, and imported.

| Param | Type | Default | Notes |
|---|---|---|---|
| `uid` | str | required | A `uid` from `ue_search_sketchfab`. |
| `destination` | str | `/Game/Sketchfab` | Content folder to import into. |

Returns `{imported: [asset_path, ...]}`. The server and editor must share a filesystem (the file is downloaded locally, then imported). glTF import relies on the engine's Interchange importer, which is on by default in UE 5.

---

## AI generation

Generate a 3D model from a text prompt with [Meshy](https://meshy.ai), then import it. Generation is asynchronous, so it is three tools: start, poll, import. Requires `MESHY_API_KEY` (create one under meshy.ai > Settings > API).

### `ue_generate_model`

Start a Meshy text-to-3D task.

| Param | Type | Default | Notes |
|---|---|---|---|
| `prompt` | str | required | What to generate, e.g. `"a mossy stone golem"`. |
| `art_style` | str | `realistic` | `realistic` or `sculpture`. |

Returns `{task_id, status, provider}`. Hold onto `task_id`.

### `ue_generation_status`

Poll a task until it is ready.

| Param | Type | Default | Notes |
|---|---|---|---|
| `task_id` | str | required | From `ue_generate_model`. |

Returns `{task_id, status, progress, model_urls}`. `status` runs PENDING, then IN_PROGRESS, then SUCCEEDED (or FAILED). Import once it is SUCCEEDED.

### `ue_import_generated`

Download a finished model and import it. Fails if the task is not SUCCEEDED yet.

| Param | Type | Default | Notes |
|---|---|---|---|
| `task_id` | str | required | A SUCCEEDED task. |
| `destination` | str | `/Game/Generated` | Content folder to import into. |
| `file_format` | str | `glb` | `glb`, `fbx`, `obj`, or `usdz`. |

Returns `{imported: [asset_path, ...]}`. Like Sketchfab import, the server and editor must share a filesystem. Generated models come in at a normalized size, so expect to rescale after import.

---

## Materials

### `ue_create_material`

Creates a material wired from constant expressions. Good for blockout and stylized work; for node graphs beyond constants, use `ue_python` with `unreal.MaterialEditingLibrary`.

| Param | Type | Default | Notes |
|---|---|---|---|
| `folder` | str | required | e.g. `/Game/Materials` |
| `name` | str | required | e.g. `M_Lava` |
| `base_color` | [r, g, b] | None | 0..1 |
| `metallic` | float | None | 0..1 |
| `roughness` | float | None | 0..1 |
| `emissive` | [r, g, b] | None | Values above 1.0 glow with bloom |

### `ue_create_material_instance`

| Param | Type | Default | Notes |
|---|---|---|---|
| `folder` | str | required | |
| `name` | str | required | |
| `parent_path` | str | required | The parent material (must expose parameters) |
| `scalar_params` | {name: float} | None | |
| `vector_params` | {name: [r,g,b] or [r,g,b,a]} | None | |
| `texture_params` | {name: texture path} | None | |

### `ue_assign_material`

| Param | Type | Default | Notes |
|---|---|---|---|
| `label` | str | required | Actor outliner label |
| `material_path` | str | required | |
| `slot` | int | 0 | Material slot index on the first mesh component |

---

## Blueprints

### `ue_create_blueprint`

| Param | Type | Default | Notes |
|---|---|---|---|
| `folder` | str | required | |
| `name` | str | required | e.g. `BP_Collectible` |
| `parent_class` | str | `/Script/Engine.Actor` | Engine class path or a parent Blueprint asset path |

### `ue_add_component`

| Param | Type | Default | Notes |
|---|---|---|---|
| `blueprint_path` | str | required | |
| `component_class` | str | required | Short name (`StaticMeshComponent`, `SphereComponent`, `PointLightComponent`) or a `/Script` path |
| `name` | str | None | Component name in the Blueprint |

Adds to the Blueprint's root, compiles, and saves.

### `ue_set_blueprint_default`

Set a class default (CDO property) and recompile.

| Param | Type | Default | Notes |
|---|---|---|---|
| `blueprint_path` | str | required | |
| `property_name` | str | required | snake_case |
| `value` | any | required | |

Blueprint graph logic (nodes and wires) is not scriptable through Unreal's Python API. UEMCP can create the asset, components, and defaults; the event graph remains hand-authored. This is an engine limitation, not a UEMCP one.

---

## Levels

### `ue_open_level` / `ue_new_level`

`ue_open_level(path)` opens an existing level. `ue_new_level(path, template=None)` creates one, optionally from a template level asset, and opens it. Unsaved changes in the current level are discarded without prompting (remote execution runs unattended), so `ue_save_all` first if it matters.

---

## Viewport

### `ue_set_camera` / `ue_get_camera`

Get or set the editor viewport camera `{location, rotation}`.

### `ue_focus_actor`

Selects the actor and aligns the viewport camera to it (same as pressing F in the editor).

### `ue_screenshot`

| Param | Type | Default |
|---|---|---|
| `width` | int | 1280 |
| `height` | int | 720 |

Returns the image directly into the conversation. Uses Unreal's HighResShot, so an editor viewport must be visible (not minimized), and the MCP server must run on the same machine as the editor. The screenshot-then-look loop is the core of agentic level work: make a change, screenshot, evaluate, iterate.

---

## Play

### `ue_play` / `ue_stop_play`

Start and stop simulating the level in the viewport. `ue_play` uses Simulate mode (physics, Niagara, and most gameplay run; no player pawn is possessed). True PIE with input injection is on the roadmap. `ue_stop_play` doubles as the keyboard-free escape from a play session that has captured the mouse: remote execution rides the editor tick, which keeps running during play.

### `ue_release_mouse`

Free the mouse cursor from a play session without stopping it. Play mode can capture the mouse and lock it to the game viewport; the built-in escapes (Shift+F1, Esc) are keyboard-only, which strands mouse-only users. This shows the cursor and switches the player controller to game-and-UI input with the viewport lock disabled, so the pointer can leave the viewport while the session keeps running. Raises a clear error when no play session is active. Works alongside the project-level fix (Project Settings > Engine > Input: `DefaultViewportMouseCaptureMode=CaptureDuringMouseDown`, `DefaultViewportMouseLockMode=DoNotLock`, `bCaptureMouseOnLaunch=False`), which prevents the trap in the first place.

---

## Render

### `ue_render_sequence`

| Param | Type | Default |
|---|---|---|
| `sequence_path` | str | (required) |
| `output_dir` | str | `<project>/Saved/MovieRenders/<sequence>` |
| `output_format` | str | `png` |
| `resolution` | [int, int] | `[1920, 1080]` |
| `start_frame` | int | (sequence range) |
| `end_frame` | int | (sequence range) |
| `frame_rate` | int | (sequence rate) |
| `map_path` | str | current level |
| `config_path` | str | (built from params) |
| `headless` | bool | `false` |
| `timeout` | float | `600` |

Renders a Level Sequence with [Movie Render Queue](https://dev.epicgames.com/documentation/en-us/unreal-engine/render-cinematics-in-unreal-engine). The **Movie Render Queue plugin must be enabled** in the project; the tool returns a clear error if it is not.

`output_format` is `png`, `jpg`, `bmp`, `exr` (image sequences), `prores` (a `.mov` video, the reliable built-in encoder), or `mp4`. `mp4` has no built-in output node: it renders PNG frames and then runs the project's configured [command-line (ffmpeg) encoder](https://dev.epicgames.com/documentation/en-us/unreal-engine/command-line-encoding-in-unreal-engine) over them, so it only produces a video when that encoder is set up in Project Settings; the frames are kept either way. Prefer `prores` for dependency-free video.

`config_path` (optional) uses a saved Movie Pipeline config preset instead of building one from the parameters; it means the same thing in both modes.

`sequence_path`, `config_path`, and `map_path` must be `/Game/...` content paths (letters, digits, `_`, `.`, `/`). The tool rejects anything else before launching the headless process, so a path cannot smuggle extra `UnrealEditor-Cmd` switches.

**In-editor mode** (default) builds the Movie Pipeline config from the parameters, renders through a PIE executor, and blocks until the render finishes (a marker file signals completion) or `timeout` seconds elapse. Returns `{mode, status, output_dir, format, files, frame_count}`.

**Headless mode** (`headless=true`) renders in a separate offscreen `UnrealEditor-Cmd` process using the single-sequence command line (map positional, `-LevelSequence`, `-MoviePipelineConfig`). When `config_path` is omitted it auto-authors a config preset asset under `/Game/UEMCP/Render` from the parameters, so no manual setup is needed. The editor executable is taken from `UEMCP_EDITOR_CMD`, else derived from the running editor; with the editor closed, set `UEMCP_EDITOR_CMD` and pass `config_path` (no live editor to query or author from). Returns `{mode, status, output_dir, format, exit_code, command, files, log_tail}`.

> **Status: experimental.** The pure-Python logic (format mapping, command line, snippet generation) is covered by tests, but the in-editor render and headless paths have not yet been exercised against a live editor. The Unreal API names this uses can vary across 5.x. See the open items below before relying on it in production.
>
> Open items / not yet verified against a live editor:
> - `build_save_render_config` creates the preset with `AssetTools.create_asset(..., factory=None)`; if a factory turns out to be required for `MoviePipelinePrimaryConfig`, headless auto-author needs adjusting.
> - In-editor completion relies on `MoviePipelinePIEExecutor.on_executor_finished_delegate` and a keep-alive reference; the marker-file handshake is untested at runtime.
> - `MoviePipelineOutputSetting` field names (`output_directory`, `output_resolution`, `use_custom_playback_range`, `output_frame_rate`) and `render_queue_with_executor_instance` are assumed stable across UE 5.x.
> - `mp4` depends on the project's command-line (ffmpeg) encoder being configured; by design, not auto-set.
> - Headless against an already-open project can hit asset file locks; render with the editor closed when possible.
> - For a user-supplied `config_path` in headless mode, output-file collection is best-effort (the config's output directory is not read back).
