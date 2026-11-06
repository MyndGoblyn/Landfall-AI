import json
import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from scripts.package_semantic_bundle import package_semantic_bundle
from services.enhanced_suggestion_engine import EnhancedSuggestionEngine
from services.semantic_bundle import load_semantic_bundle
from services.semantic_distribution import SemanticBundleDistribution


class FakeResponse:
    def __init__(self, content: bytes):
        self.content = content
        self.headers = {"Content-Length": str(len(content))}

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size: int):
        for offset in range(0, len(self.content), chunk_size):
            yield self.content[offset: offset + chunk_size]

    def close(self):
        return None


def _write_resources(path: Path, suffix: str = "") -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "mechanics_registry.json").write_text(
        json.dumps([{
            "name": f"Test Mechanic{suffix}",
            "aliases": [],
            "theme_family": "test",
        }]),
        encoding="utf-8",
    )
    (path / "archetype_signal_registry.json").write_text(
        json.dumps([{
            "id": f"test_archetype{suffix}",
            "name": "Test Archetype",
        }]),
        encoding="utf-8",
    )
    (path / "competitive_card_labels.json").write_text(
        json.dumps({
            "schema_version": 1,
            "version": f"test{suffix}",
            "cards": [{"name": f"Test Card{suffix}", "labels": []}],
            "power_outliers": [],
        }),
        encoding="utf-8",
    )
    (path / "commander_profiles.json").write_text(
        json.dumps([{
            "oracle_id": "test-oracle",
            "name": "Test Commander",
            "review_status": "reviewed",
            "reviewed_at": "2026-11-06",
            "confidence": "high",
            "game_plan": "Test a deterministic commander plan.",
            "archetype_ids": [],
            "supported_synergies": [],
            "playstyles": ["value"],
            "win_paths": ["Test path"],
            "support_needs": ["Test support"],
            "common_failure_modes": ["Test failure"],
            "anti_synergies": ["Test anti-synergy"],
            "evidence_sources": ["test"],
            "packages": [],
        }]),
        encoding="utf-8",
    )


def _remote(package: dict):
    manifest = Path(package["manifest_path"]).read_bytes()
    release = Path(package["release_path"]).read_bytes()
    release_url = "https://semantic.test/" + package["artifact"]["object_path"]

    def request_get(url, **_kwargs):
        if url == "https://semantic.test/catalog/semantic/manifest.json":
            return FakeResponse(manifest)
        if url == release_url:
            return FakeResponse(release)
        raise AssertionError(url)

    return request_get


def test_semantic_bundle_is_verified_distributed_and_atomically_loaded(tmp_path):
    data_dir = tmp_path / "data"
    _write_resources(data_dir)
    package = package_semantic_bundle(data_dir, tmp_path / "dist")
    bundle = load_semantic_bundle(
        _materialize_release(package, tmp_path / "bundle.json")
    )
    assert bundle["semantic_version"] == package["semantic_version"]

    target = tmp_path / "cache" / "semantic_bundle.json"
    distribution = SemanticBundleDistribution(
        "https://semantic.test/catalog/semantic/manifest.json",
        target,
        request_get=_remote(package),
    )
    result = distribution.refresh()
    assert result["changed"] is True
    distribution.commit()

    engine = EnhancedSuggestionEngine(scryfall_service=None)
    status = engine.reload_semantic_bundle(target)
    assert status["mechanics"] == 1
    assert status["archetypes"] == 1
    assert status["competitive_cards"] == 1
    assert status["commander_profiles"] == 1


def _materialize_release(package: dict, output: Path) -> Path:
    import gzip

    with gzip.open(package["release_path"], "rb") as source:
        output.write_bytes(source.read())
    return output
