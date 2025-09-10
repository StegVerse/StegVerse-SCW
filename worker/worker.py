import os, json, time, redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

def log(run_id, line):
    r.rpush(f"run:{run_id}:logs", line)

def process_job(job):
    run_id = job["run_id"]
    run_key = f"run:{run_id}"
    r.hset(run_key, mapping={"status":"running","started_at":str(time.time())})
    log(run_id, f"Starting job {run_id} (language={job.get('language')})")
    code = job.get("code","")
    log(run_id, f"Received {len(code)} chars of code.")
    time.sleep(1.0)
    log(run_id, "Running simulated tests...")
    time.sleep(1.0)
    passed = "True" if len(code) > 0 else "False"
    log(run_id, f"Tests passed: {passed}")
    r.hset(run_key, mapping={
        "status":"completed",
        "completed_at":str(time.time()),
        "result":f"len={len(code)}, tests_passed={passed}"
    })

def main():
    print("Worker started. Listening on queue 'runs'...")
    while True:
        item = r.brpop("runs", timeout=5)
        if not item:
            continue
        _, payload = item
        try:
            job = json.loads(payload)
            process_job(job)
        except Exception as e:
            run_id = (job or {}).get("run_id","unknown")
            r.hset(f"run:{run_id}", mapping={"status":"failed","error":str(e)})
            print("Job failed:", e)

if __name__ == "__main__":
    main()