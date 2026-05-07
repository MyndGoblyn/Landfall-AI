import aiohttp
import asyncio
from typing import Dict, List, Optional
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class ScryfallService:
    BASE_URL = "https://api.scryfall.com"
    
    def __init__(self):
        self.cache: Dict[str, Dict] = {}  # Simple in-memory cache
        self.cache_expiry: Dict[str, datetime] = {}
        self.cache_ttl = timedelta(hours=24)
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
    
    def _is_cache_valid(self, key: str) -> bool:
        if key not in self.cache:
            return False
        if key not in self.cache_expiry:
            return False
        return datetime.now() < self.cache_expiry[key]
    
    async def search_card(self, name: str, fuzzy: bool = True) -> Optional[Dict]:
        """Search for a card by name using Scryfall API"""
        cache_key = f"card:{name.lower()}"
        
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key]
        
        try:
            session = await self.get_session()
            endpoint = "/cards/named"
            params = {"fuzzy" if fuzzy else "exact": name}
            
            async with session.get(f"{self.BASE_URL}{endpoint}", params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    self.cache[cache_key] = data
                    self.cache_expiry[cache_key] = datetime.now() + self.cache_ttl
                    return data
                elif response.status == 404:
                    logger.warning(f"Card not found: {name}")
                    return None
                else:
                    logger.error(f"Scryfall API error: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching card {name}: {str(e)}")
            return None
    
    async def get_card_bulk(self, names: List[str]) -> List[Optional[Dict]]:
        """Fetch multiple cards with rate limiting"""
        results = []
        for name in names:
            card = await self.search_card(name)
            results.append(card)
            await asyncio.sleep(0.1)  # Scryfall rate limit: 10 req/sec
        return results
    
    async def search_cards_by_criteria(self, query: str, limit: int = 20) -> List[Dict]:
        """Search cards using Scryfall search syntax"""
        try:
            session = await self.get_session()
            params = {"q": query, "unique": "cards", "order": "edhrec"}
            
            async with session.get(f"{self.BASE_URL}/cards/search", params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('data', [])[:limit]
                else:
                    logger.error(f"Scryfall search error: {response.status}")
                    return []
        except Exception as e:
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
