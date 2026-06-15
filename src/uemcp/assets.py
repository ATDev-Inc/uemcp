"""External asset-library providers.

A provider knows how to search a web catalog and download an asset to a local
file that Unreal can import. Providers are pure Python: no Unreal dependency and
no third-party packages (stdlib ``urllib``/``zipfile`` only), so they are fully
unit-testable. The MCP layer downloads with a provider, then reuses the normal
``ue_import_asset`` path to bring the file into the project.

Implemented here: Sketchfab. The :class:`AssetProvider` interface is the
extension point for further providers (AI generation such as Meshy, and
Fab/Quixel Megascans) -- they subclass it and register in ``_PROVIDERS``.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass

_USER_AGENT = "uemcp-asset-client"
_HTTP_TIMEOUT = 60.0
_MODEL_EXTS = (".gltf", ".glb", ".fbx", ".obj")  # in UE import preference order
_MAX_ARCHIVE_BYTES = 1024 * 1024 * 1024  # 1 GB uncompressed cap (zip-bomb guard)
_MAX_ARCHIVE_MEMBERS = 10000


class AssetProviderError(RuntimeError):
    """A provider could not search or download (auth, network, or no results)."""


@dataclass
class AssetHit:
    uid: str
    name: str
    author: str = ""
    license: str = ""
    face_count: int | None = None
    downloadable: bool = True

    def as_dict(self) -> dict:
        return {
            "uid": self.uid,
            "name": self.name,
            "author": self.author,
            "license": self.license,
            "face_count": self.face_count,
            "downloadable": self.downloadable,
        }


def _require_https(url: str) -> None:
    """Only fetch over https. Blocks file://, ftp://, and plain-http SSRF from a
    download URL that arrived in (untrusted) API response JSON."""
    scheme = urllib.parse.urlparse(url).scheme.lower()
    if scheme != "https":
        raise AssetProviderError(f"Refusing to fetch non-https URL (scheme {scheme!r})")


def _get_json(url: str, headers: dict | None = None) -> dict:
    """GET a URL and parse JSON. Module-level so tests can monkeypatch it."""
    _require_https(url)
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise AssetProviderError(f"HTTP {exc.code} from {url}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise AssetProviderError(f"Could not reach {url}: {exc.reason}") from exc


def _download(url: str, dest_path: str) -> str:
    """Stream a URL to a local file. Module-level so tests can monkeypatch it."""
    _require_https(url)
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
            with open(dest_path, "wb") as fh:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    fh.write(chunk)
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as exc:
        # Don't leave a truncated/empty file behind for a later import to choke on.
        try:
            os.remove(dest_path)
        except OSError:
            pass
        raise AssetProviderError(f"Download failed from {url}: {exc}") from exc
    return dest_path


def _post_json(url: str, payload: dict, headers: dict | None = None) -> dict:
    """POST a JSON body and parse the JSON response. Monkeypatched in tests."""
    _require_https(url)
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"User-Agent": _USER_AGENT, "Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise AssetProviderError(f"HTTP {exc.code} from {url}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise AssetProviderError(f"Could not reach {url}: {exc.reason}") from exc


def _extract_model(archive_path: str, dest_dir: str) -> str:
    """Unzip a downloaded model archive and return the best importable file."""
    extract_dir = os.path.join(dest_dir, "model")
    with zipfile.ZipFile(archive_path) as zf:
        infos = zf.infolist()
        if len(infos) > _MAX_ARCHIVE_MEMBERS:
            raise AssetProviderError(f"Archive has too many entries ({len(infos)})")
        total = sum(i.file_size for i in infos)
        if total > _MAX_ARCHIVE_BYTES:
            raise AssetProviderError(f"Refusing to extract {total} bytes (zip-bomb guard)")
        zf.extractall(extract_dir)
    found: dict[str, str] = {}
    for root, _dirs, files in os.walk(extract_dir):
        for name in files:
            ext = os.path.splitext(name)[1].lower()
            if ext in _MODEL_EXTS and ext not in found:
                found[ext] = os.path.join(root, name)
    for ext in _MODEL_EXTS:
        if ext in found:
            return found[ext]
    raise AssetProviderError(f"No importable model ({', '.join(_MODEL_EXTS)}) in {archive_path}")


class AssetProvider(ABC):
    """Search a web catalog and download an asset to a local file UE can import."""

    name: str = "asset"

    @abstractmethod
    def search(self, query: str, limit: int = 20) -> list[AssetHit]:
        """Return matching assets. ``uid`` of a hit feeds :meth:`download`."""

    @abstractmethod
    def download(self, uid: str, dest_dir: str) -> str:
        """Download asset ``uid`` into ``dest_dir``; return a local path to import."""


class SketchfabProvider(AssetProvider):
    """Sketchfab: search is public; download needs ``SKETCHFAB_API_TOKEN``."""

    name = "sketchfab"
    SEARCH_URL = "https://api.sketchfab.com/v3/search"
    MODEL_URL = "https://api.sketchfab.com/v3/models"

    def __init__(self, token: str | None = None):
        self.token = token if token is not None else os.environ.get("SKETCHFAB_API_TOKEN")

    def _auth_headers(self) -> dict:
        if not self.token:
            raise AssetProviderError(
                "Sketchfab download needs an API token. Set SKETCHFAB_API_TOKEN "
                "(create one under sketchfab.com > Settings > API)."
            )
        return {"Authorization": f"Token {self.token}"}

    def search(self, query: str, limit: int = 20) -> list[AssetHit]:
        params = urllib.parse.urlencode(
            {
                "type": "models",
                "q": query,
                "downloadable": "true",
                "count": max(1, min(int(limit), 24)),
            }
        )
        data = _get_json(f"{self.SEARCH_URL}?{params}")
        hits: list[AssetHit] = []
        for model in data.get("results") or []:
            user = model.get("user")
            user = user if isinstance(user, dict) else {}
            lic = model.get("license") or {}
            hits.append(
                AssetHit(
                    uid=model.get("uid", ""),
                    name=model.get("name", "(unnamed)"),
                    author=user.get("displayName") or user.get("username", ""),
                    license=lic.get("label", "") if isinstance(lic, dict) else "",
                    face_count=model.get("faceCount"),
                    downloadable=bool(model.get("isDownloadable", True)),
                )
            )
        return hits

    def download(self, uid: str, dest_dir: str) -> str:
        info = _get_json(f"{self.MODEL_URL}/{uid}/download", headers=self._auth_headers())
        gltf = info.get("gltf") or {}
        url = gltf.get("url")
        if not url:
            raise AssetProviderError(f"No glTF download available for Sketchfab model {uid}")
        os.makedirs(dest_dir, exist_ok=True)
        archive = os.path.join(dest_dir, f"{uid}.zip")
        _download(url, archive)
        return _extract_model(archive, dest_dir)


class GenerativeProvider(ABC):
    """Generate a 3D asset from a prompt, then download the finished file to import.

    Generation is asynchronous: :meth:`generate` starts a task and returns its id,
    :meth:`status` polls it, and :meth:`download` fetches the model once it has
    succeeded -- the same local-file-then-``ue_import_asset`` contract that the
    catalog providers use.
    """

    name: str = "generative"

    @abstractmethod
    def generate(self, prompt: str, **opts) -> str:
        """Start a generation task; return its task id."""

    @abstractmethod
    def status(self, task_id: str) -> dict:
        """Return ``{task_id, status, progress, ...}`` for a task."""

    @abstractmethod
    def download(self, task_id: str, dest_dir: str, file_format: str = "glb") -> str:
        """Download the finished model into ``dest_dir``; return a local path to import."""


class MeshyProvider(GenerativeProvider):
    """Meshy text-to-3D generation. Needs ``MESHY_API_KEY``."""

    name = "meshy"
    TEXT_URL = "https://api.meshy.ai/openapi/v2/text-to-3d"
    _FORMATS = ("glb", "fbx", "obj", "usdz")
    _ART_STYLES = ("realistic", "sculpture")

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key if api_key is not None else os.environ.get("MESHY_API_KEY")

    def _auth_headers(self) -> dict:
        if not self.api_key:
            raise AssetProviderError(
                "Meshy generation needs an API key. Set MESHY_API_KEY "
                "(create one at meshy.ai > Settings > API)."
            )
        return {"Authorization": f"Bearer {self.api_key}"}

    def generate(self, prompt: str, art_style: str = "realistic", mode: str = "preview") -> str:
        if art_style not in self._ART_STYLES:
            raise AssetProviderError(f"art_style must be one of {', '.join(self._ART_STYLES)}")
        payload = {"mode": mode, "prompt": prompt, "art_style": art_style}
        data = _post_json(self.TEXT_URL, payload, headers=self._auth_headers())
        task_id = data.get("result") or data.get("id")
        if not task_id:
            raise AssetProviderError(f"Meshy did not return a task id: {data}")
        return str(task_id)

    def status(self, task_id: str) -> dict:
        data = _get_json(f"{self.TEXT_URL}/{task_id}", headers=self._auth_headers())
        return {
            "task_id": task_id,
            "status": data.get("status", "UNKNOWN"),
            "progress": data.get("progress", 0),
            "model_urls": data.get("model_urls") or {},
        }

    def download(self, task_id: str, dest_dir: str, file_format: str = "glb") -> str:
        fmt = file_format.lower()
        if fmt not in self._FORMATS:
            raise AssetProviderError(
                f"Unsupported Meshy format {file_format!r}; pick one of {', '.join(self._FORMATS)}"
            )
        info = self.status(task_id)
        if info["status"] != "SUCCEEDED":
            raise AssetProviderError(
                f"Meshy task {task_id} is {info['status']} ({info['progress']}%); "
                "not ready to import yet -- poll ue_generation_status until SUCCEEDED."
            )
        url = info["model_urls"].get(fmt)
        if not url:
            have = ", ".join(info["model_urls"]) or "none"
            raise AssetProviderError(f"Meshy task {task_id} has no {fmt} output. Available: {have}")
        os.makedirs(dest_dir, exist_ok=True)
        return _download(url, os.path.join(dest_dir, f"{task_id}.{fmt}"))


_PROVIDERS: dict[str, type[AssetProvider]] = {
    "sketchfab": SketchfabProvider,
}


def get_provider(name: str) -> AssetProvider:
    cls = _PROVIDERS.get(name.lower())
    if cls is None:
        known = ", ".join(sorted(_PROVIDERS)) or "(none)"
        raise AssetProviderError(f"Unknown asset provider {name!r}. Known: {known}")
    return cls()


def provider_status() -> list[dict]:
    """Report each provider and whether its download credentials are configured."""
    return [
        {
            "name": "sketchfab",
            "kind": "catalog (search + download)",
            "search": "public (no token needed)",
            "download_ready": bool(os.environ.get("SKETCHFAB_API_TOKEN")),
            "token_env": "SKETCHFAB_API_TOKEN",
        },
        {
            "name": "meshy",
            "kind": "generative (text-to-3D)",
            "search": "n/a",
            "download_ready": bool(os.environ.get("MESHY_API_KEY")),
            "token_env": "MESHY_API_KEY",
        },
    ]
