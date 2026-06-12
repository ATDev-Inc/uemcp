"""The UEMCP server: MCP tools that drive a live Unreal Editor."""

from __future__ import annotations

import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP, Image

from . import __version__, snippets
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

SCREENSHOT_TIMEOUT = 20.0


def create_server(bridge: UnrealBridge | None = None) -> FastMCP:
    bridge = bridge or UnrealBridge()
    mcp = FastMCP("uemcp", instructions=INSTRUCTIONS)

    # ------------------------------------------------------------ editor ----

    @mcp.tool()
    def ue_status() -> dict:
        """Discover running Unreal Editor instances and report connection state."""
        instances = bridge.client.discover()
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
