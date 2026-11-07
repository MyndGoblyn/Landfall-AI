from fastapi import FastAPI, APIRouter, Header, HTTPException, Depends, Request, Response, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import asyncio
import hashlib
import secrets
import smtplib
import re
from pathlib import Path
from email.message import EmailMessage
from pydantic import BaseModel, Field, ConfigDict, EmailStr, field_validator
from typing import List, Optional, Dict, Any, Literal, Mapping
import uuid
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt
import requests
from contextlib import asynccontextmanager

from services.scryfall_service import ScryfallService
from services.candidate_provider import build_candidate_provider
from services.catalog_distribution import build_catalog_distribution_from_env
from services.commander_atlas import (
    ARCHETYPE_FILTERS,
    PLAYSTYLE_FILTERS,
    CommanderAtlas,
)
from services.semantic_distribution import build_semantic_distribution_from_env
from services.deck_parser import DeckParser
from services.deck_input_assessment import (
    apply_recommendation_restraint,
    assess_deck_input,
    blocking_message,
)
from services.deck_intent import DeckIntentProfile, normalize_intent_profile
from services.build_intent import (
    BuildIntent,
    migrate_legacy_deck_intent,
    normalize_build_intent,
)
from services.deck_constructor import (
    ConstructorUnavailable,
    DeckConstructor,
    build_revision_diff,
)
from services.enhanced_suggestion_engine import EnhancedSuggestionEngine
from services.feedback_policy import feedback_policy_status
from services.in_memory_db import InMemoryClient, InMemoryDB

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

ENVIRONMENT = os.environ.get('ENVIRONMENT', 'development').lower()

# Database connection
USE_IN_MEMORY_DB = os.environ.get('USE_IN_MEMORY_DB') == 'true'
if USE_IN_MEMORY_DB:
    client = InMemoryClient()
    db = InMemoryDB()
else:
    mongo_url = os.environ.get('MONGO_URL')
    db_name = os.environ.get('DB_NAME')
    if not mongo_url or not db_name:
        raise RuntimeError('MONGO_URL and DB_NAME are required unless USE_IN_MEMORY_DB=true')
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

# JWT Secret
JWT_SECRET = os.environ.get('JWT_SECRET')
if not JWT_SECRET:
    if ENVIRONMENT == 'production':
        raise RuntimeError('JWT_SECRET is required when ENVIRONMENT=production')
    JWT_SECRET = 'dev-only-landfall-ai-secret-change-me'
if ENVIRONMENT == 'production' and len(JWT_SECRET) < 32:
    raise RuntimeError('JWT_SECRET must be at least 32 characters in production')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 168  # 7 days
AUTH_COOKIE_NAME = os.environ.get('AUTH_COOKIE_NAME', 'landfall_session')
AUTH_COOKIE_SECURE = os.environ.get('AUTH_COOKIE_SECURE', 'true' if ENVIRONMENT == 'production' else 'false').lower() == 'true'
AUTH_COOKIE_SAMESITE = os.environ.get('AUTH_COOKIE_SAMESITE', 'none' if ENVIRONMENT == 'production' else 'lax')
AUTH_COOKIE_DOMAIN = os.environ.get('AUTH_COOKIE_DOMAIN') or None
APP_PUBLIC_URL = os.environ.get('APP_PUBLIC_URL', 'http://localhost:3000').rstrip('/')
REQUIRE_EMAIL_VERIFICATION = os.environ.get(
    'REQUIRE_EMAIL_VERIFICATION',
    'true' if ENVIRONMENT == 'production' else 'false'
).lower() == 'true'
CAPTCHA_REQUIRED = os.environ.get(
    'CAPTCHA_REQUIRED',
    'true' if ENVIRONMENT == 'production' else 'false'
).lower() == 'true'
TURNSTILE_SECRET_KEY = os.environ.get('TURNSTILE_SECRET_KEY')
SMTP_HOST = os.environ.get('SMTP_HOST')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USERNAME = os.environ.get('SMTP_USERNAME')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')
SMTP_FROM_EMAIL = os.environ.get('SMTP_FROM_EMAIL') or SMTP_USERNAME
SMTP_USE_TLS = os.environ.get('SMTP_USE_TLS', 'true').lower() == 'true'
SMTP_USE_SSL = os.environ.get('SMTP_USE_SSL', 'false').lower() == 'true'
SMTP_TIMEOUT_SECONDS = int(os.environ.get('SMTP_TIMEOUT_SECONDS', '20'))
BREVO_API_KEY = os.environ.get('BREVO_API_KEY')
EMAIL_PROVIDER = os.environ.get('EMAIL_PROVIDER', 'smtp').lower()
EMAIL_FROM_NAME = os.environ.get('EMAIL_FROM_NAME', 'LandFall AI')
TOKEN_EXPIRATION_HOURS = int(os.environ.get('AUTH_TOKEN_EXPIRATION_HOURS', '24'))
PASSWORD_RESET_EXPIRATION_MINUTES = int(os.environ.get('PASSWORD_RESET_EXPIRATION_MINUTES', '30'))
LOGIN_ATTEMPT_LIMIT = int(os.environ.get('LOGIN_ATTEMPT_LIMIT', '5'))
LOGIN_ATTEMPT_WINDOW_MINUTES = int(os.environ.get('LOGIN_ATTEMPT_WINDOW_MINUTES', '15'))
AUTH_ACTION_ATTEMPT_LIMIT = int(os.environ.get('AUTH_ACTION_ATTEMPT_LIMIT', '5'))
AUTH_ACTION_WINDOW_MINUTES = int(os.environ.get('AUTH_ACTION_WINDOW_MINUTES', '15'))
RESET_ACCOUNTS_KEY = os.environ.get('RESET_ACCOUNTS_KEY')
RESET_ACCOUNT_COLLECTIONS = [
    "users",
    "decks",
    "analysis_runs",
    "tracked_commanders",
    "build_drafts",
    "card_collection",
    "recommendation_feedback",
    "auth_tokens",
    "rate_limits",
]

if CAPTCHA_REQUIRED and not TURNSTILE_SECRET_KEY:
    raise RuntimeError('TURNSTILE_SECRET_KEY is required when CAPTCHA_REQUIRED=true')
if ENVIRONMENT == 'production' and REQUIRE_EMAIL_VERIFICATION:
    if EMAIL_PROVIDER == 'brevo_api' and (not BREVO_API_KEY or not SMTP_FROM_EMAIL):
        raise RuntimeError('BREVO_API_KEY and SMTP_FROM_EMAIL are required when EMAIL_PROVIDER=brevo_api')
    if EMAIL_PROVIDER != 'brevo_api' and (not SMTP_HOST or not SMTP_FROM_EMAIL):
        raise RuntimeError('SMTP_HOST and SMTP_FROM_EMAIL are required for email verification in production')

security = HTTPBearer(auto_error=False)


async def prepare_database():
    if hasattr(db.users, 'create_index'):
        try:
            await db.users.create_index('email', unique=True)
            await db.tracked_commanders.create_index(
                [('user_id', 1), ('commander_oracle_id', 1)],
                unique=True,
            )
            await db.tracked_commanders.create_index(
                [('user_id', 1), ('updated_at', -1)]
            )
            await db.build_drafts.create_index(
                [('user_id', 1), ('deck_id', 1), ('revision', 1)],
                unique=True,
            )
            await db.build_drafts.create_index(
                [('user_id', 1), ('deck_id', 1), ('created_at', -1)]
            )
            await db.card_collection.create_index(
                [('user_id', 1), ('oracle_id', 1)],
                unique=True,
            )
            await db.card_collection.create_index(
                [('user_id', 1), ('name_key', 1)]
            )
            await db.recommendation_feedback.create_index(
                'event_key', unique=True
            )
            await db.recommendation_feedback.create_index(
                [('user_id', 1), ('deck_id', 1), ('created_at', -1)]
            )
            await db.auth_tokens.create_index('token_hash', unique=True)
            await db.auth_tokens.create_index('expires_at')
            await db.rate_limits.create_index('key', unique=True)
            await db.scryfall_cards.create_index('name_lower', unique=True)
            await db.scryfall_cards.create_index('lookup_keys')
            await db.scryfall_cards.create_index('oracle_id', sparse=True)
            await db.scryfall_cards.create_index('fetched_at', expireAfterSeconds=2592000)
            await db.scryfall_searches.create_index('query_key', unique=True)
            await db.scryfall_searches.create_index('fetched_at', expireAfterSeconds=604800)
        except Exception as exc:
            logger.warning("Could not ensure database indexes: %s", exc)
    logger.warning(
        "Scryfall persistent cache enabled=%s",
        scryfall_service.get_cache_status()["persistent_cache_enabled"],
    )
    logger.warning(
        "Candidate provider status=%s",
        getattr(candidate_provider, "get_status", lambda: {})(),
    )


def _local_catalog_status(provider_status: Dict[str, Any]) -> Dict[str, Any]:
    if provider_status.get("type") == "fallback":
        primary = provider_status.get("primary")
        return primary if isinstance(primary, dict) else {}
    return provider_status


async def prepare_candidate_catalog():
    """Refresh the optional remote snapshot without making startup depend on it."""
    if catalog_distribution is None:
        return

    try:
        refresh_result = await asyncio.to_thread(catalog_distribution.refresh)
    except Exception as exc:
        logger.warning("Remote candidate catalog refresh failed; using fallback: %s", exc)
        prepare = getattr(candidate_provider, "prepare", None)
        if callable(prepare) and catalog_distribution.target_path.exists():
            try:
                await prepare()
            except Exception as load_exc:
                logger.warning("Last-known candidate catalog could not be loaded: %s", load_exc)
        return

    prepare = getattr(candidate_provider, "prepare", None)
    if not callable(prepare):
        return
    try:
        provider_status = await prepare()
        local_status = _local_catalog_status(provider_status)
        expected_count = refresh_result.manifest["card_count"]
        if local_status.get("card_count") != expected_count:
            raise RuntimeError(
                "Loaded catalog card count "
                f"{local_status.get('card_count')} did not match manifest {expected_count}"
            )
        catalog_distribution.commit()
    except Exception as exc:
        if refresh_result.changed:
            await asyncio.to_thread(catalog_distribution.rollback, str(exc))
            try:
                await prepare()
            except Exception as rollback_exc:
                logger.warning(
                    "Candidate catalog rollback could not load; using live Scryfall: %s",
                    rollback_exc,
                )
        logger.warning("Candidate catalog validation failed; using fallback: %s", exc)


async def prepare_semantic_bundle():
    """Refresh optional registry evidence without making startup depend on it."""
    if semantic_distribution is None:
        return
    refresh_result = None
    try:
        refresh_result = await asyncio.to_thread(semantic_distribution.refresh)
        status = suggestion_engine.reload_semantic_bundle(
            semantic_distribution.target_path
        )
        expected = refresh_result["manifest"].get("resource_counts") or {}
        actual = {
            "mechanics_registry": status["mechanics"],
            "archetype_registry": status["archetypes"],
            "competitive_registry": status["competitive_cards"],
            "commander_profile_registry": status["commander_profiles"],
        }
        if expected and expected != actual:
            raise RuntimeError(
                f"Loaded semantic resource counts {actual} did not match {expected}"
            )
        semantic_distribution.commit()
    except Exception as exc:
        if refresh_result and refresh_result.get("changed"):
            await asyncio.to_thread(semantic_distribution.rollback, str(exc))
        if semantic_distribution.target_path.exists():
            try:
                suggestion_engine.reload_semantic_bundle(
                    semantic_distribution.target_path
                )
            except Exception as fallback_exc:
                logger.warning(
                    "Last-known semantic bundle could not be loaded: %s",
                    fallback_exc,
                )
        logger.warning(
            "Remote semantic bundle refresh failed; using bundled evidence: %s",
            exc,
        )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await prepare_candidate_catalog()
    await prepare_semantic_bundle()
    await prepare_database()
    try:
        yield
    finally:
        await scryfall_service.close()
        client.close()


# Create the main app
app = FastAPI(lifespan=lifespan)
api_router = APIRouter(prefix="/api")

# Initialize services
scryfall_service = ScryfallService(db=db)
deck_parser = DeckParser(scryfall_service)
catalog_distribution = build_catalog_distribution_from_env(ENVIRONMENT)
semantic_distribution = build_semantic_distribution_from_env(ENVIRONMENT)
candidate_provider = build_candidate_provider(
    scryfall_service,
    catalog_path=(catalog_distribution.target_path if catalog_distribution else None),
)
suggestion_engine = EnhancedSuggestionEngine(
    scryfall_service,
    candidate_provider=candidate_provider,
    planner_mode=os.environ.get(
        'RECOMMENDATION_PLANNER_MODE',
        'v3' if ENVIRONMENT == 'production' else 'shadow',
    ),
)
deck_constructor = DeckConstructor(
    suggestion_engine,
    scryfall_service,
    mode=os.environ.get('BUILD_CONSTRUCTOR_MODE', 'scaffold').lower(),
    max_scaffold_slots=int(os.environ.get('BUILD_CONSTRUCTOR_MAX_SLOTS', '40')),
)
commander_atlas = CommanderAtlas(candidate_provider, suggestion_engine)

# ==================== MODELS ====================

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    role: str = "player"  # player, store_owner, admin
    email_verified: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    captcha_token: Optional[str] = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 12:
            raise ValueError("Password must be at least 12 characters")
        return value

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    captcha_token: Optional[str] = None

class AuthResponse(BaseModel):
    message: str
    user: Optional[User] = None
    access_token: Optional[str] = None
    dev_link: Optional[str] = None

class ResetAccountsResponse(BaseModel):
    message: str
    deleted: Dict[str, int]

class TestEmailRequest(BaseModel):
    to_email: EmailStr

class TestEmailResponse(BaseModel):
    message: str
    smtp: Dict[str, Any]

class ScryfallCacheStatusResponse(BaseModel):
    persistent_cache_enabled: bool
    l1_entries: int
    l1_valid_entries: int
    counters: Dict[str, int]
    collection_counts: Dict[str, Optional[int]]
    candidate_provider: Dict[str, Any] = Field(default_factory=dict)
    candidate_catalog_distribution: Dict[str, Any] = Field(default_factory=dict)
    semantic_bundle_distribution: Dict[str, Any] = Field(default_factory=dict)
    semantic_bundle: Dict[str, Any] = Field(default_factory=dict)
    recommendation_ranker: Dict[str, Any] = Field(default_factory=dict)
    deck_role_assessment: Dict[str, Any] = Field(default_factory=dict)
    recommendation_planner: Dict[str, Any] = Field(default_factory=dict)

class PasswordForgotRequest(BaseModel):
    email: EmailStr
    captcha_token: Optional[str] = None

class PasswordResetRequest(BaseModel):
    token: str
    password: str
    captcha_token: Optional[str] = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 12:
            raise ValueError("Password must be at least 12 characters")
        return value

class VerifyEmailRequest(BaseModel):
    token: str

class ResendVerificationRequest(BaseModel):
    email: EmailStr
    captcha_token: Optional[str] = None

class DeckCard(BaseModel):
    name: str
    qty: int = 1
    set_code: Optional[str] = None
    collector_number: Optional[str] = None
    type_line: Optional[str] = None
    oracle_text: Optional[str] = None
    cmc: Optional[float] = None
    colors: List[str] = []
    color_identity: List[str] = []
    tags: List[str] = []

class Deck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    name: str
    commander: Optional[str] = None
    commanders: List[str] = Field(default_factory=list)
    cards: List[DeckCard] = []
    format: str = "commander"
    color_identity: List[str] = []
    imported_from: Optional[str] = None
    input_assessment: Dict[str, Any] = {}
    last_build_draft_id: Optional[str] = None
    build_draft_revision: Optional[int] = None
    build_intent: Optional[BuildIntent] = None
    intent_profile: DeckIntentProfile = Field(default_factory=DeckIntentProfile)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class DeckCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    commander: Optional[str] = None
    commanders: List[str] = Field(default_factory=list)
    format: str = "commander"
    build_intent: Optional[BuildIntent] = None

class DeckImport(BaseModel):
    source_type: str  # "url" or "text"
    source_data: str  # URL or decklist text


class BuildDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    deck_id: str
    revision: int = Field(ge=1)
    constructor_version: str
    status: str
    source_fingerprint: str
    result: Dict[str, Any]
    change_summary: Dict[str, Any] = Field(default_factory=dict)
    applied_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BuildDraftApplyRequest(BaseModel):
    confirmed: bool

    @field_validator("confirmed")
    @classmethod
    def require_confirmation(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Applying a scaffold requires explicit confirmation")
        return value


def _clean_tracked_note(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


class TrackCommanderCreate(BaseModel):
    commander_name: str = Field(min_length=1, max_length=200)
    source: str = Field(
        default="commander_lab",
        pattern="^(commander_lab|commander_atlas|discover)$",
    )
    note: Optional[str] = Field(default=None, max_length=400)

    @field_validator("commander_name")
    @classmethod
    def clean_commander_name(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("note")
    @classmethod
    def clean_note(cls, value: Optional[str]) -> Optional[str]:
        return _clean_tracked_note(value)


class TrackCommanderNoteUpdate(BaseModel):
    note: Optional[str] = Field(default=None, max_length=400)

    @field_validator("note")
    @classmethod
    def clean_note(cls, value: Optional[str]) -> Optional[str]:
        return _clean_tracked_note(value)


class TrackedCommander(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    commander_oracle_id: str
    name: str
    image_url: Optional[str] = None
    color_identity: List[str] = Field(default_factory=list)
    type_line: Optional[str] = None
    source: str = Field(pattern="^(commander_lab|commander_atlas|discover)$")
    note: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def _clean_card_name(value: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValueError("Card name cannot be blank")
    return cleaned


class CollectionImportEntry(BaseModel):
    card_name: str = Field(min_length=1, max_length=200)
    quantity: int = Field(default=1, ge=1, le=999)

    @field_validator("card_name")
    @classmethod
    def clean_card_name(cls, value: str) -> str:
        return _clean_card_name(value)


class CollectionImportRequest(BaseModel):
    entries: List[CollectionImportEntry] = Field(min_length=1, max_length=5000)
    mode: Literal["merge", "replace"] = "merge"


class CollectionQuantityUpdate(BaseModel):
    quantity: int = Field(ge=1, le=999)


class CollectionCard(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    oracle_id: str
    name: str
    quantity: int = Field(ge=1, le=999)
    image_url: Optional[str] = None
    type_line: Optional[str] = None
    color_identity: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


FeedbackAction = Literal[
    "accept_add",
    "reject_add",
    "accept_cut",
    "keep_cut",
    "accept_swap",
]


class RecommendationFeedbackCreate(BaseModel):
    analysis_id: str = Field(min_length=1, max_length=80)
    action: FeedbackAction
    card_name: str = Field(min_length=1, max_length=200)
    paired_card_name: Optional[str] = Field(default=None, max_length=200)
    reason_code: Optional[str] = Field(
        default=None,
        pattern="^(fit|budget|owned|power|strategy|duplicate|availability|other)$",
    )

    @field_validator("card_name")
    @classmethod
    def clean_feedback_card(cls, value: str) -> str:
        return _clean_card_name(value)

    @field_validator("paired_card_name")
    @classmethod
    def clean_feedback_pair(cls, value: Optional[str]) -> Optional[str]:
        return _clean_card_name(value) if value else None


class RecommendationFeedback(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deck_id: str
    source_type: Literal["analysis", "build_draft"]
    source_id: str
    action: str
    card_name: Optional[str] = None
    paired_card_name: Optional[str] = None
    reason_code: Optional[str] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Suggestion(BaseModel):
    card_name: str
    reason: str
    role_tag: str  # draw, ramp, removal, etc.
    cmc: float
    price: Optional[float] = None
    synergy_tags: List[str] = []
    confidence: float = 0.8
    fit_tier: Optional[str] = None
    score: Optional[int] = None
    evidence: Optional[str] = None
    evidence_tags: List[str] = []
    penalty_tags: List[str] = []
    marginal_utility: Optional[float] = None
    effective_role_gain: Optional[float] = None
    role_gains: Dict[str, float] = {}
    coverage_before: Optional[float] = None
    coverage_after: Optional[float] = None
    coverage_target: Optional[int] = None
    intent_alignment: List[str] = []
    intent_warnings: List[str] = []
    intent_score_delta: int = 0
    invariant_traits: List[str] = []
    invariant_alignment: List[str] = []
    invariant_warnings: List[str] = []
    invariant_score_delta: int = 0
    preservation_requirements: List[str] = []
    matched_plan_lanes: List[str] = Field(default_factory=list)
    evidence_confidence: Optional[float] = None
    confidence_band: Optional[str] = None
    confidence_model: Optional[str] = None
    confidence_basis: List[str] = Field(default_factory=list)
    confidence_scope: Optional[str] = None
    expected_deck_improvement: Optional[float] = None
    strategy_balance_gain: Optional[str] = None
    strategy_balance_before: Optional[Dict[str, float]] = None
    portfolio_version: Optional[str] = None
    selection_position: Optional[int] = None
    selection_reason: Optional[str] = None
    rank_assessment: Optional[Dict[str, Any]] = None
    data_freshness: Dict[str, Any] = Field(default_factory=dict)
    suggested_quantity: Optional[int] = None
    action_only: bool = False
    image_url: Optional[str] = None
    image_url_back: Optional[str] = None  # For double-faced cards

class AnalysisRun(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deck_id: str
    user_id: str
    analysis_depth: str = "fast"
    suggestions_add: List[Suggestion] = []
    suggestions_cut: List[Suggestion] = []
    swap_pairs: List[Dict[str, Any]] = []
    stats: Dict[str, Any] = {}
    commander_synergies: List[str] = []
    commander_archetypes: List[Dict[str, Any]] = []
    coverage_level: str = "partial"
    coverage_notes: Optional[str] = None
    coverage_signals: List[Dict[str, Any]] = []
    heuristic_signals: List[Dict[str, Any]] = []
    playstyle_tips: List[str] = []
    detected_themes: List[str] = []
    combo_suggestions: List[Dict[str, Any]] = []
    input_assessment: Dict[str, Any] = {}
    intent_profile: DeckIntentProfile = Field(default_factory=DeckIntentProfile)
    intent_summary: Dict[str, Any] = {}
    deck_invariants: Dict[str, Any] = {}
    strategy_profile: Dict[str, Any] = Field(default_factory=dict)
    recommendation_planner: Dict[str, Any] = Field(default_factory=dict)
    performance: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ==================== AUTH HELPERS ====================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def normalize_email(email: str) -> str:
    return email.strip().lower()

def create_token(user_id: str, email: str) -> str:
    issued_at = datetime.now(timezone.utc)
    payload = {
        'user_id': user_id,
        'email': normalize_email(email),
        'iat': issued_at,
        'jti': str(uuid.uuid4()),
        'exp': issued_at + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_token(token: str) -> Dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=JWT_EXPIRATION_HOURS * 60 * 60,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite=AUTH_COOKIE_SAMESITE,
        domain=AUTH_COOKIE_DOMAIN,
        path="/",
    )

def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        domain=AUTH_COOKIE_DOMAIN,
        path="/",
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite=AUTH_COOKIE_SAMESITE,
    )

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Dict:
    raw_token = credentials.credentials if credentials else request.cookies.get(AUTH_COOKIE_NAME)
    if not raw_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_token(raw_token)
    user = await db.users.find_one({"id": payload['user_id']}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if REQUIRE_EMAIL_VERIFICATION and not user.get("email_verified", False):
        raise HTTPException(status_code=403, detail="Please verify your email before continuing")
    return user

def parse_stored_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(value)

def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get('x-forwarded-for', '')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.client.host if request.client else 'unknown'

def auth_rate_limit_key(request: Request, action: str, identifier: str) -> str:
    return f"auth:{action}:{get_client_ip(request)}:{identifier}"

async def get_active_rate_events(key: str, window_minutes: int) -> List[datetime]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    doc = await db.rate_limits.find_one({"key": key}, {"_id": 0})
    raw_events = doc.get("events", []) if doc else []
    active_events = [
        parse_stored_datetime(event)
        for event in raw_events
        if parse_stored_datetime(event) > cutoff
    ]
    if doc:
        await db.rate_limits.update_one(
            {"key": key},
            {"$set": {"events": [event.isoformat() for event in active_events]}}
        )
    return active_events

async def enforce_rate_limit(key: str, limit: int, window_minutes: int, detail: str) -> None:
    if len(await get_active_rate_events(key, window_minutes)) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail
        )

async def record_rate_event(key: str, window_minutes: int) -> None:
    events = await get_active_rate_events(key, window_minutes)
    events.append(datetime.now(timezone.utc))
    serialized = [event.isoformat() for event in events]
    existing = await db.rate_limits.find_one({"key": key}, {"_id": 0})
    if existing:
        await db.rate_limits.update_one({"key": key}, {"$set": {"events": serialized}})
    else:
        await db.rate_limits.insert_one({"key": key, "events": serialized})

async def clear_rate_events(key: str) -> None:
    existing = await db.rate_limits.find_one({"key": key}, {"_id": 0})
    if existing:
        await db.rate_limits.update_one({"key": key}, {"$set": {"events": []}})

async def enforce_login_rate_limit(request: Request, email: str) -> str:
    key = auth_rate_limit_key(request, "login", normalize_email(email))
    await enforce_rate_limit(
        key,
        LOGIN_ATTEMPT_LIMIT,
        LOGIN_ATTEMPT_WINDOW_MINUTES,
        "Too many failed login attempts. Please wait and try again."
    )
    return key

async def enforce_auth_action_rate_limit(request: Request, action: str, identifier: str = "global") -> None:
    key = auth_rate_limit_key(request, action, normalize_email(identifier))
    await enforce_rate_limit(
        key,
        AUTH_ACTION_ATTEMPT_LIMIT,
        AUTH_ACTION_WINDOW_MINUTES,
        "Too many requests. Please wait and try again."
    )
    await record_rate_event(key, AUTH_ACTION_WINDOW_MINUTES)

async def verify_captcha(captcha_token: Optional[str], request: Request) -> None:
    if not CAPTCHA_REQUIRED:
        return
    if not captcha_token:
        raise HTTPException(status_code=400, detail="CAPTCHA verification is required")

    def submit_turnstile_verification() -> Dict[str, Any]:
        response = requests.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={
                "secret": TURNSTILE_SECRET_KEY,
                "response": captcha_token,
                "remoteip": get_client_ip(request),
            },
            timeout=8,
        )
        response.raise_for_status()
        return response.json()

    try:
        result = await asyncio.to_thread(submit_turnstile_verification)
    except Exception as exc:
        logger.warning("CAPTCHA verification request failed: %s", exc)
        raise HTTPException(status_code=400, detail="CAPTCHA verification failed")

    if not result.get("success"):
        error_codes = result.get("error-codes") or []
        logger.warning("CAPTCHA verification rejected: %s", error_codes)
        suffix = f": {', '.join(error_codes)}" if error_codes else ""
        raise HTTPException(status_code=400, detail=f"CAPTCHA verification failed{suffix}")

def hash_auth_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

async def create_auth_token(user_id: str, purpose: str, expires_at: datetime) -> str:
    raw_token = secrets.token_urlsafe(32)
    await db.auth_tokens.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "purpose": purpose,
        "token_hash": hash_auth_token(raw_token),
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "used_at": None,
    })
    return raw_token

async def consume_auth_token(raw_token: str, purpose: str) -> Dict[str, Any]:
    token_doc = await db.auth_tokens.find_one({
        "token_hash": hash_auth_token(raw_token),
        "purpose": purpose,
        "used_at": None,
    }, {"_id": 0})
    if not token_doc:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    if parse_stored_datetime(token_doc["expires_at"]) < datetime.now(timezone.utc):
        await db.auth_tokens.update_one(
            {"id": token_doc["id"]},
            {"$set": {"used_at": datetime.now(timezone.utc).isoformat()}}
        )
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    await db.auth_tokens.update_one(
        {"id": token_doc["id"]},
        {"$set": {"used_at": datetime.now(timezone.utc).isoformat()}}
    )
    return token_doc

def build_auth_link(path: str, token: str) -> str:
    if path == "/verify-email":
        return f"{APP_PUBLIC_URL}/?verify_email_token={token}"
    if path == "/reset-password":
        return f"{APP_PUBLIC_URL}/?reset_password_token={token}"
    return f"{APP_PUBLIC_URL}{path}?token={token}"

def send_email(to_email: str, subject: str, body: str) -> bool:
    if EMAIL_PROVIDER == 'brevo_api':
        if not BREVO_API_KEY or not SMTP_FROM_EMAIL:
            logger.warning("Brevo API email is not configured; email to %s was not sent", to_email)
            return False

        response = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "accept": "application/json",
                "api-key": BREVO_API_KEY,
                "content-type": "application/json",
            },
            json={
                "sender": {"name": EMAIL_FROM_NAME, "email": SMTP_FROM_EMAIL},
                "to": [{"email": to_email}],
                "subject": subject,
                "textContent": body,
            },
            timeout=SMTP_TIMEOUT_SECONDS,
        )
        if response.status_code >= 400:
            logger.error("Brevo API email failed: %s %s", response.status_code, response.text)
            response.raise_for_status()
        return True

    if not SMTP_HOST or not SMTP_FROM_EMAIL:
        logger.warning("SMTP is not configured; email to %s was not sent", to_email)
        return False

    message = EmailMessage()
    message["From"] = SMTP_FROM_EMAIL
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    smtp_class = smtplib.SMTP_SSL if SMTP_USE_SSL else smtplib.SMTP
    with smtp_class(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS) as smtp:
        if SMTP_USE_TLS and not SMTP_USE_SSL:
            smtp.starttls()
        if SMTP_USERNAME and SMTP_PASSWORD:
            smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
        smtp.send_message(message)
    return True

async def send_required_email(to_email: str, subject: str, body: str) -> bool:
    try:
        sent = await asyncio.to_thread(send_email, to_email, subject, body)
    except Exception as exc:
        logger.error("Email delivery failed for %s: %s", to_email, exc)
        raise HTTPException(
            status_code=502,
            detail="Email delivery failed. Please check SMTP settings and try again."
        )

    if not sent:
        raise HTTPException(
            status_code=502,
            detail="Email delivery is not configured. Please check SMTP settings."
        )
    return True

async def send_verification_email(user: User) -> Optional[str]:
    token = await create_auth_token(
        user.id,
        "email_verification",
        datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRATION_HOURS)
    )
    link = build_auth_link("/verify-email", token)
    body = (
        "Welcome to LandFall AI.\n\n"
        "Verify your email address to finish securing your account:\n"
        f"{link}\n\n"
        f"This link expires in {TOKEN_EXPIRATION_HOURS} hours."
    )
    await send_required_email(user.email, "Verify your LandFall AI account", body)
    return link if ENVIRONMENT != "production" else None

async def send_password_reset_email(user: User) -> Optional[str]:
    token = await create_auth_token(
        user.id,
        "password_reset",
        datetime.now(timezone.utc) + timedelta(minutes=PASSWORD_RESET_EXPIRATION_MINUTES)
    )
    link = build_auth_link("/reset-password", token)
    body = (
        "A password reset was requested for your LandFall AI account.\n\n"
        "Reset your password here:\n"
        f"{link}\n\n"
        f"This link expires in {PASSWORD_RESET_EXPIRATION_MINUTES} minutes. "
        "If you did not request this, you can ignore this email."
    )
    await send_required_email(user.email, "Reset your LandFall AI password", body)
    return link if ENVIRONMENT != "production" else None

# ==================== AUTH ROUTES ====================

@api_router.post("/auth/register", response_model=AuthResponse)
async def register(user_data: UserCreate, request: Request, response: Response):
    email = normalize_email(user_data.email)
    await enforce_auth_action_rate_limit(request, "register", email)
    await verify_captcha(user_data.captcha_token, request)

    # Check if user exists
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    user = User(
        email=email,
        role="player",
        email_verified=not REQUIRE_EMAIL_VERIFICATION
    )
    user_dict = user.model_dump()
    user_dict['password_hash'] = hash_password(user_data.password)
    user_dict['created_at'] = user_dict['created_at'].isoformat()
    
    await db.users.insert_one(user_dict)

    if REQUIRE_EMAIL_VERIFICATION:
        try:
            dev_link = await send_verification_email(user)
        except HTTPException:
            await db.users.delete_one({"id": user.id})
            await db.auth_tokens.delete_many({"user_id": user.id})
            raise
        return AuthResponse(
            message="Account created. Check your email to verify your account before logging in.",
            user=None,
            dev_link=dev_link,
        )

    token = create_token(user.id, user.email)
    set_auth_cookie(response, token)
    return AuthResponse(message="Account created", user=user, access_token=token)

@api_router.post("/auth/login", response_model=AuthResponse)
async def login(login_data: UserLogin, request: Request, response: Response):
    email = normalize_email(login_data.email)
    rate_key = await enforce_login_rate_limit(request, email)
    await verify_captcha(login_data.captcha_token, request)

    user_doc = await db.users.find_one({"email": email})
    if not user_doc or not verify_password(login_data.password, user_doc['password_hash']):
        await record_rate_event(rate_key, LOGIN_ATTEMPT_WINDOW_MINUTES)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    await clear_rate_events(rate_key)
    
    user = User(**{k: v for k, v in user_doc.items() if k != 'password_hash'})
    if isinstance(user.created_at, str):
        user.created_at = datetime.fromisoformat(user.created_at)

    if not user.email_verified:
        if REQUIRE_EMAIL_VERIFICATION:
            await send_verification_email(user)
        raise HTTPException(status_code=403, detail="Please verify your email before logging in")
    
    token = create_token(user.id, user.email)
    set_auth_cookie(response, token)
    return AuthResponse(message="Login successful", user=user, access_token=token)

@api_router.post("/auth/logout")
async def logout(response: Response):
    clear_auth_cookie(response)
    return {"message": "Logged out"}

@api_router.get("/auth/diagnostics")
async def auth_diagnostics():
    return {
        "environment": ENVIRONMENT,
        "captcha_required": CAPTCHA_REQUIRED,
        "turnstile_secret_configured": bool(TURNSTILE_SECRET_KEY),
        "email_verification_required": REQUIRE_EMAIL_VERIFICATION,
        "smtp_host_configured": bool(SMTP_HOST),
        "smtp_from_configured": bool(SMTP_FROM_EMAIL),
        "app_public_url": APP_PUBLIC_URL,
        "cors_origins": cors_origins,
    }

@api_router.post("/auth/email/resend", response_model=AuthResponse)
async def resend_verification(request_data: ResendVerificationRequest, request: Request):
    email = normalize_email(request_data.email)
    await enforce_auth_action_rate_limit(request, "resend_verification", email)
    await verify_captcha(request_data.captcha_token, request)

    user_doc = await db.users.find_one({"email": email}, {"_id": 0})
    if user_doc and not user_doc.get("email_verified", False):
        user = User(**{k: v for k, v in user_doc.items() if k != 'password_hash'})
        if isinstance(user.created_at, str):
            user.created_at = datetime.fromisoformat(user.created_at)
        dev_link = await send_verification_email(user)
        return AuthResponse(message="If that email needs verification, a new link has been sent.", dev_link=dev_link)

    return AuthResponse(message="If that email needs verification, a new link has been sent.")

@api_router.post("/auth/email/verify", response_model=AuthResponse)
async def verify_email(request_data: VerifyEmailRequest, response: Response):
    token_doc = await consume_auth_token(request_data.token, "email_verification")
    user_doc = await db.users.find_one({"id": token_doc["user_id"]}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    await db.users.update_one(
        {"id": token_doc["user_id"]},
        {"$set": {"email_verified": True}}
    )
    user_doc["email_verified"] = True
    user = User(**{k: v for k, v in user_doc.items() if k != 'password_hash'})
    if isinstance(user.created_at, str):
        user.created_at = datetime.fromisoformat(user.created_at)

    token = create_token(user.id, user.email)
    set_auth_cookie(response, token)
    return AuthResponse(message="Email verified", user=user, access_token=token)

@api_router.post("/auth/password/forgot", response_model=AuthResponse)
async def forgot_password(request_data: PasswordForgotRequest, request: Request):
    email = normalize_email(request_data.email)
    await enforce_auth_action_rate_limit(request, "password_forgot", email)
    await verify_captcha(request_data.captcha_token, request)

    user_doc = await db.users.find_one({"email": email}, {"_id": 0})
    dev_link = None
    if user_doc:
        user = User(**{k: v for k, v in user_doc.items() if k != 'password_hash'})
        if isinstance(user.created_at, str):
            user.created_at = datetime.fromisoformat(user.created_at)
        dev_link = await send_password_reset_email(user)

    return AuthResponse(
        message="If an account exists for that email, a password reset link has been sent.",
        dev_link=dev_link,
    )

@api_router.post("/auth/password/reset", response_model=AuthResponse)
async def reset_password(request_data: PasswordResetRequest, request: Request, response: Response):
    await enforce_auth_action_rate_limit(request, "password_reset", get_client_ip(request))
    await verify_captcha(request_data.captcha_token, request)

    token_doc = await consume_auth_token(request_data.token, "password_reset")
    user_doc = await db.users.find_one({"id": token_doc["user_id"]}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    await db.users.update_one(
        {"id": token_doc["user_id"]},
        {"$set": {
            "password_hash": hash_password(request_data.password),
            "email_verified": True,
        }}
    )
    user_doc["email_verified"] = True
    user = User(**{k: v for k, v in user_doc.items() if k != 'password_hash'})
    if isinstance(user.created_at, str):
        user.created_at = datetime.fromisoformat(user.created_at)

    token = create_token(user.id, user.email)
    set_auth_cookie(response, token)
    return AuthResponse(message="Password updated", user=user, access_token=token)

@api_router.post("/admin/reset-accounts", response_model=ResetAccountsResponse)
async def reset_accounts(x_reset_key: Optional[str] = Header(default=None, alias="X-Reset-Key")):
    if not RESET_ACCOUNTS_KEY:
        raise HTTPException(status_code=404, detail="Reset endpoint is disabled")
    if not x_reset_key or not secrets.compare_digest(x_reset_key, RESET_ACCOUNTS_KEY):
        raise HTTPException(status_code=403, detail="Invalid reset key")

    deleted_counts = {}
    for collection_name in RESET_ACCOUNT_COLLECTIONS:
        collection = getattr(db, collection_name)
        result = await collection.delete_many({})
        deleted_counts[collection_name] = result.deleted_count

    return ResetAccountsResponse(
        message="Account reset complete. Remove RESET_ACCOUNTS_KEY and redeploy now.",
        deleted=deleted_counts,
    )

@api_router.post("/admin/test-email", response_model=TestEmailResponse)
async def test_email(
    request_data: TestEmailRequest,
    x_reset_key: Optional[str] = Header(default=None, alias="X-Reset-Key")
):
    if not RESET_ACCOUNTS_KEY:
        raise HTTPException(status_code=404, detail="Admin test endpoint is disabled")
    if not x_reset_key or not secrets.compare_digest(x_reset_key, RESET_ACCOUNTS_KEY):
        raise HTTPException(status_code=403, detail="Invalid admin key")

    smtp_summary = {
        "provider": EMAIL_PROVIDER,
        "brevo_api_key_configured": bool(BREVO_API_KEY),
        "host": SMTP_HOST,
        "port": SMTP_PORT,
        "username_configured": bool(SMTP_USERNAME),
        "password_configured": bool(SMTP_PASSWORD),
        "from_email": SMTP_FROM_EMAIL,
        "use_tls": SMTP_USE_TLS,
        "use_ssl": SMTP_USE_SSL,
        "timeout_seconds": SMTP_TIMEOUT_SECONDS,
    }

    try:
        await send_required_email(
            request_data.to_email,
            "LandFall AI SMTP test",
            "This is a LandFall AI SMTP test email. If you received it, backend email delivery is working."
        )
    except HTTPException as exc:
        detail = exc.detail
        if isinstance(detail, str):
            detail = f"{detail} Check backend logs for the provider error."
        raise HTTPException(status_code=exc.status_code, detail=detail)

    return TestEmailResponse(
        message="SMTP test email sent.",
        smtp=smtp_summary,
    )

async def count_collection_documents(collection) -> Optional[int]:
    if not hasattr(collection, "count_documents"):
        return None
    try:
        return await collection.count_documents({})
    except Exception as exc:
        logger.warning("Could not count collection documents: %s", exc)
        return None

@api_router.get("/admin/scryfall-cache", response_model=ScryfallCacheStatusResponse)
async def scryfall_cache_status(x_reset_key: Optional[str] = Header(default=None, alias="X-Reset-Key")):
    if not RESET_ACCOUNTS_KEY:
        raise HTTPException(status_code=404, detail="Admin diagnostics endpoint is disabled")
    if not x_reset_key or not secrets.compare_digest(x_reset_key, RESET_ACCOUNTS_KEY):
        raise HTTPException(status_code=403, detail="Invalid admin key")

    status_payload = scryfall_service.get_cache_status()
    collection_counts = {
        "scryfall_cards": await count_collection_documents(getattr(db, "scryfall_cards", None)),
        "scryfall_searches": await count_collection_documents(getattr(db, "scryfall_searches", None)),
    }
    return ScryfallCacheStatusResponse(
        **status_payload,
        collection_counts=collection_counts,
        candidate_provider=getattr(candidate_provider, "get_status", lambda: {})(),
        candidate_catalog_distribution=(
            catalog_distribution.get_status() if catalog_distribution else {"enabled": False}
        ),
        semantic_bundle_distribution=(
            semantic_distribution.get_status() if semantic_distribution else {"enabled": False}
        ),
        semantic_bundle=suggestion_engine.get_semantic_bundle_status(),
        recommendation_ranker=suggestion_engine.get_ranker_status(),
        deck_role_assessment=suggestion_engine.get_deck_role_status(),
        recommendation_planner=suggestion_engine.get_planner_status(),
    )

@api_router.get("/auth/me", response_model=User)
async def get_me(current_user: Dict = Depends(get_current_user)):
    user = User(**current_user)
    if isinstance(user.created_at, str):
        user.created_at = datetime.fromisoformat(user.created_at)
    return user

# ==================== DECK ROUTES ====================

@api_router.get("/decks", response_model=List[Deck])
async def get_decks(current_user: Dict = Depends(get_current_user)):
    decks = await db.decks.find({"user_id": current_user['id']}, {"_id": 0}).to_list(100)
    for deck in decks:
        if isinstance(deck.get('created_at'), str):
            deck['created_at'] = datetime.fromisoformat(deck['created_at'])
    return decks

@api_router.post("/decks", response_model=Deck)
async def create_deck(deck_data: DeckCreate, current_user: Dict = Depends(get_current_user)):
    normalized_build = (
        normalize_build_intent(deck_data.build_intent)
        if deck_data.build_intent is not None
        else None
    )
    if normalized_build:
        build_value = normalized_build["intent"]
        if " ".join(deck_data.name.split()) != build_value["deck_name"]:
            raise HTTPException(
                status_code=400,
                detail="Deck name must match the confirmed build intent",
            )
        requested_commanders = [
            name for name in (
                build_value.get("commander_name"),
                build_value.get("partner_name"),
            )
            if name
        ]
        supplied_commanders = deck_data.commanders or (
            [deck_data.commander] if deck_data.commander else []
        )
        if supplied_commanders and supplied_commanders != requested_commanders:
            raise HTTPException(
                status_code=400,
                detail="Commander selection must match the confirmed build intent",
            )
    else:
        build_value = None
        requested_commanders = deck_data.commanders or (
            [deck_data.commander] if deck_data.commander else []
        )

    deck = Deck(
        user_id=current_user['id'],
        name=build_value["deck_name"] if build_value else deck_data.name,
        commander=(
            requested_commanders[0] if requested_commanders else None
        ),
        commanders=requested_commanders,
        format=build_value["format"] if build_value else deck_data.format,
        build_intent=build_value,
        intent_profile=(
            normalized_build["deck_intent_profile"]
            if normalized_build
            else DeckIntentProfile()
        ),
    )
    deck_dict = deck.model_dump()
    deck_dict['created_at'] = deck_dict['created_at'].isoformat()
    
    await db.decks.insert_one(deck_dict)
    return deck

@api_router.get("/decks/{deck_id}", response_model=Deck)
async def get_deck(deck_id: str, current_user: Dict = Depends(get_current_user)):
    deck = await db.decks.find_one({"id": deck_id, "user_id": current_user['id']}, {"_id": 0})
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    if isinstance(deck.get('created_at'), str):
        deck['created_at'] = datetime.fromisoformat(deck['created_at'])
    return deck


@api_router.post("/build-intents/normalize")
async def preview_build_intent(
    build_intent: BuildIntent,
    current_user: Dict = Depends(get_current_user),
):
    """Expose every deterministic mapping before the user saves the intent."""
    return await _normalize_build_intent_for_user(
        build_intent,
        current_user["id"],
        preserve_collection_reference=True,
    )


@api_router.get("/decks/{deck_id}/build-intent")
async def get_deck_build_intent(
    deck_id: str,
    current_user: Dict = Depends(get_current_user),
):
    deck = await db.decks.find_one(
        {"id": deck_id, "user_id": current_user['id']},
        {"_id": 0},
    )
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    if deck.get("build_intent"):
        return {
            "source": "saved_build_intent",
            **await _normalize_build_intent_for_user(
                deck["build_intent"],
                current_user["id"],
                preserve_collection_reference=True,
            ),
        }
    return {
        "source": "migrated_deck_intent_v1",
        **migrate_legacy_deck_intent(
            deck.get("intent_profile"),
            deck_name=deck.get("name") or "Commander deck",
            commander_name=deck.get("commander"),
            existing_deck_id=deck_id,
        ),
    }


@api_router.put("/decks/{deck_id}/build-intent", response_model=Deck)
async def update_deck_build_intent(
    deck_id: str,
    build_intent: BuildIntent,
    current_user: Dict = Depends(get_current_user),
):
    existing = await db.decks.find_one(
        {"id": deck_id, "user_id": current_user['id']},
        {"_id": 0},
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Deck not found")
    normalized = normalize_build_intent(build_intent)
    canonical = normalized["intent"]
    if (
        canonical["starting_point"] == "existing_deck"
        and canonical.get("existing_deck_id") != deck_id
    ):
        raise HTTPException(
            status_code=400,
            detail="Build intent references a different existing deck",
        )
    commanders = [
        name for name in (
            canonical.get("commander_name"),
            canonical.get("partner_name"),
        )
        if name
    ]
    await db.decks.update_one(
        {"id": deck_id, "user_id": current_user['id']},
        {"$set": {
            "name": canonical["deck_name"],
            "commander": commanders[0] if commanders else None,
            "commanders": commanders,
            "format": canonical["format"],
            "build_intent": canonical,
            "intent_profile": normalized["deck_intent_profile"],
        }},
    )
    deck = await db.decks.find_one(
        {"id": deck_id, "user_id": current_user['id']},
        {"_id": 0},
    )
    if isinstance(deck.get('created_at'), str):
        deck['created_at'] = datetime.fromisoformat(deck['created_at'])
    return deck


def _build_draft_from_document(document: Dict[str, Any]) -> BuildDraft:
    payload = dict(document)
    payload.pop("_id", None)
    for field_name in ("created_at", "applied_at"):
        if payload.get(field_name) is not None:
            payload[field_name] = parse_stored_datetime(payload[field_name])
    return BuildDraft.model_validate(payload)


@api_router.get("/decks/{deck_id}/build-drafts", response_model=List[BuildDraft])
async def get_build_drafts(
    deck_id: str,
    current_user: Dict = Depends(get_current_user),
):
    deck = await db.decks.find_one(
        {"id": deck_id, "user_id": current_user['id']},
        {"_id": 0},
    )
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    documents = await db.build_drafts.find(
        {"deck_id": deck_id, "user_id": current_user['id']},
        {"_id": 0},
    ).sort("revision", -1).to_list(20)
    return [_build_draft_from_document(document) for document in documents]


@api_router.post("/decks/{deck_id}/build-drafts", response_model=BuildDraft)
async def create_build_draft(
    deck_id: str,
    current_user: Dict = Depends(get_current_user),
):
    deck = await db.decks.find_one(
        {"id": deck_id, "user_id": current_user['id']},
        {"_id": 0},
    )
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    if not deck.get("build_intent"):
        raise HTTPException(
            status_code=409,
            detail="Save a confirmed Guided Build plan before generating a scaffold",
        )
    normalized = await _normalize_build_intent_for_user(
        deck["build_intent"],
        current_user["id"],
        preserve_collection_reference=False,
    )
    try:
        result = await deck_constructor.construct(deck, normalized)
    except ConstructorUnavailable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    previous_documents = await db.build_drafts.find(
        {"deck_id": deck_id, "user_id": current_user['id']},
        {"_id": 0},
    ).sort("revision", -1).to_list(1)
    previous = previous_documents[0] if previous_documents else None
    revision = int(previous.get("revision", 0)) + 1 if previous else 1
    now = datetime.now(timezone.utc)
    draft = BuildDraft(
        user_id=current_user['id'],
        deck_id=deck_id,
        revision=revision,
        constructor_version=result["constructor_version"],
        status=result["status"],
        source_fingerprint=result["source_fingerprint"],
        result=result,
        change_summary=build_revision_diff(
            previous.get("result") if previous else None,
            result,
        ),
        created_at=now,
    )
    document = draft.model_dump()
    document["created_at"] = now.isoformat()
    await db.build_drafts.insert_one(document)
    return draft


@api_router.post(
    "/decks/{deck_id}/build-drafts/{draft_id}/apply",
    response_model=Deck,
)
async def apply_build_draft(
    deck_id: str,
    draft_id: str,
    request_data: BuildDraftApplyRequest,
    current_user: Dict = Depends(get_current_user),
):
    del request_data
    deck = await db.decks.find_one(
        {"id": deck_id, "user_id": current_user['id']},
        {"_id": 0},
    )
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    draft = await db.build_drafts.find_one(
        {
            "id": draft_id,
            "deck_id": deck_id,
            "user_id": current_user['id'],
        },
        {"_id": 0},
    )
    if not draft:
        raise HTTPException(status_code=404, detail="Build draft not found")
    result = draft.get("result") or {}
    validation = result.get("validation") or {}
    if not validation.get("passed") or result.get("status") == "blocked":
        raise HTTPException(
            status_code=409,
            detail="Resolve the scaffold validation errors before applying it",
        )
    if not deck.get("build_intent"):
        raise HTTPException(status_code=409, detail="The saved build intent is unavailable")
    normalized = await _normalize_build_intent_for_user(
        deck["build_intent"],
        current_user["id"],
        preserve_collection_reference=False,
    )
    current_fingerprint = deck_constructor.source_fingerprint(deck, normalized)
    if current_fingerprint != draft.get("source_fingerprint"):
        raise HTTPException(
            status_code=409,
            detail="The deck or build intent changed; regenerate the scaffold before applying it",
        )

    proposed_cards = result.get("proposed_main_deck") or []
    update_data = {
        "cards": proposed_cards,
        "color_identity": (result.get("commander") or {}).get("color_identity") or [],
        "last_build_draft_id": draft_id,
        "build_draft_revision": draft.get("revision"),
    }
    update_data["input_assessment"] = assess_deck_input({
        **deck,
        **update_data,
    })
    await db.decks.update_one(
        {"id": deck_id, "user_id": current_user['id']},
        {"$set": update_data},
    )
    applied_at = datetime.now(timezone.utc)
    await db.build_drafts.update_one(
        {"id": draft_id, "user_id": current_user['id']},
        {"$set": {"applied_at": applied_at.isoformat()}},
    )
    feedback_key = hashlib.sha256(
        f"{current_user['id']}|{deck_id}|{draft_id}|applied_build_draft".encode()
    ).hexdigest()
    feedback_document = {
        "id": str(uuid.uuid4()),
        "event_key": feedback_key,
        "user_id": current_user["id"],
        "deck_id": deck_id,
        "source_type": "build_draft",
        "source_id": draft_id,
        "action": "applied_build_draft",
        "card_name": None,
        "paired_card_name": None,
        "reason_code": None,
        "provenance": {
            "feedback_policy": feedback_policy_status(),
            "constructor_version": draft.get("constructor_version"),
            "revision": draft.get("revision"),
            "source_fingerprint": draft.get("source_fingerprint"),
            "selected_cards": [
                {
                    "name": card.get("name"),
                    "qty": card.get("qty", 1),
                    "source": card.get("source"),
                    "confidence": card.get("confidence"),
                }
                for card in result.get("selected_cards") or []
            ],
        },
        "created_at": applied_at.isoformat(),
        "updated_at": applied_at.isoformat(),
    }
    if not await db.recommendation_feedback.find_one({"event_key": feedback_key}):
        await db.recommendation_feedback.insert_one(feedback_document)
    updated = await db.decks.find_one(
        {"id": deck_id, "user_id": current_user['id']},
        {"_id": 0},
    )
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    return updated


@api_router.put("/decks/{deck_id}/intent", response_model=Deck)
async def update_deck_intent(
    deck_id: str,
    intent_profile: DeckIntentProfile,
    current_user: Dict = Depends(get_current_user),
):
    """Persist user-owned intent that recommendation inference must respect."""
    existing = await db.decks.find_one(
        {"id": deck_id, "user_id": current_user['id']},
        {"_id": 0},
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Deck not found")
    normalized = normalize_intent_profile(intent_profile)
    await db.decks.update_one(
        {"id": deck_id, "user_id": current_user['id']},
        {"$set": {"intent_profile": normalized}},
    )
    deck = await db.decks.find_one(
        {"id": deck_id, "user_id": current_user['id']},
        {"_id": 0},
    )
    if isinstance(deck.get('created_at'), str):
        deck['created_at'] = datetime.fromisoformat(deck['created_at'])
    return deck

@api_router.get("/decks/{deck_id}/cards")
async def get_deck_cards_with_images(deck_id: str, current_user: Dict = Depends(get_current_user)):
    """Get deck cards with images from Scryfall"""
    deck = await db.decks.find_one({"id": deck_id, "user_id": current_user['id']}, {"_id": 0})
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    
    cards_with_images = []
    for card in deck.get('cards', []):
        # Fetch fresh Scryfall data for image
        scryfall_card = await scryfall_service.search_card(card['name'])
        if scryfall_card:
            images = suggestion_engine._get_card_images(scryfall_card)
            card_with_image = {
                **card,
                'image_url': images['front'],
                'image_url_back': images['back'],
                'scryfall_uri': scryfall_card.get('scryfall_uri')
            }
            cards_with_images.append(card_with_image)
        else:
            cards_with_images.append(card)
    
    return {
        'deck_name': deck.get('name'),
        'commander': deck.get('commander'),
        'commanders': deck.get('commanders') or (
            [deck.get('commander')] if deck.get('commander') else []
        ),
        'cards': cards_with_images,
        'total_cards': sum(c.get('qty', 1) for c in deck.get('cards', []))
    }

@api_router.post("/decks/{deck_id}/import")
async def import_deck(deck_id: str, import_data: DeckImport, current_user: Dict = Depends(get_current_user)):
    deck = await db.decks.find_one({"id": deck_id, "user_id": current_user['id']})
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    
    try:
        # Parse deck
        parsed_deck = await deck_parser.parse_deck(import_data.source_type, import_data.source_data)
        
        # Update deck (parsed_deck['cards'] are already dicts)
        update_data = {
            "cards": parsed_deck['cards'],
            "commander": parsed_deck['commander'],
            "commanders": parsed_deck.get('commanders') or (
                [parsed_deck['commander']] if parsed_deck.get('commander') else []
            ),
            "color_identity": parsed_deck['color_identity'],
            "imported_from": import_data.source_data if import_data.source_type == "url" else "text"
        }
        input_assessment = assess_deck_input(update_data)
        update_data["input_assessment"] = input_assessment
        
        await db.decks.update_one(
            {"id": deck_id},
            {"$set": update_data}
        )
        
        total_cards = sum(card.get('qty', 1) for card in parsed_deck['cards'])
        return {
            "message": "Deck imported successfully",
            "cards_count": total_cards,
            "unique_cards_count": len(parsed_deck['cards']),
            "input_assessment": input_assessment,
        }
    except Exception as e:
        logging.error(f"Import error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to import deck: {str(e)}")

@api_router.delete("/decks/{deck_id}")
async def delete_deck(deck_id: str, current_user: Dict = Depends(get_current_user)):
    result = await db.decks.delete_one({"id": deck_id, "user_id": current_user['id']})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Deck not found")
    await db.build_drafts.delete_many({
        "deck_id": deck_id,
        "user_id": current_user['id'],
    })
    await db.recommendation_feedback.delete_many({
        "deck_id": deck_id,
        "user_id": current_user['id'],
    })
    return {"message": "Deck deleted"}


# ==================== CARD COLLECTION ROUTES ====================

def _collection_card_from_document(document: Dict[str, Any]) -> CollectionCard:
    payload = dict(document)
    payload.pop("_id", None)
    payload.pop("user_id", None)
    payload.pop("name_key", None)
    for field_name in ("created_at", "updated_at"):
        if payload.get(field_name) is not None:
            payload[field_name] = parse_stored_datetime(payload[field_name])
    return CollectionCard.model_validate(payload)


async def _collection_documents(user_id: str) -> List[Dict[str, Any]]:
    return await db.card_collection.find(
        {"user_id": user_id},
        {"_id": 0},
    ).sort("name_key", 1).to_list(5000)


async def _saved_collection_quantities(user_id: str) -> Dict[str, int]:
    documents = await _collection_documents(user_id)
    return {
        str(document.get("name")): int(document.get("quantity") or 0)
        for document in documents
        if document.get("name") and int(document.get("quantity") or 0) > 0
    }


async def _normalize_build_intent_for_user(
    value: Mapping | BuildIntent,
    user_id: str,
    *,
    preserve_collection_reference: bool,
) -> Dict[str, Any]:
    intent = value if isinstance(value, BuildIntent) else BuildIntent.model_validate(dict(value))
    if intent.collection_source != "saved_collection" or intent.collection_mode == "all_cards":
        return normalize_build_intent(intent)

    quantities = await _saved_collection_quantities(user_id)
    hydrated = intent.model_copy(update={
        "owned_card_names": [],
        "owned_card_quantities": quantities,
    })
    normalized = normalize_build_intent(hydrated)
    normalized["mapping"]["collection"].update({
        "source": "saved_collection",
        "snapshot_copy_count": sum(quantities.values()),
    })
    if preserve_collection_reference:
        normalized["intent"]["owned_card_names"] = list(intent.owned_card_names)
        normalized["intent"]["owned_card_quantities"] = dict(intent.owned_card_quantities)
    return normalized


@api_router.get("/card-collection", response_model=List[CollectionCard])
async def get_card_collection(
    current_user: Dict = Depends(get_current_user),
):
    documents = await _collection_documents(current_user["id"])
    return [_collection_card_from_document(document) for document in documents]


@api_router.get("/card-collection/summary")
async def get_card_collection_summary(
    current_user: Dict = Depends(get_current_user),
):
    documents = await _collection_documents(current_user["id"])
    quantities = [int(document.get("quantity") or 0) for document in documents]
    latest = max(
        (document.get("updated_at") for document in documents if document.get("updated_at")),
        default=None,
    )
    return {
        "unique_cards": len(documents),
        "total_copies": sum(quantities),
        "updated_at": latest,
        "builder_behavior": {
            "prefer_owned": "scoring_bias",
            "owned_only": "hard_candidate_gate",
            "ranking_training": False,
        },
    }


@api_router.post("/card-collection/import", response_model=List[CollectionCard])
async def import_card_collection(
    request_data: CollectionImportRequest,
    current_user: Dict = Depends(get_current_user),
):
    requested: Dict[str, Dict[str, Any]] = {}
    for entry in request_data.entries:
        key = entry.card_name.casefold()
        if key in requested:
            requested[key]["quantity"] = min(
                999,
                int(requested[key]["quantity"]) + entry.quantity,
            )
        else:
            requested[key] = {
                "name": entry.card_name,
                "quantity": entry.quantity,
            }

    submitted = list(requested.values())
    resolved = await scryfall_service.get_card_bulk([item["name"] for item in submitted])
    missing = [
        item["name"]
        for item, card in zip(submitted, resolved)
        if not card or not card.get("oracle_id")
    ]
    if missing:
        raise HTTPException(
            status_code=400,
            detail="Unrecognized collection cards: " + ", ".join(missing[:20]),
        )

    canonical: Dict[str, Dict[str, Any]] = {}
    for item, card in zip(submitted, resolved):
        oracle_id = str(card["oracle_id"])
        existing = canonical.get(oracle_id)
        quantity = item["quantity"] + (existing["quantity"] if existing else 0)
        images = suggestion_engine._get_card_images(card)
        canonical[oracle_id] = {
            "oracle_id": oracle_id,
            "name": str(card.get("name") or item["name"]),
            "name_key": str(card.get("name") or item["name"]).casefold(),
            "quantity": min(999, quantity),
            "image_url": images["front"],
            "type_line": card.get("type_line"),
            "color_identity": card.get("color_identity") or [],
        }

    existing_documents = await _collection_documents(current_user["id"])
    existing_by_oracle = {
        document.get("oracle_id"): document
        for document in existing_documents
        if document.get("oracle_id")
    }
    if request_data.mode == "replace":
        await db.card_collection.delete_many({"user_id": current_user["id"]})

    now = datetime.now(timezone.utc).isoformat()
    for oracle_id, card in canonical.items():
        previous = existing_by_oracle.get(oracle_id)
        document = {
            **card,
            "id": previous.get("id") if previous else str(uuid.uuid4()),
            "user_id": current_user["id"],
            "created_at": previous.get("created_at") if previous else now,
            "updated_at": now,
        }
        query = {"user_id": current_user["id"], "oracle_id": oracle_id}
        current = await db.card_collection.find_one(query, {"_id": 0})
        if current:
            await db.card_collection.update_one(query, {"$set": document})
        else:
            await db.card_collection.insert_one(document)

    return await get_card_collection(current_user=current_user)


@api_router.patch(
    "/card-collection/{oracle_id}",
    response_model=CollectionCard,
)
async def update_collection_quantity(
    oracle_id: str,
    request_data: CollectionQuantityUpdate,
    current_user: Dict = Depends(get_current_user),
):
    query = {"user_id": current_user["id"], "oracle_id": oracle_id}
    document = await db.card_collection.find_one(query, {"_id": 0})
    if not document:
        raise HTTPException(status_code=404, detail="Collection card not found")
    await db.card_collection.update_one(query, {"$set": {
        "quantity": request_data.quantity,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }})
    stored = await db.card_collection.find_one(query, {"_id": 0})
    return _collection_card_from_document(stored)


@api_router.delete("/card-collection/{oracle_id}")
async def delete_collection_card(
    oracle_id: str,
    current_user: Dict = Depends(get_current_user),
):
    result = await db.card_collection.delete_one({
        "user_id": current_user["id"],
        "oracle_id": oracle_id,
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Collection card not found")
    return {"message": "Card removed from collection"}


# ==================== PRIVATE FEEDBACK ROUTES ====================

def _feedback_from_document(document: Dict[str, Any]) -> RecommendationFeedback:
    payload = dict(document)
    payload.pop("_id", None)
    payload.pop("user_id", None)
    payload.pop("event_key", None)
    for field_name in ("created_at", "updated_at"):
        if payload.get(field_name) is not None:
            payload[field_name] = parse_stored_datetime(payload[field_name])
    return RecommendationFeedback.model_validate(payload)


def _find_suggestion(items: List[Dict[str, Any]], card_name: str) -> Optional[Dict[str, Any]]:
    key = card_name.casefold()
    return next(
        (item for item in items if str(item.get("card_name") or "").casefold() == key),
        None,
    )


@api_router.get("/feedback-policy")
async def get_feedback_policy(
    current_user: Dict = Depends(get_current_user),
):
    del current_user
    return feedback_policy_status()


@api_router.get("/decks/{deck_id}/feedback", response_model=List[RecommendationFeedback])
async def get_deck_feedback(
    deck_id: str,
    current_user: Dict = Depends(get_current_user),
):
    deck = await db.decks.find_one(
        {"id": deck_id, "user_id": current_user["id"]},
        {"_id": 0},
    )
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    documents = await db.recommendation_feedback.find(
        {"deck_id": deck_id, "user_id": current_user["id"]},
        {"_id": 0},
    ).sort("created_at", -1).to_list(500)
    return [_feedback_from_document(document) for document in documents]


@api_router.post(
    "/decks/{deck_id}/feedback",
    response_model=RecommendationFeedback,
)
async def record_recommendation_feedback(
    deck_id: str,
    request_data: RecommendationFeedbackCreate,
    current_user: Dict = Depends(get_current_user),
):
    deck = await db.decks.find_one(
        {"id": deck_id, "user_id": current_user["id"]},
        {"_id": 0},
    )
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    analysis = await db.analysis_runs.find_one({
        "id": request_data.analysis_id,
        "deck_id": deck_id,
        "user_id": current_user["id"],
    }, {"_id": 0})
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    suggestion = None
    pair_snapshot = None
    if request_data.action in {"accept_add", "reject_add"}:
        suggestion = _find_suggestion(analysis.get("suggestions_add") or [], request_data.card_name)
    elif request_data.action in {"accept_cut", "keep_cut"}:
        suggestion = _find_suggestion(analysis.get("suggestions_cut") or [], request_data.card_name)
    else:
        add_key = request_data.card_name.casefold()
        cut_key = str(request_data.paired_card_name or "").casefold()
        pair_snapshot = next((
            pair for pair in analysis.get("swap_pairs") or []
            if str((pair.get("add") or {}).get("card_name") or "").casefold() == add_key
            and str((pair.get("cut") or {}).get("card_name") or "").casefold() == cut_key
        ), None)
        suggestion = (pair_snapshot or {}).get("add")
    if not suggestion:
        raise HTTPException(
            status_code=400,
            detail="Feedback must reference a recommendation from this analysis",
        )

    action_group = (
        "add" if request_data.action in {"accept_add", "reject_add"}
        else "cut" if request_data.action in {"accept_cut", "keep_cut"}
        else "swap"
    )
    event_source = "|".join([
        current_user["id"],
        deck_id,
        request_data.analysis_id,
        action_group,
        request_data.card_name.casefold(),
        str(request_data.paired_card_name or "").casefold(),
    ])
    event_key = hashlib.sha256(event_source.encode()).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    existing = await db.recommendation_feedback.find_one(
        {"event_key": event_key},
        {"_id": 0},
    )
    provenance = {
        "feedback_policy": feedback_policy_status(),
        "analysis_created_at": analysis.get("created_at"),
        "analysis_depth": analysis.get("analysis_depth"),
        "recommendation_planner": analysis.get("recommendation_planner") or {},
        "semantic_version": suggestion_engine.get_semantic_bundle_status().get("semantic_version"),
        "suggestion": {
            key: suggestion.get(key)
            for key in (
                "card_name", "role_tag", "reason", "score", "confidence",
                "evidence_confidence", "confidence_model", "portfolio_version",
                "selection_position", "selection_reason",
            )
        },
        "pair_reason": (pair_snapshot or {}).get("reason"),
    }
    document = {
        "id": existing.get("id") if existing else str(uuid.uuid4()),
        "event_key": event_key,
        "user_id": current_user["id"],
        "deck_id": deck_id,
        "source_type": "analysis",
        "source_id": request_data.analysis_id,
        "action": request_data.action,
        "card_name": request_data.card_name,
        "paired_card_name": request_data.paired_card_name,
        "reason_code": request_data.reason_code,
        "provenance": provenance,
        "created_at": existing.get("created_at") if existing else now,
        "updated_at": now,
    }
    if existing:
        await db.recommendation_feedback.update_one(
            {"event_key": event_key},
            {"$set": document},
        )
    else:
        await db.recommendation_feedback.insert_one(document)
    return _feedback_from_document(document)


@api_router.get("/feedback-history", response_model=List[RecommendationFeedback])
async def get_feedback_history(
    current_user: Dict = Depends(get_current_user),
):
    documents = await db.recommendation_feedback.find(
        {"user_id": current_user["id"]},
        {"_id": 0},
    ).sort("created_at", -1).to_list(1000)
    return [_feedback_from_document(document) for document in documents]


@api_router.delete("/feedback-history")
async def delete_feedback_history(
    current_user: Dict = Depends(get_current_user),
):
    result = await db.recommendation_feedback.delete_many({
        "user_id": current_user["id"],
    })
    return {
        "message": "Private recommendation feedback history deleted",
        "deleted": result.deleted_count,
    }


# ==================== TRACKED COMMANDER ROUTES ====================

def _tracked_commander_from_document(document: Dict[str, Any]) -> TrackedCommander:
    payload = dict(document)
    payload.pop("_id", None)
    for field_name in ("created_at", "updated_at"):
        if payload.get(field_name) is not None:
            payload[field_name] = parse_stored_datetime(payload[field_name])
    return TrackedCommander.model_validate(payload)


@api_router.get("/tracked-commanders", response_model=List[TrackedCommander])
async def get_tracked_commanders(
    current_user: Dict = Depends(get_current_user),
):
    documents = await db.tracked_commanders.find(
        {"user_id": current_user["id"]},
        {"_id": 0},
    ).sort("updated_at", -1).to_list(500)
    return [_tracked_commander_from_document(document) for document in documents]


@api_router.get(
    "/tracked-commanders/{commander_oracle_id}",
    response_model=TrackedCommander,
)
async def get_tracked_commander(
    commander_oracle_id: str,
    current_user: Dict = Depends(get_current_user),
):
    document = await db.tracked_commanders.find_one(
        {
            "user_id": current_user["id"],
            "commander_oracle_id": commander_oracle_id,
        },
        {"_id": 0},
    )
    if not document:
        raise HTTPException(status_code=404, detail="Commander is not tracked")
    return _tracked_commander_from_document(document)


@api_router.post("/tracked-commanders", response_model=TrackedCommander)
async def track_commander(
    request_data: TrackCommanderCreate,
    current_user: Dict = Depends(get_current_user),
):
    commander_card = await scryfall_service.search_card(request_data.commander_name)
    if not commander_card:
        raise HTTPException(status_code=404, detail="Commander not found")
    if not suggestion_engine._is_commander_eligible(commander_card):
        raise HTTPException(status_code=400, detail="Card is not a legal commander")

    commander_oracle_id = commander_card.get("oracle_id")
    if not commander_oracle_id:
        raise HTTPException(
            status_code=502,
            detail="Commander identity is unavailable; try again later",
        )

    now = datetime.now(timezone.utc)
    query = {
        "user_id": current_user["id"],
        "commander_oracle_id": commander_oracle_id,
    }
    existing = await db.tracked_commanders.find_one(query, {"_id": 0})
    images = suggestion_engine._get_card_images(commander_card)
    presentation = {
        "name": commander_card.get("name") or request_data.commander_name,
        "image_url": images["front"],
        "color_identity": commander_card.get("color_identity") or [],
        "type_line": commander_card.get("type_line"),
        "updated_at": now.isoformat(),
    }

    if existing:
        if request_data.note is not None:
            presentation["note"] = request_data.note
        await db.tracked_commanders.update_one(query, {"$set": presentation})
    else:
        tracked = TrackedCommander(
            user_id=current_user["id"],
            commander_oracle_id=commander_oracle_id,
            name=presentation["name"],
            image_url=presentation["image_url"],
            color_identity=presentation["color_identity"],
            type_line=presentation["type_line"],
            source=request_data.source,
            note=request_data.note,
            created_at=now,
            updated_at=now,
        )
        document = tracked.model_dump()
        document["created_at"] = tracked.created_at.isoformat()
        document["updated_at"] = tracked.updated_at.isoformat()
        await db.tracked_commanders.insert_one(document)

    stored = await db.tracked_commanders.find_one(query, {"_id": 0})
    return _tracked_commander_from_document(stored)


@api_router.patch(
    "/tracked-commanders/{commander_oracle_id}",
    response_model=TrackedCommander,
)
async def update_tracked_commander_note(
    commander_oracle_id: str,
    request_data: TrackCommanderNoteUpdate,
    current_user: Dict = Depends(get_current_user),
):
    query = {
        "user_id": current_user["id"],
        "commander_oracle_id": commander_oracle_id,
    }
    existing = await db.tracked_commanders.find_one(query, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Commander is not tracked")

    await db.tracked_commanders.update_one(
        query,
        {"$set": {
            "note": request_data.note,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    stored = await db.tracked_commanders.find_one(query, {"_id": 0})
    return _tracked_commander_from_document(stored)


@api_router.delete("/tracked-commanders/{commander_oracle_id}")
async def untrack_commander(
    commander_oracle_id: str,
    current_user: Dict = Depends(get_current_user),
):
    result = await db.tracked_commanders.delete_one({
        "user_id": current_user["id"],
        "commander_oracle_id": commander_oracle_id,
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Commander is not tracked")
    return {"message": "Commander removed from Track List"}

# ==================== ANALYSIS ROUTES ====================

class AnalysisRequest(BaseModel):
    categories: Optional[List[str]] = None  # ['ramp', 'draw', 'removal', 'counter', 'recursion', 'tutor']
    intent_profile: Optional[DeckIntentProfile] = None

async def run_deck_analysis(
    deck_id: str,
    user_id: str,
    categories: Optional[List[str]] = None,
    deep: bool = False,
    intent_profile: Optional[DeckIntentProfile] = None,
) -> AnalysisRun:
    deck = await db.decks.find_one({"id": deck_id, "user_id": user_id}, {"_id": 0})
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    if intent_profile is not None:
        normalized_intent = normalize_intent_profile(intent_profile)
        await db.decks.update_one(
            {"id": deck_id, "user_id": user_id},
            {"$set": {"intent_profile": normalized_intent}},
        )
        deck['intent_profile'] = normalized_intent
    else:
        deck['intent_profile'] = normalize_intent_profile(
            deck.get('intent_profile')
        )
    
    input_assessment = assess_deck_input(deck)
    if not input_assessment['analysis_allowed']:
        raise HTTPException(
            status_code=400,
            detail=blocking_message(input_assessment),
        )
    
    try:
        result = await suggestion_engine.analyze_deck(deck, categories=categories, deep=deep)
        result = apply_recommendation_restraint(result, input_assessment)
        
        analysis = AnalysisRun(
            deck_id=deck_id,
            user_id=user_id,
            analysis_depth='deep' if deep else 'fast',
            suggestions_add=result['suggestions_add'],
            suggestions_cut=result['suggestions_cut'],
            swap_pairs=result.get('swap_pairs', []),
            stats=result['stats'],
            commander_synergies=result.get('commander_synergies', []),
            commander_archetypes=result.get('commander_archetypes', []),
            coverage_level=result.get('coverage_level', 'partial'),
            coverage_notes=result.get('coverage_notes'),
            coverage_signals=result.get('coverage_signals', []),
            heuristic_signals=result.get('heuristic_signals', []),
            playstyle_tips=result.get('playstyle_tips', []),
            detected_themes=result.get('detected_themes', []),
            combo_suggestions=result.get('combo_suggestions', []),
            input_assessment=result.get('input_assessment', {}),
            intent_profile=result.get('intent_profile', deck['intent_profile']),
            intent_summary=result.get('intent_summary', {}),
            deck_invariants=result.get('deck_invariants', {}),
            strategy_profile=result.get('strategy_profile', {}),
            recommendation_planner=result.get('recommendation_planner', {}),
            performance=result.get('performance', {}),
        )
        
        analysis_dict = analysis.model_dump()
        analysis_dict['created_at'] = analysis_dict['created_at'].isoformat()
        
        await db.analysis_runs.insert_one(analysis_dict)
        
        return analysis
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@api_router.post("/decks/{deck_id}/analyze", response_model=AnalysisRun)
async def analyze_deck(
    deck_id: str,
    analysis_request: Optional[AnalysisRequest] = None,
    current_user: Dict = Depends(get_current_user)
):
    categories = analysis_request.categories if analysis_request else None
    intent_profile = analysis_request.intent_profile if analysis_request else None
    return await run_deck_analysis(
        deck_id,
        current_user['id'],
        categories=categories,
        deep=False,
        intent_profile=intent_profile,
    )

@api_router.post("/decks/{deck_id}/analyze/deep", response_model=AnalysisRun)
async def deep_analyze_deck(
    deck_id: str,
    analysis_request: Optional[AnalysisRequest] = None,
    current_user: Dict = Depends(get_current_user)
):
    """Run an opt-in deeper analysis with a larger Scryfall search budget."""
    categories = analysis_request.categories if analysis_request else None
    intent_profile = analysis_request.intent_profile if analysis_request else None
    return await run_deck_analysis(
        deck_id,
        current_user['id'],
        categories=categories,
        deep=True,
        intent_profile=intent_profile,
    )

@api_router.get("/analysis/{analysis_id}", response_model=AnalysisRun)
async def get_analysis(analysis_id: str, current_user: Dict = Depends(get_current_user)):
    analysis = await db.analysis_runs.find_one(
        {"id": analysis_id, "user_id": current_user['id']},
        {"_id": 0}
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if isinstance(analysis.get('created_at'), str):
        analysis['created_at'] = datetime.fromisoformat(analysis['created_at'])
    return analysis

@api_router.get("/decks/{deck_id}/analyses", response_model=List[AnalysisRun])
async def get_deck_analyses(deck_id: str, current_user: Dict = Depends(get_current_user)):
    analyses = await db.analysis_runs.find(
        {"deck_id": deck_id, "user_id": current_user['id']},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    
    for analysis in analyses:
        if isinstance(analysis.get('created_at'), str):
            analysis['created_at'] = datetime.fromisoformat(analysis['created_at'])
    return analyses

@api_router.get("/analysis/{analysis_id}/export")
async def export_analysis(analysis_id: str, current_user: Dict = Depends(get_current_user)):
    analysis = await db.analysis_runs.find_one(
        {"id": analysis_id, "user_id": current_user['id']},
        {"_id": 0}
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    deck = await db.decks.find_one({"id": analysis['deck_id']}, {"_id": 0})
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    
    # Generate markdown export
    markdown = suggestion_engine.export_to_markdown(deck, analysis)
    
    return {"markdown": markdown, "filename": f"{deck['name']}_analysis.md"}

class ReplaceSuggestionRequest(BaseModel):
    dismissed_cards: List[str]  # List of card names to exclude
    role_tag: Optional[str] = None  # Filter by specific role

@api_router.post("/decks/{deck_id}/replace-suggestion")
async def replace_suggestion(
    deck_id: str,
    request: ReplaceSuggestionRequest,
    current_user: Dict = Depends(get_current_user)
):
    """Generate a replacement suggestion, excluding dismissed cards"""
    deck = await db.decks.find_one({"id": deck_id, "user_id": current_user['id']}, {"_id": 0})
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    
    input_assessment = assess_deck_input(deck)
    if not input_assessment['analysis_allowed']:
        raise HTTPException(
            status_code=400,
            detail=blocking_message(input_assessment),
        )
    if not input_assessment['recommendations_allowed']:
        raise HTTPException(
            status_code=400,
            detail=(
                "Automated replacements are paused until this deck's unusual "
                "construction constraint is confirmed."
            ),
        )
    
    try:
        # Get one replacement suggestion
        result = await suggestion_engine.get_replacement_suggestion(
            deck, 
            dismissed_cards=request.dismissed_cards,
            role_tag=request.role_tag
        )
        
        if not result:
            return {"suggestion": None, "message": "No more suggestions available"}
        
        return {"suggestion": result}
    except Exception as e:
        logging.error(f"Replacement suggestion error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate replacement: {str(e)}")

# ==================== COMMANDER FEATURES ====================

class CommanderLookupRequest(BaseModel):
    commander_name: str

class CommanderMoreRecommendationsRequest(BaseModel):
    commander_name: str
    exclude_names: List[str] = Field(default_factory=list)
    page: int = 1

class RandomCommanderRequest(BaseModel):
    colors: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    search_text: Optional[str] = None
    max_cmc: Optional[int] = None


@api_router.get("/commander-atlas")
async def browse_commander_atlas(
    query: str = Query(default="", max_length=80),
    colors: str = Query(default="", max_length=6),
    color_mode: str = Query(default="exact", pattern="^(exact|inclusive)$"),
    max_cmc: Optional[int] = Query(default=None, ge=0, le=20),
    archetype: str = Query(default="", max_length=40),
    playstyle: str = Query(default="", max_length=20),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=48),
    current_user: Dict = Depends(get_current_user),
):
    del current_user
    normalized_colors = "".join(dict.fromkeys(colors.upper()))
    if any(color not in "WUBRGC" for color in normalized_colors):
        raise HTTPException(status_code=400, detail="Invalid color identity filter")
    if "C" in normalized_colors and len(normalized_colors) > 1:
        raise HTTPException(
            status_code=400,
            detail="Colorless cannot be combined with colored identities",
        )
    normalized_archetype = archetype.casefold().strip()
    if normalized_archetype and normalized_archetype not in ARCHETYPE_FILTERS:
        raise HTTPException(status_code=400, detail="Unsupported archetype filter")
    normalized_playstyle = playstyle.casefold().strip()
    if normalized_playstyle and normalized_playstyle not in PLAYSTYLE_FILTERS:
        raise HTTPException(status_code=400, detail="Unsupported playstyle filter")
    return await commander_atlas.search(
        query=query,
        colors=normalized_colors,
        color_mode=color_mode,
        max_cmc=max_cmc,
        archetype=normalized_archetype,
        playstyle=normalized_playstyle,
        page=page,
        page_size=page_size,
    )


@api_router.get("/commander-atlas/{commander_oracle_id}/profile")
async def get_commander_atlas_profile(
    commander_oracle_id: str,
    current_user: Dict = Depends(get_current_user),
):
    del current_user
    match = await commander_atlas.get(commander_oracle_id)
    if not match:
        raise HTTPException(status_code=404, detail="Commander profile not found")
    analysis = await suggestion_engine.analyze_commander(match["card"])
    status = commander_atlas.get_status()
    return {
        "catalog_entry": match["catalog_entry"],
        "analysis": analysis,
        "reviewed_profile": analysis.get("reviewed_profile"),
        "data_freshness": {
            "catalog_version": status.get("catalog_version"),
            "source_updated_at": status.get("source_updated_at"),
            "semantic_version": suggestion_engine.get_semantic_bundle_status().get(
                "semantic_version"
            ),
        },
    }

def _commander_candidate_payload(card: Dict) -> Dict:
    images = suggestion_engine._get_card_images(card)
    return {
        "oracle_id": card.get("oracle_id"),
        "name": card.get("name"),
        "type_line": card.get("type_line"),
        "oracle_text": card.get("oracle_text", ""),
        "cmc": card.get("cmc", 0),
        "color_identity": card.get("color_identity", []),
        "image_url": images["front"],
        "image_url_back": images["back"],
    }

def _commander_candidate_name_matches(card_name: str, query: str) -> bool:
    tokens = re.findall(r"[A-Za-z0-9]+", query.lower())
    if not tokens:
        return False
    words = re.findall(r"[A-Za-z0-9]+", card_name.lower())
    return all(any(word.startswith(token) for word in words) for token in tokens)

@api_router.get("/commander/search")
async def search_commanders(
    query: str = Query(..., min_length=2, max_length=80),
    current_user: Dict = Depends(get_current_user)
):
    """Return commander candidates for ambiguous or partial card names."""
    safe_query = suggestion_engine._quote_scryfall_phrase(query)
    search_queries = [
        f"name:{safe_query} is:commander f:commander",
        f"{safe_query} is:commander f:commander",
    ]
    candidates = []
    seen_names = set()

    for search_query in search_queries:
        results = await scryfall_service.search_cards_by_criteria(search_query, limit=20)
        for card in results:
            if not suggestion_engine._is_commander_eligible(card):
                continue
            if not _commander_candidate_name_matches(card.get("name", ""), query):
                continue
            name_key = card.get("name", "").lower()
            if not name_key or name_key in seen_names:
                continue
            candidates.append(_commander_candidate_payload(card))
            seen_names.add(name_key)
            if len(candidates) >= 8:
                break
        if len(candidates) >= 8:
            break

    return {"query": query, "candidates": candidates}

@api_router.post("/commander/lookup")
async def lookup_commander(request: CommanderLookupRequest, current_user: Dict = Depends(get_current_user)):
    """Lookup a specific commander and provide strategy analysis"""
    try:
        # Search for commander
        commander_card = await scryfall_service.search_card(request.commander_name)
        if not commander_card:
            raise HTTPException(status_code=404, detail="Commander not found")
        
        # Check if it can actually be chosen as a commander.
        if not suggestion_engine._is_commander_eligible(commander_card):
            raise HTTPException(status_code=400, detail="Card is not a legal commander")
        
        # Analyze commander
        result = await suggestion_engine.analyze_commander(commander_card)
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Commander lookup error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Lookup failed: {str(e)}")

@api_router.post("/commander/lookup/deep")
async def deep_lookup_commander(request: CommanderLookupRequest, current_user: Dict = Depends(get_current_user)):
    """Lookup a commander with a larger recommendation search budget."""
    try:
        commander_card = await scryfall_service.search_card(request.commander_name)
        if not commander_card:
            raise HTTPException(status_code=404, detail="Commander not found")

        if not suggestion_engine._is_commander_eligible(commander_card):
            raise HTTPException(status_code=400, detail="Card is not a legal commander")

        result = await suggestion_engine.analyze_commander(commander_card, deep=True)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Deep commander lookup error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Deep lookup failed: {str(e)}")

@api_router.post("/commander/recommendations/more")
async def more_commander_recommendations(
    request: CommanderMoreRecommendationsRequest,
    current_user: Dict = Depends(get_current_user)
):
    """Search for additional commander recommendations only after the user asks."""
    try:
        commander_card = await scryfall_service.search_card(request.commander_name)
        if not commander_card:
            raise HTTPException(status_code=404, detail="Commander not found")

        if not suggestion_engine._is_commander_eligible(commander_card):
            raise HTTPException(status_code=400, detail="Card is not a legal commander")

        return await suggestion_engine.find_more_commander_recommendations(
            commander_card,
            exclude_names=request.exclude_names,
            page=request.page,
        )
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"More commander recommendation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"More recommendations failed: {str(e)}")

@api_router.post("/commander/random")
async def random_commander(request: RandomCommanderRequest, current_user: Dict = Depends(get_current_user)):
    """Generate a random commander with filters"""
    try:
        result = await suggestion_engine.get_random_commander(
            colors=request.colors,
            keywords=request.keywords,
            search_text=request.search_text,
            max_cmc=request.max_cmc
        )
        return result
    except Exception as e:
        logging.error(f"Random commander error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")

@api_router.get("/")
async def root():
    provider_status = getattr(candidate_provider, "get_status", lambda: {})()
    local_status = _local_catalog_status(provider_status)
    planner_status = suggestion_engine.get_planner_status()
    distribution_status = (
        catalog_distribution.get_status() if catalog_distribution else {"enabled": False}
    )
    semantic_status = (
        semantic_distribution.get_status() if semantic_distribution else {"enabled": False}
    )
    return {
        "message": "LandFall AI API v1.0",
        "status": "ready",
        "candidate_catalog": {
            "available": bool(local_status.get("available")),
            "loaded": bool(local_status.get("loaded")),
            "catalog_version": local_status.get("catalog_version"),
            "source_updated_at": local_status.get("source_updated_at"),
            "card_count": local_status.get("card_count"),
            "distribution_state": distribution_status.get("state", "disabled"),
        },
        "semantic_bundle": {
            **suggestion_engine.get_semantic_bundle_status(),
            "distribution_state": semantic_status.get("state", "disabled"),
        },
        "commander_atlas": commander_atlas.get_status(),
        "recommendation_planner": {
            "mode": planner_status["mode"],
            "query_planner_version": planner_status["query_planner_version"],
            "portfolio_version": planner_status["portfolio_version"],
        },
        "deck_constructor": deck_constructor.get_status(),
        "feedback": feedback_policy_status(),
    }

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app.include_router(api_router)

DEFAULT_CORS_ORIGINS = 'http://localhost:3000,http://127.0.0.1:3000'
cors_origins = [
    origin.strip()
    for origin in os.environ.get('CORS_ORIGINS', DEFAULT_CORS_ORIGINS).split(',')
    if origin.strip()
]
if ENVIRONMENT == 'production' and (not cors_origins or '*' in cors_origins):
    raise RuntimeError('CORS_ORIGINS must list trusted frontend origins in production')

@app.middleware("http")
async def enforce_trusted_origins(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin and origin not in cors_origins:
            return JSONResponse({"detail": "Origin is not allowed"}, status_code=403)
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")
    return response

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
