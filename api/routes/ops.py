import os, json, urllib.request, urllib.error
from fastapi import APIRouter, Header, HTTPException
from typing import Optional

router = APIRouter(prefix="/v1/ops", tags=["ops"])

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

RENDER_UI_DEPLOY_HOOK = os.getenv("RENDER_UI_DEPLOY_HOOK","")   # e.g., https://api.render.com/deploy/srv-xxx?key=yyy
RENDER_API_DEPLOY_HOOK = os.getenv("RENDER_API_DEPLOY_HOOK","")
RENDER_WORKER_DEPLOY_HOOK = os.getenv("RENDER_WORKER_DEPLOY_HOOK","")

CF_ZONE_ID = os.getenv("CLOUDFLARE_ZONE_ID","")
CF_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN","")

SCW_UI_URL = os.getenv("SCW_UI_URL","https://scw-ui.onrender.com").rstrip("/")
SCW_API_URL = os.getenv("SCW_API_URL","https://scw-api.onrender.com").rstrip("/")

def _auth(token: Optional[str]):
    if not ADMIN_TOKEN:
        # If not configured, allow no destructive action
        raise HTTPException(status_code=501, detail="admin ops not configured")
    if not token or token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="forbidden")

def _post(url: str, data: dict | None = None, headers: dict | None = None):
    req = urllib.request.Request(url, method="POST")
    if headers:
        for k,v in headers.items(): req.add_header(k, v)
    if data is None: data = {}
    body = json.dumps(data).encode("utf-8")
    req.add_header("Content-Type","application/json")
    with urllib.request.urlopen(req, body, timeout=20) as r:
        return r.status, r.read().decode("utf-8","ignore")

@router.post("/redeploy/ui")
def redeploy_ui(x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")):
    _auth(x_admin_token)
    if not RENDER_UI_DEPLOY_HOOK:
        raise HTTPException(status_code=501, detail="render ui deploy hook not set")
    code, text = _post(RENDER_UI_DEPLOY_HOOK, {"source":"diag-ui"})
    return {"ok": code in (200,201,202), "status": code, "body": text[:1000]}

@router.post("/redeploy/api")
def redeploy_api(x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")):
    _auth(x_admin_token)
    if not RENDER_API_DEPLOY_HOOK:
        raise HTTPException(status_code=501, detail="render api deploy hook not set")
    code, text = _post(RENDER_API_DEPLOY_HOOK, {"source":"diag-api"})
    return {"ok": code in (200,201,202), "status": code, "body": text[:1000]}

@router.post("/redeploy/worker")
def redeploy_worker(x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")):
    _auth(x_admin_token)
    if not RENDER_WORKER_DEPLOY_HOOK:
        raise HTTPException(status_code=501, detail="render worker deploy hook not set")
    code, text = _post(RENDER_WORKER_DEPLOY_HOOK, {"source":"diag-worker"})
    return {"ok": code in (200,201,202), "status": code, "body": text[:1000]}

@router.post("/purge/cloudflare")
def purge_cloudflare(x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")):
    _auth(x_admin_token)
    if not (CF_ZONE_ID and CF_API_TOKEN):
        raise HTTPException(status_code=501, detail="cloudflare not configured")
    url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/purge_cache"
    headers = {"Authorization": f"Bearer {CF_API_TOKEN}"}
    code, text = _post(url, {"purge_everything": True}, headers)
    return {"ok": code==200, "status": code, "body": text[:1000]}

# Simple snapshot (same as browser diag does)
@router.get("/snapshot")
def snapshot():
    import urllib.request, json
    def jget(u):
        try:
            with urllib.request.urlopen(u, timeout=15) as r:
                return True, json.loads(r.read().decode())
        except Exception as e:
            return False, str(e)

    ok_api, who = jget(SCW_API_URL + "/whoami")
    ok_rep, rep = jget(SCW_API_URL + "/v1/legal/report/latest")
    ok_alerts, alerts = jget(SCW_API_URL + "/v1/legal/alerts")
    return {
        "api": {"ok": ok_api, "whoami": who},
        "report": {"ok": ok_rep, "data": rep},
        "alerts": {"ok": ok_alerts, "data": alerts if ok_alerts else None}
    }
