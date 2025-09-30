# Worker Runbook
## Symptoms
- DLQ grows
- processed metric flat
## Checks
- GET /v1/ops/queues
- /metrics: scw_runs_processed_total
## Remedies
- POST /v1/ops/dlq/retry
- Increase RUNS_MAX_RETRIES or fix code path
