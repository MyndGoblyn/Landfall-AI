import gzip
import json
import sys
from pathlib import Path

import pytest


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from scripts.package_scryfall_catalog import package_catalog
from services.card_catalog import build_catalog_payload
from services.catalog_distribution import CatalogDistribution, CatalogDistributionError


def _card(name: str, oracle_id: str) -> dict:
    return {
        "name": name,
        "oracle_id": oracle_id,
        "type_line": "Artifact",
        "oracle_text": "Draw a card.",
        "cmc": 2,
        "colors": [],
        "color_identity": [],
        "legalities": {"commander": "legal"},
    }


def _write_catalog(path: Path, version: str, names: list[str]) -> None:
    payload = build_catalog_payload(
        [_card(name, f"oracle-{index}") for index, name in enumerate(names)],
        catalog_version=version,
        generated_at="2026-11-05T12:00:00+00:00",
        source_updated_at="2026-11-05T11:00:00+00:00",
    )
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


class FakeResponse:
    def __init__(self, content: bytes, content_type: str):
        self.content = content
        self.headers = {
            "Content-Length": str(len(content)),
            "Content-Type": content_type,
        }
        self.closed = False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size: int):
        for offset in range(0, len(self.content), chunk_size):
            yield self.content[offset : offset + chunk_size]

    def close(self):
        self.closed = True


def _remote(package: dict):
    manifest_bytes = Path(package["manifest_path"]).read_bytes()
    release_bytes = Path(package["release_path"]).read_bytes()
    artifact_url = "https://catalog.test/" + package["artifact"]["object_path"]

    def request_get(url, **_kwargs):
        if url == "https://catalog.test/catalog/manifest.json":
            return FakeResponse(manifest_bytes, "application/json")
        if url == artifact_url:
            return FakeResponse(release_bytes, "application/gzip")
        raise AssertionError(f"Unexpected URL: {url}")

    return request_get


def test_package_catalog_creates_deterministic_verified_artifact(tmp_path):
    source = tmp_path / "catalog.json"
    _write_catalog(source, "test-v1", ["Alpha", "Beta"])

    first = package_catalog(source, tmp_path / "dist")
    second = package_catalog(source, tmp_path / "dist-again")

    assert first["card_count"] == 2
    assert (
        first["artifact"]["compressed_sha256"]
        == second["artifact"]["compressed_sha256"]
    )
    assert first["artifact"]["object_path"].startswith("catalog/releases/")
    assert (
        Path(first["versioned_manifest_path"]).read_bytes()
        == Path(first["manifest_path"]).read_bytes()
    )
    with gzip.open(first["release_path"], "rb") as handle:
        assert handle.read() == source.read_bytes()


def test_distribution_promotes_and_reuses_a_verified_snapshot(tmp_path):
    source = tmp_path / "catalog.json"
    _write_catalog(source, "test-v1", ["Alpha", "Beta"])
    package = package_catalog(source, tmp_path / "dist")
    target = tmp_path / "cache" / "catalog.json"
    distribution = CatalogDistribution(
        "https://catalog.test/catalog/manifest.json",
        target,
        request_get=_remote(package),
    )

    first = distribution.refresh()
    assert first.changed is True
    assert target.read_bytes() == source.read_bytes()
    assert distribution.get_status()["state"] == "ready"
    distribution.commit()

    second = distribution.refresh()
    assert second.changed is False
    assert target.read_bytes() == source.read_bytes()


def test_distribution_rejects_corruption_without_replacing_last_good(tmp_path):
    old_source = tmp_path / "old.json"
    _write_catalog(old_source, "test-v1", ["Alpha"])
    old_package = package_catalog(old_source, tmp_path / "old-dist")
    target = tmp_path / "cache" / "catalog.json"
    distribution = CatalogDistribution(
        "https://catalog.test/catalog/manifest.json",
        target,
        request_get=_remote(old_package),
    )
    distribution.refresh()
    distribution.commit()

    new_source = tmp_path / "new.json"
    _write_catalog(new_source, "test-v2", ["Beta", "Gamma"])
    new_package = package_catalog(new_source, tmp_path / "new-dist")
    good_remote = _remote(new_package)

    def corrupt_remote(url, **kwargs):
        response = good_remote(url, **kwargs)
        if url.endswith(".json.gz"):
            response.content = response.content[:-1] + b"x"
        return response

    distribution.request_get = corrupt_remote
    with pytest.raises(CatalogDistributionError, match="checksum"):
        distribution.refresh()

    assert target.read_bytes() == old_source.read_bytes()
    assert distribution.get_status()["state"] == "degraded"


def test_distribution_can_roll_back_a_promoted_snapshot(tmp_path):
    old_source = tmp_path / "old.json"
    _write_catalog(old_source, "test-v1", ["Alpha"])
    old_package = package_catalog(old_source, tmp_path / "old-dist")
    target = tmp_path / "cache" / "catalog.json"
    distribution = CatalogDistribution(
        "https://catalog.test/catalog/manifest.json",
        target,
        request_get=_remote(old_package),
    )
    distribution.refresh()
    distribution.commit()

    new_source = tmp_path / "new.json"
    _write_catalog(new_source, "test-v2", ["Beta", "Gamma"])
    new_package = package_catalog(new_source, tmp_path / "new-dist")
    distribution.request_get = _remote(new_package)
    result = distribution.refresh()
    assert result.changed is True
    assert target.read_bytes() == new_source.read_bytes()

    distribution.rollback("simulated provider rejection")
    assert target.read_bytes() == old_source.read_bytes()
    assert distribution.get_status()["state"] == "degraded"
