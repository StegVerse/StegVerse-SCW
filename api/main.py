# api/main.py
import os
import json
import time
import uuid
from typing import List, Optional

import redis
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

# If you have extra ops routes, this keeps them mounted.
try:
    from routes.ops import router as ops_router
except Exception:
    ops_router = None

# --------------------------
# Config & Redis connection
# --------------------------
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
RUNS_QUEUE_KEY = os.getenv("RUNS_QUEUE_KEY", "queue:runs")  # must match the worker
# Metrics keys (used by the worker; we read them here)
RUNS_PROCESSED_KEY = os.getenv("RUNS_PROCESSED_KEY", "metrics:runs:processed")
RUNS_FAILED_KEY    = os.getenv("RUNS_FAILED_KEY",    "metrics:runs:failed")
WORKER_HEARTBEAT_KEY = os.getenv("WORKER_HEARTBEAT_KEY", "worker:heartbeat")

r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# Allow one or more UI origins via env (comma-separated)
UI_ORIGINS = [o.strip() for o in os.getenv("UI_ORIGINS", "").split(",") if o.strip()]
# Quick toggle for testing: CORS_ALLOW_ALL=1
CORS_ALLOW_ALL = os.getenv("CORS_ALLOW_ALL", "0") == "1"

app = FastAPI(title="StegVerse SCW API", version="0.1.0")

# Mount external ops router if present
if ops_router:
    app.include_router(ops_router)

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
# Ops Endpoints (for automation)
# --------------------------
@app.get("/v1/ops/health")
def ops_health():
    # simple 200 OK used by Actions/Render checks
    return {"status": "ok", "ts": int(now_ts())}

@app.get("/v1/ops/env/required")
def env_required():
    required = ["REDIS_URL", "RUNS_QUEUE_KEY"]
    present = {k: (os.getenv(k) is not None) for k in required}
    return {"required": required, "present": present}

@app.post("/v1/ops/deploy/report")
def deploy_report():
    # can be extended to log/store deploy details
    return JSONResponse({"report": "Deploy acknowledged", "ts": int(now_ts())})

# Enqueue a synthetic job for end-to-end testing
@app.post("/v1/ops/queue/test")
def queue_test():
    payload = {"task": "test", "ts": int(now_ts()), "job_id": str(uuid.uuid4())}
    r.lpush(RUNS_QUEUE_KEY, json.dumps(payload))
    return {"queued": True, "key": RUNS_QUEUE_KEY, "payload": payload}

# Read worker metrics (heartbeat + counters)
@app.get("/v1/ops/metrics")
def metrics():
    processed = int(r.get(RUNS_PROCESSED_KEY) or 0)
    failed    = int(r.get(RUNS_FAILED_KEY) or 0)
    hb        = int(r.get(WORKER_HEARTBEAT_KEY) or 0)
    age       = int(now_ts()) - hb if hb else None
    return {
        "queue_key": RUNS_QUEUE_KEY,
        "processed": processed,
        "failed": failed,
        "worker_heartbeat_ts": hb,
        "worker_heartbeat_age_sec": age
    }

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
# Runs
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
    # ✅ enqueue to env-driven queue key (matches worker)
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

# Simple root ping
@app.get("/")
def root():
    return {"service": "StegVerse-SCW", "message": "API root"}
