"""Every snippet builder must produce valid Python, before and after wrapping."""

import pytest

from uemcp import snippets
from uemcp.bridge import wrap_body

CASES = [
    ("project_info", snippets.build_project_info, ()),
    ("console_command", snippets.build_console_command, ('stat fps "quoted"',)),
    ("list_actors", snippets.build_list_actors, ("PointLight", "Key", 25)),
    ("list_actors_no_filters", snippets.build_list_actors, (None, None, 100)),
    (
        "spawn_actor_class",
        snippets.build_spawn_actor,
        ("/Script/Engine.PointLight", [0, 0, 300], [0, 0, 0], None, "KeyLight"),
    ),
    (
        "spawn_actor_asset",
        snippets.build_spawn_actor,
        ("/Game/Props/SM_Chair", [10.5, -20, 0], [0, 0, 90], [2, 2, 2], None),
    ),
    ("destroy_actor", snippets.build_destroy_actor, ("KeyLight",)),
    (
        "set_actor_transform",
        snippets.build_set_actor_transform,
        ("KeyLight", [1, 2, 3], [0, 45, 0], None),
    ),
    (
        "set_actor_property_scalar",
        snippets.build_set_actor_property,
        ("KeyLight", "intensity", 5000.0),
    ),
    (
        "set_actor_property_color",
        snippets.build_set_actor_property,
        ("KeyLight", "light_color", [1.0, 0.5, 0.25]),
    ),
    ("get_actor", snippets.build_get_actor, ("KeyLight",)),
    (
        "batch_edit",
        snippets.build_batch_edit,
        (
            [
                {"op": "set_property", "property": "intensity", "value": 5000.0},
                {"op": "set_property", "property": "light_color", "value": [1.0, 0.5, 0.25]},
                {"op": "set_transform", "location": [0, 0, 100], "mode": "relative"},
                {"op": "set_transform", "scale": [2, 2, 2], "mode": "absolute"},
                {"op": "set_material", "material_path": "/Game/Materials/M_X", "slot": 0},
                {"op": "destroy"},
            ],
            "PointLight",
            "Key",
            None,
            500,
            True,
            False,
        ),
    ),
    (
        "batch_edit_dry_labels",
        snippets.build_batch_edit,
        (
            [{"op": "set_property", "property": "intensity", "value": 1}],
            None,
            None,
            ["A", "B"],
            10,
            False,
            True,
        ),
    ),
    ("search_assets", snippets.build_search_assets, ("/Game", "chair", "StaticMesh", 50)),
    ("asset_info", snippets.build_asset_info, ("/Game/Props/SM_Chair",)),
    ("import_asset", snippets.build_import_asset, ("C:\\stuff\\model.fbx", "/Game/Imported")),
    ("create_folder", snippets.build_create_folder, ("/Game/Levels/Greybox",)),
    (
        "duplicate_asset",
        snippets.build_duplicate_asset,
        ("/Game/Props/SM_Chair", "/Game/Props/SM_Chair2"),
    ),
    ("delete_asset", snippets.build_delete_asset, ("/Game/Props/SM_Chair2",)),
    ("save_dirty", snippets.build_save_dirty, ()),
    (
        "create_material_full",
        snippets.build_create_material,
        ("/Game/Materials", "M_Test", [1, 0, 0], 0.5, 0.2, [0, 1, 0]),
    ),
    (
        "create_material_bare",
        snippets.build_create_material,
        ("/Game/Materials", "M_Bare", None, None, None, None),
    ),
    (
        "create_material_instance",
        snippets.build_create_material_instance,
        (
            "/Game/Materials",
            "MI_Test",
            "/Game/Materials/M_Test",
            {"Roughness": 0.8},
            {"Tint": [1, 0, 0]},
            {"BaseTex": "/Game/Textures/T_Wood"},
        ),
    ),
    (
        "assign_material",
        snippets.build_assign_material,
        ("Chair", "/Game/Materials/M_Test", 0),
    ),
    (
        "create_blueprint",
        snippets.build_create_blueprint,
        ("/Game/Blueprints", "BP_Test", "/Script/Engine.Actor"),
    ),
    (
        "add_component",
        snippets.build_add_component,
        ("/Game/Blueprints/BP_Test", "StaticMeshComponent", "Mesh"),
    ),
    (
        "set_blueprint_default",
        snippets.build_set_blueprint_default,
        ("/Game/Blueprints/BP_Test", "initial_life_span", 5.0),
    ),
    ("open_level", snippets.build_open_level, ("/Game/Maps/Main",)),
    ("new_level", snippets.build_new_level, ("/Game/Maps/New", "/Engine/Maps/Templates/Basic")),
    ("new_level_blank", snippets.build_new_level, ("/Game/Maps/New", None)),
    ("set_camera", snippets.build_set_camera, ([100, 200, 300], [0, -30, 90])),
    ("get_camera", snippets.build_get_camera, ()),
    ("focus_actor", snippets.build_focus_actor, ("KeyLight",)),
    ("screenshot", snippets.build_screenshot, (1920, 1080)),
    ("start_play", snippets.build_start_play, ()),
    ("stop_play", snippets.build_stop_play, ()),
]


@pytest.mark.parametrize("name,builder,args", CASES, ids=[c[0] for c in CASES])
def test_snippet_compiles(name, builder, args):
    body = builder(*args)
    compile(wrap_body(body), f"<{name}>", "exec")


@pytest.mark.parametrize("name,builder,args", CASES, ids=[c[0] for c in CASES])
def test_snippet_has_return(name, builder, args):
    assert "return" in builder(*args)


def test_repr_interpolation_is_safe_for_quotes():
    body = snippets.build_destroy_actor('He said "hi" and it\'s fine')
    compile(wrap_body(body), "<quotes>", "exec")


def test_wrap_body_indents_multiline_blocks():
    wrapped = wrap_body("if True:\n    x = 1\nreturn x")
    compile(wrapped, "<indent>", "exec")
    assert "def __uemcp_main():" in wrapped
