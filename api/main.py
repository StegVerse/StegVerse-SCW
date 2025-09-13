import os, json, uuid, time
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import redis

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://scw-ui.onrender.com"],  # your UI origin
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

app = FastAPI(title="StegVerse SCW API", version="0.1.0")

class Project(BaseModel):
    name: str

class RunRequest(BaseModel):
    project_id: str
    language: str = "python"
    code: str
    entrypoint: Optional[str] = None

@app.get("/healthz")
def healthz():
    try:
        r.ping()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "degraded", "error": str(e)}

@app.post("/v1/projects")
def create_project(p: Project):
    pid = str(uuid.uuid4())
    r.hset(f"project:{pid}", mapping={"name": p.name, "created_at": str(time.time())})
    r.sadd("projects", pid)
    return {"project_id": pid, "name": p.name}

@app.get("/v1/projects")
def list_projects():
    ids = list(r.smembers("projects"))
    out = []
    for pid in ids:
        data = r.hgetall(f"project:{pid}")
        if data:
            out.append({"project_id": pid, **data})
    return {"projects": out}

@app.post("/v1/runs")
def create_run(req: RunRequest):
    rid = str(uuid.uuid4())
    run_key = f"run:{rid}"
    run_data = {
        "run_id": rid,
        "project_id": req.project_id,
        "language": req.language,
        "code_len": str(len(req.code)),
        "status": "queued",
        "created_at": str(time.time())
    }
    r.hset(run_key, mapping=run_data)
    payload = {
        "run_id": rid,
        "project_id": req.project_id,
        "language": req.language,
        "code": req.code,
        "entrypoint": req.entrypoint
    }
    r.lpush("runs", json.dumps(payload))
    return {"run_id": rid, "status": "queued"}

@app.get("/v1/runs/{run_id}")
def get_run(run_id: str):
    data = r.hgetall(f"run:{run_id}")
    if not data:
        raise HTTPException(status_code=404, detail="run not found")
    logs = r.lrange(f"run:{run_id}:logs", 0, -1)
    if logs:
        data["logs"] = logs
    return data
