"""The UEMCP server: MCP tools that drive a live Unreal Editor."""

from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP, Image

from . import __version__, assets, render, snippets
from .bridge import UnrealBridge
from .remote_exec import MODE_EXEC_FILE

INSTRUCTIONS = """\
UEMCP drives a live Unreal Engine 5 editor. The editor must be running with the
'Python Editor Script Plugin' enabled and remote execution turned on. Call
ue_status first if a tool reports a connection problem. Asset and class paths
use Unreal conventions: project content lives under /Game/..., engine classes
under /Script/Engine.ClassName (for example /Script/Engine.PointLight).
Distances are in centimeters and rotations are [roll, pitch, yaw] in degrees.
For anything not covered by a dedicated tool, ue_python runs arbitrary editor
Python with full access to the unreal module.
"""

SCREENSHOT_TIMEOUT = 30.0  # a cold HighResShot (first of a session) can be slow


def create_server(bridge: UnrealBridge | None = None) -> FastMCP:
    bridge = bridge or UnrealBridge()
    mcp = FastMCP("uemcp", instructions=INSTRUCTIONS)

    # ------------------------------------------------------------ editor ----

    @mcp.tool()
    def ue_status() -> dict:
        """Discover running Unreal Editor instances and report connection state."""
        instances = bridge.client.discover_with_retries()
        return {
            "connected": bridge.client.is_connected,
            "connected_to": (
                bridge.client.instance.project_name if bridge.client.instance else None
            ),
            "instances": [
                {
                    "node_id": i.node_id,
                    "project": i.project_name,
                    "engine_version": i.engine_version,
                    "machine": i.machine,
                }
                for i in instances
            ],
            "hint": (
                None
                if instances
                else "No editors found. In Unreal: enable the 'Python Editor Script "
                "Plugin', then check 'Enable Remote Execution' under Project Settings "
                "> Plugins > Python, and restart the editor."
            ),
        }

    @mcp.tool()
    def ue_python(code: str) -> dict:
        """Run arbitrary Python inside the Unreal Editor (full `unreal` module access).

        This is the escape hatch for anything the dedicated tools do not cover.
        Use print() for output you want back.
        """
        result = bridge.run_raw(code, exec_mode=MODE_EXEC_FILE)
        return {
            "success": result.success,
            "output": result.output_text(),
            "result": result.result,
        }

    @mcp.tool()
    def ue_console_command(command: str) -> dict:
        """Execute an Unreal console command (for example `stat fps` or `r.ScreenPercentage 50`)."""
        return bridge.run_json(snippets.build_console_command(command))

    @mcp.tool()
    def ue_project_info() -> dict:
        """Get engine version, project paths, and the currently open level."""
        return bridge.run_json(snippets.build_project_info())

    # ------------------------------------------------------------ actors ----

    @mcp.tool()
    def ue_list_actors(
        filter_class: str | None = None,
        name_contains: str | None = None,
        limit: int = 100,
    ) -> dict:
        """List actors in the open level, optionally filtered by class or label substring."""
        return bridge.run_json(snippets.build_list_actors(filter_class, name_contains, limit))

    @mcp.tool()
    def ue_spawn_actor(
        class_path: str,
        location: list[float] | None = None,
        rotation: list[float] | None = None,
        scale: list[float] | None = None,
        label: str | None = None,
    ) -> dict:
        """Spawn an actor from an engine class (/Script/Engine.PointLight) or an asset (/Game/...).

        location is [x, y, z] in centimeters; rotation is [roll, pitch, yaw] in degrees.
        """
        return bridge.run_json(
            snippets.build_spawn_actor(
                class_path, location or [0, 0, 0], rotation or [0, 0, 0], scale, label
            )
        )

    @mcp.tool()
    def ue_destroy_actor(label: str) -> dict:
        """Delete the actor with the given outliner label from the open level."""
        return bridge.run_json(snippets.build_destroy_actor(label))

    @mcp.tool()
    def ue_set_actor_transform(
        label: str,
        location: list[float] | None = None,
        rotation: list[float] | None = None,
        scale: list[float] | None = None,
    ) -> dict:
        """Move, rotate, or scale an actor by its outliner label. Omitted parts are unchanged."""
        return bridge.run_json(snippets.build_set_actor_transform(label, location, rotation, scale))

    @mcp.tool()
    def ue_set_actor_property(label: str, property_name: str, value) -> dict:
        """Set an editor property on an actor (snake_case name, for example `intensity`).

        Lists of 3 or 4 numbers are coerced to Vector or LinearColor when needed.
        """
        return bridge.run_json(snippets.build_set_actor_property(label, property_name, value))

    @mcp.tool()
    def ue_get_actor(label: str) -> dict:
        """Get an actor's transform, class, and component list by its outliner label."""
        return bridge.run_json(snippets.build_get_actor(label))

    @mcp.tool()
    def ue_batch_edit(
        operations: list[dict],
        filter_class: str | None = None,
        name_contains: str | None = None,
        labels: list[str] | None = None,
        limit: int = 500,
        continue_on_error: bool = True,
        dry_run: bool = False,
    ) -> dict:
        """Apply operations to many actors in one editor round trip.

        Select actors by `labels` (exact) and/or `filter_class` + `name_contains`
        (same as ue_list_actors); at least one selector is required. `operations`
        is an ordered list of dicts, each with an `op`:
        {"op": "set_property", "property": ..., "value": ...},
        {"op": "set_transform", "location"/"rotation"/"scale": [...],
        "mode": "absolute"|"relative"},
        {"op": "set_material", "material_path": ..., "slot": 0}, or {"op": "destroy"}.
        Relative transforms add to location/rotation and multiply scale; destroy is
        applied last. dry_run reports which actors would be touched without changing
        anything. Per-actor errors are collected (continue_on_error) or abort.
        """
        return bridge.run_json(
            snippets.build_batch_edit(
                operations,
                filter_class,
                name_contains,
                labels,
                limit,
                continue_on_error,
                dry_run,
            )
        )

    # ------------------------------------------------------------ assets ----

    @mcp.tool()
    def ue_search_assets(
        root: str = "/Game",
        query: str | None = None,
        class_filter: str | None = None,
        limit: int = 50,
    ) -> dict:
        """Search project assets by name substring and/or class (StaticMesh, Material, ...)."""
        return bridge.run_json(snippets.build_search_assets(root, query, class_filter, limit))

    @mcp.tool()
    def ue_asset_info(path: str) -> dict:
        """Inspect one asset: class, plus mesh LODs/materials or blueprint class when relevant."""
        return bridge.run_json(snippets.build_asset_info(path))

    @mcp.tool()
    def ue_import_asset(file_path: str, destination: str = "/Game/Imported") -> dict:
        """Import a file from disk (FBX, OBJ, PNG, WAV, ...) into the project content folder."""
        return bridge.run_json(snippets.build_import_asset(file_path, destination))

    @mcp.tool()
    def ue_create_folder(path: str) -> dict:
        """Create a content browser folder, for example /Game/Levels/Greybox."""
        return bridge.run_json(snippets.build_create_folder(path))

    @mcp.tool()
    def ue_duplicate_asset(source: str, destination: str) -> dict:
        """Duplicate an asset to a new content path."""
        return bridge.run_json(snippets.build_duplicate_asset(source, destination))

    @mcp.tool()
    def ue_delete_asset(path: str) -> dict:
        """Delete an asset from the project. Fails if other assets still reference it."""
        return bridge.run_json(snippets.build_delete_asset(path))

    @mcp.tool()
    def ue_save_all() -> dict:
        """Save all dirty packages: the open level and any modified assets."""
        return bridge.run_json(snippets.build_save_dirty())

    # ----------------------------------------------------- asset libraries ----

    @mcp.tool()
    def ue_asset_providers() -> dict:
        """List external asset-library providers and whether their credentials are set."""
        return {"providers": assets.provider_status()}

    @mcp.tool()
    def ue_search_sketchfab(query: str, limit: int = 12) -> dict:
        """Search Sketchfab for downloadable 3D models (public, no token needed).

        Returns each model's `uid`, which ue_import_sketchfab consumes. Mind the
        `license` field before using a model.
        """
        hits = assets.SketchfabProvider().search(query, limit)
        return {"count": len(hits), "results": [h.as_dict() for h in hits]}

    @mcp.tool()
    def ue_import_sketchfab(uid: str, destination: str = "/Game/Sketchfab") -> dict:
        """Download a Sketchfab model by `uid` and import it into the project.

        Needs SKETCHFAB_API_TOKEN. The model is fetched as glTF and imported with
        the same path as ue_import_asset; the result lists the created asset paths.
        """
        provider = assets.SketchfabProvider()
        work_dir = tempfile.mkdtemp(prefix="uemcp_sketchfab_")
        try:
            model_file = provider.download(uid, work_dir)
            return bridge.run_json(snippets.build_import_asset(model_file, destination))
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    @mcp.tool()
    def ue_generate_model(prompt: str, art_style: str = "realistic") -> dict:
        """Start a Meshy text-to-3D generation (needs MESHY_API_KEY).

        Asynchronous: returns a task_id. Poll ue_generation_status until it is
        SUCCEEDED, then ue_import_generated to bring the model in. art_style is
        `realistic` or `sculpture`. Models come in untextured and normalized in size.
        """
        task_id = assets.MeshyProvider().generate(prompt, art_style=art_style)
        return {"task_id": task_id, "status": "PENDING", "provider": "meshy"}

    @mcp.tool()
    def ue_generation_status(task_id: str) -> dict:
        """Check a Meshy generation task. Status is SUCCEEDED when it is ready to import."""
        return assets.MeshyProvider().status(task_id)

    @mcp.tool()
    def ue_import_generated(
        task_id: str, destination: str = "/Game/Generated", file_format: str = "glb"
    ) -> dict:
        """Download a finished Meshy model by task_id and import it into the project.

        Fails if the task is not SUCCEEDED yet. file_format is glb, fbx, obj, or usdz.
        """
        provider = assets.MeshyProvider()
        work_dir = tempfile.mkdtemp(prefix="uemcp_meshy_")
        try:
            model_file = provider.download(task_id, work_dir, file_format=file_format)
            return bridge.run_json(snippets.build_import_asset(model_file, destination))
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    # --------------------------------------------------------- materials ----

    @mcp.tool()
    def ue_create_material(
        folder: str,
        name: str,
        base_color: list[float] | None = None,
        metallic: float | None = None,
        roughness: float | None = None,
        emissive: list[float] | None = None,
    ) -> dict:
        """Create a simple constant-based material. base_color and emissive are [r, g, b] 0..1."""
        return bridge.run_json(
            snippets.build_create_material(folder, name, base_color, metallic, roughness, emissive)
        )

    @mcp.tool()
    def ue_create_material_instance(
        folder: str,
        name: str,
        parent_path: str,
        scalar_params: dict[str, float] | None = None,
        vector_params: dict[str, list[float]] | None = None,
        texture_params: dict[str, str] | None = None,
    ) -> dict:
        """Create a material instance of a parent material and set its parameters."""
        return bridge.run_json(
            snippets.build_create_material_instance(
                folder, name, parent_path, scalar_params, vector_params, texture_params
            )
        )

    @mcp.tool()
    def ue_assign_material(label: str, material_path: str, slot: int = 0) -> dict:
        """Assign a material to the first mesh component of an actor."""
        return bridge.run_json(snippets.build_assign_material(label, material_path, slot))

    # -------------------------------------------------------- blueprints ----

    @mcp.tool()
    def ue_create_blueprint(
        folder: str, name: str, parent_class: str = "/Script/Engine.Actor"
    ) -> dict:
        """Create a Blueprint asset from a parent class path or parent Blueprint asset path."""
        return bridge.run_json(snippets.build_create_blueprint(folder, name, parent_class))

    @mcp.tool()
    def ue_add_component(
        blueprint_path: str, component_class: str, name: str | None = None
    ) -> dict:
        """Add a component to a Blueprint (StaticMeshComponent or a /Script class path)."""
        return bridge.run_json(snippets.build_add_component(blueprint_path, component_class, name))

    @mcp.tool()
    def ue_set_blueprint_default(blueprint_path: str, property_name: str, value) -> dict:
        """Set a class default value on a Blueprint and recompile it."""
        return bridge.run_json(
            snippets.build_set_blueprint_default(blueprint_path, property_name, value)
        )

    # ------------------------------------------------------------ levels ----

    @mcp.tool()
    def ue_open_level(path: str) -> dict:
        """Open a level by content path, for example /Game/Maps/MainLevel."""
        return bridge.run_json(snippets.build_open_level(path))

    @mcp.tool()
    def ue_new_level(path: str, template: str | None = None) -> dict:
        """Create and open a new level, optionally copied from a template level asset."""
        return bridge.run_json(snippets.build_new_level(path, template))

    # ---------------------------------------------------------- viewport ----

    @mcp.tool()
    def ue_set_camera(location: list[float], rotation: list[float]) -> dict:
        """Move the editor viewport camera. rotation is [roll, pitch, yaw] in degrees."""
        return bridge.run_json(snippets.build_set_camera(location, rotation))

    @mcp.tool()
    def ue_get_camera() -> dict:
        """Get the editor viewport camera's location and rotation."""
        return bridge.run_json(snippets.build_get_camera())

    @mcp.tool()
    def ue_focus_actor(label: str) -> dict:
        """Select an actor and point the viewport camera at it."""
        return bridge.run_json(snippets.build_focus_actor(label))

    @mcp.tool()
    def ue_screenshot(width: int = 1280, height: int = 720) -> Image:
        """Take a screenshot of the editor viewport and return it as an image.

        Only works when the MCP server runs on the same machine as the editor.
        """
        started = time.time()
        data = bridge.run_json(snippets.build_screenshot(width, height))
        shot = _wait_for_screenshot(Path(data["dir"]), started)
        return Image(data=shot.read_bytes(), format="png")

    # --------------------------------------------------------------- pie ----

    @mcp.tool()
    def ue_play() -> dict:
        """Start simulating the open level in the editor viewport."""
        return bridge.run_json(snippets.build_start_play())

    @mcp.tool()
    def ue_stop_play() -> dict:
        """Stop the active simulate/play-in-editor session."""
        return bridge.run_json(snippets.build_stop_play())

    @mcp.tool()
    def ue_release_mouse() -> dict:
        """Free the mouse cursor from a play session without stopping it.

        Play mode can capture the mouse and lock it to the game viewport,
        which a mouse-only user cannot escape without a keyboard (Shift+F1
        or Esc). This shows the cursor and switches the player controller
        to game-and-UI input with the viewport lock disabled, so the
        pointer can leave the viewport while the session keeps running.
        Use ue_stop_play to end the session entirely.
        """
        return bridge.run_json(snippets.build_release_mouse())

    # -------------------------------------------------- movie render queue ----

    @mcp.tool()
    def ue_render_sequence(
        sequence_path: str,
        output_dir: str | None = None,
        output_format: str = "png",
        resolution: list[int] | None = None,
        start_frame: int | None = None,
        end_frame: int | None = None,
        frame_rate: int | None = None,
        map_path: str | None = None,
        config_path: str | None = None,
        headless: bool = False,
        timeout: float = 600.0,
    ) -> dict:
        """Render a Level Sequence with Movie Render Queue (needs the MRQ plugin).

        output_format is png, jpg, bmp, exr, prores (.mov video), or mp4. resolution
        is [width, height]. In-editor mode (the default) renders through a PIE
        executor and blocks until the render finishes or timeout seconds elapse.
        Set headless=True to render in a separate offscreen process. Pass config_path
        to use a saved Movie Pipeline config preset instead of building one from the
        parameters. mp4 has no built-in encoder: it renders PNG frames and runs the
        project's configured command-line (ffmpeg) encoder, so it needs that set up;
        prores is the reliable built-in video output.
        """
        render.validate_object_path(sequence_path, "sequence_path")
        if config_path:
            render.validate_object_path(config_path, "config_path")
        if map_path:
            render.validate_object_path(map_path, "map_path")
        targets = bridge.run_json(snippets.build_render_targets())
        seq_name = sequence_path.rstrip("/").rsplit("/", 1)[-1].split(".")[0]
        out_dir = output_dir or str(
            Path(targets["project_dir"]) / "Saved" / "MovieRenders" / seq_name
        )
        output_classes = [] if config_path else render.resolve_output_classes(output_format)

        if headless:
            map_package = map_path.split(".")[0] if map_path else targets.get("map_package")
            if not map_package:
                raise RuntimeError("No map to render; open a level or pass map_path.")
            if config_path:
                config_object = render.to_object_path(config_path)
                collect_dir = out_dir if output_dir else None
            else:
                cfg_asset = f"/Game/UEMCP/Render/MRQ_{seq_name}"
                saved = bridge.run_json(
                    snippets.build_save_render_config(
                        cfg_asset,
                        out_dir,
                        output_classes,
                        resolution,
                        start_frame,
                        end_frame,
                        frame_rate,
                    )
                )
                config_object = saved["config_object"]
                collect_dir = saved["output_dir"]
            result = render.run_headless(
                render.resolve_editor_cmd(targets.get("editor_exe")),
                targets["project_file"],
                map_package,
                render.to_object_path(sequence_path),
                config_object,
                resolution,
                collect_dir,
                timeout,
            )
            return {
                "mode": "headless",
                "status": "ok" if result["exit_code"] == 0 else "failed",
                "output_dir": collect_dir,
                "format": output_format,
                **result,
            }

        marker = str(Path(out_dir) / "_uemcp_render.json")
        map_object = render.to_object_path(map_path) if map_path else None
        started = time.time()
        info = bridge.run_json(
            snippets.build_render_sequence(
                sequence_path,
                out_dir,
                output_classes,
                marker,
                resolution,
                start_frame,
                end_frame,
                frame_rate,
                map_object,
                config_path,
            )
        )
        payload = _wait_for_marker(Path(info["marker"]), started, timeout)
        files = payload.get("files", [])
        return {
            "mode": "in_editor",
            "status": "ok" if payload.get("success") else "failed",
            "output_dir": info["output_dir"],
            "format": output_format,
            "files": files,
            "frame_count": len(files),
            "error": payload.get("error"),
        }

    # ------------------------------------------------------------ prompts ----

    @mcp.prompt()
    def unreal_workflow_strategy() -> str:
        """How to drive Unreal reliably: orient, place relative to the scene, verify."""
        return """\
When working in Unreal through UEMCP, follow this loop:

1. Orient first. Call ue_status to confirm a live editor, then ue_project_info for
   the engine version and the open level. Use ue_list_actors to see what is already
   in the scene before adding anything.

2. Do not assume the world origin is where the action is. Real levels are often built
   thousands of units away from [0, 0, 0], so an actor spawned at the origin can be
   invisible (off-screen, a kilometer from the camera). Anchor new actors to existing
   geometry: get a reference actor's location with ue_get_actor (or ue_list_actors),
   or read the camera with ue_get_camera, and place relative to that.

3. Prefer existing content over primitives. ue_search_assets to find a /Game asset,
   then ue_spawn_actor with its path. Use engine classes (/Script/Engine.PointLight)
   or /Engine/BasicShapes/* only for true primitives and lights.

4. Conventions: distances are centimeters, rotations are [roll, pitch, yaw] in degrees,
   colors are [r, g, b] in 0..1. Properties are snake_case (ue_set_actor_property).

5. Verify visually. After a change, ue_focus_actor on what you touched (or ue_set_camera),
   then ue_screenshot and actually look at the result before reporting success.

6. ue_python is the escape hatch for anything the dedicated tools do not cover.

7. Nothing is written to disk until ue_save_all. Leave it to the user as a checkpoint
   unless they ask you to save.
"""

    return mcp


def _wait_for_screenshot(directory: Path, started: float) -> Path:
    """Poll the screenshot folder for a new, fully written PNG."""
    deadline = started + SCREENSHOT_TIMEOUT
    while time.time() < deadline:
        candidates = [
            p
            for p in directory.glob("**/*.png")
            if p.stat().st_mtime >= started - 2.0
        ]
        if candidates:
            newest = max(candidates, key=lambda p: p.stat().st_mtime)
            size = newest.stat().st_size
            time.sleep(0.4)
            if size > 0 and newest.stat().st_size == size:
                return newest
        time.sleep(0.3)
    raise RuntimeError(
        f"Screenshot did not appear in {directory} within {SCREENSHOT_TIMEOUT:.0f}s. "
        "Is an editor viewport visible (not minimized)?"
    )


def _wait_for_marker(marker: Path, started: float, timeout: float) -> dict:
    """Poll for the render's completion marker and return its parsed payload."""
    deadline = started + timeout
    while time.time() < deadline:
        if marker.exists():
            try:
                return json.loads(marker.read_text())
            except (ValueError, OSError):
                time.sleep(0.3)  # mid-write; read again
                continue
        time.sleep(0.5)
    raise RuntimeError(
        f"Render did not finish within {timeout:.0f}s (no marker at {marker}). "
        "The render may still be running in the editor."
    )


def main() -> None:
    """Entry point for the `uemcp` console script."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="uemcp",
        description=f"UEMCP {__version__}: MCP server for Unreal Engine 5",
    )
    parser.add_argument(
        "--project",
        help="Prefer the editor instance running this project (when several are open)",
    )
    args = parser.parse_args()

    bridge = UnrealBridge()
    if args.project:
        bridge.config.project_name = args.project
    create_server(bridge).run()


if __name__ == "__main__":
    main()
