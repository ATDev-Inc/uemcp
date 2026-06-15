"""Pure-function tests for the headless Movie Render Queue helper."""

import pytest

from uemcp import render


def test_resolve_output_classes_known():
    assert render.resolve_output_classes("png") == ["MoviePipelineImageSequenceOutput_PNG"]
    assert render.resolve_output_classes(".PNG") == ["MoviePipelineImageSequenceOutput_PNG"]
    assert render.resolve_output_classes("prores") == ["MoviePipelineAppleProResOutput"]


def test_resolve_output_classes_mp4_adds_encoder():
    classes = render.resolve_output_classes("mp4")
    assert "MoviePipelineCommandLineEncoder" in classes
    assert any("ImageSequence" in c for c in classes)


def test_resolve_output_classes_unknown():
    with pytest.raises(ValueError):
        render.resolve_output_classes("gif")


def test_to_object_path():
    assert render.to_object_path("/Game/Cine/Cfg") == "/Game/Cine/Cfg.Cfg"
    assert render.to_object_path("/Game/Cine/Cfg.Cfg") == "/Game/Cine/Cfg.Cfg"


def test_validate_object_path_accepts_content_paths():
    assert render.validate_object_path("/Game/Cine/Seq", "x") == "/Game/Cine/Seq"
    assert render.validate_object_path("/Game/Maps/Main.Main", "x") == "/Game/Maps/Main.Main"


@pytest.mark.parametrize(
    "bad",
    [
        '/Game/Cfg -ExecCmds="py x"',  # the injection payload
        "/Game/Cfg -windowed",
        "/Game/a b",  # any whitespace
        "Game/NoLeadingSlash",
        "-Game/LeadingDash",
        "/Game/Cfg=1",
        '/Game/Cfg"x',
        "",
    ],
)
def test_validate_object_path_rejects_injection(bad):
    with pytest.raises(ValueError):
        render.validate_object_path(bad, "x")


def test_build_headless_command():
    cmd = render.build_headless_command(
        "UnrealEditor-Cmd.exe",
        "C:/p/My.uproject",
        "/Game/Maps/Main",
        "/Game/Cine/Seq.Seq",
        "/Game/Cine/Cfg.Cfg",
        [1280, 720],
    )
    assert cmd[0] == "UnrealEditor-Cmd.exe"
    assert "C:/p/My.uproject" in cmd
    assert "/Game/Maps/Main" in cmd
    for flag in ("-game", "-RenderOffscreen", "-resx=1280", "-resy=720"):
        assert flag in cmd
    assert "-LevelSequence=/Game/Cine/Seq.Seq" in cmd
    assert "-MoviePipelineConfig=/Game/Cine/Cfg.Cfg" in cmd


def test_build_headless_command_default_resolution():
    cmd = render.build_headless_command("e", "p", "m", "s", "c", None)
    assert "-resx=1920" in cmd
    assert "-resy=1080" in cmd


def test_resolve_editor_cmd_env_override(monkeypatch):
    monkeypatch.setenv("UEMCP_EDITOR_CMD", "X-Cmd.exe")
    assert render.resolve_editor_cmd("whatever.exe") == "X-Cmd.exe"


def test_resolve_editor_cmd_requires_exe(monkeypatch):
    monkeypatch.delenv("UEMCP_EDITOR_CMD", raising=False)
    with pytest.raises(RuntimeError):
        render.resolve_editor_cmd(None)


def test_resolve_editor_cmd_prefers_cmd_variant(monkeypatch, tmp_path):
    monkeypatch.delenv("UEMCP_EDITOR_CMD", raising=False)
    editor = tmp_path / "UnrealEditor.exe"
    editor.write_text("")
    cmd = tmp_path / "UnrealEditor-Cmd.exe"
    cmd.write_text("")
    assert render.resolve_editor_cmd(str(editor)) == str(cmd)


def test_resolve_editor_cmd_falls_back_without_cmd_variant(monkeypatch, tmp_path):
    monkeypatch.delenv("UEMCP_EDITOR_CMD", raising=False)
    editor = tmp_path / "UnrealEditor.exe"
    editor.write_text("")
    assert render.resolve_editor_cmd(str(editor)) == str(editor)


def test_collect_output_files(tmp_path):
    (tmp_path / "a.png").write_text("x")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.png").write_text("y")
    assert len(render.collect_output_files(str(tmp_path))) == 2


def test_collect_output_files_missing_or_none():
    assert render.collect_output_files("/no/such/dir") == []
    assert render.collect_output_files(None) == []
