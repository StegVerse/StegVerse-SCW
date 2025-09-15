# api/routes/ops.py
import os, json, time, urllib.request, urllib.error
from typing import Optional, Dict, Any
from fastapi import APIRouter, Header, HTTPException

router = APIRouter(prefix="/v1/ops", tags=["ops"])

# -----------------------------
# Configuration via ENV VARS
# -----------------------------
ADMIN_TOKEN               = os.getenv("ADMIN_TOKEN", "")

# Render “Deploy Hooks”
#   In Render service → Settings → Deploy hooks → copy each hook URL
RENDER_UI_DEPLOY_HOOK     = os.getenv("RENDER_UI_DEPLOY_HOOK", "")
RENDER_API_DEPLOY_HOOK    = os.getenv("RENDER_API_DEPLOY_HOOK", "")
RENDER_WORKER_DEPLOY_HOOK = os.getenv("RENDER_WORKER_DEPLOY_HOOK", "")

# Cloudflare API (for cache purge)
CLOUDFLARE_ZONE_ID        = os.getenv("CLOUDFLARE_ZONE_ID", "")
CLOUDFLARE_API_TOKEN      = os.getenv("CLOUDFLARE_API_TOKEN", "")

# Public endpoints (used by snapshot and UI diag)
SCW_UI_URL                = (os.getenv("SCW_UI_URL") or "https://scw-ui.onrender.com").rstrip("/")
SCW_API_URL               = (os.getenv("SCW_API_URL") or "https://scw-api.onrender.com").rstrip("/")

# Optional: small guard to reduce accidental hammering
MIN_REDEPLOY_INTERVAL_S   = int(os.getenv("MIN_REDEPLOY_INTERVAL_S", "15"))
_last_call_at: Dict[str, float] = {}

def _auth(token: Optional[str]):
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=501, detail="admin ops not configured")
    if not token or token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="forbidden")

def _throttle(key: str):
    now = time.time()
    last = _last_call_at.get(key, 0)
    if now - last < MIN_REDEPLOY_INTERVAL_S:
        raise HTTPException(status_code=429, detail=f"too many requests; retry after {int(MIN_REDEPLOY_INTERVAL_S - (now - last))}s")
    _last_call_at[key] = now

def _post_json(url: str, data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None):
    req = urllib.request.Request(url, method="POST")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    if data is None:
        data = {}
    body = json.dumps(data).encode("utf-8")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, body, timeout=25) as r:
        return r.status, r.read().decode("utf-8", "ignore")

# -----------------------------
# Read-only snapshot (no auth)
# -----------------------------
@router.get("/snapshot")
def snapshot():
    def jget(u):
        try:
            with urllib.request.urlopen(u, timeout=12) as r:
                return True, json.loads(r.read().decode("utf-8", "ignore"))
        except Exception as e:
            return False, str(e)
    ok_api, who = jget(SCW_API_URL + "/whoami")
    ok_rep, rep = jget(SCW_API_URL + "/v1/legal/report/latest")
    ok_alerts, alerts = jget(SCW_API_URL + "/v1/legal/alerts")
    return {
        "api": {"ok": ok_api, "whoami": who},
        "report": {"ok": ok_rep, "data": rep if ok_rep else None},
        "alerts": {"ok": ok_alerts, "data": alerts if ok_alerts else None},
        "ui": {"base": SCW_UI_URL, "api_base": SCW_API_URL},
    }

# -----------------------------
# Mutating ops (auth required)
# -----------------------------
@router.post("/purge/cloudflare")
def purge_cloudflare(x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")):
    _auth(x_admin_token)
    if not (CLOUDFLARE_ZONE_ID and CLOUDFLARE_API_TOKEN):
        raise HTTPException(status_code=501, detail="cloudflare not configured")
    _throttle("purge_cf")
    url = f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/purge_cache"
    headers = {"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}"}
    code, text = _post_json(url, {"purge_everything": True}, headers)
    return {"ok": code == 200, "status": code, "body": text[:1200]}

@router.post("/redeploy/ui")
def redeploy_ui(x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")):
    _auth(x_admin_token)
    if not RENDER_UI_DEPLOY_HOOK:
        raise HTTPException(status_code=501, detail="render ui deploy hook not set")
    _throttle("redeploy_ui")
    code, text = _post_json(RENDER_UI_DEPLOY_HOOK, {"source": "ops"})
    return {"ok": code in (200, 201, 202), "status": code, "body": text[:1200]}

@router.post("/redeploy/api")
def redeploy_api(x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")):
    _auth(x_admin_token)
    if not RENDER_API_DEPLOY_HOOK:
        raise HTTPException(status_code=501, detail="render api deploy hook not set")
    _throttle("redeploy_api")
    code, text = _post_json(RENDER_API_DEPLOY_HOOK, {"source": "ops"})
    return {"ok": code in (200, 201, 202), "status": code, "body": text[:1200]}

@router.post("/redeploy/worker")
def redeploy_worker(x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")):
    _auth(x_admin_token)
    if not RENDER_WORKER_DEPLOY_HOOK:
        raise HTTPException(status_code=501, detail="render worker deploy hook not set")
    _throttle("redeploy_worker")
    code, text = _post_json(RENDER_WORKER_DEPLOY_HOOK, {"source": "ops"})
    return {"ok": code in (200, 201, 202), "status": code, "body": text[:1200]}
