# api/observability.py
from __future__ import annotations
import uuid, os
from typing import Callable, Awaitable
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import (
    Counter, Gauge, Histogram, CollectorRegistry,
    generate_latest, CONTENT_TYPE_LATEST
)

# ---- Core HTTP metrics ----
HTTP_REQUESTS = Counter("http_requests_total", "HTTP requests", ["path", "method", "code"])
HTTP_INFLIGHT = Gauge("http_inflight_requests", "In-flight requests")
HTTP_LATENCY = Histogram("http_request_duration_seconds", "Request latency (seconds)", ["path", "method"])

# ---- App/queue metrics (exported at scrape time) ----
RUNS_QUEUE_DEPTH = Gauge("scw_runs_queue_depth", "Depth of the runs queue")
RUNS_DLQ_DEPTH   = Gauge("scw_runs_dead_queue_depth", "Depth of the dead-letter queue")
RUNS_PROCESSED_TOTAL = Gauge("scw_runs_processed_total", "Total runs processed (from Redis counter)")
RUNS_PROCESSED_BY_LANG = Gauge("scw_runs_processed_by_language", "Runs processed by language", ["language"])

class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        response: Response = await call_next(request)
        response.headers["x-request-id"] = rid
        return response

class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        HTTP_INFLIGHT.inc()
        path, method = request.url.path, request.method
        with HTTP_LATENCY.labels(path, method).time():
            try:
                response: Response = await call_next(request)
                HTTP_REQUESTS.labels(path, method, str(response.status_code)).inc()
                return response
            finally:
                HTTP_INFLIGHT.dec()

def _refresh_runtime_gauges_from_redis():
    """Called at scrape time: pull counters/gauges from Redis if available."""
    try:
        import redis
        r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
        RUNS_QUEUE_DEPTH.set(r.llen(os.getenv("RUNS_QUEUE", "runs")))
        RUNS_DLQ_DEPTH.set(r.llen(os.getenv("RUNS_DLQ", "runs:dead")))
        total = int(r.get("metrics:runs_processed_total") or 0)
        RUNS_PROCESSED_TOTAL.set(total)
        # by-language hash: metrics:runs_processed_by_lang -> {py: 10, js: 2}
        for lang, cnt in (r.hgetall("metrics:runs_processed_by_lang") or {}).items():
            try:
                RUNS_PROCESSED_BY_LANG.labels(lang).set(int(cnt))
            except Exception:
                pass
    except Exception:
        # Avoid breaking /metrics if Redis is unavailable
        pass

def install_observability(app: FastAPI) -> None:
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(MetricsMiddleware)

    @app.get("/metrics")
    def _metrics() -> Response:
        # Pull fresh queue/counter values before exposing
        _refresh_runtime_gauges_from_redis()
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
