"""Create the immutable gzip artifact and manifest used by R2 distribution."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1]
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.card_catalog import CATALOG_SCHEMA_VERSION
from services.catalog_distribution import (
    CATALOG_MANIFEST_SCHEMA_VERSION,
    inspect_catalog_snapshot,
)


DEFAULT_SOURCE = BACKEND_PATH / "data" / "scryfall_oracle_cards.json"
DEFAULT_OUTPUT_DIR = BACKEND_PATH / "data" / "catalog_dist"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_catalog(source: Path, output_dir: Path) -> dict:
    source = source.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Catalog source does not exist: {source}")

    header, card_count = inspect_catalog_snapshot(source)
    if header.get("schema_version") != CATALOG_SCHEMA_VERSION:
        raise RuntimeError("Catalog source has an unsupported schema")
    catalog_version = header.get("catalog_version")
    if not isinstance(catalog_version, str) or not catalog_version:
        raise RuntimeError("Catalog source has no version")

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
                filename="scryfall_oracle_cards.json",
                mode="wb",
                fileobj=raw_handle,
                mtime=0,
            ) as gzip_handle, source.open("rb") as source_handle:
                shutil.copyfileobj(source_handle, gzip_handle, length=1024 * 1024)

        compressed_sha256 = _sha256_file(temporary_path)
        release_name = f"{compressed_sha256}.json.gz"
        release_path = releases_dir / release_name
        os.replace(temporary_path, release_path)
        temporary_path = None

        manifest = {
            "manifest_schema_version": CATALOG_MANIFEST_SCHEMA_VERSION,
            "catalog_schema_version": CATALOG_SCHEMA_VERSION,
            "catalog_version": catalog_version,
            "generated_at": header.get("generated_at"),
            "source_updated_at": header.get("source_updated_at"),
            "card_count": card_count,
            "artifact": {
                "object_path": f"catalog/releases/{release_name}",
                "compression": "gzip",
                "compressed_sha256": compressed_sha256,
                "uncompressed_sha256": _sha256_file(source),
                "compressed_bytes": release_path.stat().st_size,
                "uncompressed_bytes": source.stat().st_size,
            },
        }
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = output_dir / "manifest.json"
        manifest_temp = manifest_path.with_suffix(".json.tmp")
        manifest_text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
        manifest_temp.write_text(manifest_text, encoding="utf-8")
        os.replace(manifest_temp, manifest_path)

        manifests_dir = output_dir / "manifests"
        manifests_dir.mkdir(parents=True, exist_ok=True)
        versioned_manifest_path = manifests_dir / f"{compressed_sha256}.json"
        versioned_manifest_path.write_text(manifest_text, encoding="utf-8")
        return {
            "manifest_path": str(manifest_path),
            "versioned_manifest_path": str(versioned_manifest_path),
            "release_path": str(release_path),
            **manifest,
        }
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    result = package_catalog(args.source, args.output_dir)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
