#!/usr/bin/env python3
import os, sys, time, json, traceback
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# New, namespaced queue key (safer than bare "runs")
QUEUE_KEY = os.getenv("RUNS_QUEUE_KEY", "queue:runs")
LEGACY_KEYS = ["runs"]  # old key(s) we might migrate from

def log(msg, **kw):
    print(json.dumps({"ts": int(time.time()), "msg": msg, **kw}), flush=True)

def redis_client():
    return redis.from_url(REDIS_URL, decode_responses=True)

def ensure_queue_is_list(r: redis.Redis):
    """
    Make sure QUEUE_KEY is a list:
    - If QUEUE_KEY exists but is wrong type, rename it out of the way.
    - If legacy 'runs' exists and QUEUE_KEY doesn't, migrate it (if list).
    """
    try:
        t = r.type(QUEUE_KEY)  # returns bytes in older clients, str in newer
        t = t.decode() if isinstance(t, (bytes, bytearray)) else t
    except Exception as e:
        log("redis_type_check_failed", error=str(e))
        return

    if t not in (None, "none", "list"):
        # Move the bad key aside so the worker can create a proper list
        backup = f"badtype:{QUEUE_KEY}:{int(time.time())}"
        try:
            r.rename(QUEUE_KEY, backup)
            log("renamed_bad_queue_key", from_key=QUEUE_KEY, to_key=backup, original_type=t)
        except redis.ResponseError:
            # If key doesn’t exist or rename invalid, ignore
            pass

    # If new key doesn't exist but a legacy key does, migrate it
    exists_new = bool(r.exists(QUEUE_KEY))
    for k in LEGACY_KEYS:
        if exists_new:
            break
        t_legacy = r.type(k)
        t_legacy = t_legacy.decode() if isinstance(t_legacy, (bytes, bytearray)) else t_legacy
        if t_legacy == "list":
            try:
                r.rename(k, QUEUE_KEY)
                log("migrated_legacy_queue", from_key=k, to_key=QUEUE_KEY)
                exists_new = True
                break
            except redis.ResponseError:
                pass
        elif t_legacy not in ("none", None):
            # Don’t delete data; just move it out of the way
            backup = f"badtype:{k}:{int(time.time())}"
            try:
                r.rename(k, backup)
                log("renamed_bad_legacy_key", from_key=k, to_key=backup, original_type=t_legacy)
            except redis.ResponseError:
                pass

    # Ensure the queue key exists as a list (LPUSH of a marker + LPOP to create it)
    if not r.exists(QUEUE_KEY):
        r.lpush(QUEUE_KEY, "__init__")
        r.lpop(QUEUE_KEY)
        log("initialized_queue_key", key=QUEUE_KEY)

def process_job(payload: str):
    """
    Do your actual work here.
    Replace this stub with your logic.
    """
    log("processing", payload=payload)
    # TODO: implement actual job handling
    time.sleep(1)

def main():
    log("worker_start", queue=QUEUE_KEY, url=REDIS_URL)
    r = redis_client()
    ensure_queue_is_list(r)

    while True:
        try:
            # Block up to 5s waiting for work
            item = r.brpop(QUEUE_KEY, timeout=5)
            if item is None:
                # idle tick
                continue
            key, payload = item
            process_job(payload)
        except redis.ResponseError as e:
            # If type drift happens again, self-heal and continue
            if "WRONGTYPE" in str(e).upper():
                log("wrongtype_detected_repairing", error=str(e))
                ensure_queue_is_list(r)
                time.sleep(0.5)
                continue
            else:
                log("redis_response_error", error=str(e))
                time.sleep(1)
        except Exception as e:
            log("unhandled_exception", error=str(e), tb=traceback.format_exc())
            time.sleep(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("worker_stop")
        sys.exit(0)
