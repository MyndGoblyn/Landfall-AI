from fastapi import FastAPI, APIRouter, Header, HTTPException, Depends, Request, Response, status
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
from pathlib import Path
from email.message import EmailMessage
from pydantic import BaseModel, Field, ConfigDict, EmailStr, field_validator
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt
import requests

from services.scryfall_service import ScryfallService
from services.deck_parser import DeckParser
from services.enhanced_suggestion_engine import EnhancedSuggestionEngine
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
    "auth_tokens",
    "rate_limits",
]

if CAPTCHA_REQUIRED and not TURNSTILE_SECRET_KEY:
    raise RuntimeError('TURNSTILE_SECRET_KEY is required when CAPTCHA_REQUIRED=true')
if ENVIRONMENT == 'production' and REQUIRE_EMAIL_VERIFICATION and (not SMTP_HOST or not SMTP_FROM_EMAIL):
    raise RuntimeError('SMTP_HOST and SMTP_FROM_EMAIL are required for email verification in production')

security = HTTPBearer(auto_error=False)

# Create the main app
app = FastAPI()
api_router = APIRouter(prefix="/api")

# Initialize services
scryfall_service = ScryfallService()
deck_parser = DeckParser(scryfall_service)
suggestion_engine = EnhancedSuggestionEngine(scryfall_service)

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
    dev_link: Optional[str] = None

class ResetAccountsResponse(BaseModel):
    message: str
    deleted: Dict[str, int]

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
    cards: List[DeckCard] = []
    format: str = "commander"
    color_identity: List[str] = []
    imported_from: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class DeckCreate(BaseModel):
    name: str
    commander: Optional[str] = None

class DeckImport(BaseModel):
    source_type: str  # "url" or "text"
    source_data: str  # URL or decklist text

class Suggestion(BaseModel):
    card_name: str
    reason: str
    role_tag: str  # draw, ramp, removal, etc.
    cmc: float
    price: Optional[float] = None
    synergy_tags: List[str] = []
    confidence: float = 0.8
    image_url: Optional[str] = None
    image_url_back: Optional[str] = None  # For double-faced cards

class AnalysisRun(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    deck_id: str
    user_id: str
    suggestions_add: List[Suggestion] = []
    suggestions_cut: List[Suggestion] = []
    stats: Dict[str, Any] = {}
    commander_synergies: List[str] = []
    playstyle_tips: List[str] = []
    detected_themes: List[str] = []
    combo_suggestions: List[Dict[str, Any]] = []
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
        raise HTTPException(status_code=400, detail="CAPTCHA verification failed")

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
    return f"{APP_PUBLIC_URL}{path}?token={token}"

def send_email(to_email: str, subject: str, body: str) -> bool:
    if not SMTP_HOST or not SMTP_FROM_EMAIL:
        logger.warning("SMTP is not configured; email to %s was not sent", to_email)
        return False

    message = EmailMessage()
    message["From"] = SMTP_FROM_EMAIL
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
        if SMTP_USE_TLS:
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
    return AuthResponse(message="Account created", user=user)

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
    return AuthResponse(message="Login successful", user=user)

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
    return AuthResponse(message="Email verified", user=user)

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
    return AuthResponse(message="Password updated", user=user)

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
    deck = Deck(
        user_id=current_user['id'],
        name=deck_data.name,
        commander=deck_data.commander
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
            image_uris = scryfall_card.get('image_uris', {})
            card_with_image = {
                **card,
                'image_url': image_uris.get('normal') or image_uris.get('small'),
                'scryfall_uri': scryfall_card.get('scryfall_uri')
            }
            cards_with_images.append(card_with_image)
        else:
            cards_with_images.append(card)
    
    return {
        'deck_name': deck.get('name'),
        'commander': deck.get('commander'),
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
            "color_identity": parsed_deck['color_identity'],
            "imported_from": import_data.source_data if import_data.source_type == "url" else "text"
        }
        
        await db.decks.update_one(
            {"id": deck_id},
            {"$set": update_data}
        )
        
        total_cards = sum(card.get('qty', 1) for card in parsed_deck['cards'])
        return {
            "message": "Deck imported successfully",
            "cards_count": total_cards,
            "unique_cards_count": len(parsed_deck['cards'])
        }
    except Exception as e:
        logging.error(f"Import error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to import deck: {str(e)}")

@api_router.delete("/decks/{deck_id}")
async def delete_deck(deck_id: str, current_user: Dict = Depends(get_current_user)):
    result = await db.decks.delete_one({"id": deck_id, "user_id": current_user['id']})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Deck not found")
    return {"message": "Deck deleted"}

# ==================== ANALYSIS ROUTES ====================

class AnalysisRequest(BaseModel):
    categories: Optional[List[str]] = None  # ['ramp', 'draw', 'removal', 'counter', 'recursion', 'tutor']
    
@api_router.post("/decks/{deck_id}/analyze", response_model=AnalysisRun)
async def analyze_deck(
    deck_id: str, 
    analysis_request: Optional[AnalysisRequest] = None,
    current_user: Dict = Depends(get_current_user)
):
    deck = await db.decks.find_one({"id": deck_id, "user_id": current_user['id']}, {"_id": 0})
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    
    if not deck.get('cards') or len(deck['cards']) < 50:
        raise HTTPException(status_code=400, detail="Deck must have at least 50 cards to analyze")
    
    try:
        # Run suggestion engine with optional category filter
        categories = analysis_request.categories if analysis_request else None
        result = await suggestion_engine.analyze_deck(deck, categories=categories)
        
        # Create analysis run
        analysis = AnalysisRun(
            deck_id=deck_id,
            user_id=current_user['id'],
            suggestions_add=result['suggestions_add'],
            suggestions_cut=result['suggestions_cut'],
            stats=result['stats']
        )
        
        analysis_dict = analysis.model_dump()
        analysis_dict['created_at'] = analysis_dict['created_at'].isoformat()
        # Store commander synergies and playstyle tips
        analysis_dict['commander_synergies'] = result.get('commander_synergies', [])
        analysis_dict['playstyle_tips'] = result.get('playstyle_tips', [])
        analysis_dict['detected_themes'] = result.get('detected_themes', [])
        analysis_dict['combo_suggestions'] = result.get('combo_suggestions', [])
        
        await db.analysis_runs.insert_one(analysis_dict)
        
        return analysis
    except Exception as e:
        logging.error(f"Analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

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
    
    if not deck.get('cards') or len(deck['cards']) < 50:
        raise HTTPException(status_code=400, detail="Deck must have at least 50 cards")
    
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

class RandomCommanderRequest(BaseModel):
    colors: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    max_cmc: Optional[int] = None

@api_router.post("/commander/lookup")
async def lookup_commander(request: CommanderLookupRequest, current_user: Dict = Depends(get_current_user)):
    """Lookup a specific commander and provide strategy analysis"""
    try:
        # Search for commander
        commander_card = await scryfall_service.search_card(request.commander_name)
        if not commander_card:
            raise HTTPException(status_code=404, detail="Commander not found")
        
        # Check if it's a legal commander
        if not commander_card.get('legalities', {}).get('commander') == 'legal':
            raise HTTPException(status_code=400, detail="Card is not a legal commander")
        
        # Analyze commander
        result = await suggestion_engine.analyze_commander(commander_card)
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Commander lookup error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Lookup failed: {str(e)}")

@api_router.post("/commander/random")
async def random_commander(request: RandomCommanderRequest, current_user: Dict = Depends(get_current_user)):
    """Generate a random commander with filters"""
    try:
        result = await suggestion_engine.get_random_commander(
            colors=request.colors,
            keywords=request.keywords,
            max_cmc=request.max_cmc
        )
        return result
    except Exception as e:
        logging.error(f"Random commander error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")

@api_router.get("/")
async def root():
    return {"message": "LandFall AI API v1.0", "status": "ready"}

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

@app.on_event("startup")
async def prepare_database():
    if hasattr(db.users, 'create_index'):
        try:
            await db.users.create_index('email', unique=True)
            await db.auth_tokens.create_index('token_hash', unique=True)
            await db.auth_tokens.create_index('expires_at')
            await db.rate_limits.create_index('key', unique=True)
        except Exception as exc:
            logger.warning("Could not ensure auth database indexes: %s", exc)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
