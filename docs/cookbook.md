# Cookbook

Prompt recipes that work well with UEMCP. These are starting points; the model chains the tools itself.

## The core loop: change, look, iterate

The highest-leverage habit is asking for a screenshot after changes:

> Spawn a point light above the table, then screenshot the viewport so we can see it. Adjust intensity until it reads like warm evening light, screenshot after each change.

`ue_screenshot` closes the feedback loop that makes agentic editor work actually converge.

## Three-point lighting rig

> Set up three-point lighting around the actor labeled "Hero": a warm key light front-left, a cool fill at quarter intensity front-right, and a rim light behind. Use spot lights, aim them at the actor, then screenshot.

## Greybox a room

> Greybox a 12x8 meter room at the origin: floor, four walls, and a doorway gap in the south wall. Use the engine's basic cube mesh (/Engine/BasicShapes/Cube) scaled appropriately. Label everything Room_*. Remember units are centimeters.

## Scatter set dressing

> Search /Game for static meshes with "rock" in the name. Scatter 25 of them in a 2000-unit radius around [0, 0, 0] with random yaw and scale between 0.8 and 1.5. Use ue_python for the loop so it is one call.

That last sentence matters: for bulk operations, nudging the model toward a single `ue_python` loop is much faster than 25 `ue_spawn_actor` calls.

## Material pass

> Create a material folder /Game/Materials/Blockout with five materials: neutral grey 0.5 roughness, warm wood tone, brushed metal (metallic 0.9, roughness 0.3), emissive signal red, and glass-ish (roughness 0.05). Then assign the wood one to every actor whose label starts with "Table".

## Blueprint scaffolding

> Create BP_Pickup in /Game/Blueprints: parent Actor, with a StaticMeshComponent called Mesh, a SphereComponent called Trigger, and a RotatingMovementComponent. Set initial_life_span default to 0.

UEMCP creates assets, components, and defaults. Event graph logic cannot be authored through Unreal's Python API, so wiring the overlap event stays manual (or in C++).

## Asset audit

> List every material in /Game and flag ones whose name does not start with M_ or MI_. Then list textures over nothing in /Game/Textures, and give me a table of what you found.

## Level review

> Open /Game/Maps/Arena. Fly the camera to four corners of the map at height 800 looking toward the center, screenshot each, and give me notes on composition and obvious visual bugs.

## Performance triage

> Run `stat unit`, `stat fps`, and `stat gpu` via console commands, screenshot the viewport with the overlays visible, then summarize where the frame time is going.

## Escape hatch examples

`ue_python` has the full `unreal` module. Things people reach for:

```python
# Batch-rename actors
import unreal
subsys = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
for i, a in enumerate(a for a in subsys.get_all_level_actors()
                      if "Cube" in a.get_actor_label()):
    a.set_actor_label(f"Crate_{i:02d}")

# Set a component property the dedicated tools cannot reach
light = next(a for a in subsys.get_all_level_actors()
             if a.get_actor_label() == "KeyLight")
light.light_component.set_editor_property("use_temperature", True)
light.light_component.set_editor_property("temperature", 3200.0)
```

If you find yourself pasting the same `ue_python` snippet repeatedly, that is a tool waiting to be born. PRs welcome: [CONTRIBUTING.md](../CONTRIBUTING.md).
