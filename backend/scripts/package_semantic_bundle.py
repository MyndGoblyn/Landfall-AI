"""Create the immutable semantic-registry release served from R2."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1]
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.semantic_bundle import build_semantic_bundle


DEFAULT_DATA_DIR = BACKEND_PATH / "data"
DEFAULT_OUTPUT_DIR = BACKEND_PATH / "data" / "semantic_dist"


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def package_semantic_bundle(data_dir: Path, output_dir: Path) -> Dict:
    bundle = build_semantic_bundle(data_dir.resolve())
    raw = json.dumps(
        bundle,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    output_dir = output_dir.resolve()
    releases_dir = output_dir / "releases"
    releases_dir.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=".json.gz",
            dir=releases_dir,
            delete=False,
        ) as raw_handle:
            temporary_path = Path(raw_handle.name)
            with gzip.GzipFile(
                filename="semantic_bundle.json",
                mode="wb",
                fileobj=raw_handle,
                mtime=0,
            ) as compressed:
                compressed.write(raw)
        compressed_bytes = temporary_path.read_bytes()
        compressed_sha = _sha256(compressed_bytes)
        release_path = releases_dir / f"{compressed_sha}.json.gz"
        os.replace(temporary_path, release_path)
        temporary_path = None
        manifest = {
            "manifest_schema_version": 1,
            "semantic_schema_version": bundle["schema_version"],
            "semantic_version": bundle["semantic_version"],
            "generated_at": bundle.get("generated_at"),
            "resource_counts": {
                name: (
                    len(resource.get("cards") or [])
                    if name == "competitive_registry"
                    else len(resource)
                )
                for name, resource in bundle["resources"].items()
            },
            "artifact": {
                "object_path": f"catalog/semantic/releases/{release_path.name}",
                "compression": "gzip",
                "compressed_sha256": compressed_sha,
                "uncompressed_sha256": _sha256(raw),
                "compressed_bytes": len(compressed_bytes),
                "uncompressed_bytes": len(raw),
            },
        }
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return {
            "manifest_path": str(manifest_path),
            "release_path": str(release_path),
            **manifest,
        }
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    print(json.dumps(package_semantic_bundle(args.data_dir, args.output_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
