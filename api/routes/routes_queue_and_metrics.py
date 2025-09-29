from fastapi import APIRouter
import os, json, time, redis

router = APIRouter()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
QUEUE_KEY = os.getenv("RUNS_QUEUE_KEY", "queue:runs")
KEY_PROCESSED = os.getenv("RUNS_PROCESSED_KEY", "metrics:runs:processed")
KEY_FAILED    = os.getenv("RUNS_FAILED_KEY",    "metrics:runs:failed")
KEY_HEARTBEAT = os.getenv("WORKER_HEARTBEAT_KEY","worker:heartbeat")

r = redis.from_url(REDIS_URL, decode_responses=True)

@router.post("/v1/ops/queue/test")
def queue_test():
    payload = {"task":"test", "ts": int(time.time())}
    r.lpush(QUEUE_KEY, json.dumps(payload))
    return {"queued": True, "key": QUEUE_KEY, "payload": payload}

@router.get("/v1/ops/metrics")
def metrics():
    processed = int(r.get(KEY_PROCESSED) or 0)
    failed    = int(r.get(KEY_FAILED) or 0)
    hb        = int(r.get(KEY_HEARTBEAT) or 0)
    age       = int(time.time()) - hb if hb else None
    return {
        "queue_key": QUEUE_KEY,
        "processed": processed,
        "failed": failed,
        "worker_heartbeat_ts": hb,
        "worker_heartbeat_age_sec": age
    }
