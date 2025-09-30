# api/main.py
from __future__ import annotations
import os, json, time, uuid, hashlib
from typing import List, Optional

import redis
from fastapi import FastAPI, HTTPException, Request, Response, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

# Routers (keep your existing ops router if you have one)
try:
    from routes.ops import router as ops_router
except Exception:
    ops_router = None

# Observability
from api.observability import install_observability, RUNS_PROCESSED

# --------------------------
# Config & Redis connection
# --------------------------
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
RUNS_QUEUE = os.getenv("RUNS_QUEUE", "runs")
DLQ_QUEUE = os.getenv("RUNS_DLQ", "runs:dead")
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# Allow one or more UI origins via env (comma-separated)
UI_ORIGINS = [o.strip() for o in os.getenv("UI_ORIGINS", "").split(",") if o.strip()]
CORS_ALLOW_ALL = os.getenv("CORS_ALLOW_ALL", "0") == "1"

tags_metadata = [
    {"name": "system", "description": "Discovery & health"},
    {"name": "projects", "description": "Project CRUD"},
    {"name": "runs", "description": "Submit & inspect code runs"},
    {"name": "ops", "description": "Operational endpoints (queues, metrics)"},
]

app = FastAPI(
    title="StegVerse SCW API",
    version="0.2.0",
    openapi_tags=tags_metadata,
    description="SCW API with observability, idempotency, and ops helpers.",
)

# Install observability (request ID, Prometheus /metrics)
install_observability(app)

# Attach external router if present
if ops_router is not None:
    app.include_router(ops_router, tags=["ops"])

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

def _hash_run_fields(project_id: str, language: str, code: str) -> str:
    h = hashlib.sha256()
    h.update(project_id.encode())
    h.update(b"|")
    h.update(language.encode())
    h.update(b"|")
    h.update(code.encode())
    return h.hexdigest()

# --------------------------
# System / Discovery
# --------------------------
@app.get("/healthz", tags=["system"])
def healthz():
    try:
        r.ping()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"unhealthy: {e}")

@app.get("/whoami", tags=["system"])
def whoami(request: Request):
    host = request.headers.get("x-forwarded-host") or request.url.hostname
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    base = f"{proto}://{host}"
    return {"url": base, "service": "scw-api"}

@app.get("/friendly", response_class=HTMLResponse, tags=["system"])
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
          <a href="{base}/metrics" target="_blank">Open /metrics</a>
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
@app.post("/v1/projects", tags=["projects"])
def create_project(body: ProjectCreate):
    return _create_project_inner(body.name)

@app.get("/v1/projects/create", tags=["projects"])
def create_project_simple(name: str = "Auto Smoke"):
    return _create_project_inner(name)

@app.get("/v1/projects", tags=["projects"])
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
# Runs (with Idempotency-Key support)
# --------------------------
class RunCreateBody(RunCreate):
    pass

@app.post("/v1/runs", tags=["runs"])
def create_run(
    body: RunCreateBody,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    ensure_project_exists(body.project_id)

    # Compute a stable fingerprint; also allow client-supplied Idempotency-Key
    content_hash = _hash_run_fields(body.project_id, body.language, body.code)
    idem_key = idempotency_key or f"{body.project_id}:{content_hash}"
    idem_redis_key = f"idem:{idem_key}"

    # Fast-path: if we have a run_id recorded for this idempotency key, return it
    run_id_existing = r.get(idem_redis_key)
    if run_id_existing and r.exists(f"run:{run_id_existing}"):
        data = r.hgetall(f"run:{run_id_existing}")
        logs = r.lrange(f"run:{run_id_existing}:logs", 0, -1) if r.exists(f"run:{run_id_existing}:logs") else []
        result = r.get(f"run:{run_id_existing}:result")
        return {
            "run_id": run_id_existing,
            "status": data.get("status", "queued"),
            "idempotent": True,
            "logs": logs,
            "result": result,
        }

    # Otherwise, create a new run
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
        "_content_hash": content_hash,
        "_created": now,
    }
    r.lpush(RUNS_QUEUE, json.dumps(payload))

    # Remember idempotency mapping with a TTL (avoid unbounded growth)
    r.setex(idem_redis_key, int(os.getenv("IDEMPOTENCY_TTL_SEC", "86400")), run_id)

    return {"run_id": run_id, "status": "queued", "idempotent": False}

@app.get("/v1/runs/{run_id}", tags=["runs"])
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
# Ops helpers (queues / dlq)
# --------------------------
@app.get("/v1/ops/queues", tags=["ops"])
def queues():
    sizes = {
        "runs": r.llen(RUNS_QUEUE),
        "dead": r.llen(DLQ_QUEUE),
        "projects": r.scard("projects"),
        "runs_set": r.scard("runs"),
    }
    return {"ok": True, "sizes": sizes}

@app.post("/v1/ops/dlq/retry", tags=["ops"])
def dlq_retry(limit: int = 100):
    moved = 0
    for _ in range(max(1, min(limit, 1000))):
        item = r.rpop(DLQ_QUEUE)
        if not item: break
        r.lpush(RUNS_QUEUE, item)
        moved += 1
    return {"ok": True, "moved": moved}
