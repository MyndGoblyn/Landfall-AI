import gzip
import json
import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from scripts.sync_scryfall_catalog import (
    _write_catalog,
    iter_json_array,
    iter_jsonl_gzip,
)


def test_bulk_array_parser_streams_across_small_unicode_chunks(tmp_path):
    source = tmp_path / "bulk.json"
    cards = [
        {"name": "Æther Adept", "oracle_text": "Return target creature."},
        {"name": "Opt", "oracle_text": "Scry 1. Draw a card."},
    ]
    source.write_text(json.dumps(cards, ensure_ascii=False), encoding="utf-8")

    parsed = list(iter_json_array(source, chunk_size=7))

    assert parsed == cards


def test_catalog_writer_emits_versioned_slim_snapshot(tmp_path):
    source = tmp_path / "bulk.json"
    output = tmp_path / "catalog.json"
    source.write_text(
        json.dumps(
            [
                {
                    "name": "Opt",
                    "oracle_text": "Scry 1. Draw a card.",
                    "type_line": "Instant",
                    "color_identity": ["U"],
                    "legalities": {"commander": "legal"},
                    "edhrec_rank": 50,
                    "purchase_uris": {"store": "unused"},
                }
            ]
        ),
        encoding="utf-8",
    )

    count = _write_catalog(
        source,
        output,
        {"updated_at": "2026-07-30T00:00:00Z"},
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert count == 1
    assert payload["schema_version"] == 1
    assert payload["catalog_version"] == "oracle_cards:2026-07-30T00:00:00Z"
    assert payload["cards"][0]["edhrec_rank"] == 50
    assert "purchase_uris" not in payload["cards"][0]


def test_current_scryfall_jsonl_gzip_format_streams_into_catalog(tmp_path):
    source = tmp_path / "bulk.jsonl.gz"
    output = tmp_path / "catalog.json"
    cards = [
        {"name": "Opt", "oracle_text": "Draw a card."},
        {"name": "Ponder", "oracle_text": "Shuffle, then draw a card."},
    ]
    with gzip.open(source, "wt", encoding="utf-8") as handle:
        for card in cards:
            handle.write(json.dumps(card) + "\n")

    assert list(iter_jsonl_gzip(source)) == cards
    count = _write_catalog(
        source,
        output,
        {"updated_at": "2026-07-30T00:00:00Z"},
        source_format="jsonl_gzip",
    )

    assert count == 2
    assert [card["name"] for card in json.loads(output.read_text())["cards"]] == [
        "Opt",
        "Ponder",
    ]
