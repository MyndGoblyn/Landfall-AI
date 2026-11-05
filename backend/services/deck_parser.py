import re
import asyncio
import aiohttp
import requests
from typing import Dict, List, Optional
import logging
from services.scryfall_service import ScryfallService

logger = logging.getLogger(__name__)

class DeckParser:
    def __init__(self, scryfall_service: ScryfallService):
        self.scryfall = scryfall_service
        self.color_name_map = {
            "White": "W",
            "Blue": "U",
            "Black": "B",
            "Red": "R",
            "Green": "G",
            "Colorless": "C",
        }
    
    async def parse_deck(self, source_type: str, source_data: str) -> Dict:
        """Main entry point for deck parsing"""
        if source_type == "url":
            return await self._parse_url(source_data)
        elif source_type == "text":
            return await self._parse_text(source_data)
        else:
            raise ValueError(f"Invalid source_type: {source_type}")
    
    async def _parse_url(self, url: str) -> Dict:
        """Parse deck from URL (Archidekt or Moxfield)"""
        if "archidekt.com" in url:
            return await self._parse_archidekt(url)
        elif "moxfield.com" in url:
            return await self._parse_moxfield(url)
        else:
            raise ValueError("Unsupported deck URL. Only Archidekt and Moxfield are supported.")
    
    async def _parse_archidekt(self, url: str) -> Dict:
        """Parse Archidekt deck URL"""
        try:
            # Extract deck ID from URL
            deck_id_match = re.search(r'/decks/(\d+)', url)
            if not deck_id_match:
                raise ValueError("Invalid Archidekt URL")
            
            deck_id = deck_id_match.group(1)
            api_url = f"https://archidekt.com/api/decks/{deck_id}/"
            
            async with aiohttp.ClientSession(headers=self._source_headers()) as session:
                async with session.get(api_url) as response:
                    if response.status != 200:
                        raise ValueError(f"Failed to fetch deck from Archidekt: {response.status}")
                    
                    return await self._parse_archidekt_payload(await response.json())
        except Exception as e:
            logger.error(f"Archidekt parsing error: {str(e)}")
            raise ValueError(f"Failed to parse Archidekt deck: {str(e)}")
    
    async def _parse_moxfield(self, url: str) -> Dict:
        """Parse Moxfield deck URL"""
        try:
            # Extract deck ID from URL
            deck_id_match = re.search(r'/decks/([a-zA-Z0-9_-]+)', url)
            if not deck_id_match:
                raise ValueError("Invalid Moxfield URL")
            
            deck_id = deck_id_match.group(1)
            api_url = f"https://api2.moxfield.com/v3/decks/all/{deck_id}"
            
            # Moxfield's Cloudflare edge currently rejects aiohttp's TLS
            # fingerprint even with the same accepted application headers.
            # Offload requests so the async API remains non-blocking.
            data = await asyncio.to_thread(self._fetch_source_json, api_url)
            return await self._parse_moxfield_payload(data)
        except Exception as e:
            logger.error(f"Moxfield parsing error: {str(e)}")
            raise ValueError(f"Failed to parse Moxfield deck: {str(e)}")
    
    async def _parse_text(self, text: str) -> Dict:
        """Parse deck from plain text format"""
        lines = text.strip().split('\n')
        parsed_entries = []
        commander = None
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('//'):
                continue
            
            # Parse format: "1 Card Name" or "1x Card Name" or "Card Name"
            match = re.match(r'^(\d+)x?\s+(.+)$', line)
            if match:
                qty = int(match.group(1))
                card_name = match.group(2).strip()
            else:
                qty = 1
                card_name = line
            
            # Check for commander marker
            if '*CMDR*' in card_name.upper() or 'COMMANDER' in card_name.upper():
                card_name = re.sub(r'\*CMDR\*|COMMANDER', '', card_name, flags=re.IGNORECASE).strip()
                commander = card_name
            
            parsed_entries.append((card_name, qty))

        cards = []
        scryfall_cards = await self.scryfall.get_card_bulk([name for name, _qty in parsed_entries])
        for (card_name, qty), scryfall_card in zip(parsed_entries, scryfall_cards):
            if scryfall_card:
                card_info = self._build_card_info(scryfall_card, qty)
                cards.append(card_info)
        
        # If no commander specified, assume first legendary creature
        if not commander and cards:
            for card in cards:
                if card.get('type_line') and 'Legendary Creature' in card['type_line']:
                    commander = card['name']
                    break
        
        # Determine color identity
        color_identity = []
        if commander:
            commander_card = await self.scryfall.search_card(commander)
            if commander_card:
                color_identity = commander_card.get('color_identity', [])

            # The commander is stored separately throughout the analysis system.
            # Remove one marked/inferred copy so every import path consistently
            # analyzes the Commander main deck (normally 99 cards).
            commander_key = commander.casefold()
            removed_commander = False
            normalized_cards = []
            for card in cards:
                if not removed_commander and card.get('name', '').casefold() == commander_key:
                    qty = int(card.get('qty', 1) or 1)
                    removed_commander = True
                    if qty > 1:
                        normalized_cards.append({**card, 'qty': qty - 1})
                    continue
                normalized_cards.append(card)
            cards = normalized_cards
        
        return {
            "commander": commander,
            "cards": cards,
            "color_identity": color_identity
        }

    async def _parse_archidekt_payload(self, data: Dict) -> Dict:
        """Normalize an Archidekt response to a commander plus main deck."""
        excluded_categories = {'commander', 'maybeboard', 'sideboard'}
        excluded_categories.update(
            str(category.get('name', '')).casefold()
            for category in data.get('categories', [])
            if not category.get('includedInDeck', True)
        )

        commander = None
        commander_row = None
        cards = []
        for card_data in data.get('cards', []):
            oracle = card_data.get('card', {}).get('oracleCard', {})
            card_name = oracle.get('name')
            if not card_name:
                continue

            categories = {
                str(category).casefold()
                for category in (card_data.get('categories') or [])
            }
            if 'commander' in categories:
                if commander is None:
                    commander = card_name
                    commander_row = card_data
                continue
            if categories.intersection(excluded_categories):
                continue

            qty = int(card_data.get('quantity', 1) or 1)
            card_info = self._build_archidekt_card_info(card_data, qty)
            if card_info:
                cards.append(card_info)
                continue

            # Fallback only if Archidekt did not include enough card data.
            scryfall_card = await self.scryfall.search_card(card_name)
            if scryfall_card:
                cards.append(self._build_card_info(scryfall_card, qty))

        color_identity = []
        if commander_row:
            oracle = commander_row.get('card', {}).get('oracleCard', {})
            color_identity = self._map_archidekt_colors(oracle.get('colorIdentity', []))
        if commander and not color_identity:
            commander_card = await self.scryfall.search_card(commander)
            if commander_card:
                color_identity = commander_card.get('color_identity', [])

        return {
            "commander": commander,
            "cards": cards,
            "color_identity": color_identity,
        }

    async def _parse_moxfield_payload(self, data: Dict) -> Dict:
        """Normalize current and legacy Moxfield responses without N+1 lookups."""
        commander_entries = self._moxfield_board_entries(data, 'commanders')
        mainboard_entries = self._moxfield_board_entries(data, 'mainboard')

        commander = None
        commander_card = None
        if commander_entries:
            commander_card = commander_entries[0].get('card') or commander_entries[0]
            commander = commander_card.get('name')

        cards = []
        for entry in mainboard_entries:
            qty = int(entry.get('quantity', 1) or 1)
            card_info = self._build_moxfield_card_info(entry, qty)
            if card_info:
                cards.append(card_info)
                continue

            card = entry.get('card') or entry
            card_name = card.get('name')
            if card_name:
                scryfall_card = await self.scryfall.search_card(card_name)
                if scryfall_card:
                    cards.append(self._build_card_info(scryfall_card, qty))

        color_identity = list((commander_card or {}).get('color_identity') or [])
        if commander and not color_identity:
            scryfall_card = await self.scryfall.search_card(commander)
            if scryfall_card:
                color_identity = scryfall_card.get('color_identity', [])

        return {
            "commander": commander,
            "cards": cards,
            "color_identity": color_identity,
        }

    def _moxfield_board_entries(self, data: Dict, board_name: str) -> List[Dict]:
        boards = data.get('boards') or {}
        board = boards.get(board_name) if isinstance(boards, dict) else None
        raw_entries = (board or {}).get('cards') if isinstance(board, dict) else None

        # Compatibility with the pre-boards Moxfield response used by the
        # original importer.
        if raw_entries is None:
            raw_entries = data.get(board_name) or {}
        if isinstance(raw_entries, dict):
            return list(raw_entries.values())
        if isinstance(raw_entries, list):
            return raw_entries
        return []

    def _source_headers(self) -> Dict[str, str]:
        return {
            'User-Agent': 'LandfallAI/1.0 (deck import)',
            'Accept': 'application/json',
        }

    def _fetch_source_json(self, url: str) -> Dict:
        response = requests.get(
            url,
            headers=self._source_headers(),
            timeout=30,
        )
        if response.status_code != 200:
            raise ValueError(
                f"Failed to fetch deck source: {response.status_code}"
            )
        return response.json()
    
    def _build_card_info(self, scryfall_card: Dict, qty: int = 1) -> Dict:
        """Build card info dict from Scryfall data"""
        extracted = self.scryfall.extract_card_data(scryfall_card)
        return {
            "name": extracted['name'],
            "qty": qty,
            "set_code": extracted['set_code'],
            "collector_number": extracted['collector_number'],
            "type_line": extracted['type_line'],
            "oracle_text": extracted['oracle_text'],
            "cmc": extracted['cmc'],
            "colors": extracted['colors'],
            "color_identity": extracted['color_identity'],
            "tags": self._extract_tags(extracted['oracle_text'], extracted.get('keywords', []))
        }

    def _build_archidekt_card_info(self, archidekt_entry: Dict, qty: int = 1) -> Optional[Dict]:
        """Build card info directly from Archidekt's deck API response."""
        card = archidekt_entry.get('card') or {}
        oracle = card.get('oracleCard') or {}
        name = oracle.get('name')
        if not name:
            return None

        type_line = self._build_archidekt_type_line(oracle)
        oracle_text = oracle.get('text') or ''
        keywords = oracle.get('keywords') or []
        edition = card.get('edition') or {}

        return {
            "name": name,
            "qty": qty,
            "set_code": edition.get('editioncode'),
            "collector_number": card.get('collectorNumber'),
            "type_line": type_line,
            "oracle_text": oracle_text,
            "cmc": oracle.get('cmc', 0) or 0,
            "colors": self._map_archidekt_colors(oracle.get('colors', [])),
            "color_identity": self._map_archidekt_colors(oracle.get('colorIdentity', [])),
            "tags": self._extract_tags(oracle_text, keywords)
        }

    def _build_moxfield_card_info(self, moxfield_entry: Dict, qty: int = 1) -> Optional[Dict]:
        """Build card info from the Scryfall-shaped card in Moxfield's API."""
        card = moxfield_entry.get('card') or moxfield_entry
        name = card.get('name')
        if not name:
            return None

        faces = card.get('card_faces') or []
        oracle_text = card.get('oracle_text') or ' // '.join(
            face.get('oracle_text', '') for face in faces if face.get('oracle_text')
        )
        type_line = card.get('type_line') or ' // '.join(
            face.get('type_line', '') for face in faces if face.get('type_line')
        )
        keywords = card.get('keywords') or []

        return {
            "name": name,
            "qty": qty,
            "set_code": card.get('set'),
            "collector_number": card.get('collector_number') or card.get('cn'),
            "type_line": type_line,
            "oracle_text": oracle_text,
            "cmc": card.get('cmc', 0) or 0,
            "colors": card.get('colors') or [],
            "color_identity": card.get('color_identity') or [],
            "tags": self._extract_tags(oracle_text, keywords),
        }

    def _map_archidekt_colors(self, colors: List[str]) -> List[str]:
        """Convert Archidekt color names to Magic color identity symbols."""
        mapped = []
        for color in colors or []:
            symbol = self.color_name_map.get(color, color)
            if symbol and symbol != "C" and symbol not in mapped:
                mapped.append(symbol)
        return mapped

    def _build_archidekt_type_line(self, oracle: Dict) -> str:
        """Build a display type line from Archidekt oracle type arrays."""
        supertypes = oracle.get('superTypes') or []
        types = oracle.get('types') or []
        subtypes = oracle.get('subTypes') or []

        primary_types = " ".join([*supertypes, *types]).strip()
        subtype_text = " ".join(subtypes).strip()
        if primary_types and subtype_text:
            return f"{primary_types} - {subtype_text}"
        return primary_types or subtype_text
    
    def _extract_tags(self, oracle_text: str, keywords: List[str]) -> List[str]:
        """Extract synergy tags from oracle text"""
        tags = []
        oracle_lower = oracle_text.lower()
        
        tag_keywords = {
            'landfall': ['landfall', 'land enters the battlefield'],
            'treasure': ['treasure', 'create a treasure'],
            'token': ['create', 'token'],
            'equipment': ['equipment', 'equip'],
            'counters': ['+1/+1 counter', 'counter on'],
            'reanimator': ['return', 'graveyard', 'battlefield'],
            'spellslinger': ['instant', 'sorcery', 'cast'],
            'stax': ['opponents can\'t', 'sacrifice', 'tax'],
            'blink': ['exile', 'return', 'battlefield'],
            'aristocrats': ['dies', 'sacrifice', 'death']
        }
        
        for tag, words in tag_keywords.items():
            if any(word in oracle_lower for word in words):
                tags.append(tag)
        
        return list(set(tags))
