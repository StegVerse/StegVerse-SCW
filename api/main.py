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

# --------------------------
# Config & Redis connection
# --------------------------
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# Allow one or more UI origins via env (comma-separated). Example:
# UI_ORIGINS="https://scw-ui.onrender.com,https://dev-ui.example.com"
UI_ORIGINS = [o.strip() for o in os.getenv("UI_ORIGINS", "").split(",") if o.strip()]
# Quick toggle for testing: CORS_ALLOW_ALL=1
CORS_ALLOW_ALL = os.getenv("CORS_ALLOW_ALL", "0") == "1"

app = FastAPI(title="StegVerse SCW API", version="0.1.0")

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
    # If UI_ORIGINS is empty, you can hardcode your UI here during first boot:
    # UI_ORIGINS = ["https://scw-ui.onrender.com"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=UI_ORIGINS or ["https://scw-ui.onrender.com"],
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

# --------------------------
# System / Discovery
# --------------------------
@app.get("/healthz")
def healthz():
    try:
        # Light ping to Redis
        r.ping()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"unhealthy: {e}")

@app.get("/whoami")
def whoami(request: Request):
    # Respect reverse-proxy headers from Render/CF/etc
    host = request.headers.get("x-forwarded-host") or request.url.hostname
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    base = f"{proto}://{host}"
    return {"url": base, "service": "scw-api"}

@app.get("/friendly", response_class=HTMLResponse)
def friendly(request: Request):
    host = request.headers.get("x-forwarded-host") or request.url.hostname
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    base = f"{proto}://{host}"
    html = f"""
    <html>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1"/>
        <title>SCW API Helper</title>
        <style>
          body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; max-width: 760px; margin: 24px auto; line-height: 1.4; }}
          code {{ background: #f2f2f2; padding: 2px 4px; border-radius: 4px; }}
          .row a {{ margin-right: 12px; }}
          button {{ padding: 6px 10px; }}
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
        <hr/>
        <h3>Quick Start</h3>
        <ol>
          <li>Copy API URL (button above)</li>
          <li>Paste into the UI field (if not prefilled)</li>
          <li>Create Project → Run</li>
        </ol>
      </body>
    </html>
    """
    return HTMLResponse(content=html, status_code=200)

# --------------------------
# Projects
# --------------------------
@app.post("/v1/projects")
def create_project(body: ProjectCreate):
    project_id = str(uuid.uuid4())
    key = f"project:{project_id}"
    r.hset(
        key,
        mapping={
            "project_id": project_id,
            "name": body.name,
            "created_at": str(now_ts()),
        },
    )
    # Keep an index for listing
    r.sadd("projects", project_id)
    return {"project_id": project_id, "name": body.name}

@app.get("/v1/projects")
def list_projects(limit: int = 50):
    ids = list(r.smembers("projects"))
    # naive “recent first” by created_at; fetch and sort
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
# Runs
# --------------------------
@app.post("/v1/runs")
def create_run(body: RunCreate):
    ensure_project_exists(body.project_id)

    run_id = str(uuid.uuid4())
    now = str(now_ts())

    # Store run metadata
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
    # Optional index
    r.sadd("runs", run_id)

    # Queue payload for the worker
    payload = {
        "run_id": run_id,
        "project_id": body.project_id,
        "language": body.language,
        "code": body.code,
    }
    r.lpush("runs", json.dumps(payload))

    return {"run_id": run_id, "status": "queued"}

@app.get("/v1/runs/{run_id}")
def get_run(run_id: str):
    run_key = f"run:{run_id}"
    if not r.exists(run_key):
        raise HTTPException(status_code=404, detail="Run not found")

    data = r.hgetall(run_key)

    # Optional logs list (worker can push lines to this list)
    # e.g., r.rpush(f"run:{run_id}:logs", "Started...", "Executing...", "Done")
    logs_key = f"run:{run_id}:logs"
    logs: List[str] = r.lrange(logs_key, 0, -1) if r.exists(logs_key) else []

    # Optional final result string
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
