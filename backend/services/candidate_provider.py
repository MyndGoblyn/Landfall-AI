"""Candidate retrieval interfaces for recommendation and discovery ranking."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Protocol

from services.card_catalog import LocalCardCatalog
from services.scryfall_service import ScryfallService


logger = logging.getLogger(__name__)


class CandidateProvider(Protocol):
    """Retrieve a broad card pool without deciding final recommendation rank."""

    async def search_cards(self, query: str, limit: int) -> List[Dict]:
        ...


class ScryfallCandidateProvider:
    """Compatibility provider that preserves the current live search behavior."""

    def __init__(self, scryfall_service: ScryfallService):
        self.scryfall = scryfall_service

    async def search_cards(self, query: str, limit: int) -> List[Dict]:
        if self.scryfall is None:
            return []
        return await self.scryfall.search_cards_by_criteria(query, limit=limit)

    def get_status(self) -> Dict:
        return {"type": "scryfall", "available": self.scryfall is not None}

    def cache_identity(self) -> tuple:
        return ("scryfall",)

    async def prepare(self) -> Dict:
        return self.get_status()


class LocalCatalogCandidateProvider:
    """Search a versioned local Scryfall oracle-card snapshot."""

    def __init__(
        self,
        catalog_path: str | Path,
        expansion_factor: int = 4,
        maximum_limit: int = 160,
    ):
        self.catalog = LocalCardCatalog(catalog_path)
        self.expansion_factor = max(1, int(expansion_factor))
        self.maximum_limit = max(1, int(maximum_limit))

    def recommended_limit(self, requested_limit: int) -> int:
        """Use the local snapshot to score a wider pool without more API calls."""
        if not self.catalog.available:
            return requested_limit
        return min(
            self.maximum_limit,
            max(requested_limit, requested_limit * self.expansion_factor),
        )

    async def search_cards(self, query: str, limit: int) -> List[Dict]:
        return await self.catalog.search_async(query, limit)

    async def search_many(
        self,
        requests: List[tuple[str, int]],
    ) -> Dict[str, List[Dict]]:
        return await self.catalog.search_many_async(requests)

    def get_status(self) -> Dict:
        return {
            "type": "local_catalog",
            "expansion_factor": self.expansion_factor,
            "maximum_limit": self.maximum_limit,
            **self.catalog.get_status(),
        }

    def cache_identity(self) -> tuple:
        return ("local_catalog", *self.catalog.cache_identity())

    async def prepare(self) -> Dict:
        return await self.catalog.load_async()


class FallbackCandidateProvider:
    """Prefer a broad local catalog and retain live search as a safety net."""

    def __init__(
        self,
        primary: CandidateProvider,
        fallback: CandidateProvider,
        fallback_on_empty: bool = True,
    ):
        self.primary = primary
        self.fallback = fallback
        self.fallback_on_empty = fallback_on_empty
        self.counters = {
            "primary_hits": 0,
            "primary_empty": 0,
            "primary_errors": 0,
            "fallback_hits": 0,
        }

    def recommended_limit(self, requested_limit: int) -> int:
        resolver = getattr(self.primary, "recommended_limit", None)
        if callable(resolver):
            return max(requested_limit, int(resolver(requested_limit)))
        return requested_limit

    async def search_cards(self, query: str, limit: int) -> List[Dict]:
        try:
            results = await self.primary.search_cards(query, limit)
            if results:
                self.counters["primary_hits"] += 1
                return results
            self.counters["primary_empty"] += 1
            if not self.fallback_on_empty:
                return []
        except Exception as exc:
            self.counters["primary_errors"] += 1
            logger.warning("Local candidate catalog search failed; using Scryfall: %s", exc)

        results = await self.fallback.search_cards(query, limit)
        if results:
            self.counters["fallback_hits"] += 1
        return results

    async def search_many(
        self,
        requests: List[tuple[str, int]],
    ) -> Dict[str, List[Dict]]:
        """Use the local batch path, falling back only for empty queries."""
        ordered = list(requests)
        primary_many = getattr(self.primary, "search_many", None)
        if not callable(primary_many):
            return {
                query: rows
                for (query, _limit), rows in zip(
                    ordered,
                    await asyncio.gather(*(
                        self.search_cards(query, limit)
                        for query, limit in ordered
                    )),
                )
            }

        try:
            results = await primary_many(ordered)
        except Exception as exc:
            self.counters["primary_errors"] += len(ordered)
            logger.warning(
                "Local candidate catalog batch search failed; using Scryfall: %s",
                exc,
            )
            results = {}

        missing = []
        for query, limit in ordered:
            if results.get(query):
                self.counters["primary_hits"] += 1
            elif self.fallback_on_empty:
                self.counters["primary_empty"] += 1
                missing.append((query, limit))

        if not missing:
            return {query: list(results.get(query) or []) for query, _limit in ordered}

        semaphore = asyncio.Semaphore(3)

        async def live_search(query: str, limit: int):
            async with semaphore:
                return await self.fallback.search_cards(query, limit)

        fallback_rows = await asyncio.gather(*(
            live_search(query, limit) for query, limit in missing
        ))
        for (query, _limit), rows in zip(missing, fallback_rows):
            results[query] = rows
            if rows:
                self.counters["fallback_hits"] += 1
        return {query: list(results.get(query) or []) for query, _limit in ordered}

    def get_status(self) -> Dict:
        primary_status = getattr(self.primary, "get_status", lambda: {})()
        fallback_status = getattr(self.fallback, "get_status", lambda: {})()
        return {
            "type": "fallback",
            "primary": primary_status,
            "fallback": fallback_status,
            "counters": dict(self.counters),
        }

    def cache_identity(self) -> tuple:
        primary_identity = getattr(self.primary, "cache_identity", lambda: (type(self.primary).__name__,))()
        fallback_identity = getattr(self.fallback, "cache_identity", lambda: (type(self.fallback).__name__,))()
        return ("fallback", primary_identity, fallback_identity)

    async def prepare(self) -> Dict:
        prepare = getattr(self.primary, "prepare", None)
        if callable(prepare):
            await prepare()
        return self.get_status()


def build_candidate_provider(
    scryfall_service: Optional[ScryfallService],
    catalog_path: Optional[str | Path] = None,
) -> CandidateProvider:
    """Build the production provider, enabling the catalog when configured."""
    live_provider = ScryfallCandidateProvider(scryfall_service)
    catalog_enabled = os.environ.get("CANDIDATE_CATALOG_ENABLED", "true").lower() == "true"
    if not catalog_enabled:
        return live_provider
    configured_path = catalog_path or os.environ.get("SCRYFALL_CATALOG_PATH")
    default_path = Path(__file__).resolve().parents[1] / "data" / "scryfall_oracle_cards.json"

    if configured_path is None and default_path.exists():
        configured_path = default_path
    if configured_path is None:
        return live_provider

    local_provider = LocalCatalogCandidateProvider(
        configured_path,
        expansion_factor=int(os.environ.get("CANDIDATE_CATALOG_EXPANSION_FACTOR", "4")),
        maximum_limit=int(os.environ.get("CANDIDATE_CATALOG_MAX_RESULTS", "160")),
    )
    return FallbackCandidateProvider(local_provider, live_provider)
