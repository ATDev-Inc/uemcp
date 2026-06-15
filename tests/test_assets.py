"""Asset-library providers: search parsing, auth gating, download+extract flow.

All HTTP is monkeypatched, so these run with no network and no API token.
"""

import zipfile

import pytest

from uemcp import assets
from uemcp.assets import AssetProviderError, SketchfabProvider, _extract_model


def test_sketchfab_search_parses_results(monkeypatch):
    captured = {}

    def fake_get_json(url, headers=None):
        captured["url"] = url
        return {
            "results": [
                {
                    "uid": "abc123",
                    "name": "Old Barrel",
                    "user": {"displayName": "Modeler Jane", "username": "jane"},
                    "license": {"label": "CC Attribution"},
                    "faceCount": 4200,
                    "isDownloadable": True,
                }
            ]
        }

    monkeypatch.setattr(assets, "_get_json", fake_get_json)
    hits = SketchfabProvider(token="t").search("barrel", limit=5)
    assert "q=barrel" in captured["url"] and "downloadable=true" in captured["url"]
    assert len(hits) == 1
    hit = hits[0]
    assert hit.uid == "abc123"
    assert hit.name == "Old Barrel"
    assert hit.author == "Modeler Jane"
    assert hit.license == "CC Attribution"
    assert hit.as_dict()["face_count"] == 4200


def test_sketchfab_search_tolerates_missing_fields(monkeypatch):
    monkeypatch.setattr(assets, "_get_json", lambda url, headers=None: {"results": [{"uid": "x"}]})
    (hit,) = SketchfabProvider(token="t").search("anything")
    assert hit.uid == "x"
    assert hit.name == "(unnamed)"
    assert hit.author == ""


def test_sketchfab_download_requires_token(monkeypatch):
    monkeypatch.delenv("SKETCHFAB_API_TOKEN", raising=False)
    with pytest.raises(AssetProviderError, match="SKETCHFAB_API_TOKEN"):
        SketchfabProvider(token=None).download("abc123", "/tmp/whatever")


def test_sketchfab_download_extracts_model(monkeypatch, tmp_path):
    monkeypatch.setattr(
        assets,
        "_get_json",
        lambda url, headers=None: {"gltf": {"url": "https://example/scene.zip"}},
    )

    def fake_download(url, dest_path):
        with zipfile.ZipFile(dest_path, "w") as zf:
            zf.writestr("scene.gltf", "{}")
            zf.writestr("textures/diffuse.png", b"x")
        return dest_path

    monkeypatch.setattr(assets, "_download", fake_download)
    result = SketchfabProvider(token="t").download("abc123", str(tmp_path))
    assert result.endswith("scene.gltf")


def test_extract_prefers_gltf_over_fbx(tmp_path):
    archive = tmp_path / "a.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("model.fbx", b"x")
        zf.writestr("model.gltf", b"{}")
    assert _extract_model(str(archive), str(tmp_path)).endswith("model.gltf")


def test_extract_raises_when_no_model(tmp_path):
    archive = tmp_path / "a.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("readme.txt", b"hello")
    with pytest.raises(AssetProviderError, match="No importable model"):
        _extract_model(str(archive), str(tmp_path))


def test_get_provider_unknown():
    with pytest.raises(AssetProviderError, match="Unknown asset provider"):
        assets.get_provider("nope")


def test_provider_status_reports_tokens(monkeypatch):
    monkeypatch.setenv("SKETCHFAB_API_TOKEN", "secret")
    monkeypatch.delenv("MESHY_API_KEY", raising=False)
    status = {p["name"]: p for p in assets.provider_status()}
    assert status["sketchfab"]["download_ready"] is True
    assert status["meshy"]["download_ready"] is False


# --- Meshy (generative) ---------------------------------------------------


def test_meshy_generate_returns_task_id(monkeypatch):
    from uemcp.assets import MeshyProvider

    captured = {}

    def fake_post(url, payload, headers=None):
        captured["url"], captured["payload"], captured["headers"] = url, payload, headers
        return {"result": "task-42"}

    monkeypatch.setattr(assets, "_post_json", fake_post)
    task_id = MeshyProvider(api_key="k").generate("a stone golem", mode="preview")
    assert task_id == "task-42"
    assert captured["payload"]["prompt"] == "a stone golem"
    assert captured["headers"]["Authorization"] == "Bearer k"


def test_meshy_generate_requires_key(monkeypatch):
    from uemcp.assets import MeshyProvider

    monkeypatch.delenv("MESHY_API_KEY", raising=False)
    with pytest.raises(AssetProviderError, match="MESHY_API_KEY"):
        MeshyProvider(api_key=None).generate("anything")


def test_meshy_status_parses(monkeypatch):
    from uemcp.assets import MeshyProvider

    monkeypatch.setattr(
        assets,
        "_get_json",
        lambda url, headers=None: {"status": "IN_PROGRESS", "progress": 37},
    )
    info = MeshyProvider(api_key="k").status("task-42")
    assert info["status"] == "IN_PROGRESS"
    assert info["progress"] == 37


def test_meshy_download_rejects_unfinished(monkeypatch):
    from uemcp.assets import MeshyProvider

    monkeypatch.setattr(
        assets, "_get_json", lambda url, headers=None: {"status": "PENDING", "progress": 0}
    )
    with pytest.raises(AssetProviderError, match="not ready"):
        MeshyProvider(api_key="k").download("task-42", "/tmp/x")


def test_meshy_download_fetches_finished_model(monkeypatch, tmp_path):
    from uemcp.assets import MeshyProvider

    monkeypatch.setattr(
        assets,
        "_get_json",
        lambda url, headers=None: {
            "status": "SUCCEEDED",
            "progress": 100,
            "model_urls": {"glb": "https://example/model.glb"},
        },
    )
    monkeypatch.setattr(assets, "_download", lambda url, dest: dest)
    out = MeshyProvider(api_key="k").download("task-42", str(tmp_path), file_format="glb")
    assert out.endswith("task-42.glb")


def test_meshy_download_missing_format(monkeypatch, tmp_path):
    from uemcp.assets import MeshyProvider

    monkeypatch.setattr(
        assets,
        "_get_json",
        lambda url, headers=None: {"status": "SUCCEEDED", "model_urls": {"glb": "u"}},
    )
    with pytest.raises(AssetProviderError, match="no fbx output"):
        MeshyProvider(api_key="k").download("task-42", str(tmp_path), file_format="fbx")


# --- hardening: https-only, zip-bomb cap, input validation ----------------


def test_download_rejects_non_https():
    with pytest.raises(AssetProviderError, match="non-https"):
        assets._download("http://example/model.glb", "ignored")


def test_get_json_rejects_file_url():
    with pytest.raises(AssetProviderError, match="non-https"):
        assets._get_json("file:///etc/passwd")


def test_extract_rejects_zip_bomb(monkeypatch, tmp_path):
    monkeypatch.setattr(assets, "_MAX_ARCHIVE_BYTES", 1)
    archive = tmp_path / "a.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("model.gltf", "{}")
    with pytest.raises(AssetProviderError, match="zip-bomb"):
        assets._extract_model(str(archive), str(tmp_path))


def test_meshy_generate_validates_art_style():
    from uemcp.assets import MeshyProvider

    with pytest.raises(AssetProviderError, match="art_style"):
        MeshyProvider(api_key="k").generate("x", art_style="cartoon")


def test_meshy_download_unsupported_format():
    from uemcp.assets import MeshyProvider

    with pytest.raises(AssetProviderError, match="Unsupported Meshy format"):
        MeshyProvider(api_key="k").download("t", "/tmp/x", file_format="stl")


def test_meshy_generate_payload_defaults(monkeypatch):
    from uemcp.assets import MeshyProvider

    captured = {}

    def fake_post(url, payload, headers=None):
        captured.update(payload)
        return {"result": "t"}

    monkeypatch.setattr(assets, "_post_json", fake_post)
    MeshyProvider(api_key="k").generate("a golem")
    assert captured["mode"] == "preview"
    assert captured["art_style"] == "realistic"


# --- error paths ----------------------------------------------------------


def test_sketchfab_download_no_gltf(monkeypatch, tmp_path):
    monkeypatch.setattr(assets, "_get_json", lambda url, headers=None: {})
    with pytest.raises(AssetProviderError, match="No glTF"):
        SketchfabProvider(token="t").download("uid", str(tmp_path))


def test_meshy_generate_no_task_id(monkeypatch):
    from uemcp.assets import MeshyProvider

    monkeypatch.setattr(assets, "_post_json", lambda url, payload, headers=None: {})
    with pytest.raises(AssetProviderError, match="did not return a task id"):
        MeshyProvider(api_key="k").generate("x")


def test_download_removes_partial_file_on_failure(monkeypatch, tmp_path):
    import urllib.request

    dest = tmp_path / "partial.bin"

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n):
            raise OSError("boom mid-stream")

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: FakeResp())
    with pytest.raises(AssetProviderError, match="Download failed"):
        assets._download("https://example/x.bin", str(dest))
    assert not dest.exists()
