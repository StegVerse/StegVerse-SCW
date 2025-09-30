# SCW API — OpenAPI Notes

## Versioning
- All public routes are prefixed with `/v1/`.
- Breaking changes bump the prefix: `/v2/…`.

## Idempotency
- `POST /v1/runs` accepts `Idempotency-Key` header.
- If present, the server uses this key to deduplicate run creation.
- If absent, the server computes a deterministic content hash from `{project_id, language, code}`.
- Mapping is stored in Redis under `idem:{key}` with TTL (default 86,400s).

## Observability
- `/metrics` exposes Prometheus metrics:
  - `http_requests_total{path,method,code}`
  - `http_inflight_requests`
  - `http_request_duration_seconds{path,method}`
  - `scw_runs_processed_total` (reserved; increment from worker if desired)

## Operational endpoints
- `GET /v1/ops/queues` → queue sizes (runs, dead)
- `POST /v1/ops/dlq/retry?limit=N` → move up to N messages from DLQ to runs

## CORS
- `CORS_ALLOW_ALL=1` to open up for testing.
- Otherwise, configure allowed origins with `UI_ORIGINS="https://ui.example.com,https://other.example.com"`.

## Compatibility
- Clients should tolerate additional fields in responses.
- Deprecations announced minimally 30 days in advance; old version kept for at least 90 days.
