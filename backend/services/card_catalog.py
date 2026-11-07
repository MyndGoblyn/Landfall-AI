"""Versioned local card catalog and the Scryfall-query subset LandFallAI emits."""

from __future__ import annotations

import asyncio
import json
import math
import re
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence


CATALOG_SCHEMA_VERSION = 1
CATALOG_CARD_FIELDS = (
    "name",
    "oracle_id",
    "type_line",
    "oracle_text",
    "mana_cost",
    "cmc",
    "power",
    "toughness",
    "colors",
    "color_identity",
    "set",
    "collector_number",
    "prices",
    "keywords",
    "legalities",
    "image_uris",
    "card_faces",
    "scryfall_uri",
    "edhrec_rank",
)
CATALOG_FACE_FIELDS = (
    "name",
    "type_line",
    "oracle_text",
    "mana_cost",
    "cmc",
    "colors",
    "image_uris",
)
CATALOG_IMAGE_FIELDS = ("normal", "large", "small")
CATALOG_PRICE_FIELDS = ("usd", "usd_foil")


class CatalogError(RuntimeError):
    """Base class for catalog failures that should use the live fallback."""


class CatalogUnavailableError(CatalogError):
    pass


class CatalogValidationError(CatalogError):
    pass


class CatalogQueryError(CatalogError):
    pass


def slim_catalog_card(card: Dict) -> Dict:
    """Retain recommendation fields while removing bulk-data-only payload."""
    slim = {field: card.get(field) for field in CATALOG_CARD_FIELDS if field in card}
    if isinstance(slim.get("prices"), dict):
        slim["prices"] = {
            field: slim["prices"].get(field)
            for field in CATALOG_PRICE_FIELDS
            if slim["prices"].get(field) is not None
        }
    if isinstance(slim.get("legalities"), dict):
        slim["legalities"] = {
            "commander": slim["legalities"].get("commander")
        }
    if isinstance(slim.get("image_uris"), dict):
        slim["image_uris"] = {
            field: slim["image_uris"].get(field)
            for field in CATALOG_IMAGE_FIELDS
            if slim["image_uris"].get(field)
        }
    if slim.get("card_faces"):
        faces = []
        for face in slim["card_faces"]:
            slim_face = {
                field: face.get(field)
                for field in CATALOG_FACE_FIELDS
                if field in face
            }
            if isinstance(slim_face.get("image_uris"), dict):
                slim_face["image_uris"] = {
                    field: slim_face["image_uris"].get(field)
                    for field in CATALOG_IMAGE_FIELDS
                    if slim_face["image_uris"].get(field)
                }
            faces.append(slim_face)
        slim["card_faces"] = faces
    return slim


def _combined_field(card: Dict, field: str) -> str:
    cached_value = card.get(f"_catalog_{field}")
    if isinstance(cached_value, str):
        return cached_value
    values = [card.get(field) or ""]
    values.extend((face.get(field) or "") for face in card.get("card_faces") or [])
    return "\n".join(str(value) for value in values if value).lower()


def _public_card(card: Dict) -> Dict:
    return {key: value for key, value in card.items() if not key.startswith("_catalog_")}


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _tokenize_query(query: str) -> List[str]:
    tokens: List[str] = []
    buffer: List[str] = []
    quote: Optional[str] = None
    in_regex = False
    escaped = False

    def flush():
        if buffer:
            tokens.append("".join(buffer))
            buffer.clear()

    for char in query.strip():
        if quote:
            buffer.append(char)
            if char == quote and not escaped:
                quote = None
            escaped = char == "\\" and not escaped
            if char != "\\":
                escaped = False
            continue

        if in_regex:
            buffer.append(char)
            if char == "/" and not escaped:
                in_regex = False
            escaped = char == "\\" and not escaped
            if char != "\\":
                escaped = False
            continue

        if char in {"'", '"'}:
            quote = char
            buffer.append(char)
            continue
        if char == "/" and "".join(buffer).endswith(":"):
            in_regex = True
            buffer.append(char)
            continue
        if char.isspace():
            flush()
            continue
        if char in {"(", ")"}:
            flush()
            tokens.append(char)
            continue
        buffer.append(char)

    if quote or in_regex:
        raise CatalogQueryError("Unterminated quoted or regular-expression query value")
    flush()
    return tokens


_ORACLE_TAG_TERMS = {
    "artifact": ("artifact",),
    "enchantment": ("enchantment", "aura"),
    "graveyard": ("graveyard", "dies", "flashback", "escape"),
    "recursion": ("from your graveyard", "return target", "return a"),
    "reanimate": ("return target creature card", "return a creature card", "reanimate"),
    "sacrifice": ("sacrifice", "dies"),
    "aristocrats": ("sacrifice", "whenever another creature dies"),
    "tokens": ("token", "populate"),
    "treasure": ("treasure token",),
    "lifegain": ("gain life", "gained life"),
    "counters": ("counter", "proliferate", "modified"),
    "spellslinger": ("instant or sorcery", "whenever you cast", "magecraft"),
    "blink": ("exile another", "return it to the battlefield"),
    "exile": ("from exile", "exile the top", "play that card"),
    "card-advantage": ("draw a card", "draw cards"),
    "mill": ("mill",),
}


Predicate = Callable[[Dict], bool]


class _QueryParser:
    def __init__(self, query: str):
        self.query = query
        self.tokens = _tokenize_query(query)
        self.position = 0

    def parse(self) -> Predicate:
        if not self.tokens:
            raise CatalogQueryError("Candidate query cannot be empty")
        predicate = self._parse_or()
        if self.position != len(self.tokens):
            raise CatalogQueryError(f"Unexpected token: {self.tokens[self.position]}")
        return predicate

    def _peek(self) -> Optional[str]:
        if self.position >= len(self.tokens):
            return None
        return self.tokens[self.position]

    def _take(self) -> str:
        token = self._peek()
        if token is None:
            raise CatalogQueryError("Unexpected end of candidate query")
        self.position += 1
        return token

    def _parse_or(self) -> Predicate:
        predicates = [self._parse_and()]
        while (self._peek() or "").upper() == "OR":
            self._take()
            predicates.append(self._parse_and())
        if len(predicates) == 1:
            return predicates[0]
        return lambda card: any(predicate(card) for predicate in predicates)

    def _parse_and(self) -> Predicate:
        predicates: List[Predicate] = []
        while self._peek() is not None and self._peek() != ")" and (self._peek() or "").upper() != "OR":
            predicates.append(self._parse_atom())
        if not predicates:
            raise CatalogQueryError("Expected a search condition")
        if len(predicates) == 1:
            return predicates[0]
        return lambda card: all(predicate(card) for predicate in predicates)

    def _parse_atom(self) -> Predicate:
        token = self._take()
        if token == "(":
            predicate = self._parse_or()
            if self._take() != ")":
                raise CatalogQueryError("Unbalanced candidate-query parentheses")
            return predicate
        if token == ")":
            raise CatalogQueryError("Unexpected closing parenthesis")
        return self._compile_term(token)

    def _compile_term(self, token: str) -> Predicate:
        negated = token.startswith("-")
        source = token[1:] if negated else token
        predicate = self._compile_positive_term(source)
        if negated:
            return lambda card: not predicate(card)
        return predicate

    def _compile_positive_term(self, term: str) -> Predicate:
        if term.startswith("!"):
            expected = _unquote(term[1:]).lower()
            return lambda card: (card.get("name") or "").lower() == expected

        comparison = re.fullmatch(r"(cmc|mv|id)(<=|>=|=|<|>)(.+)", term, flags=re.IGNORECASE)
        if comparison:
            field, operator, raw_value = comparison.groups()
            if field.lower() == "id":
                return self._identity_predicate(operator, raw_value)
            return self._number_predicate("cmc", operator, raw_value)

        if ":" not in term:
            value = _unquote(term).lower()
            return lambda card: value in (
                (card.get("name") or "").lower()
                + "\n"
                + _combined_field(card, "oracle_text")
                + "\n"
                + _combined_field(card, "type_line")
            )

        field, raw_value = term.split(":", 1)
        field = field.lower()
        value = _unquote(raw_value).lower()
        if field == "o":
            return self._text_predicate("oracle_text", raw_value)
        if field in {"t", "type"}:
            return self._text_predicate("type_line", raw_value)
        if field in {"kw", "keyword"}:
            return lambda card: (
                value in {str(keyword).lower() for keyword in card.get("keywords") or []}
                or value in _combined_field(card, "oracle_text")
            )
        if field == "otag":
            terms = _ORACLE_TAG_TERMS.get(value)
            if not terms:
                raise CatalogQueryError(f"Unsupported oracle tag in local catalog: {value}")
            return lambda card: any(
                candidate in (_combined_field(card, "oracle_text") + "\n" + _combined_field(card, "type_line"))
                for candidate in terms
            )
        if field in {"f", "format"} and value == "commander":
            return lambda card: (card.get("legalities") or {}).get("commander") in {"legal", "restricted"}
        if field == "is" and value == "commander":
            return self._commander_predicate
        if field == "is" and value in {"dfc", "double-faced"}:
            return lambda card: len(card.get("card_faces") or []) >= 2
        if field == "id":
            return self._identity_predicate("=", value)
        raise CatalogQueryError(f"Unsupported candidate-query field: {field}")

    def _text_predicate(self, field: str, raw_value: str) -> Predicate:
        if raw_value.startswith("/") and raw_value.endswith("/") and len(raw_value) > 2:
            try:
                pattern = re.compile(raw_value[1:-1], flags=re.IGNORECASE)
            except re.error as exc:
                raise CatalogQueryError(f"Invalid candidate-query regular expression: {exc}") from exc
            return lambda card: bool(pattern.search(_combined_field(card, field)))
        value = _unquote(raw_value).lower()
        return lambda card: value in _combined_field(card, field)

    def _identity_predicate(self, operator: str, raw_value: str) -> Predicate:
        normalized = raw_value.strip().lower()
        expected = set() if normalized in {"", "c"} else {char.upper() for char in normalized if char in "wubrg"}
        if operator == "=":
            return lambda card: {
                str(color).upper() for color in card.get("color_identity") or []
            } == expected
        if operator == "<=":
            return lambda card: {
                str(color).upper() for color in card.get("color_identity") or []
            }.issubset(expected)
        raise CatalogQueryError(f"Unsupported color-identity comparison: id{operator}{raw_value}")

    def _number_predicate(self, field: str, operator: str, raw_value: str) -> Predicate:
        try:
            expected = float(raw_value)
        except ValueError as exc:
            raise CatalogQueryError(f"Invalid numeric query value: {raw_value}") from exc

        comparisons = {
            "=": lambda actual: actual == expected,
            "<=": lambda actual: actual <= expected,
            ">=": lambda actual: actual >= expected,
            "<": lambda actual: actual < expected,
            ">": lambda actual: actual > expected,
        }
        compare = comparisons[operator]

        def predicate(card: Dict) -> bool:
            try:
                return compare(float(card.get(field, 0) or 0))
            except (TypeError, ValueError):
                return False

        return predicate

    @staticmethod
    def _commander_predicate(card: Dict) -> bool:
        type_line = _combined_field(card, "type_line")
        oracle_text = _combined_field(card, "oracle_text")
        return (
            ("legendary" in type_line and "creature" in type_line)
            or "can be your commander" in oracle_text
            or ("legendary enchantment" in type_line and "background" in type_line)
        )


def compile_catalog_query(query: str) -> Predicate:
    """Compile the supported query subset into a reusable card predicate."""
    return _QueryParser(query).parse()


def _popularity_key(card: Dict) -> tuple:
    try:
        edhrec_rank = float(card.get("edhrec_rank"))
    except (TypeError, ValueError):
        edhrec_rank = math.inf
    return (edhrec_rank, (card.get("name") or "").lower())


class LocalCardCatalog:
    """Lazily load, hot-reload, and search a local oracle-card snapshot."""

    def __init__(self, path: str | Path, query_cache_size: int = 128):
        self.path = Path(path).expanduser().resolve()
        self.query_cache_size = max(1, int(query_cache_size))
        self._lock = threading.RLock()
        self._signature: Optional[tuple] = None
        self._cards: Sequence[Dict] = ()
        self._name_index: Dict[str, Dict] = {}
        self._catalog_version: Optional[str] = None
        self._source_updated_at: Optional[str] = None
        self._query_cache: OrderedDict[str, Sequence[Dict]] = OrderedDict()

    @property
    def available(self) -> bool:
        return self.path.is_file()

    def _file_signature(self) -> tuple:
        try:
            stat = self.path.stat()
        except OSError as exc:
            raise CatalogUnavailableError(f"Catalog snapshot is unavailable at {self.path}") from exc
        return (stat.st_mtime_ns, stat.st_size)

    def _ensure_loaded(self):
        signature = self._file_signature()
        if self._signature == signature and self._cards:
            return

        with self._lock:
            signature = self._file_signature()
            if self._signature == signature and self._cards:
                return
            try:
                with self.path.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
            except (OSError, json.JSONDecodeError) as exc:
                raise CatalogValidationError(f"Could not read candidate catalog: {exc}") from exc

            if isinstance(payload, list):
                raw_cards = payload
                catalog_version = f"raw:{signature[0]}:{signature[1]}"
                source_updated_at = None
            elif isinstance(payload, dict):
                schema_version = payload.get("schema_version")
                if schema_version != CATALOG_SCHEMA_VERSION:
                    raise CatalogValidationError(
                        f"Unsupported catalog schema {schema_version!r}; expected {CATALOG_SCHEMA_VERSION}"
                    )
                raw_cards = payload.get("cards")
                catalog_version = str(payload.get("catalog_version") or f"snapshot:{signature[0]}:{signature[1]}")
                source_updated_at = payload.get("source_updated_at")
            else:
                raise CatalogValidationError("Catalog must contain an object or a Scryfall card list")

            if not isinstance(raw_cards, list) or not raw_cards:
                raise CatalogValidationError("Catalog contains no cards")

            unique_cards: Dict[str, Dict] = {}
            for raw_card in raw_cards:
                if not isinstance(raw_card, dict) or not raw_card.get("name"):
                    continue
                card = slim_catalog_card(raw_card)
                card["_catalog_oracle_text"] = _combined_field(card, "oracle_text")
                card["_catalog_type_line"] = _combined_field(card, "type_line")
                key = str(card.get("oracle_id") or card["name"]).lower()
                existing = unique_cards.get(key)
                if existing is None or _popularity_key(card) < _popularity_key(existing):
                    unique_cards[key] = card

            if not unique_cards:
                raise CatalogValidationError("Catalog contains no valid card records")

            self._cards = tuple(unique_cards.values())
            self._name_index = {
                str(card.get("name") or "").casefold(): card
                for card in self._cards
                if card.get("name")
            }
            for card in self._cards:
                for face in card.get("card_faces") or []:
                    face_name = str(face.get("name") or "").casefold()
                    if face_name:
                        self._name_index.setdefault(face_name, card)
            self._catalog_version = catalog_version
            self._source_updated_at = source_updated_at
            self._signature = signature
            self._query_cache.clear()

    def search(self, query: str, limit: int) -> List[Dict]:
        if limit <= 0:
            return []
        self._ensure_loaded()

        with self._lock:
            cached = self._query_cache.get(query)
            if cached is not None:
                self._query_cache.move_to_end(query)
                return [_public_card(card) for card in cached[:limit]]

        predicate = compile_catalog_query(query)
        matches = tuple(sorted((card for card in self._cards if predicate(card)), key=_popularity_key))

        with self._lock:
            self._query_cache[query] = matches
            self._query_cache.move_to_end(query)
            while len(self._query_cache) > self.query_cache_size:
                self._query_cache.popitem(last=False)
        return [_public_card(card) for card in matches[:limit]]

    def load(self) -> Dict:
        """Eagerly validate and load the current snapshot."""
        self._ensure_loaded()
        return self.get_status()

    async def load_async(self) -> Dict:
        return await asyncio.to_thread(self.load)

    async def search_async(self, query: str, limit: int) -> List[Dict]:
        return await asyncio.to_thread(self.search, query, limit)

    def resolve(self, name: str) -> Optional[Dict]:
        """Resolve a canonical card or face name from the frozen snapshot."""
        self._ensure_loaded()
        card = self._name_index.get(str(name or "").strip().casefold())
        return _public_card(card) if card else None

    def resolve_many(self, names: Iterable[str]) -> List[Optional[Dict]]:
        """Resolve exact names in caller order without live network access."""
        self._ensure_loaded()
        return [
            (
                _public_card(card)
                if (card := self._name_index.get(str(name or "").strip().casefold()))
                else None
            )
            for name in names
        ]

    async def resolve_async(self, name: str) -> Optional[Dict]:
        return await asyncio.to_thread(self.resolve, name)

    async def resolve_many_async(self, names: Iterable[str]) -> List[Optional[Dict]]:
        ordered = list(names)
        return await asyncio.to_thread(self.resolve_many, ordered)

    def get_status(self) -> Dict:
        return {
            "available": self.available,
            "loaded": bool(self._cards),
            "path": str(self.path),
            "catalog_version": self._catalog_version,
            "source_updated_at": self._source_updated_at,
            "card_count": len(self._cards),
            "cached_queries": len(self._query_cache),
        }

    def cache_identity(self) -> tuple:
        """Return a hashable snapshot identity for upstream result caches."""
        try:
            signature = self._file_signature()
        except CatalogUnavailableError:
            signature = None
        return (str(self.path), signature)


def build_catalog_payload(
    cards: Iterable[Dict],
    catalog_version: str,
    generated_at: str,
    source_updated_at: Optional[str],
) -> Dict:
    """Build the stable on-disk schema used by the sync script and tests."""
    return {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "catalog_version": catalog_version,
        "generated_at": generated_at,
        "source_updated_at": source_updated_at,
        "cards": [slim_catalog_card(card) for card in cards if isinstance(card, dict) and card.get("name")],
    }
