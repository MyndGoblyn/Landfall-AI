"""Freeze the public real-deck validation set into immutable local snapshots."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from zoneinfo import ZoneInfo


BACKEND_PATH = Path(__file__).resolve().parents[1]
REPO_PATH = BACKEND_PATH.parent
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.card_catalog import slim_catalog_card
from services.deck_input_assessment import assess_deck_input
from services.deck_parser import DeckParser
from services.scryfall_service import ScryfallService


CASES = [
    ("01", "budget-yuriko", "https://moxfield.com/decks/GpLW-6jxdUGIavsSTPLSow"),
    ("02", "budget-lathril", "https://archidekt.com/decks/6718162/elf_ballin_on_a_budget_100_lathril_deck"),
    ("03", "budget-meren", "https://archidekt.com/decks/7225704/meren_of_clan_nel_toth_budget_edh"),
    ("04", "light-paws", "https://moxfield.com/decks/EpvBn69ncUOjs3V380PK3A"),
    ("05", "budget-talrand", "https://archidekt.com/decks/13291295/talrand_sky_summoner"),
    ("06", "political-zedruu", "https://archidekt.com/decks/5824399/zedruu_the_greathearted_budget_group_hug_deck"),
    ("07", "krenko", "https://moxfield.com/decks/o9Oh4asciUWyqDp0Ya6WwA"),
    ("08", "atraxa", "https://moxfield.com/decks/njMiTWJsREmUXPB4L97A3w"),
    ("09", "budget-wilhelt", "https://moxfield.com/decks/UXK30FVy5kupYBvxiEfcHA"),
    ("10", "budget-vadrik", "https://archidekt.com/decks/4665428/budget_cedh_vadrik_astral_archmage"),
    ("11", "muldrotha", "https://moxfield.com/decks/kTYAXLKbzUK41IgN_TBfjg"),
    ("12", "cedh-yuriko", "https://moxfield.com/decks/tr0JklmIcUSWM4ZqC5IaxA"),
    ("13", "cedh-najeela", "https://moxfield.com/decks/0NhQNtlEWkGJJWY3Jo_wJw"),
    ("14", "jank-zedruu", "https://archidekt.com/decks/330081/extreme_jank_bad_santa_zedruu"),
    ("15", "low-land-grist", "https://moxfield.com/decks/KACfZpvjC0SxiosNzIdIcQ"),
    ("16", "mountain-joke", "https://archidekt.com/decks/24600156/97_mountain_deck_fuk_u"),
    ("17", "unfinished-urza", "https://archidekt.com/decks/20910613/unfinished_urza_precon"),
    ("18", "partial-lathril", "https://archidekt.com/decks/1799945/lathril_budget_build"),
]
VALIDATION_TIMEZONE = ZoneInfo("America/New_York")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=(
            REPO_PATH
            / "tests"
            / "fixtures"
            / "real_deck_validation"
            / datetime.now(VALIDATION_TIMEZONE).date().isoformat()
        ),
    )
    return parser.parse_args()


def _json_bytes(value: Dict) -> bytes:
    return (
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _plain_text(snapshot: Dict) -> str:
    lines = [
        f"# LandfallAI real-deck validation snapshot {snapshot['case_id']}",
        f"# Frozen at {snapshot['fetched_at']}",
        f"# Source: {snapshot['source_url']}",
    ]
    if snapshot.get("commander"):
        lines.extend(["", "# Commander", f"1 {snapshot['commander']} *CMDR*"])
    lines.extend(["", "# Mainboard"])
    lines.extend(
        f"{int(card.get('qty', 1) or 1)} {card['name']}"
        for card in snapshot.get("cards") or []
    )
    return "\n".join(lines) + "\n"


async def freeze(output_dir: Path) -> Dict:
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError(
            f"Refusing to overwrite non-empty immutable snapshot directory: {output_dir}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    scryfall = ScryfallService()
    parser = DeckParser(scryfall)
    fetched_at = datetime.now(timezone.utc).isoformat()
    validation_date = datetime.now(VALIDATION_TIMEZONE).date().isoformat()
    index_rows: List[Dict] = []
    try:
        for case_id, slug, source_url in CASES:
            deck = await parser.parse_deck("url", source_url)
            commander = deck.get("commander")
            commander_card = (
                await scryfall.search_card(commander) if commander else None
            )
            snapshot = {
                "schema_version": 1,
                "case_id": case_id,
                "slug": slug,
                "fetched_at": fetched_at,
                "source_url": source_url,
                "source_platform": (
                    "moxfield" if "moxfield.com" in source_url else "archidekt"
                ),
                "commander": commander,
                "commander_card": (
                    slim_catalog_card(commander_card) if commander_card else None
                ),
                "color_identity": deck.get("color_identity") or [],
                "cards": deck.get("cards") or [],
            }
            assessment = assess_deck_input(snapshot)
            json_name = f"{case_id}-{slug}.json"
            text_name = f"{case_id}-{slug}.txt"
            json_payload = _json_bytes(snapshot)
            text_payload = _plain_text(snapshot).encode("utf-8")
            (output_dir / json_name).write_bytes(json_payload)
            (output_dir / text_name).write_bytes(text_payload)
            index_rows.append({
                "case_id": case_id,
                "slug": slug,
                "source_url": source_url,
                "snapshot_file": json_name,
                "plain_text_file": text_name,
                "snapshot_sha256": _sha256(json_payload),
                "plain_text_sha256": _sha256(text_payload),
                "commander": commander,
                "mainboard_cards": assessment["mainboard_cards"],
                "submitted_cards": assessment["submitted_cards"],
                "unique_cards": assessment["unique_cards"],
                "land_cards": assessment["land_cards"],
                "input_status": assessment["status"],
            })
    finally:
        await scryfall.close()

    index = {
        "schema_version": 1,
        "validation_date": validation_date,
        "fetched_at": fetched_at,
        "immutable": True,
        "deck_count": len(index_rows),
        "cases": index_rows,
    }
    index_payload = _json_bytes(index)
    (output_dir / "snapshot_index.json").write_bytes(index_payload)
    return index


def main() -> int:
    args = parse_args()
    index = asyncio.run(freeze(args.output_dir))
    print(json.dumps(index, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
