import os, hmac, hashlib, json, time
from typing import Optional, Dict, Any, List

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# --- Storage layer: Redis (preferred) with in-memory fallback ---

USE_MEMORY_ONLY = False  # toggled if Redis fails to init
_mem_kv: Dict[str, str] = {}
_mem_list: List[str] = []

def _mem_get(key: str) -> Optional[str]:
    return _mem_kv.get(key)

def _mem_set(key: str, val: str):
    _mem_kv[key] = val

def _mem_lpush(key: str, val: str):
    _mem_list.insert(0, val)

def _mem_hset(name: str, key: str, val: str):
    _mem_kv[f"{name}:{key}"] = val

def _mem_hgetall(name: str) -> Dict[str, str]:
    prefix = f"{name}:"
    return {k[len(prefix):]: v for k, v in _mem_kv.items() if k.startswith(prefix)}

# Try to set up Redis client safely
REDIS_URL = os.getenv("REDIS_URL", "").strip()
redis_client = None
if REDIS_URL:
    try:
        import redis  # import inside try so missing package doesn't kill startup
        redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        # Do NOT ping on startup; some platforms kill on repeated ping failures.
    except Exception:
        USE_MEMORY_ONLY = True
else:
    USE_MEMORY_ONLY = True

K_ADMIN = "scw:admin_token"
K_BOOTSTRAP_TS = "scw:bootstrap_ts"
K_LAST_ROTATE_TS = "scw:last_rotate_ts"
K_AUDIT = "scw:audit"
K_RESET_SECRET = "scw:reset_secret"
K_SERVICE_REG = "scw:services"

def now_ts() -> int:
    return int(time.time())

def _get(key: str) -> Optional[str]:
    if USE_MEMORY_ONLY or not redis_client:
        return _mem_get(key)
    try:
        return redis_client.get(key)
    except Exception:
        return _mem_get(key)  # soft fallback read

def _set(key: str, val: str):
    if USE_MEMORY_ONLY or not redis_client:
        _mem_set(key, val)
        return
    try:
        redis_client.set(key, val)
    except Exception:
        _mem_set(key, val)  # soft fallback write

def _lpush(key: str, val: str):
    if USE_MEMORY_ONLY or not redis_client:
        _mem_lpush(key, val)
        return
    try:
        redis_client.lpush(key, val)
    except Exception:
        _mem_lpush(key, val)

def _hset(name: str, key: str, val: str):
    if USE_MEMORY_ONLY or not redis_client:
        _mem_hset(name, key, val)
        return
    try:
        redis_client.hset(name, key, val)
    except Exception:
        _mem_hset(name, key, val)

def _hgetall(name: str) -> Dict[str, str]:
    if USE_MEMORY_ONLY or not redis_client:
        return _mem_hgetall(name)
    try:
        return redis_client.hgetall(name)
    except Exception:
        return _mem_hgetall(name)

def audit(event: str, payload: Dict[str, Any]):
    entry = {"ts": now_ts(), "event": event, "payload": payload}
    _lpush(K_AUDIT, json.dumps(entry))

# --- Security / config ---

HMAC_SECRET = os.getenv("HMAC_SECRET", "")
ALLOW_ORIGINS = os.getenv("ALLOW_ORIGINS", "*")
ENV_NAME = os.getenv("ENV_NAME", "prod")

def sig(body: bytes) -> str:
    if not HMAC_SECRET:
        return ""
    import hashlib
    return hmac.new(HMAC_SECRET.encode(), body, hashlib.sha256).hexdigest()

def require_admin(x_admin_token: Optional[str]):
    stored = _get(K_ADMIN)
    if not stored:
        raise HTTPException(status_code=403, detail="Admin token not set. Bootstrap required.")
    if not x_admin_token or x_admin_token != stored:
        raise HTTPException(status_code=403, detail="Invalid admin token.")

# --- Models ---

class BootstrapBody(BaseModel):
    admin_token: str = Field(min_length=16)

class RotateBody(BaseModel):
    new_admin_token: str = Field(min_length=16)
    reset_secret: Optional[str] = None

class BrandWebhooks(BaseModel):
    render: List[str] = []
    netlify: List[str] = []
    vercel: List[str] = []

class BrandManifest(BaseModel):
    brand_id: str
    app_name: str
    package_id: Optional[str] = None
    primary_hex: str
    logo_url: str
    domain: str = ""
    env_overrides: Dict[str, str] = {}
    # If you want server-side override of hooks, wire them here later:
    webhooks: BrandWebhooks = BrandWebhooks()

class ServiceRegistration(BaseModel):
    name: str
    base_url: str
    hmac_required: bool = True

# --- App ---

app = FastAPI(title="SCW-API", version="1.0.1", docs_url="/docs", openapi_url="/openapi.json")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOW_ORIGINS.split(",")] if ALLOW_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/v1/ops/health")
def health():
    # No Redis calls here so health never crashes
    return {
        "ok": True,
        "env": ENV_NAME,
        "admin_set": bool(_get(K_ADMIN)),
        "storage": "memory" if (USE_MEMORY_ONLY or not REDIS_URL) else "redis",
        "redis_url_set": bool(REDIS_URL),
    }

@app.get("/v1/ops/config/status")
def status(x_admin_token: Optional[str] = Header(None, convert_underscores=False)):
    # Status is readable w/o admin to help setup (no secrets returned)
    return {
        "admin_set": bool(_get(K_ADMIN)),
        "bootstrapped_at": _get(K_BOOTSTRAP_TS),
        "last_rotate_at": _get(K_LAST_ROTATE_TS),
        "storage": "memory" if (USE_MEMORY_ONLY or not REDIS_URL) else "redis",
    }

@app.post("/v1/ops/config/bootstrap")
def bootstrap(body: BootstrapBody):
    if _get(K_ADMIN):
        raise HTTPException(status_code=409, detail="Admin token already set. Use rotate.")
    _set(K_ADMIN, body.admin_token)
    _set(K_BOOTSTRAP_TS, str(now_ts()))
    audit("bootstrap", {"ok": True})
    return {"ok": True, "message": "Admin token set."}

@app.post("/v1/ops/config/rotate")
def rotate(body: RotateBody, x_admin_token: Optional[str] = Header(None, convert_underscores=False)):
    stored = _get(K_ADMIN)
    if not stored:
        raise HTTPException(status_code=403, detail="Admin token not set. Bootstrap required.")
    reset_secret = _get(K_RESET_SECRET)
    if x_admin_token != stored and (not reset_secret or body.reset_secret != reset_secret):
        raise HTTPException(status_code=403, detail="Invalid admin token or reset secret.")
    _set(K_ADMIN, body.new_admin_token)
    _set(K_LAST_ROTATE_TS, str(now_ts()))
    audit("rotate", {"ok": True})
    return {"ok": True, "message": "Admin token rotated."}

@app.post("/v1/ops/service/register")
def svc_register(body: ServiceRegistration, x_admin_token: Optional[str] = Header(None, convert_underscores=False)):
    require_admin(x_admin_token)
    _hset(K_SERVICE_REG, body.name, json.dumps(body.dict()))
    audit("service_register", {"name": body.name})
    return {"ok": True, "message": "Service registered."}

# --- Build trigger (no-op stub + webhooks fan-out) ---

class HookResult(BaseModel):
    url: str
    status: int
    body: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

@app.post("/v1/ops/build/trigger")
def build_trigger(manifest: BrandManifest, x_admin_token: Optional[str] = Header(None, convert_underscores=False)):
    require_admin(x_admin_token)

    # Gather webhooks from env (server authority), so UI doesn't need to know secrets:
    # Comma-separated lists
    render_hooks = [h for h in os.getenv("RENDER_HOOKS", "").split(",") if h.strip()]
    netlify_hooks = [h for h in os.getenv("NETLIFY_HOOKS", "").split(",") if h.strip()]
    vercel_hooks = [h for h in os.getenv("VERCEL_HOOKS", "").split(",") if h.strip()]

    # Allow manifest.webhooks as additive (optional)
    render_hooks += manifest.webhooks.render
    netlify_hooks += manifest.webhooks.netlify
    vercel_hooks += manifest.webhooks.vercel

    payload = {
        "brand": manifest.dict(),
        "meta": {"ts": now_ts(), "env": ENV_NAME},
    }

    results: List[HookResult] = []
    async def fire(url: str):
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                # Most hooks accept POST with empty body; we send JSON so downstream can read brand vars.
                resp = await client.post(url, json=payload)
                body = None
                try:
                    body = resp.json()
                except Exception:
                    body = {"text": resp.text[:500]}
                return HookResult(url=url, status=resp.status_code, body=body)
        except Exception as e:
            return HookResult(url=url, status=0, error=str(e)[:400])

    import asyncio
    tasks = []
    for u in (render_hooks + netlify_hooks + vercel_hooks):
        tasks.append(fire(u))
    results = asyncio.get_event_loop().run_until_complete(asyncio.gather(*tasks)) if tasks else []

    audit("build_trigger", {"brand_id": manifest.brand_id, "results": [r.dict() for r in results]})
    return {"ok": True, "brand_id": manifest.brand_id, "hook_results": [r.dict() for r in results]}
