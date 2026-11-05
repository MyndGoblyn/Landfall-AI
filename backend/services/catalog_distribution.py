"""Validated distribution of the production card catalog from Cloudflare R2."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from urllib.parse import urljoin, urlparse

import requests

from services.card_catalog import CATALOG_SCHEMA_VERSION


CATALOG_MANIFEST_SCHEMA_VERSION = 1
DEFAULT_PRODUCTION_MANIFEST_URL = "https://landfallai.live/catalog/manifest.json"
DEFAULT_MAX_COMPRESSED_BYTES = 64 * 1024 * 1024
DEFAULT_MAX_UNCOMPRESSED_BYTES = 256 * 1024 * 1024
MANIFEST_MAX_BYTES = 64 * 1024
_RELEASE_PATH = re.compile(r"^catalog/releases/([0-9a-f]{64})\.json\.gz$")


class CatalogDistributionError(RuntimeError):
    """A remote artifact could not be safely promoted."""


@dataclass(frozen=True)
class CatalogRefreshResult:
    changed: bool
    manifest: Dict[str, Any]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise CatalogDistributionError(f"Manifest {field} must be a positive integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise CatalogDistributionError(
            f"Manifest {field} must be a positive integer"
        ) from exc
    if parsed <= 0:
        raise CatalogDistributionError(f"Manifest {field} must be a positive integer")
    return parsed


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _response_content_length(response: Any) -> Optional[int]:
    raw_value = response.headers.get("Content-Length")
    if raw_value is None:
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError) as exc:
        raise CatalogDistributionError(
            "Remote response has an invalid Content-Length"
        ) from exc


def _parse_manifest(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise CatalogDistributionError("Catalog manifest must be a JSON object")
    if payload.get("manifest_schema_version") != CATALOG_MANIFEST_SCHEMA_VERSION:
        raise CatalogDistributionError("Catalog manifest schema is unsupported")
    if payload.get("catalog_schema_version") != CATALOG_SCHEMA_VERSION:
        raise CatalogDistributionError("Catalog schema is unsupported")

    catalog_version = payload.get("catalog_version")
    if not isinstance(catalog_version, str) or not catalog_version.strip():
        raise CatalogDistributionError("Catalog manifest has no catalog version")
    artifact = payload.get("artifact")
    if not isinstance(artifact, dict):
        raise CatalogDistributionError("Catalog manifest has no artifact")
    if artifact.get("compression") != "gzip":
        raise CatalogDistributionError("Catalog artifact compression must be gzip")

    object_path = artifact.get("object_path")
    compressed_sha256 = artifact.get("compressed_sha256")
    uncompressed_sha256 = artifact.get("uncompressed_sha256")
    match = _RELEASE_PATH.fullmatch(str(object_path or ""))
    if not match or match.group(1) != compressed_sha256:
        raise CatalogDistributionError(
            "Catalog artifact path or compressed checksum is invalid"
        )
    if not isinstance(uncompressed_sha256, str) or not re.fullmatch(
        r"[0-9a-f]{64}", uncompressed_sha256
    ):
        raise CatalogDistributionError("Catalog artifact checksum is invalid")

    normalized = dict(payload)
    normalized["card_count"] = _positive_int(payload.get("card_count"), "card_count")
    normalized_artifact = dict(artifact)
    normalized_artifact["compressed_bytes"] = _positive_int(
        artifact.get("compressed_bytes"), "artifact.compressed_bytes"
    )
    normalized_artifact["uncompressed_bytes"] = _positive_int(
        artifact.get("uncompressed_bytes"), "artifact.uncompressed_bytes"
    )
    normalized["artifact"] = normalized_artifact
    return normalized


def inspect_catalog_snapshot(path: Path) -> tuple[Dict[str, Any], int]:
    """Validate the deterministic catalog envelope without retaining card objects."""
    with path.open("rb") as handle:
        prefix = handle.read(1024 * 1024)
        marker = re.search(rb",\s*\"cards\"\s*:\s*\[", prefix)
        if marker is None:
            raise CatalogDistributionError("Catalog snapshot has no cards array")
        try:
            header = json.loads(prefix[: marker.start()] + b"}")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CatalogDistributionError(
                "Catalog snapshot header is invalid"
            ) from exc
        handle.seek(marker.end())

        in_string = False
        escaped = False
        object_depth = 0
        card_count = 0
        array_ended = False
        trailing = bytearray()

        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            for index, value in enumerate(chunk):
                if array_ended:
                    trailing.extend(chunk[index:])
                    break
                if in_string:
                    if escaped:
                        escaped = False
                    elif value == 0x5C:
                        escaped = True
                    elif value == 0x22:
                        in_string = False
                    continue
                if value == 0x22:
                    in_string = True
                elif value == 0x7B:
                    object_depth += 1
                elif value == 0x7D:
                    object_depth -= 1
                    if object_depth < 0:
                        raise CatalogDistributionError(
                            "Catalog cards array is malformed"
                        )
                    if object_depth == 0:
                        card_count += 1
                elif object_depth == 0 and value == 0x5D:
                    array_ended = True
                elif object_depth == 0 and value not in b" \t\r\n,":
                    raise CatalogDistributionError(
                        "Catalog cards array contains a non-object value"
                    )

        if in_string or object_depth != 0 or not array_ended:
            raise CatalogDistributionError("Catalog cards array is incomplete")
        if bytes(trailing).strip() != b"}":
            raise CatalogDistributionError("Catalog snapshot has invalid trailing data")
        return header, card_count


class CatalogDistribution:
    """Download, verify, and atomically promote a catalog artifact."""

    def __init__(
        self,
        manifest_url: str,
        target_path: str | Path,
        *,
        request_get: Callable[..., Any] = requests.get,
        timeout_seconds: int = 30,
        max_compressed_bytes: int = DEFAULT_MAX_COMPRESSED_BYTES,
        max_uncompressed_bytes: int = DEFAULT_MAX_UNCOMPRESSED_BYTES,
    ):
        parsed_url = urlparse(manifest_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("Catalog manifest URL must be an absolute HTTP(S) URL")
        if parsed_url.scheme != "https" and parsed_url.hostname not in {
            "localhost",
            "127.0.0.1",
        }:
            raise ValueError("Remote catalog manifests must use HTTPS")
        self.manifest_url = manifest_url
        self.target_path = Path(target_path).expanduser().resolve()
        self.sidecar_path = self.target_path.with_suffix(
            self.target_path.suffix + ".manifest.json"
        )
        self.previous_path = self.target_path.with_suffix(
            self.target_path.suffix + ".previous"
        )
        self.previous_sidecar_path = self.sidecar_path.with_suffix(
            self.sidecar_path.suffix + ".previous"
        )
        self.request_get = request_get
        self.timeout_seconds = max(1, int(timeout_seconds))
        self.max_compressed_bytes = max(1, int(max_compressed_bytes))
        self.max_uncompressed_bytes = max(1, int(max_uncompressed_bytes))
        self._lock = threading.RLock()
        self._status: Dict[str, Any] = {
            "enabled": True,
            "state": "idle",
            "manifest_url": manifest_url,
            "target_path": str(self.target_path),
            "last_attempt_at": None,
            "last_success_at": None,
            "last_error": None,
            "catalog_version": None,
            "source_updated_at": None,
            "card_count": None,
            "artifact_sha256": None,
        }

    def _set_status(self, **values: Any) -> None:
        with self._lock:
            self._status.update(values)

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._status)

    def _request_manifest(self) -> Dict[str, Any]:
        response = self.request_get(
            self.manifest_url,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "identity",
                "User-Agent": "LandfallAI/1.0 (catalog distribution)",
            },
            timeout=(10, self.timeout_seconds),
        )
        try:
            response.raise_for_status()
            content_length = _response_content_length(response)
            if content_length is not None and content_length > MANIFEST_MAX_BYTES:
                raise CatalogDistributionError("Catalog manifest is unexpectedly large")
            content = response.content
            if len(content) > MANIFEST_MAX_BYTES:
                raise CatalogDistributionError("Catalog manifest is unexpectedly large")
            try:
                payload = json.loads(content)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise CatalogDistributionError(
                    "Catalog manifest is not valid JSON"
                ) from exc
            return _parse_manifest(payload)
        finally:
            response.close()

    def _current_matches(self, manifest: Dict[str, Any]) -> bool:
        if not self.target_path.is_file() or not self.sidecar_path.is_file():
            return False
        try:
            current_manifest = _parse_manifest(
                json.loads(self.sidecar_path.read_text(encoding="utf-8"))
            )
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            CatalogDistributionError,
        ):
            return False
        artifact = manifest["artifact"]
        return (
            current_manifest["artifact"]["uncompressed_sha256"]
            == artifact["uncompressed_sha256"]
            and self.target_path.stat().st_size == artifact["uncompressed_bytes"]
            and _sha256_file(self.target_path) == artifact["uncompressed_sha256"]
        )

    def _download_artifact(self, manifest: Dict[str, Any]) -> Path:
        artifact = manifest["artifact"]
        if artifact["compressed_bytes"] > self.max_compressed_bytes:
            raise CatalogDistributionError(
                "Compressed catalog exceeds the configured safety limit"
            )
        if artifact["uncompressed_bytes"] > self.max_uncompressed_bytes:
            raise CatalogDistributionError(
                "Catalog exceeds the configured safety limit"
            )

        artifact_url = urljoin(self.manifest_url, "/" + artifact["object_path"])
        response = self.request_get(
            artifact_url,
            headers={
                "Accept": "application/gzip, application/octet-stream",
                "Accept-Encoding": "identity",
                "User-Agent": "LandfallAI/1.0 (catalog distribution)",
            },
            stream=True,
            timeout=(10, self.timeout_seconds),
        )
        compressed_path: Optional[Path] = None
        output_path: Optional[Path] = None
        keep_output = False
        try:
            response.raise_for_status()
            content_length = _response_content_length(response)
            if (
                content_length is not None
                and content_length != artifact["compressed_bytes"]
            ):
                raise CatalogDistributionError(
                    "Compressed catalog size does not match its manifest"
                )
            self.target_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="wb",
                suffix=".catalog.json.gz",
                dir=self.target_path.parent,
                delete=False,
            ) as compressed_handle:
                compressed_path = Path(compressed_handle.name)
                compressed_digest = hashlib.sha256()
                compressed_bytes = 0
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    compressed_bytes += len(chunk)
                    if compressed_bytes > self.max_compressed_bytes:
                        raise CatalogDistributionError(
                            "Compressed catalog exceeded its safety limit"
                        )
                    compressed_digest.update(chunk)
                    compressed_handle.write(chunk)
            if compressed_bytes != artifact["compressed_bytes"]:
                raise CatalogDistributionError(
                    "Compressed catalog size does not match its manifest"
                )
            if compressed_digest.hexdigest() != artifact["compressed_sha256"]:
                raise CatalogDistributionError(
                    "Compressed catalog checksum does not match its manifest"
                )

            with tempfile.NamedTemporaryFile(
                mode="wb",
                suffix=".catalog.json",
                dir=self.target_path.parent,
                delete=False,
            ) as output_handle:
                output_path = Path(output_handle.name)
                output_digest = hashlib.sha256()
                output_bytes = 0
                try:
                    with gzip.open(compressed_path, "rb") as compressed_handle:
                        for chunk in iter(
                            lambda: compressed_handle.read(1024 * 1024), b""
                        ):
                            output_bytes += len(chunk)
                            if output_bytes > self.max_uncompressed_bytes:
                                raise CatalogDistributionError(
                                    "Catalog exceeded its safety limit"
                                )
                            output_digest.update(chunk)
                            output_handle.write(chunk)
                except (OSError, EOFError) as exc:
                    raise CatalogDistributionError(
                        "Catalog artifact is not valid gzip data"
                    ) from exc

            if output_bytes != artifact["uncompressed_bytes"]:
                raise CatalogDistributionError(
                    "Catalog size does not match its manifest"
                )
            if output_digest.hexdigest() != artifact["uncompressed_sha256"]:
                raise CatalogDistributionError(
                    "Catalog checksum does not match its manifest"
                )

            header, card_count = inspect_catalog_snapshot(output_path)
            if header.get("schema_version") != manifest["catalog_schema_version"]:
                raise CatalogDistributionError(
                    "Catalog snapshot schema does not match its manifest"
                )
            if header.get("catalog_version") != manifest["catalog_version"]:
                raise CatalogDistributionError(
                    "Catalog snapshot version does not match its manifest"
                )
            if header.get("source_updated_at") != manifest.get("source_updated_at"):
                raise CatalogDistributionError(
                    "Catalog source timestamp does not match its manifest"
                )
            if card_count != manifest["card_count"]:
                raise CatalogDistributionError(
                    "Catalog card count does not match its manifest"
                )
            keep_output = True
            return output_path
        finally:
            response.close()
            if compressed_path and compressed_path.exists():
                compressed_path.unlink()
            if output_path and output_path.exists() and not keep_output:
                output_path.unlink()

    def _promote(self, downloaded_path: Path, manifest: Dict[str, Any]) -> None:
        for stale_path in (self.previous_path, self.previous_sidecar_path):
            if stale_path.exists():
                stale_path.unlink()
        if self.target_path.exists():
            os.replace(self.target_path, self.previous_path)
        if self.sidecar_path.exists():
            os.replace(self.sidecar_path, self.previous_sidecar_path)

        sidecar_temp: Optional[Path] = None
        try:
            os.replace(downloaded_path, self.target_path)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix=".manifest.json",
                dir=self.target_path.parent,
                delete=False,
            ) as handle:
                sidecar_temp = Path(handle.name)
                json.dump(manifest, handle, ensure_ascii=False, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(sidecar_temp, self.sidecar_path)
        except Exception:
            self._restore_previous_files()
            raise
        finally:
            if sidecar_temp and sidecar_temp.exists():
                sidecar_temp.unlink()

    def _restore_previous_files(self) -> None:
        if self.previous_path.exists():
            if self.target_path.exists():
                self.target_path.unlink()
            os.replace(self.previous_path, self.target_path)
        elif self.target_path.exists():
            self.target_path.unlink()

        if self.previous_sidecar_path.exists():
            if self.sidecar_path.exists():
                self.sidecar_path.unlink()
            os.replace(self.previous_sidecar_path, self.sidecar_path)
        elif self.sidecar_path.exists():
            self.sidecar_path.unlink()

    def refresh(self) -> CatalogRefreshResult:
        self._set_status(
            state="refreshing", last_attempt_at=_utc_now(), last_error=None
        )
        downloaded_path: Optional[Path] = None
        try:
            manifest = self._request_manifest()
            if self._current_matches(manifest):
                self._set_ready(manifest)
                return CatalogRefreshResult(changed=False, manifest=manifest)
            downloaded_path = self._download_artifact(manifest)
            self._promote(downloaded_path, manifest)
            downloaded_path = None
            self._set_ready(manifest)
            return CatalogRefreshResult(changed=True, manifest=manifest)
        except Exception as exc:
            self._set_status(state="degraded", last_error=str(exc))
            if isinstance(exc, CatalogDistributionError):
                raise
            raise CatalogDistributionError(f"Catalog refresh failed: {exc}") from exc
        finally:
            if downloaded_path and downloaded_path.exists():
                downloaded_path.unlink()

    def _set_ready(self, manifest: Dict[str, Any]) -> None:
        self._set_status(
            state="ready",
            last_success_at=_utc_now(),
            last_error=None,
            catalog_version=manifest["catalog_version"],
            source_updated_at=manifest.get("source_updated_at"),
            card_count=manifest["card_count"],
            artifact_sha256=manifest["artifact"]["uncompressed_sha256"],
        )

    def commit(self) -> None:
        for backup_path in (self.previous_path, self.previous_sidecar_path):
            if backup_path.exists():
                backup_path.unlink()

    def rollback(self, reason: str) -> None:
        self._restore_previous_files()
        self._set_status(state="degraded", last_error=reason)


def build_catalog_distribution_from_env(
    environment: str,
) -> Optional[CatalogDistribution]:
    catalog_enabled = (
        os.environ.get("CANDIDATE_CATALOG_ENABLED", "true").lower() == "true"
    )
    enabled = catalog_enabled and (
        os.environ.get("CANDIDATE_CATALOG_REMOTE_ENABLED", "true").lower() == "true"
    )
    manifest_url = os.environ.get("SCRYFALL_CATALOG_MANIFEST_URL")
    if not manifest_url and environment == "production" and enabled:
        manifest_url = DEFAULT_PRODUCTION_MANIFEST_URL
    if not enabled or not manifest_url:
        return None

    configured_path = os.environ.get("SCRYFALL_CATALOG_PATH")
    if configured_path:
        target_path = Path(configured_path)
    else:
        cache_root = Path(
            os.environ.get(
                "LANDFALL_CACHE_DIR",
                str(Path(tempfile.gettempdir()) / "landfallai"),
            )
        )
        target_path = cache_root / "scryfall_oracle_cards.json"
    return CatalogDistribution(
        manifest_url,
        target_path,
        timeout_seconds=int(
            os.environ.get("CANDIDATE_CATALOG_REMOTE_TIMEOUT_SECONDS", "30")
        ),
        max_compressed_bytes=int(
            os.environ.get(
                "CANDIDATE_CATALOG_MAX_COMPRESSED_BYTES",
                str(DEFAULT_MAX_COMPRESSED_BYTES),
            )
        ),
        max_uncompressed_bytes=int(
            os.environ.get(
                "CANDIDATE_CATALOG_MAX_UNCOMPRESSED_BYTES",
                str(DEFAULT_MAX_UNCOMPRESSED_BYTES),
            )
        ),
    )
