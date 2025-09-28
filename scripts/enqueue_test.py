#!/usr/bin/env python3
"""
Quick producer to push one test job into the queue
Run with: python3 enqueue_test.py
"""

import os, json, redis, time

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
QUEUE_KEY = os.getenv("RUNS_QUEUE_KEY", "queue:runs")

r = redis.from_url(REDIS_URL, decode_responses=True)
payload = {"task": "test", "ts": int(time.time())}

r.lpush(QUEUE_KEY, json.dumps(payload))
print(f"✅ Enqueued job into {QUEUE_KEY}: {payload}")
