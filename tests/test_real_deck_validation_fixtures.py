import hashlib
import json
import sys
from collections import Counter
from pathlib import Path


REPO_PATH = Path(__file__).resolve().parents[1]
BACKEND_PATH = REPO_PATH / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from scripts.run_real_deck_validation import _plain_snapshot_contents
from services.deck_intent import normalize_intent_profile
from services.deck_input_assessment import assess_deck_input


FIXTURE_DIR = (
    REPO_PATH
    / "tests"
    / "fixtures"
    / "real_deck_validation"
    / "2026-08-04"
)


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_immutable_snapshot_index_hashes_and_plain_text_contents_match():
    index = load_json(FIXTURE_DIR / "snapshot_index.json")

    assert index["immutable"]
    assert index["validation_date"] == "2026-08-04"
    assert index["deck_count"] == 18
    assert len(index["cases"]) == 18

    for case in index["cases"]:
        snapshot_path = FIXTURE_DIR / case["snapshot_file"]
        plain_path = FIXTURE_DIR / case["plain_text_file"]
        snapshot = load_json(snapshot_path)
        plain = _plain_snapshot_contents(plain_path)
        quantities = Counter({
            card["name"]: int(card.get("qty", 1) or 1)
            for card in snapshot["cards"]
        })

        assert sha256(snapshot_path) == case["snapshot_sha256"]
        assert sha256(plain_path) == case["plain_text_sha256"]
        assert plain["commander"] == snapshot["commander"]
        assert plain["cards"] == quantities
        assert sum(quantities.values()) == case["mainboard_cards"]
        assert len(quantities) == case["unique_cards"]


def test_review_manifest_intents_and_input_expectations_match_snapshots():
    manifest = load_json(FIXTURE_DIR / "review_manifest.json")

    assert len(manifest["cases"]) == 18
    for case in manifest["cases"]:
        snapshot = load_json(FIXTURE_DIR / case["snapshot_file"])
        normalize_intent_profile(case["intent_profile"])
        assessment = assess_deck_input(snapshot)
        expected = case["expected_input"]
        actual_codes = {issue["code"] for issue in assessment["issues"]}

        assert assessment["status"] == expected["status"]
        assert assessment["analysis_allowed"] == expected["analysis_allowed"]
        assert (
            assessment["recommendations_allowed"]
            == expected["recommendations_allowed"]
        )
        assert set(expected.get("issue_codes", [])) <= actual_codes


def test_baseline_reviewed_results_remain_immutable():
    results = load_json(FIXTURE_DIR / "review_results.json")
    counts = results["counts"]
    case_counts = Counter(case["result"] for case in results["case_results"])

    assert len(results["case_results"]) == 18
    assert counts["strict_passes"] == case_counts["pass"] == 6
    assert counts["partial"] == case_counts["partial"] == 2
    assert counts["failed"] == case_counts["fail"] == 10
    assert not results["passed"]
    assert len(results["changed_top_choice_reviews"]) == 12
    assert all(
        review["decision"] in {"approved", "defect"}
        for review in results["changed_top_choice_reviews"]
    )


def test_promotion_reviewed_results_and_machine_status_are_consistent():
    results = load_json(FIXTURE_DIR / "review_results_v2_promotion.json")
    status = load_json(
        REPO_PATH / "tests" / "fixtures" / "real_deck_validation_status.json"
    )
    counts = results["counts"]
    case_counts = Counter(case["result"] for case in results["case_results"])

    assert len(results["case_results"]) == 18
    assert counts["strict_passes"] == case_counts["pass"] == 18
    assert counts["partial"] == case_counts["partial"] == 0
    assert counts["failed"] == case_counts["fail"] == 0
    assert results["passed"]
    assert len(results["changed_top_choice_reviews"]) == 11
    assert all(
        review["decision"] == "approved"
        for review in results["changed_top_choice_reviews"]
    )
    assert status["validation_date"] == results["validation_date"]
    assert status["strict_passes"] == counts["strict_passes"]
    assert status["partial"] == counts["partial"]
    assert status["failed"] == counts["failed"]
    assert status["passed"]
    assert (REPO_PATH / status["report"]).is_file()
