# worker.py
from __future__ import annotations
import os, time, json, traceback
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
RUNS_QUEUE = os.getenv("RUNS_QUEUE", "runs")
DLQ_QUEUE = os.getenv("RUNS_DLQ", "runs:dead")
MAX_RETRIES = int(os.getenv("RUNS_MAX_RETRIES", "3"))           # per message
POLL_TIMEOUT = int(os.getenv("RUNS_POLL_TIMEOUT_SEC", "5"))     # BRPOP timeout

r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

def log_run(run_id: str, line: str) -> None:
    r.lpush(f"run:{run_id}:logs", line)
    r.hset(f"run:{run_id}", mapping={"updated_at": str(time.time())})

def set_status(run_id: str, status: str) -> None:
    r.hset(f"run:{run_id}", mapping={"status": status, "updated_at": str(time.time())})

def execute(payload: dict) -> str:
    """
    Your actual execution logic goes here.
    Return a string result; raise Exception for retryable failures.
    """
    lang = payload.get("language", "python")
    code = payload.get("code", "")
    # Simple demo: echo back
    time.sleep(0.5)
    return f"[{lang}] OK len(code)={len(code)}"

def main():
    print(f"Worker started. Listening on queue '{RUNS_QUEUE}'...")
    while True:
        item = r.brpop(RUNS_QUEUE, timeout=POLL_TIMEOUT)
        if not item:
            continue
        _, raw = item
        try:
            payload = json.loads(raw)
        except Exception:
            # Bad JSON → cannot process; dead-letter it
            r.lpush(DLQ_QUEUE, raw)
            continue

        run_id = payload.get("run_id") or "unknown"
        attempt = int(payload.get("_attempt", 0))
        set_status(run_id, "running")
        log_run(run_id, f"Attempt {attempt+1}")

        try:
            result = execute(payload)
            r.set(f"run:{run_id}:result", result)
            set_status(run_id, "succeeded")
            log_run(run_id, "DONE")
            # (Optional) increment a Prometheus counter via a sidecar; here we just log
        except Exception as e:
            attempt += 1
            payload["_attempt"] = attempt
            log_run(run_id, f"ERROR: {e}\n{traceback.format_exc()}")
            if attempt < MAX_RETRIES:
                # Exponential backoff (cap at 30s)
                delay = min(2 ** attempt, 30)
                time.sleep(delay)
                r.lpush(RUNS_QUEUE, json.dumps(payload))
                set_status(run_id, "queued")
            else:
                set_status(run_id, "failed")
                r.lpush(DLQ_QUEUE, json.dumps(payload))

if __name__ == "__main__":
    try:
        r.ping()
    except Exception as e:
        print(f"Redis not reachable: {e}")
        time.sleep(2)
    main()
