"""Headless Movie Render Queue: format mapping and the offscreen render process.

The in-editor render path lives in `snippets.build_render_sequence`. This module
owns the local-process side: choosing the editor command-line executable,
building the argument list, running it, and collecting the produced files. The
command builder and format mapping are pure functions so they can be unit-tested
without launching Unreal.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

# output_format -> the unreal output-setting class(es) added to a Movie Pipeline
# config. mp4 has no built-in output node: it renders PNG frames and runs the
# project's configured command-line (ffmpeg) encoder over them.
FORMAT_SETTINGS = {
    "png": ["MoviePipelineImageSequenceOutput_PNG"],
    "jpg": ["MoviePipelineImageSequenceOutput_JPG"],
    "jpeg": ["MoviePipelineImageSequenceOutput_JPG"],
    "bmp": ["MoviePipelineImageSequenceOutput_BMP"],
    "exr": ["MoviePipelineImageSequenceOutput_EXR"],
    "prores": ["MoviePipelineAppleProResOutput"],
    "mp4": ["MoviePipelineImageSequenceOutput_PNG", "MoviePipelineCommandLineEncoder"],
}

VIDEO_FORMATS = {"prores", "mp4"}


def resolve_output_classes(output_format: str) -> list[str]:
    """Map an output_format to the unreal output-setting class names to add."""
    key = output_format.lower().lstrip(".")
    try:
        return list(FORMAT_SETTINGS[key])
    except KeyError:
        raise ValueError(
            f"Unknown output_format {output_format!r}; expected one of: "
            f"{', '.join(sorted(FORMAT_SETTINGS))}"
        ) from None


def resolve_editor_cmd(editor_exe: str | None) -> str:
    """Pick the editor command-line exe: UEMCP_EDITOR_CMD, else derive from editor_exe.

    `editor_exe` is the running editor's `sys.executable` (typically
    .../Binaries/Win64/UnrealEditor.exe); the headless renderer prefers the
    sibling UnrealEditor-Cmd variant when it exists.
    """
    override = os.environ.get("UEMCP_EDITOR_CMD")
    if override:
        return override
    if not editor_exe:
        raise RuntimeError(
            "Cannot locate the Unreal editor executable for a headless render. "
            "Set UEMCP_EDITOR_CMD to the path of UnrealEditor-Cmd."
        )
    path = Path(editor_exe)
    if path.stem.endswith("-Cmd"):
        return str(path)
    cmd = path.with_name(path.stem + "-Cmd" + path.suffix)
    return str(cmd) if cmd.exists() else str(path)


def to_object_path(asset_path: str) -> str:
    """Turn a content path (/Game/X/Cfg) into an object path (/Game/X/Cfg.Cfg)."""
    package = asset_path.split(".")[0]
    name = package.rstrip("/").rsplit("/", 1)[-1]
    return f"{package}.{name}"


def build_headless_command(
    editor_cmd: str,
    uproject: str,
    map_package: str,
    sequence_object: str,
    config_object: str,
    resolution,
) -> list[str]:
    """Build the UnrealEditor-Cmd argument list for an offscreen MRQ render.

    Uses the single-sequence form: the map is positional, the sequence is passed
    with -LevelSequence, and -MoviePipelineConfig points at a config preset.
    """
    res = [int(v) for v in (resolution or [1920, 1080])]
    return [
        editor_cmd,
        uproject,
        map_package,
        "-game",
        "-NoSplash",
        "-RenderOffscreen",
        "-Unattended",
        "-windowed",
        f"-resx={res[0]}",
        f"-resy={res[1]}",
        "-NoLoadingScreen",
        f"-LevelSequence={sequence_object}",
        f"-MoviePipelineConfig={config_object}",
    ]


def collect_output_files(output_dir: str | None, since: float | None = None) -> list[str]:
    """List files under output_dir, optionally only those modified since a time."""
    if not output_dir:
        return []
    base = Path(output_dir)
    if not base.exists():
        return []
    files = []
    for path in base.rglob("*"):
        if path.is_file() and (since is None or path.stat().st_mtime >= since):
            files.append(str(path))
    return sorted(files)


def run_headless(
    editor_cmd: str,
    uproject: str,
    map_package: str,
    sequence_object: str,
    config_object: str,
    resolution,
    output_dir: str | None,
    timeout: float,
) -> dict:
    """Run the offscreen render to completion and return its result."""
    command = build_headless_command(
        editor_cmd, uproject, map_package, sequence_object, config_object, resolution
    )
    proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    log = (proc.stdout or "") + (proc.stderr or "")
    return {
        "exit_code": proc.returncode,
        "command": command,
        "files": collect_output_files(output_dir),
        "log_tail": log[-4000:],
    }
