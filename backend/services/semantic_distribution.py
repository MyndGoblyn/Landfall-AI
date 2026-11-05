"""Verified optional delivery of semantic registries from Cloudflare R2."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from urllib.parse import urljoin, urlparse

import requests

from services.semantic_bundle import (
    SEMANTIC_BUNDLE_SCHEMA_VERSION,
    load_semantic_bundle,
)


DEFAULT_PRODUCTION_SEMANTIC_MANIFEST_URL = (
    "https://landfallai.live/catalog/semantic/manifest.json"
)
MANIFEST_MAX_BYTES = 64 * 1024
DEFAULT_MAX_COMPRESSED_BYTES = 4 * 1024 * 1024
DEFAULT_MAX_UNCOMPRESSED_BYTES = 16 * 1024 * 1024
_RELEASE_PATH = re.compile(
    r"^catalog/semantic/releases/([0-9a-f]{64})\.json\.gz$"
)


class SemanticDistributionError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _positive(value: Any, field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise SemanticDistributionError(
            f"Semantic manifest {field} must be a positive integer"
        ) from exc
    if isinstance(value, bool) or parsed <= 0:
        raise SemanticDistributionError(
            f"Semantic manifest {field} must be a positive integer"
        )
    return parsed


def parse_semantic_manifest(payload: Any) -> Dict:
    if not isinstance(payload, dict):
        raise SemanticDistributionError("Semantic manifest must be an object")
    if payload.get("manifest_schema_version") != 1:
        raise SemanticDistributionError("Semantic manifest schema is unsupported")
    if payload.get("semantic_schema_version") != SEMANTIC_BUNDLE_SCHEMA_VERSION:
        raise SemanticDistributionError("Semantic bundle schema is unsupported")
    version = payload.get("semantic_version")
    if not isinstance(version, str) or not version.startswith("semantic:"):
        raise SemanticDistributionError("Semantic manifest has no valid version")
    artifact = payload.get("artifact")
    if not isinstance(artifact, dict) or artifact.get("compression") != "gzip":
        raise SemanticDistributionError("Semantic artifact must use gzip")
    compressed_sha = artifact.get("compressed_sha256")
    match = _RELEASE_PATH.fullmatch(str(artifact.get("object_path") or ""))
    if not match or match.group(1) != compressed_sha:
        raise SemanticDistributionError("Semantic release path is invalid")
    uncompressed_sha = artifact.get("uncompressed_sha256")
    if not isinstance(uncompressed_sha, str) or not re.fullmatch(
        r"[0-9a-f]{64}", uncompressed_sha
    ):
        raise SemanticDistributionError("Semantic checksum is invalid")
    normalized = dict(payload)
    normalized["artifact"] = {
        **artifact,
        "compressed_bytes": _positive(
            artifact.get("compressed_bytes"), "artifact.compressed_bytes"
        ),
        "uncompressed_bytes": _positive(
            artifact.get("uncompressed_bytes"), "artifact.uncompressed_bytes"
        ),
    }
    return normalized


class SemanticBundleDistribution:
    def __init__(
        self,
        manifest_url: str,
        target_path: str | Path,
        *,
        request_get: Callable[..., Any] = requests.get,
        timeout_seconds: int = 20,
        max_compressed_bytes: int = DEFAULT_MAX_COMPRESSED_BYTES,
        max_uncompressed_bytes: int = DEFAULT_MAX_UNCOMPRESSED_BYTES,
    ):
        parsed = urlparse(manifest_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Semantic manifest URL must be absolute HTTP(S)")
        if parsed.scheme != "https" and parsed.hostname not in {
            "localhost", "127.0.0.1",
        }:
            raise ValueError("Remote semantic manifests must use HTTPS")
        self.manifest_url = manifest_url
        self.target_path = Path(target_path).expanduser().resolve()
        self.sidecar_path = self.target_path.with_suffix(".manifest.json")
        self.previous_path = self.target_path.with_suffix(".previous")
        self.previous_sidecar_path = self.sidecar_path.with_suffix(".previous")
        self.request_get = request_get
        self.timeout_seconds = max(1, int(timeout_seconds))
        self.max_compressed_bytes = max(1, int(max_compressed_bytes))
        self.max_uncompressed_bytes = max(1, int(max_uncompressed_bytes))
        self._lock = threading.RLock()
        self._status = {
            "enabled": True,
            "state": "idle",
            "manifest_url": manifest_url,
            "target_path": str(self.target_path),
            "semantic_version": None,
            "last_attempt_at": None,
            "last_success_at": None,
            "last_error": None,
        }

    def _set_status(self, **values) -> None:
        with self._lock:
            self._status.update(values)

    def get_status(self) -> Dict:
        with self._lock:
            return dict(self._status)

    def _manifest(self) -> Dict:
        response = self.request_get(
            self.manifest_url,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "identity",
                "User-Agent": "LandfallAI/1.0 (semantic distribution)",
            },
            timeout=(10, self.timeout_seconds),
        )
        try:
            response.raise_for_status()
            content = response.content
            if len(content) > MANIFEST_MAX_BYTES:
                raise SemanticDistributionError("Semantic manifest is too large")
            return parse_semantic_manifest(json.loads(content))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SemanticDistributionError("Semantic manifest is invalid JSON") from exc
        finally:
            response.close()

    def _current_matches(self, manifest: Dict) -> bool:
        if not self.target_path.is_file() or not self.sidecar_path.is_file():
            return False
        try:
            local_manifest = parse_semantic_manifest(
                json.loads(self.sidecar_path.read_text(encoding="utf-8"))
            )
            load_semantic_bundle(self.target_path)
        except (OSError, ValueError, json.JSONDecodeError, SemanticDistributionError):
            return False
        artifact = manifest["artifact"]
        return (
            local_manifest["semantic_version"] == manifest["semantic_version"]
            and self.target_path.stat().st_size == artifact["uncompressed_bytes"]
            and _sha256(self.target_path) == artifact["uncompressed_sha256"]
        )

    def _download(self, manifest: Dict) -> Path:
        artifact = manifest["artifact"]
        if artifact["compressed_bytes"] > self.max_compressed_bytes:
            raise SemanticDistributionError("Compressed semantic bundle is too large")
        if artifact["uncompressed_bytes"] > self.max_uncompressed_bytes:
            raise SemanticDistributionError("Semantic bundle is too large")
        response = self.request_get(
            urljoin(self.manifest_url, "/" + artifact["object_path"]),
            headers={
                "Accept": "application/gzip, application/octet-stream",
                "Accept-Encoding": "identity",
                "User-Agent": "LandfallAI/1.0 (semantic distribution)",
            },
            stream=True,
            timeout=(10, self.timeout_seconds),
        )
        compressed_path = None
        output_path = None
        keep = False
        try:
            response.raise_for_status()
            self.target_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=self.target_path.parent, delete=False,
            ) as handle:
                compressed_path = Path(handle.name)
                digest = hashlib.sha256()
                size = 0
                for chunk in response.iter_content(256 * 1024):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > self.max_compressed_bytes:
                        raise SemanticDistributionError("Semantic download exceeded limit")
                    digest.update(chunk)
                    handle.write(chunk)
            if size != artifact["compressed_bytes"]:
                raise SemanticDistributionError("Semantic compressed size mismatch")
            if digest.hexdigest() != artifact["compressed_sha256"]:
                raise SemanticDistributionError("Semantic compressed checksum mismatch")

            with tempfile.NamedTemporaryFile(
                mode="wb", dir=self.target_path.parent, delete=False,
            ) as handle:
                output_path = Path(handle.name)
                digest = hashlib.sha256()
                size = 0
                with gzip.open(compressed_path, "rb") as source:
                    for chunk in iter(lambda: source.read(256 * 1024), b""):
                        size += len(chunk)
                        if size > self.max_uncompressed_bytes:
                            raise SemanticDistributionError("Semantic bundle exceeded limit")
                        digest.update(chunk)
                        handle.write(chunk)
            if size != artifact["uncompressed_bytes"]:
                raise SemanticDistributionError("Semantic uncompressed size mismatch")
            if digest.hexdigest() != artifact["uncompressed_sha256"]:
                raise SemanticDistributionError("Semantic checksum mismatch")
            bundle = load_semantic_bundle(output_path)
            if bundle["semantic_version"] != manifest["semantic_version"]:
                raise SemanticDistributionError("Semantic version mismatch")
            keep = True
            return output_path
        except (OSError, EOFError) as exc:
            raise SemanticDistributionError("Semantic artifact is not valid gzip") from exc
        finally:
            response.close()
            if compressed_path and compressed_path.exists():
                compressed_path.unlink()
            if output_path and output_path.exists() and not keep:
                output_path.unlink()

    def _restore(self) -> None:
        for target, previous in (
            (self.target_path, self.previous_path),
            (self.sidecar_path, self.previous_sidecar_path),
        ):
            if previous.exists():
                if target.exists():
                    target.unlink()
                os.replace(previous, target)
            elif target.exists():
                target.unlink()

    def refresh(self) -> Dict:
        self._set_status(
            state="refreshing", last_attempt_at=_utc_now(), last_error=None
        )
        downloaded: Optional[Path] = None
        try:
            manifest = self._manifest()
            if self._current_matches(manifest):
                self._ready(manifest)
                return {"changed": False, "manifest": manifest}
            downloaded = self._download(manifest)
            for target, previous in (
                (self.target_path, self.previous_path),
                (self.sidecar_path, self.previous_sidecar_path),
            ):
                if previous.exists():
                    previous.unlink()
                if target.exists():
                    os.replace(target, previous)
            try:
                os.replace(downloaded, self.target_path)
                downloaded = None
                sidecar_temp = None
                try:
                    with tempfile.NamedTemporaryFile(
                        mode="w",
                        encoding="utf-8",
                        dir=self.target_path.parent,
                        delete=False,
                    ) as handle:
                        sidecar_temp = Path(handle.name)
                        json.dump(manifest, handle, separators=(",", ":"))
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(sidecar_temp, self.sidecar_path)
                finally:
                    if sidecar_temp and sidecar_temp.exists():
                        sidecar_temp.unlink()
            except Exception:
                self._restore()
                raise
            self._ready(manifest)
            return {"changed": True, "manifest": manifest}
        except Exception as exc:
            self._set_status(state="degraded", last_error=str(exc))
            if isinstance(exc, SemanticDistributionError):
                raise
            raise SemanticDistributionError(str(exc)) from exc
        finally:
            if downloaded and downloaded.exists():
                downloaded.unlink()

    def _ready(self, manifest: Dict) -> None:
        self._set_status(
            state="ready",
            semantic_version=manifest["semantic_version"],
            last_success_at=_utc_now(),
            last_error=None,
        )

    def commit(self) -> None:
        for path in (self.previous_path, self.previous_sidecar_path):
            if path.exists():
                path.unlink()

    def rollback(self, reason: str) -> None:
        self._restore()
        self._set_status(state="degraded", last_error=reason)


def build_semantic_distribution_from_env(
    environment: str,
) -> Optional[SemanticBundleDistribution]:
    enabled = os.environ.get(
        "SEMANTIC_BUNDLE_REMOTE_ENABLED", "true"
    ).lower() == "true"
    manifest_url = os.environ.get("SEMANTIC_BUNDLE_MANIFEST_URL")
    if not manifest_url and environment == "production" and enabled:
        manifest_url = DEFAULT_PRODUCTION_SEMANTIC_MANIFEST_URL
    if not enabled or not manifest_url:
        return None
    configured_path = os.environ.get("SEMANTIC_BUNDLE_PATH")
    if configured_path:
        target = Path(configured_path)
    else:
        cache_root = Path(os.environ.get(
            "LANDFALL_CACHE_DIR",
            str(Path(tempfile.gettempdir()) / "landfallai"),
        ))
        target = cache_root / "semantic_bundle.json"
    return SemanticBundleDistribution(manifest_url, target)
