# StegVerse Developer Notes

## Topology
- UI static: `ui/public` (Render Static → rootDir `ui/public`, publish `.`)
- API: FastAPI under `api/` with Redis
- Worker: processes `runs` queue

## Ops
- `/diag.html`: live checks + one-tap fixes (redeploy, purge CF, reset worker)
- `/v1/ops/config/*`: Redis-backed config (ADMIN_TOKEN, Render hooks, Cloudflare creds)

## Required endpoints
- `/whoami`, `/v1/projects*`, `/v1/runs*`
- Health: `/healthz`

## Deploy
- Render Static (ui), Render Web (api), Render Worker
- Optional GH Actions: multi-deploy + CF purge on push to main
