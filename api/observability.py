# api/observability.py
from __future__ import annotations
import uuid
from typing import Callable, Awaitable
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

# ---- Prometheus metrics ----
HTTP_REQUESTS = Counter("http_requests_total", "HTTP requests", ["path", "method", "code"])
HTTP_INFLIGHT = Gauge("http_inflight_requests", "In-flight requests")
HTTP_LATENCY = Histogram("http_request_duration_seconds", "Request latency (seconds)", ["path", "method"])

RUNS_PROCESSED = Counter("scw_runs_processed_total", "Runs processed by worker")

class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        response: Response = await call_next(request)
        response.headers["x-request-id"] = rid
        return response

class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        HTTP_INFLIGHT.inc()
        path = request.url.path
        method = request.method
        with HTTP_LATENCY.labels(path, method).time():
            try:
                response: Response = await call_next(request)
                code = str(response.status_code)
                HTTP_REQUESTS.labels(path, method, code).inc()
                return response
            finally:
                HTTP_INFLIGHT.dec()

def install_observability(app: FastAPI) -> None:
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(MetricsMiddleware)

    @app.get("/metrics")
    def _metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
