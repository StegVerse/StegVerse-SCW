# api/routes_admin.py
import os
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse
import json
import requests  # add to requirements

router = APIRouter(prefix="/v1/admin", tags=["admin"])

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
GH_OWNER = os.getenv("GITHUB_OWNER", "")
GH_REPO  = os.getenv("GITHUB_REPO", "")
GH_WORKFLOW = os.getenv("GITHUB_WORKFLOW_FILE", "one_button_supercheck.yml")
# Fine-grained PAT with "Actions: Read & Write" on this repo (or classic token with workflow scope)
GH_TOKEN = os.getenv("GITHUB_TOKEN_REPO", "")

def require_admin(x_admin_token: str | None) -> None:
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=500, detail="ADMIN_TOKEN not configured on server")
    if not x_admin_token or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="invalid X-Admin-Token")

@router.post("/supercheck/run")
def run_supercheck(
    api_base: str | None = None,
    auto_apply: bool = True,
    auto_commit: bool = False,
    queue_key: str = "queue:runs",
    x_admin_token: str | None = Header(default=None, convert_underscores=False, alias="X-Admin-Token"),
):
    """
    Triggers GitHub Actions workflow_dispatch for one_button_supercheck.yml.
    Body params (optional): api_base, auto_apply, auto_commit, queue_key.
    Auth: header X-Admin-Token must match server ADMIN_TOKEN.
    """
    require_admin(x_admin_token)

    if not (GH_OWNER and GH_REPO and GH_WORKFLOW and GH_TOKEN):
        raise HTTPException(status_code=500, detail="GitHub env not configured")

    url = f"https://api.github.com/repos/{GH_OWNER}/{GH_REPO}/actions/workflows/{GH_WORKFLOW}/dispatches"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GH_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {
        "ref": "main",
        "inputs": {
            "api_base": api_base or "",
            "queue_key": queue_key,
            "timeout_sec": "75",
            "poll_sec": "3",
            "auto_apply": "true" if auto_apply else "false",
            "auto_commit": "false" if not auto_commit else "true",
        },
    }
    r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
    if r.status_code not in (201, 204):
        raise HTTPException(status_code=502, detail=f"GitHub dispatch failed: {r.status_code} {r.text}")

    return JSONResponse({"status": "queued", "workflow": GH_WORKFLOW, "repo": f"{GH_OWNER}/{GH_REPO}"})
