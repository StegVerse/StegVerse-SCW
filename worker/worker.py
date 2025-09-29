#!/usr/bin/env python3
import os, sys, time, json, traceback, threading
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
QUEUE_KEY = os.getenv("RUNS_QUEUE_KEY", "queue:runs")  # use same in API & Actions

# metric keys
KEY_PROCESSED = os.getenv("RUNS_PROCESSED_KEY", "metrics:runs:processed")
KEY_FAILED    = os.getenv("RUNS_FAILED_KEY",    "metrics:runs:failed")
KEY_HEARTBEAT = os.getenv("WORKER_HEARTBEAT_KEY","worker:heartbeat")

LEGACY_KEYS = ["runs"]  # any old queue keys to migrate

def log(msg, **kw):
    print(json.dumps({"ts": int(time.time()), "msg": msg, **kw}), flush=True)

def rclient():
    return redis.from_url(REDIS_URL, decode_responses=True)

def ensure_queue_is_list(r: redis.Redis):
    """Guarantee QUEUE_KEY is a list; migrate/rename bad legacy keys safely."""
    try:
        t = r.type(QUEUE_KEY)
        t = t.decode() if isinstance(t, (bytes, bytearray)) else t
    except Exception as e:
        log("redis_type_check_failed", error=str(e)); return
    if t not in (None, "none", "list"):
        backup = f"badtype:{QUEUE_KEY}:{int(time.time())}"
        try:
            r.rename(QUEUE_KEY, backup)
            log("renamed_bad_queue_key", from_key=QUEUE_KEY, to_key=backup, original_type=t)
        except redis.ResponseError:
            pass
    if not r.exists(QUEUE_KEY):
        r.lpush(QUEUE_KEY, "__init__"); r.lpop(QUEUE_KEY); log("initialized_queue_key", key=QUEUE_KEY)
    # migrate legacy list if new empty
    if r.llen(QUEUE_KEY) == 0:
        for k in LEGACY_KEYS:
            t_legacy = r.type(k)
            t_legacy = t_legacy.decode() if isinstance(t_legacy, (bytes, bytearray)) else t_legacy
            if t_legacy == "list" and r.llen(k) > 0:
                try:
                    r.rename(k, QUEUE_KEY)
                    log("migrated_legacy_queue", from_key=k, to_key=QUEUE_KEY)
                    break
                except redis.ResponseError:
                    pass
            elif t_legacy not in (None, "none"):
                backup = f"badtype:{k}:{int(time.time())}"
                try:
                    r.rename(k, backup)
                    log("renamed_bad_legacy_key", from_key=k, to_key=backup, original_type=t_legacy)
                except redis.ResponseError:
                    pass

def heartbeat_loop():
    r = rclient()
    while True:
        try:
            r.set(KEY_HEARTBEAT, int(time.time()), ex=300)  # 5-min TTL
        except Exception as e:
            log("heartbeat_error", error=str(e))
        time.sleep(30)

def process_job(payload: str):
    """Replace with your real job logic."""
    log("processing", payload=payload)
    # simulate work
    time.sleep(1)

def main():
    log("worker_start", queue=QUEUE_KEY, url=REDIS_URL)
    r = rclient()
    ensure_queue_is_list(r)

    # start heartbeat thread
    t = threading.Thread(target=heartbeat_loop, daemon=True)
    t.start()

    while True:
        try:
            item = r.brpop(QUEUE_KEY, timeout=5)
            if item is None:
                continue
            _, payload = item
            try:
                process_job(payload)
                r.incr(KEY_PROCESSED)
            except Exception as job_err:
                r.incr(KEY_FAILED)
                log("job_failed", error=str(job_err), tb=traceback.format_exc(), payload=payload)
        except redis.ResponseError as e:
            if "WRONGTYPE" in str(e).upper():
                log("wrongtype_detected_repairing", error=str(e))
                ensure_queue_is_list(r)
                time.sleep(0.5)
                continue
            log("redis_response_error", error=str(e))
            time.sleep(1)
        except Exception as e:
            log("unhandled_exception", error=str(e), tb=traceback.format_exc())
            time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("worker_stop"); sys.exit(0)
