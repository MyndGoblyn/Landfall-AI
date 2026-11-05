"""Download Scryfall oracle bulk data into LandFallAI's slim local catalog."""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import requests


BACKEND_PATH = Path(__file__).resolve().parents[1]
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from services.card_catalog import CATALOG_SCHEMA_VERSION, slim_catalog_card


BULK_DATA_URL = "https://api.scryfall.com/bulk-data"
DEFAULT_TARGET = BACKEND_PATH / "data" / "scryfall_oracle_cards.json"


def _headers():
    return {
        "User-Agent": os.environ.get(
            "SCRYFALL_USER_AGENT",
            "LandfallAI/1.0 (Commander recommendation catalog sync)",
        ),
        "Accept": "application/json;q=0.9,*/*;q=0.8",
    }


def _oracle_bulk_metadata() -> dict:
    response = requests.get(BULK_DATA_URL, headers=_headers(), timeout=30)
    response.raise_for_status()
    for item in response.json().get("data") or []:
        if item.get("type") == "oracle_cards":
            return item
    raise RuntimeError("Scryfall did not return an oracle_cards bulk-data entry")


def _download_bulk(download_uri: str, directory: Path) -> Path:
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=".scryfall-download",
            dir=directory,
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            with requests.get(
                download_uri,
                headers=_headers(),
                stream=True,
                timeout=(15, 180),
            ) as response:
                response.raise_for_status()
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        handle.write(chunk)

        return temporary_path
    except Exception:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()
        raise


def iter_json_array(path: Path, chunk_size: int = 1024 * 1024):
    """Yield objects from a large top-level JSON array without loading it all."""
    decoder = json.JSONDecoder()
    buffer = ""
    position = 0
    started = False
    expect_value = True
    eof = False

    with path.open("r", encoding="utf-8") as handle:
        while True:
            while position >= len(buffer) and not eof:
                chunk = handle.read(chunk_size)
                if chunk:
                    buffer = chunk
                    position = 0
                else:
                    eof = True

            while position < len(buffer) and buffer[position].isspace():
                position += 1

            if not started:
                if position >= len(buffer):
                    if eof:
                        raise RuntimeError("Scryfall bulk download was empty")
                    continue
                if buffer[position] != "[":
                    raise RuntimeError("Scryfall oracle bulk download was not a card list")
                position += 1
                started = True
                continue

            while position < len(buffer) and buffer[position].isspace():
                position += 1

            if not expect_value:
                if position >= len(buffer):
                    if eof:
                        raise RuntimeError("Scryfall bulk array ended unexpectedly")
                    chunk = handle.read(chunk_size)
                    buffer = buffer[position:] + chunk
                    position = 0
                    if not chunk:
                        eof = True
                    continue
                if buffer[position] == "]":
                    return
                if buffer[position] != ",":
                    raise RuntimeError("Scryfall bulk array has an invalid delimiter")
                position += 1
                expect_value = True
                continue

            while position < len(buffer) and buffer[position].isspace():
                position += 1
            if position < len(buffer) and buffer[position] == "]":
                return

            try:
                value, end = decoder.raw_decode(buffer, position)
            except json.JSONDecodeError as exc:
                if eof:
                    raise RuntimeError("Scryfall bulk array contains invalid JSON") from exc
                chunk = handle.read(chunk_size)
                buffer = buffer[position:] + chunk
                position = 0
                if not chunk:
                    eof = True
                continue

            yield value
            position = end
            expect_value = False


def iter_jsonl_gzip(path: Path):
    """Yield objects from Scryfall's current gzip-compressed JSONL format."""
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"Scryfall JSONL contains invalid JSON on line {line_number}"
                ) from exc


def _write_catalog(
    source_path: Path,
    output_path: Path,
    metadata: dict,
    source_format: str = "json_array",
) -> int:
    updated_at = metadata.get("updated_at")
    header = {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "catalog_version": f"oracle_cards:{updated_at or 'unknown'}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_updated_at": updated_at,
    }
    count = 0
    with output_path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(header, ensure_ascii=False, separators=(",", ":"))[:-1])
        handle.write(',"cards":[')
        records = (
            iter_jsonl_gzip(source_path)
            if source_format == "jsonl_gzip"
            else iter_json_array(source_path)
        )
        for raw_card in records:
            if not isinstance(raw_card, dict) or not raw_card.get("name"):
                continue
            if count:
                handle.write(",")
            json.dump(
                slim_catalog_card(raw_card),
                handle,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            count += 1
        handle.write("]}")
    if count == 0:
        raise RuntimeError("Scryfall oracle bulk download contained no valid cards")
    return count


def sync_catalog(target: Path) -> dict:
    target = target.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    metadata = _oracle_bulk_metadata()
    download_uri = metadata.get("jsonl_download_uri") or metadata.get("download_uri")
    if not download_uri:
        raise RuntimeError("Scryfall bulk metadata contained no supported download URI")
    source_format = "jsonl_gzip" if metadata.get("jsonl_download_uri") else "json_array"
    download_path = _download_bulk(download_uri, target.parent)
    output_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=".landfall-catalog.json",
            dir=target.parent,
            delete=False,
        ) as handle:
            output_path = Path(handle.name)
        card_count = _write_catalog(
            download_path,
            output_path,
            metadata,
            source_format=source_format,
        )
        os.replace(output_path, target)
        updated_at = metadata.get("updated_at")
        return {
            "path": str(target),
            "catalog_version": f"oracle_cards:{updated_at or 'unknown'}",
            "source_updated_at": updated_at,
            "card_count": card_count,
            "bytes": target.stat().st_size,
        }
    finally:
        if download_path.exists():
            download_path.unlink()
        if output_path and output_path.exists():
            output_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_TARGET,
        help=f"Catalog output path (default: {DEFAULT_TARGET})",
    )
    args = parser.parse_args()
    result = sync_catalog(args.output)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
