"""Builders for the Python snippets that run inside the Unreal Editor.

Each builder returns a flush-left snippet "body". The bridge wraps the body in
a harness function, so a body may use `return` to hand back JSON-serializable
data. Builders are pure string functions: the test suite compiles every one of
them, which keeps the in-editor code honest without needing Unreal in CI.

Values are interpolated with repr(), so anything that came in as JSON
(str, int, float, bool, None, list, dict) embeds as a valid Python literal.
"""

from __future__ import annotations

_FIND_ACTOR = """\
_subsys = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
_target = None
for _a in _subsys.get_all_level_actors():
    if _a.get_actor_label() == _LABEL:
        _target = _a
        break
if _target is None:
    raise RuntimeError("No actor found with label %r" % _LABEL)"""

_ACTOR_INFO_RETURN = """\
_l = _actor.get_actor_location()
_r = _actor.get_actor_rotation()
_s = _actor.get_actor_scale3d()
return {
    "label": _actor.get_actor_label(),
    "name": _actor.get_name(),
    "class": _actor.get_class().get_name(),
    "location": [_l.x, _l.y, _l.z],
    "rotation": [_r.roll, _r.pitch, _r.yaw],
    "scale": [_s.x, _s.y, _s.z],
}"""


def _vector(values) -> str:
    x, y, z = (float(v) for v in values)
    return f"unreal.Vector({x!r}, {y!r}, {z!r})"


def _rotator(values) -> str:
    roll, pitch, yaw = (float(v) for v in values)
    return f"unreal.Rotator(roll={roll!r}, pitch={pitch!r}, yaw={yaw!r})"


# ---------------------------------------------------------------- editor ----


def build_project_info() -> str:
    return """\
_world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
return {
    "engine_version": unreal.SystemLibrary.get_engine_version(),
    "project_file": unreal.Paths.get_project_file_path(),
    "project_dir": unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()),
    "current_level": _world.get_name() if _world else None,
}"""


def build_console_command(command: str) -> str:
    return f"""\
_cmd = {command!r}
unreal.SystemLibrary.execute_console_command(None, _cmd)
return {{"command": _cmd, "executed": True}}"""


# ---------------------------------------------------------------- actors ----


def build_list_actors(filter_class: str | None, name_contains: str | None, limit: int) -> str:
    return f"""\
_filter_class = {filter_class!r}
_contains = {name_contains!r}
_limit = {int(limit)!r}
_subsys = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
_out = []
for _a in _subsys.get_all_level_actors():
    _cls = _a.get_class().get_name()
    _label = _a.get_actor_label()
    if _filter_class and _filter_class.lower() not in _cls.lower():
        continue
    if _contains and _contains.lower() not in _label.lower():
        continue
    _loc = _a.get_actor_location()
    _out.append({{
        "label": _label,
        "name": _a.get_name(),
        "class": _cls,
        "location": [_loc.x, _loc.y, _loc.z],
    }})
    if len(_out) >= _limit:
        break
return {{"count": len(_out), "actors": _out}}"""


def build_spawn_actor(
    class_path: str,
    location,
    rotation,
    scale,
    label: str | None,
) -> str:
    lines = [
        f"_path = {class_path!r}",
        f"_loc = {_vector(location)}",
        f"_rot = {_rotator(rotation)}",
        """\
_subsys = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
if _path.startswith("/Script/"):
    _cls = unreal.load_class(None, _path)
    if _cls is None:
        raise RuntimeError("Could not load class %s" % _path)
    _actor = _subsys.spawn_actor_from_class(_cls, _loc, _rot)
else:
    _obj = unreal.load_asset(_path)
    if _obj is None:
        raise RuntimeError("Could not load asset %s" % _path)
    _actor = _subsys.spawn_actor_from_object(_obj, _loc, _rot)
if _actor is None:
    raise RuntimeError("Spawn failed for %s" % _path)""",
    ]
    if scale is not None:
        lines.append(f"_actor.set_actor_scale3d({_vector(scale)})")
    if label:
        lines.append(f"_actor.set_actor_label({label!r})")
    lines.append(_ACTOR_INFO_RETURN)
    return "\n".join(lines)


def build_destroy_actor(label: str) -> str:
    return "\n".join(
        [
            f"_LABEL = {label!r}",
            _FIND_ACTOR,
            "_subsys.destroy_actor(_target)",
            'return {"destroyed": _LABEL}',
        ]
    )


def build_set_actor_transform(label: str, location, rotation, scale) -> str:
    lines = [f"_LABEL = {label!r}", _FIND_ACTOR]
    if location is not None:
        lines.append(f"_target.set_actor_location({_vector(location)}, False, False)")
    if rotation is not None:
        lines.append(f"_target.set_actor_rotation({_rotator(rotation)}, False)")
    if scale is not None:
        lines.append(f"_target.set_actor_scale3d({_vector(scale)})")
    lines.append("_actor = _target")
    lines.append(_ACTOR_INFO_RETURN)
    return "\n".join(lines)


def build_set_actor_property(label: str, property_name: str, value) -> str:
    return "\n".join(
        [
            f"_LABEL = {label!r}",
            f"_PROP = {property_name!r}",
            f"_value = {value!r}",
            _FIND_ACTOR,
            """\
try:
    _target.set_editor_property(_PROP, _value)
except Exception:
    if isinstance(_value, (list, tuple)) and len(_value) == 3:
        try:
            _target.set_editor_property(_PROP, unreal.Vector(*[float(_v) for _v in _value]))
        except Exception:
            _target.set_editor_property(
                _PROP, unreal.LinearColor(*[float(_v) for _v in _value])
            )
    elif isinstance(_value, (list, tuple)) and len(_value) == 4:
        _target.set_editor_property(_PROP, unreal.LinearColor(*[float(_v) for _v in _value]))
    else:
        raise
return {
    "label": _LABEL,
    "property": _PROP,
    "value": str(_target.get_editor_property(_PROP)),
}""",
        ]
    )


def build_get_actor(label: str) -> str:
    return "\n".join(
        [
            f"_LABEL = {label!r}",
            _FIND_ACTOR,
            """\
_comps = []
for _c in _target.get_components_by_class(unreal.ActorComponent):
    _comps.append({"name": _c.get_name(), "class": _c.get_class().get_name()})
_actor = _target""",
            _ACTOR_INFO_RETURN.replace("return {", 'return {\n    "components": _comps,'),
        ]
    )


# ---------------------------------------------------------------- assets ----


def build_search_assets(
    root: str, query: str | None, class_filter: str | None, limit: int
) -> str:
    return f"""\
_root = {root!r}
_query = {query!r}
_class = {class_filter!r}
_limit = {int(limit)!r}
_paths = unreal.EditorAssetLibrary.list_assets(_root, recursive=True, include_folder=False)
_out = []
for _p in _paths:
    _object_path = str(_p)
    _name = _object_path.split("/")[-1].split(".")[0]
    if _query and _query.lower() not in _name.lower():
        continue
    _ad = unreal.EditorAssetLibrary.find_asset_data(_object_path)
    try:
        _cls = str(_ad.asset_class_path.asset_name)
    except Exception:
        _cls = str(_ad.get_editor_property("asset_class"))
    if _class and _class.lower() != _cls.lower():
        continue
    _out.append({{"path": _object_path.split(".")[0], "name": _name, "class": _cls}})
    if len(_out) >= _limit:
        break
return {{"count": len(_out), "assets": _out}}"""


def build_asset_info(path: str) -> str:
    return f"""\
_path = {path!r}
if not unreal.EditorAssetLibrary.does_asset_exist(_path):
    raise RuntimeError("No asset at %s" % _path)
_asset = unreal.EditorAssetLibrary.load_asset(_path)
_info = {{
    "path": _path,
    "name": _asset.get_name(),
    "class": _asset.get_class().get_name(),
}}
if isinstance(_asset, unreal.StaticMesh):
    _info["num_lods"] = _asset.get_num_lods()
    _mats = []
    for _m in _asset.static_materials:
        _mi = _m.material_interface
        _mats.append(_mi.get_path_name().split(".")[0] if _mi else None)
    _info["materials"] = _mats
if isinstance(_asset, unreal.Blueprint):
    try:
        _info["generated_class"] = _asset.generated_class().get_name()
    except Exception:
        pass
return _info"""


def build_import_asset(file_path: str, destination: str) -> str:
    return f"""\
_task = unreal.AssetImportTask()
_task.filename = {file_path!r}
_task.destination_path = {destination!r}
_task.automated = True
_task.save = True
_task.replace_existing = True
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([_task])
_paths = [str(_p) for _p in (_task.imported_object_paths or [])]
if not _paths:
    raise RuntimeError("Import produced no assets (unsupported format or bad source path?)")
return {{"imported": _paths}}"""


def build_create_folder(path: str) -> str:
    return f"""\
_path = {path!r}
if unreal.EditorAssetLibrary.does_directory_exist(_path):
    return {{"path": _path, "created": False, "existed": True}}
if not unreal.EditorAssetLibrary.make_directory(_path):
    raise RuntimeError("Could not create folder %s" % _path)
return {{"path": _path, "created": True}}"""


def build_duplicate_asset(source: str, destination: str) -> str:
    return f"""\
_dup = unreal.EditorAssetLibrary.duplicate_asset({source!r}, {destination!r})
if _dup is None:
    raise RuntimeError("Could not duplicate %s" % {source!r})
unreal.EditorAssetLibrary.save_asset({destination!r})
return {{"source": {source!r}, "destination": {destination!r}}}"""


def build_delete_asset(path: str) -> str:
    return f"""\
_path = {path!r}
if not unreal.EditorAssetLibrary.does_asset_exist(_path):
    raise RuntimeError("No asset at %s" % _path)
if not unreal.EditorAssetLibrary.delete_asset(_path):
    raise RuntimeError("Could not delete %s (still referenced?)" % _path)
return {{"deleted": _path}}"""


def build_save_dirty() -> str:
    return """\
unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
return {"saved": True}"""


# ------------------------------------------------------------- materials ----


def build_create_material(
    folder: str,
    name: str,
    base_color,
    metallic: float | None,
    roughness: float | None,
    emissive,
) -> str:
    lines = [
        f"_FOLDER = {folder!r}",
        f"_NAME = {name!r}",
        """\
_at = unreal.AssetToolsHelpers.get_asset_tools()
_mat = _at.create_asset(_NAME, _FOLDER, unreal.Material, unreal.MaterialFactoryNew())
if _mat is None:
    raise RuntimeError("Could not create material (does it already exist?)")
_mel = unreal.MaterialEditingLibrary""",
    ]
    if base_color is not None:
        r, g, b = (float(v) for v in base_color)
        lines.append(
            f"""\
_e = _mel.create_material_expression(_mat, unreal.MaterialExpressionConstant3Vector, -384, -200)
_e.set_editor_property("constant", unreal.LinearColor({r!r}, {g!r}, {b!r}, 1.0))
_mel.connect_material_property(_e, "", unreal.MaterialProperty.MP_BASE_COLOR)"""
        )
    if metallic is not None:
        lines.append(
            f"""\
_e = _mel.create_material_expression(_mat, unreal.MaterialExpressionConstant, -384, 0)
_e.set_editor_property("r", {float(metallic)!r})
_mel.connect_material_property(_e, "", unreal.MaterialProperty.MP_METALLIC)"""
        )
    if roughness is not None:
        lines.append(
            f"""\
_e = _mel.create_material_expression(_mat, unreal.MaterialExpressionConstant, -384, 120)
_e.set_editor_property("r", {float(roughness)!r})
_mel.connect_material_property(_e, "", unreal.MaterialProperty.MP_ROUGHNESS)"""
        )
    if emissive is not None:
        r, g, b = (float(v) for v in emissive)
        lines.append(
            f"""\
_e = _mel.create_material_expression(_mat, unreal.MaterialExpressionConstant3Vector, -384, 240)
_e.set_editor_property("constant", unreal.LinearColor({r!r}, {g!r}, {b!r}, 1.0))
_mel.connect_material_property(_e, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)"""
        )
    lines.append(
        """\
_mel.recompile_material(_mat)
unreal.EditorAssetLibrary.save_loaded_asset(_mat)
return {"path": _mat.get_path_name().split(".")[0], "name": _NAME}"""
    )
    return "\n".join(lines)


def build_create_material_instance(
    folder: str,
    name: str,
    parent_path: str,
    scalar_params: dict | None,
    vector_params: dict | None,
    texture_params: dict | None,
) -> str:
    return f"""\
_parent = unreal.load_asset({parent_path!r})
if _parent is None:
    raise RuntimeError("No parent material at %s" % {parent_path!r})
_factory = unreal.MaterialInstanceConstantFactoryNew()
_factory.set_editor_property("initial_parent", _parent)
_at = unreal.AssetToolsHelpers.get_asset_tools()
_mi = _at.create_asset({name!r}, {folder!r}, unreal.MaterialInstanceConstant, _factory)
if _mi is None:
    raise RuntimeError("Could not create material instance (does it already exist?)")
_mel = unreal.MaterialEditingLibrary
for _k, _v in ({scalar_params!r} or {{}}).items():
    _mel.set_material_instance_scalar_parameter_value(_mi, _k, float(_v))
for _k, _v in ({vector_params!r} or {{}}).items():
    _c = list(_v) + [1.0] * (4 - len(_v))
    _mel.set_material_instance_vector_parameter_value(
        _mi, _k, unreal.LinearColor(_c[0], _c[1], _c[2], _c[3])
    )
for _k, _v in ({texture_params!r} or {{}}).items():
    _t = unreal.load_asset(_v)
    if _t is None:
        raise RuntimeError("No texture at %s" % _v)
    _mel.set_material_instance_texture_parameter_value(_mi, _k, _t)
_mel.update_material_instance(_mi)
unreal.EditorAssetLibrary.save_loaded_asset(_mi)
return {{"path": _mi.get_path_name().split(".")[0], "parent": {parent_path!r}}}"""


def build_assign_material(label: str, material_path: str, slot: int) -> str:
    return "\n".join(
        [
            f"_LABEL = {label!r}",
            _FIND_ACTOR,
            f"""\
_mat = unreal.load_asset({material_path!r})
if _mat is None:
    raise RuntimeError("No material at %s" % {material_path!r})
_comps = _target.get_components_by_class(unreal.MeshComponent)
if not _comps:
    raise RuntimeError("Actor %r has no mesh components" % _LABEL)
_comps[0].set_material({int(slot)!r}, _mat)
return {{
    "label": _LABEL,
    "material": {material_path!r},
    "slot": {int(slot)!r},
    "component": _comps[0].get_name(),
}}""",
        ]
    )


# ------------------------------------------------------------ blueprints ----


def build_create_blueprint(folder: str, name: str, parent_class: str) -> str:
    return f"""\
_PARENT = {parent_class!r}
if _PARENT.startswith("/Script/"):
    _parent_cls = unreal.load_class(None, _PARENT)
else:
    _parent_bp = unreal.load_asset(_PARENT)
    _parent_cls = _parent_bp.generated_class() if _parent_bp else None
if _parent_cls is None:
    raise RuntimeError("Could not resolve parent class %s" % _PARENT)
_factory = unreal.BlueprintFactory()
_factory.set_editor_property("parent_class", _parent_cls)
_at = unreal.AssetToolsHelpers.get_asset_tools()
_bp = _at.create_asset({name!r}, {folder!r}, None, _factory)
if _bp is None:
    raise RuntimeError("Could not create blueprint (does it already exist?)")
unreal.EditorAssetLibrary.save_loaded_asset(_bp)
return {{"path": _bp.get_path_name().split(".")[0], "parent": _PARENT}}"""


def build_add_component(blueprint_path: str, component_class: str, name: str | None) -> str:
    return f"""\
_BP = {blueprint_path!r}
_COMP = {component_class!r}
_NEWNAME = {name!r}
_bp = unreal.load_asset(_BP)
if _bp is None:
    raise RuntimeError("No blueprint at %s" % _BP)
if _COMP.startswith("/Script/"):
    _comp_cls = unreal.load_class(None, _COMP)
else:
    _py_cls = getattr(unreal, _COMP, None)
    _comp_cls = _py_cls.static_class() if _py_cls else None
if _comp_cls is None:
    raise RuntimeError("Could not resolve component class %s" % _COMP)
_sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
_handles = _sds.k2_gather_subobject_data_for_blueprint(_bp)
if not _handles:
    raise RuntimeError("Blueprint has no root subobject to attach to")
_params = unreal.AddNewSubobjectParams(
    parent_handle=_handles[0], new_class=_comp_cls, blueprint_context=_bp
)
_handle, _fail = _sds.add_new_subobject(_params)
if not _handle.is_valid():
    raise RuntimeError("Could not add component: %s" % _fail)
if _NEWNAME:
    _sds.rename_subobject(_handle, unreal.Text(_NEWNAME))
try:
    unreal.BlueprintEditorLibrary.compile_blueprint(_bp)
except Exception:
    pass
unreal.EditorAssetLibrary.save_loaded_asset(_bp)
return {{"blueprint": _BP, "component_class": _COMP, "component_name": _NEWNAME}}"""


def build_set_blueprint_default(blueprint_path: str, property_name: str, value) -> str:
    return f"""\
_BP = {blueprint_path!r}
_bp = unreal.load_asset(_BP)
if _bp is None:
    raise RuntimeError("No blueprint at %s" % _BP)
_cdo = unreal.get_default_object(_bp.generated_class())
_cdo.set_editor_property({property_name!r}, {value!r})
try:
    unreal.BlueprintEditorLibrary.compile_blueprint(_bp)
except Exception:
    pass
unreal.EditorAssetLibrary.save_loaded_asset(_bp)
return {{
    "blueprint": _BP,
    "property": {property_name!r},
    "value": str(_cdo.get_editor_property({property_name!r})),
}}"""


# ---------------------------------------------------------------- levels ----


def build_open_level(path: str) -> str:
    return f"""\
_les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not _les.load_level({path!r}):
    raise RuntimeError("Could not load level %s" % {path!r})
return {{"level": {path!r}}}"""


def build_new_level(path: str, template: str | None) -> str:
    return f"""\
_les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
_template = {template!r}
if _template:
    _ok = _les.new_level_from_template({path!r}, _template)
else:
    _ok = _les.new_level({path!r})
if not _ok:
    raise RuntimeError("Could not create level %s" % {path!r})
return {{"level": {path!r}, "template": _template}}"""


# -------------------------------------------------------------- viewport ----


def build_set_camera(location, rotation) -> str:
    loc = [float(v) for v in location]
    rot = [float(v) for v in rotation]
    return f"""\
_ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
_ues.set_level_viewport_camera_info({_vector(location)}, {_rotator(rotation)})
return {{"location": {loc!r}, "rotation": {rot!r}}}"""


def build_get_camera() -> str:
    return """\
_ues = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
_info = _ues.get_level_viewport_camera_info()
if _info is None:
    raise RuntimeError("No active level viewport")
_loc, _rot = _info
return {
    "location": [_loc.x, _loc.y, _loc.z],
    "rotation": [_rot.roll, _rot.pitch, _rot.yaw],
}"""


def build_focus_actor(label: str) -> str:
    return "\n".join(
        [
            f"_LABEL = {label!r}",
            _FIND_ACTOR,
            """\
_subsys.set_selected_level_actors([_target])
unreal.SystemLibrary.execute_console_command(None, "CAMERA ALIGN ACTIVEVIEWPORTONLY")
return {"focused": _LABEL}""",
        ]
    )


def build_screenshot(width: int, height: int) -> str:
    return f"""\
_dir = unreal.Paths.convert_relative_path_to_full(unreal.Paths.screen_shot_dir())
unreal.SystemLibrary.execute_console_command(
    None, "HighResShot %dx%d" % ({int(width)!r}, {int(height)!r})
)
return {{"dir": _dir}}"""


# ------------------------------------------------------------------- pie ----


def build_start_play() -> str:
    return """\
_les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
_les.editor_play_simulate()
return {"playing": True, "mode": "simulate"}"""


def build_stop_play() -> str:
    return """\
_les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
_les.editor_request_end_play_map()
return {"playing": False}"""
