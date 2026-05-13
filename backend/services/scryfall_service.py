import aiohttp
import asyncio
from typing import Dict, List, Optional
import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

class ScryfallService:
    BASE_URL = "https://api.scryfall.com"
    SLIM_CARD_FIELDS = (
        "name", "oracle_id", "type_line", "oracle_text", "mana_cost", "cmc",
        "power", "toughness", "colors", "color_identity",
        "set", "collector_number", "prices", "keywords", "legalities",
        "image_uris", "card_faces", "scryfall_uri",
    )
    SLIM_FACE_FIELDS = (
        "name", "type_line", "oracle_text", "mana_cost", "cmc", "colors", "image_uris",
    )
    
    def __init__(self, db=None):
        self.db = db
        self.cache: Dict[str, Dict] = {}  # Simple in-memory cache
        self.cache_expiry: Dict[str, datetime] = {}
        self.cache_ttl = timedelta(hours=24)
        self.session: Optional[aiohttp.ClientSession] = None
        self.request_timeout = aiohttp.ClientTimeout(
            total=float(os.environ.get("SCRYFALL_REQUEST_TIMEOUT_SECONDS", "12"))
        )
        self.cache_stats = {
            "card_l1_hits": 0,
            "card_l2_hits": 0,
            "card_network_misses": 0,
            "card_not_found": 0,
            "card_errors": 0,
            "search_l1_hits": 0,
            "search_l2_hits": 0,
            "search_network_misses": 0,
            "search_errors": 0,
            "l2_read_errors": 0,
            "l2_write_errors": 0,
        }
    
    async def get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    def _retry_after_seconds(self, response, fallback: float) -> float:
        """Read Retry-After when Scryfall asks us to slow down."""
        try:
            return max(float(response.headers.get("Retry-After", fallback)), fallback)
        except (TypeError, ValueError):
            return fallback

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _normalize_key(self, value: str) -> str:
        return (value or "").strip().lower()

    def _record_cache_stat(self, key: str):
        if key in self.cache_stats:
            self.cache_stats[key] += 1

    def get_cache_status(self) -> Dict:
        valid_l1_entries = sum(1 for key in self.cache if self._is_cache_valid(key))
        return {
            "persistent_cache_enabled": (
                self.db is not None
                and hasattr(self.db, "scryfall_cards")
                and hasattr(self.db, "scryfall_searches")
            ),
            "l1_entries": len(self.cache),
            "l1_valid_entries": valid_l1_entries,
            "counters": dict(self.cache_stats),
        }
    
    def _is_cache_valid(self, key: str) -> bool:
        if key not in self.cache:
            return False
        if key not in self.cache_expiry:
            return False
        return self._now() < self.cache_expiry[key]

    def _store_l1(self, cache_key: str, data):
        self.cache[cache_key] = data
        self.cache_expiry[cache_key] = self._now() + self.cache_ttl

    def _slim_card(self, card: Dict) -> Dict:
        """Keep the card fields the engine actually reads."""
        slim = {
            field: card.get(field)
            for field in self.SLIM_CARD_FIELDS
            if field in card
        }
        if "card_faces" in slim and slim["card_faces"]:
            slim["card_faces"] = [
                {
                    field: face.get(field)
                    for field in self.SLIM_FACE_FIELDS
                    if field in face
                }
                for face in slim["card_faces"]
            ]
        return slim

    async def _read_card_from_l2(self, name: str, fuzzy: bool = True) -> Optional[Dict]:
        if self.db is None or not hasattr(self.db, "scryfall_cards"):
            return None

        lookup_key = self._normalize_key(name)
        query = {"lookup_keys": lookup_key} if fuzzy else {"name_lower": lookup_key}
        try:
            doc = await self.db.scryfall_cards.find_one(query)
        except Exception as exc:
            self._record_cache_stat("l2_read_errors")
            logger.warning("Scryfall L2 card cache read failed: %s", exc)
            return None

        if not doc:
            return None
        data = doc.get("data")
        return data if isinstance(data, dict) else None

    async def _write_card_to_l2(self, card: Dict, lookup_key: Optional[str] = None):
        if self.db is None or not hasattr(self.db, "scryfall_cards") or not card.get("name"):
            return

        slim = self._slim_card(card)
        name_lower = self._normalize_key(slim["name"])
        lookup_keys = {name_lower}
        normalized_lookup = self._normalize_key(lookup_key or "")
        if normalized_lookup:
            lookup_keys.add(normalized_lookup)

        try:
            existing = await self.db.scryfall_cards.find_one({"name_lower": name_lower})
            if existing:
                lookup_keys.update(existing.get("lookup_keys") or [])
            await self.db.scryfall_cards.update_one(
                {"name_lower": name_lower},
                {
                    "$set": {
                        "name_lower": name_lower,
                        "lookup_keys": sorted(lookup_keys),
                        "oracle_id": slim.get("oracle_id"),
                        "data": slim,
                        "fetched_at": self._now(),
                    }
                },
                upsert=True,
            )
        except Exception as exc:
            self._record_cache_stat("l2_write_errors")
            logger.warning("Scryfall L2 card cache write failed: %s", exc)

    async def _read_search_from_l2(self, query_key: str) -> Optional[List[Dict]]:
        if self.db is None or not hasattr(self.db, "scryfall_searches"):
            return None

        try:
            doc = await self.db.scryfall_searches.find_one({"query_key": query_key})
        except Exception as exc:
            self._record_cache_stat("l2_read_errors")
            logger.warning("Scryfall L2 search cache read failed: %s", exc)
            return None

        if not doc:
            return None

        names = doc.get("names") or []
        cards = []
        for name in names:
            card = await self._read_card_from_l2(name, fuzzy=True)
            if not card:
                return None
            cards.append(card)
        return cards

    async def _write_search_to_l2(self, query_key: str, query: str, limit: int, cards: List[Dict]):
        if self.db is None or not hasattr(self.db, "scryfall_searches"):
            return

        names = []
        for card in cards:
            if card.get("name"):
                names.append(card["name"])
                await self._write_card_to_l2(card)

        try:
            await self.db.scryfall_searches.update_one(
                {"query_key": query_key},
                {
                    "$set": {
                        "query_key": query_key,
                        "query": query,
                        "limit": limit,
                        "names": names,
                        "fetched_at": self._now(),
                    }
                },
                upsert=True,
            )
        except Exception as exc:
            self._record_cache_stat("l2_write_errors")
            logger.warning("Scryfall L2 search cache write failed: %s", exc)
    
    async def search_card(self, name: str, fuzzy: bool = True) -> Optional[Dict]:
        """Search for a card by name using Scryfall API"""
        card, _source = await self._search_card_with_source(name, fuzzy=fuzzy)
        return card

    async def _search_card_with_source(self, name: str, fuzzy: bool = True) -> tuple[Optional[Dict], str]:
        lookup_key = self._normalize_key(name)
        mode = "fuzzy" if fuzzy else "exact"
        cache_key = f"card:{mode}:{lookup_key}"
        
        if self._is_cache_valid(cache_key):
            self._record_cache_stat("card_l1_hits")
            logger.info("Scryfall cache hit tier=L1 kind=card key=%s", lookup_key)
            return self.cache[cache_key], "l1"

        l2_card = await self._read_card_from_l2(name, fuzzy=fuzzy)
        if l2_card:
            self._record_cache_stat("card_l2_hits")
            logger.info("Scryfall cache hit tier=L2 kind=card key=%s", lookup_key)
            self._store_l1(cache_key, l2_card)
            return l2_card, "l2"
        
        try:
            session = await self.get_session()
            endpoint = "/cards/named"
            params = {"fuzzy" if fuzzy else "exact": name}
            
            for attempt in range(3):
                async with session.get(f"{self.BASE_URL}{endpoint}", params=params, timeout=self.request_timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        slim_data = self._slim_card(data)
                        await self._write_card_to_l2(slim_data, lookup_key=lookup_key)
                        self._store_l1(cache_key, slim_data)
                        self._record_cache_stat("card_network_misses")
                        logger.info("Scryfall cache miss tier=network kind=card key=%s", lookup_key)
                        return slim_data, "network"
                    elif response.status == 404:
                        self._record_cache_stat("card_not_found")
                        logger.warning(f"Card not found: {name}")
                        return None, "missing"
                    elif response.status in {429, 500, 502, 503, 504} and attempt < 2:
                        wait_time = self._retry_after_seconds(response, 0.35 * (attempt + 1))
                        logger.warning(f"Scryfall card lookup retry {attempt + 1} for {name}: {response.status}")
                        await asyncio.sleep(wait_time)
                    else:
                        self._record_cache_stat("card_errors")
                        logger.error(f"Scryfall API error: {response.status}")
                        return None, "error"
        except Exception as e:
            self._record_cache_stat("card_errors")
            logger.error(f"Error fetching card {name}: {str(e)}")
            return None, "error"
    
    async def get_card_bulk(self, names: List[str]) -> List[Optional[Dict]]:
        """Fetch multiple cards with rate limiting"""
        results = []
        for name in names:
            card, source = await self._search_card_with_source(name)
            results.append(card)
            if source == "network":
                await asyncio.sleep(0.12)  # Keep text imports below Scryfall's burst limits
        return results
    
    async def search_cards_by_criteria(self, query: str, limit: int = 20) -> List[Dict]:
        """Search cards using Scryfall search syntax"""
        query_key = f"{query.lower()}::{limit}"
        cache_key = f"search:{query_key}"
        if self._is_cache_valid(cache_key):
            self._record_cache_stat("search_l1_hits")
            logger.info("Scryfall cache hit tier=L1 kind=search key=%s", query_key)
            return self.cache[cache_key]

        l2_results = await self._read_search_from_l2(query_key)
        if l2_results is not None:
            self._record_cache_stat("search_l2_hits")
            logger.info("Scryfall cache hit tier=L2 kind=search key=%s", query_key)
            self._store_l1(cache_key, l2_results)
            return l2_results

        try:
            session = await self.get_session()
            params = {"q": query, "unique": "cards", "order": "edhrec"}
            
            for attempt in range(3):
                async with session.get(f"{self.BASE_URL}/cards/search", params=params, timeout=self.request_timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = [self._slim_card(card) for card in data.get('data', [])[:limit]]
                        await self._write_search_to_l2(query_key, query, limit, results)
                        self._store_l1(cache_key, results)
                        self._record_cache_stat("search_network_misses")
                        logger.info("Scryfall cache miss tier=network kind=search key=%s", query_key)
                        return results
                    elif response.status in {429, 500, 502, 503, 504} and attempt < 2:
                        wait_time = self._retry_after_seconds(response, 0.35 * (attempt + 1))
                        logger.warning(f"Scryfall search retry {attempt + 1}: {response.status}")
                        await asyncio.sleep(wait_time)
                    else:
                        self._record_cache_stat("search_errors")
                        logger.error(f"Scryfall search error: {response.status}")
                        return []
        except Exception as e:
            self._record_cache_stat("search_errors")
            logger.error(f"Error searching cards: {str(e)}")
            return []
    
    def extract_card_data(self, scryfall_card: Dict) -> Dict:
        """Extract relevant data from Scryfall card object"""
        return {
            "name": scryfall_card.get("name"),
            "type_line": scryfall_card.get("type_line"),
            "oracle_text": scryfall_card.get("oracle_text", ""),
            "cmc": scryfall_card.get("cmc", 0),
            "colors": scryfall_card.get("colors", []),
            "color_identity": scryfall_card.get("color_identity", []),
            "set_code": scryfall_card.get("set"),
            "collector_number": scryfall_card.get("collector_number"),
            "prices": scryfall_card.get("prices", {}),
            "keywords": scryfall_card.get("keywords", []),
            "legalities": scryfall_card.get("legalities", {}),
        }
