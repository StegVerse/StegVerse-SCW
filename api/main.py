# api/main.py
import os
import json
import time
import uuid
from typing import List, Optional

import redis
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

# Routers
# - ops router is your existing operational endpoints (health, metrics, queue/test, etc.)
# - admin router (added below) lets the diag page trigger the One-Button Supercheck via GitHub Actions
try:
    from routes.ops import router as ops_router  # if you already have this
except Exception:
    ops_router = None  # safe if not present yet

from routes_admin import router as admin_router  # NEW (provided below)

# --------------------------
# Config & Redis connection
# --------------------------
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
RUNS_QUEUE_KEY = os.getenv("RUNS_QUEUE_KEY", "queue:runs")

# decode_responses=True returns str instead of bytes
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# Allow one or more UI origins via env (comma-separated)
# UI_ORIGINS="https://scw-ui.onrender.com,https://dev-ui.example.com"
UI_ORIGINS = [o.strip() for o in os.getenv("UI_ORIGINS", "").split(",") if o.strip()]
# Quick toggle for testing: CORS_ALLOW_ALL=1
CORS_ALLOW_ALL = os.getenv("CORS_ALLOW_ALL", "0") == "1"

app = FastAPI(title="StegVerse SCW API", version="0.2.0")

# --------------------------
# CORS
# --------------------------
if CORS_ALLOW_ALL:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=UI_ORIGINS or ["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# --------------------------
# Models
# --------------------------
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1)

class RunCreate(BaseModel):
    project_id: str = Field(..., min_length=1)
    language: str = Field(..., min_length=1)
    code: str = Field(..., min_length=1)

# --------------------------
# Helpers
# --------------------------
def now_ts() -> float:
    return time.time()

def ensure_project_exists(project_id: str):
    if not r.exists(f"project:{project_id}"):
        raise HTTPException(status_code=404, detail="Project not found")

def _create_project_inner(name: str):
    project_id = str(uuid.uuid4())
    key = f"project:{project_id}"
    r.hset(
        key,
        mapping={
            "project_id": project_id,
            "name": name or "Untitled",
            "created_at": str(now_ts()),
        },
    )
    r.sadd("projects", project_id)
    return {"project_id": project_id, "name": name or "Untitled"}

# --------------------------
# System / Discovery
# --------------------------
@app.get("/healthz")
def healthz():
    try:
        r.ping()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"unhealthy: {e}")

@app.get("/whoami")
def whoami(request: Request):
    host = request.headers.get("x-forwarded-host") or request.url.hostname
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    base = f"{proto}://{host}"
    return {"url": base, "service": "scw-api"}

@app.get("/friendly", response_class=HTMLResponse)
def friendly(request: Request):
    """Built-in minimal diag page with a 'Run Supercheck' button."""
    host = request.headers.get("x-forwarded-host") or request.url.hostname
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    base = f"{proto}://{host}"
    html = f"""
    <html>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1"/>
        <title>SCW API Helper</title>
        <style>
          body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; max-width: 800px; margin: 24px auto; line-height: 1.45; padding: 0 12px; }}
          code {{ background: #f2f2f2; padding: 2px 4px; border-radius: 4px; }}
          .row a {{ margin-right: 12px; }}
          button {{ padding: 8px 12px; }}
          section {{ border: 1px solid #ddd; border-radius: 8px; padding: 12px; margin-top: 16px; }}
          input[type=text], input[type=password] {{ width: 100%; padding: 8px; }}
          label {{ display: block; margin-top: 8px; }}
          pre {{ background:#f7f7f7; padding:8px; border-radius:6px; white-space:pre-wrap; }}
        </style>
      </head>
      <body>
        <h1>SCW API Helper</h1>
        <p><strong>API Base:</strong> <code id="api">{base}</code></p>
        <div class="row">
          <button onclick="navigator.clipboard.writeText(document.getElementById('api').textContent)">Copy API URL</button>
          <a href="{base}/healthz" target="_blank">Open /healthz</a>
          <a href="{base}/whoami" target="_blank">Open /whoami</a>
        </div>

        <section>
          <h3>Run One-Button Supercheck</h3>
          <label>API Base (optional)
            <input id="apiBase" type="text" placeholder="https://&lt;your-api&gt;.onrender.com" value="{base}">
          </label>
          <label>Admin Token (X-Admin-Token)
            <input id="adminToken" type="password" placeholder="Paste ADMIN_TOKEN here">
          </label>
          <div style="margin-top:8px;">
            <label><input type="checkbox" id="autoApply" checked> Auto-apply safe fixes</label>
            <label style="margin-left:12px;"><input type="checkbox" id="autoCommit"> Commit directly to main</label>
          </div>
          <button id="runSC" style="margin-top:12px;">Run Supercheck</button>
          <pre id="scOut"></pre>
        </section>

        <script>
        document.getElementById('runSC').onclick = async () => {{
          const apiBase = document.getElementById('apiBase').value.trim();
          const token = document.getElementById('adminToken').value.trim();
          const autoApply = document.getElementById('autoApply').checked;
          const autoCommit = document.getElementById('autoCommit').checked;
          const out = document.getElementById('scOut');
          out.textContent = 'Queuing Supercheck…';
          try {{
            const res = await fetch('/v1/admin/supercheck/run', {{
              method: 'POST',
              headers: {{
                'Content-Type': 'application/json',
                'X-Admin-Token': token
              }},
              body: JSON.stringify({{
                api_base: apiBase || null,
                auto_apply: autoApply,
                auto_commit: autoCommit,
                queue_key: '{RUNS_QUEUE_KEY}'
              }})
            }});
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || res.statusText);
            out.textContent = `✅ Queued: ${{data.workflow}}\\nRepo: ${{data.repo}}\\n\\nOpen GitHub → Actions → One-Button Supercheck → latest run → download artifact supercheck_bundle → open supercheck_report.md`;
          }} catch (e) {{
            out.textContent = '❌ ' + e.message + '\\n\\nTips:\\n- Make sure ADMIN_TOKEN env var matches what you typed.\\n- Set GITHUB_* env vars on the API service.\\n- Check API logs if this keeps failing.';
          }}
        }};
        </script>
      </body>
    </html>
    """
    return HTMLResponse(content=html, status_code=200)

# --------------------------
# Projects
# --------------------------
@app.post("/v1/projects")
def create_project(body: ProjectCreate):
    return _create_project_inner(body.name)

# GET fallback for convenience (no JSON body required)
@app.get("/v1/projects/create")
def create_project_simple(name: str = "Auto Smoke"):
    return _create_project_inner(name)

@app.get("/v1/projects")
def list_projects(limit: int = 50):
    ids = list(r.smembers("projects"))
    projects = []
    for pid in ids:
        data = r.hgetall(f"project:{pid}")
        if data:
            try:
                data["created_at"] = float(data.get("created_at", "0"))
            except Exception:
                data["created_at"] = 0.0
            projects.append(data)
    projects.sort(key=lambda d: d.get("created_at", 0.0), reverse=True)
    return {"projects": projects[: max(1, min(limit, 200))]}

# --------------------------
# Runs (simple queue pattern)
# --------------------------
@app.post("/v1/runs")
def create_run(body: RunCreate):
    ensure_project_exists(body.project_id)

    run_id = str(uuid.uuid4())
    now = str(now_ts())

    run_key = f"run:{run_id}"
    r.hset(
        run_key,
        mapping={
            "run_id": run_id,
            "project_id": body.project_id,
            "language": body.language,
            "status": "queued",
            "created_at": now,
            "updated_at": now,
        },
    )
    r.sadd("runs", run_id)

    payload = {
        "run_id": run_id,
        "project_id": body.project_id,
        "language": body.language,
        "code": body.code,
    }
    # enqueue to worker
    r.lpush(RUNS_QUEUE_KEY, json.dumps(payload))

    return {"run_id": run_id, "status": "queued"}

@app.get("/v1/runs/{run_id}")
def get_run(run_id: str):
    run_key = f"run:{run_id}"
    if not r.exists(run_key):
        raise HTTPException(status_code=404, detail="Run not found")

    data = r.hgetall(run_key)
    logs_key = f"run:{run_id}:logs"
    logs: List[str] = r.lrange(logs_key, 0, -1) if r.exists(logs_key) else []
    result_key = f"run:{run_id}:result"
    result: Optional[str] = r.get(result_key)

    return {
        "run_id": data.get("run_id", run_id),
        "project_id": data.get("project_id"),
        "language": data.get("language"),
        "status": data.get("status"),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
        "logs": logs,
        "result": result,
    }

# --------------------------
# Routers
# --------------------------
if ops_router is not None:
    app.include_router(ops_router)
app.include_router(admin_router)
