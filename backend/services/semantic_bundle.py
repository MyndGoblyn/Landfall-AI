"""Versioned deterministic registries used by the recommendation engine."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, Mapping


SEMANTIC_BUNDLE_SCHEMA_VERSION = 2
RESOURCE_FILES = {
    "mechanics_registry": "mechanics_registry.json",
    "archetype_registry": "archetype_signal_registry.json",
    "competitive_registry": "competitive_card_labels.json",
    "commander_profile_registry": "commander_profiles.json",
}


def _canonical_bytes(value) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def validate_semantic_bundle(payload: Mapping) -> Dict:
    if not isinstance(payload, Mapping):
        raise ValueError("Semantic bundle must be a JSON object")
    if int(payload.get("schema_version") or 0) != SEMANTIC_BUNDLE_SCHEMA_VERSION:
        raise ValueError("Unsupported semantic bundle schema")
    version = payload.get("semantic_version")
    if not isinstance(version, str) or not version.startswith("semantic:"):
        raise ValueError("Semantic bundle has no valid version")
    resources = payload.get("resources")
    hashes = payload.get("resource_sha256")
    if not isinstance(resources, Mapping) or not isinstance(hashes, Mapping):
        raise ValueError("Semantic bundle resources are missing")

    normalized_resources = {}
    for name in RESOURCE_FILES:
        resource = resources.get(name)
        if name in {
            "mechanics_registry",
            "archetype_registry",
            "commander_profile_registry",
        }:
            if not isinstance(resource, list):
                raise ValueError(f"Semantic resource {name} must be an array")
        elif not isinstance(resource, Mapping):
            raise ValueError(f"Semantic resource {name} must be an object")
        digest = hashlib.sha256(_canonical_bytes(resource)).hexdigest()
        if hashes.get(name) != digest:
            raise ValueError(f"Semantic resource {name} checksum is invalid")
        normalized_resources[name] = resource

    bundle_digest = hashlib.sha256(
        _canonical_bytes(normalized_resources)
    ).hexdigest()
    if version != f"semantic:{bundle_digest}":
        raise ValueError("Semantic bundle version does not match its resources")
    return {
        **dict(payload),
        "resources": normalized_resources,
        "resource_sha256": dict(hashes),
    }


def build_semantic_bundle(data_dir: Path, generated_at: str | None = None) -> Dict:
    resources = {}
    hashes = {}
    for name, filename in RESOURCE_FILES.items():
        path = data_dir / filename
        with path.open("r", encoding="utf-8") as handle:
            resources[name] = json.load(handle)
        hashes[name] = hashlib.sha256(
            _canonical_bytes(resources[name])
        ).hexdigest()
    version = hashlib.sha256(_canonical_bytes(resources)).hexdigest()
    return validate_semantic_bundle({
        "schema_version": SEMANTIC_BUNDLE_SCHEMA_VERSION,
        "semantic_version": f"semantic:{version}",
        "generated_at": generated_at,
        "resource_sha256": hashes,
        "resources": resources,
    })


def load_semantic_bundle(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as handle:
        return validate_semantic_bundle(json.load(handle))
