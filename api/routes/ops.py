# api/routes/ops.py
import os, json, time, urllib.request, urllib.error
from typing import Optional, Dict, Any
from fastapi import APIRouter, Header, HTTPException
import redis

router = APIRouter(prefix="/v1/ops", tags=["ops"])

# --- Redis & helpers ---
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

def get_cfg(name: str, default: Optional[str] = None) -> Optional[str]:
    # Prefer Redis config:<NAME>, else env
    val = r.get(f"config:{name}")
    if val is not None:
        return val
    return os.getenv(name, default)

def set_cfg(name: str, value: Optional[str]):
    key = f"config:{name}"
    if value is None or value == "":
        r.delete(key)
    else:
        r.set(key, value)

def cfg_dict(*names: str) -> Dict[str, Optional[str]]:
    return {n: get_cfg(n) for n in names}

# --- Config keys we care about ---
CFG_KEYS = [
    "ADMIN_TOKEN",
    "SCW_UI_URL",
    "SCW_API_URL",
    "RENDER_UI_DEPLOY_HOOK",
    "RENDER_API_DEPLOY_HOOK",
    "RENDER_WORKER_DEPLOY_HOOK",
    "CLOUDFLARE_ZONE_ID",
    "CLOUDFLARE_API_TOKEN",
    "MIN_REDEPLOY_INTERVAL_S",
]

def _admin_token() -> str:
    return get_cfg("ADMIN_TOKEN", "") or ""

def _auth(token: Optional[str]):
    admin = _admin_token()
    if not admin:
        raise HTTPException(status_code=501, detail="admin ops not configured")
    if not token or token != admin:
        raise HTTPException(status_code=403, detail="forbidden")

_last_call_at: Dict[str, float] = {}
def _throttle(key: str):
    now = time.time()
    last = _last_call_at.get(key, 0)
    gap = int(get_cfg("MIN_REDEPLOY_INTERVAL_S", "15") or "15")
    if now - last < gap:
        raise HTTPException(status_code=429, detail=f"too many requests; retry after {int(gap - (now - last))}s")
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

# ---------- read-only snapshot (no auth) ----------
@router.get("/snapshot")
def snapshot():
    ui = (get_cfg("SCW_UI_URL", "https://scw-ui.onrender.com") or "").rstrip("/")
    api = (get_cfg("SCW_API_URL", "https://scw-api.onrender.com") or "").rstrip("/")
    def jget(u):
        try:
            with urllib.request.urlopen(u, timeout=12) as r:
                return True, json.loads(r.read().decode("utf-8", "ignore"))
        except Exception as e:
            return False, str(e)
    ok_api, who = jget(api + "/whoami")
    ok_rep, rep = jget(api + "/v1/legal/report/latest")
    ok_alerts, alerts = jget(api + "/v1/legal/alerts")
    missing = [k for k in CFG_KEYS if not get_cfg(k)]
    return {
        "ui": {"base": ui}, "api": {"base": api, "ok": ok_api, "whoami": who},
        "report": {"ok": ok_rep}, "alerts": {"ok": ok_alerts},
        "config_missing": missing,
    }
    
# ---------- bootstrap (no auth if not configured yet) ----------
@router.post("/config/bootstrap")
def config_bootstrap(payload: Dict[str, str]):
    """
    First-time setup ONLY.
    If ADMIN_TOKEN is not configured (in Redis OR env), allow setting it once.
    """
    current = _admin_token()
    if current:
        raise HTTPException(status_code=409, detail="admin already configured")
    token = (payload or {}).get("ADMIN_TOKEN", "").strip()
    if not token or len(token) < 10:
        raise HTTPException(status_code=400, detail="weak or missing ADMIN_TOKEN")
    set_cfg("ADMIN_TOKEN", token)
    return {"ok": True, "message": "admin token set"}

@router.get("/config/bootstrap/status")
def config_bootstrap_status():
    """
    Returns whether bootstrap is still open (no admin set).
    """
    return {"bootstrap_open": not bool(_admin_token())}
    
# ---------- config management (auth) ----------
@router.get("/config/list")
def config_list(x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")):
    _auth(x_admin_token)
    out = {}
    for k in CFG_KEYS:
        v = get_cfg(k)
        out[k] = ("<set>" if v else None)
    return {"ok": True, "keys": out}

@router.get("/config/get/{name}")
def config_get(name: str, x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")):
    _auth(x_admin_token)
    if name not in CFG_KEYS:
        raise HTTPException(status_code=400, detail="unknown key")
    return {"ok": True, "name": name, "value": get_cfg(name)}

@router.post("/config/set")
def config_set(payload: Dict[str, str], x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")):
    _auth(x_admin_token)
    changed = {}
    for k, v in payload.items():
        if k not in CFG_KEYS:
            continue
        set_cfg(k, v)
        changed[k] = "<set>" if v else None
    return {"ok": True, "changed": changed}

# ---------- mutating ops (auth) ----------
@router.post("/purge/cloudflare")
def purge_cloudflare(x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")):
    _auth(x_admin_token)
    zid = get_cfg("CLOUDFLARE_ZONE_ID"); tok = get_cfg("CLOUDFLARE_API_TOKEN")
    if not (zid and tok):
        raise HTTPException(status_code=501, detail="cloudflare not configured")
    _throttle("purge_cf")
    url = f"https://api.cloudflare.com/client/v4/zones/{zid}/purge_cache"
    headers = {"Authorization": f"Bearer {tok}"}
    code, text = _post_json(url, {"purge_everything": True}, headers)
    return {"ok": code == 200, "status": code, "body": text[:1200]}

@router.post("/redeploy/ui")
def redeploy_ui(x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")):
    _auth(x_admin_token)
    hook = get_cfg("RENDER_UI_DEPLOY_HOOK")
    if not hook:
        raise HTTPException(status_code=501, detail="render ui deploy hook not set")
    _throttle("redeploy_ui")
    code, text = _post_json(hook, {"source": "ops"})
    return {"ok": code in (200,201,202), "status": code, "body": text[:1200]}

@router.post("/redeploy/api")
def redeploy_api(x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")):
    _auth(x_admin_token)
    hook = get_cfg("RENDER_API_DEPLOY_HOOK")
    if not hook:
        raise HTTPException(status_code=501, detail="render api deploy hook not set")
    _throttle("redeploy_api")
    code, text = _post_json(hook, {"source": "ops"})
    return {"ok": code in (200,201,202), "status": code, "body": text[:1200]}

@router.post("/redeploy/worker")
def redeploy_worker(x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")):
    _auth(x_admin_token)
    hook = get_cfg("RENDER_WORKER_DEPLOY_HOOK")
    if not hook:
        raise HTTPException(status_code=501, detail="render worker deploy hook not set")
    _throttle("redeploy_worker")
    code, text = _post_json(hook, {"source": "ops"})
    return {"ok": code in (200,201,202), "status": code, "body": text[:1200]}
