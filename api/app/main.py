import os, hmac, hashlib, json, time
from typing import Optional, Dict, Any, List
import httpx
import uvicorn
from fastapi import FastAPI, Header, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import redis

# -----------------------------
# Redis
# -----------------------------
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

K_ADMIN = "scw:admin_token"
K_BOOTSTRAP_TS = "scw:bootstrap_ts"
K_LAST_ROTATE_TS = "scw:last_rotate_ts"
K_AUDIT = "scw:audit"          # list (push JSON lines)
K_RESET_SECRET = "scw:reset_secret"  # optional: used for forced resets
K_SERVICE_REG = "scw:services" # hash for service registry (TV, SocialUpdater, etc.)

# -----------------------------
# Config / Security
# -----------------------------
HMAC_SECRET = os.getenv("HMAC_SECRET", "")  # shared across SCW, TV, SocialUpdater
ALLOW_ORIGINS = os.getenv("ALLOW_ORIGINS", "*")
ENV_NAME = os.getenv("ENV_NAME", "prod")

def now_ts() -> int:
    return int(time.time())

def audit(event: str, payload: Dict[str, Any]):
    entry = {"ts": now_ts(), "event": event, "payload": payload}
    r.lpush(K_AUDIT, json.dumps(entry))

def require_admin(x_admin_token: Optional[str]) -> None:
    stored = r.get(K_ADMIN)
    if not stored:
        raise HTTPException(status_code=403, detail="Admin token not set. Bootstrap required.")
    if not x_admin_token or x_admin_token != stored:
        raise HTTPException(status_code=403, detail="Invalid admin token.")

def sig(body: bytes) -> str:
    if not HMAC_SECRET:
        return ""
    return hmac.new(HMAC_SECRET.encode(), body, hashlib.sha256).hexdigest()

# -----------------------------
# Models
# -----------------------------
class BootstrapBody(BaseModel):
    admin_token: str = Field(min_length=16)

class RotateBody(BaseModel):
    new_admin_token: str = Field(min_length=16)
    reset_secret: Optional[str] = None  # if provided and matches stored reset-secret, allow forced rotation

class BrandWebhooks(BaseModel):
    render: List[str] = []
    netlify: List[str] = []
    vercel:  List[str] = []

class BrandManifest(BaseModel):
    brand_id: str
    app_name: str
    package_id: Optional[str] = None   # e.g. com.stegverse.republisteg
    primary_hex: str
    logo_url: str
    domain: str
    env_overrides: Dict[str, str] = {}
    webhooks: BrandWebhooks = BrandWebhooks()

class ServiceRegistration(BaseModel):
    name: str            # "token-vault", "social-updater", etc.
    base_url: str
    hmac_required: bool = True

# -----------------------------
# App
# -----------------------------
app = FastAPI(title="SCW-API", version="1.0.0", docs_url="/docs", openapi_url="/openapi.json")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOW_ORIGINS.split(",")] if ALLOW_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/v1/ops/health")
def health():
    admin_set = bool(r.get(K_ADMIN))
    return {"ok": True, "env": ENV_NAME, "admin_set": admin_set}

@app.get("/v1/ops/config/status")
def status():
   
