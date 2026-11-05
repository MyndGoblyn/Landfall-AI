# Local Candidate Catalog

LandFallAI can search a local, versioned Scryfall oracle-card snapshot before
using live Scryfall search. This removes the small live-result window from the
recommendation quality ceiling while preserving a safe fallback.

## Build or refresh the snapshot

From the repository root:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\sync_scryfall_catalog.py
```

The generated `backend/data/scryfall_oracle_cards.json` file is intentionally
ignored by Git because it is a large, replaceable data artifact. The sync writes
an atomic replacement and records the Scryfall `updated_at` value as the catalog
version.

The importer streams Scryfall's current gzip-compressed JSONL feed and retains
compatibility with the earlier JSON-array bulk format, avoiding a full raw-data
copy in application memory.

Scryfall recommends bulk data for large local lookups. The sync and live client
both send explicit `User-Agent` and `Accept` headers.

## Runtime configuration

The default snapshot path is detected automatically when the file exists. A
different location can be selected with:

```dotenv
SCRYFALL_CATALOG_PATH=D:\data\scryfall_oracle_cards.json
CANDIDATE_CATALOG_ENABLED=true
CANDIDATE_CATALOG_EXPANSION_FACTOR=4
CANDIDATE_CATALOG_MAX_RESULTS=160
```

The expansion settings control how many candidates reach LandFallAI's existing
contextual filter and ranker. They do not change the number of recommendations
shown to users. If the catalog is missing, invalid, or cannot evaluate a query,
the provider falls back to the existing live Scryfall search path.
`CANDIDATE_CATALOG_ENABLED=false` is the immediate rollback switch.

The admin `/api/admin/scryfall-cache` diagnostic includes catalog availability,
loaded version, card count, query-cache count, and local/fallback counters.

## Quality and rollout

The local query evaluator intentionally supports the operators emitted by the
current engine: Boolean groups, implicit AND, oracle/type/keyword checks,
Commander legality, commander eligibility, color identity, mana value, regular
expressions, exact-name exclusions, and the oracle tags used by commander
discovery. Unsupported syntax fails closed to live search instead of silently
returning a partial candidate set.

Run both quality gates after catalog or retrieval changes:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\run_recommendation_benchmark.py
backend\.venv\Scripts\python.exe -m pytest -q
```
