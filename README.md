# StegVerse SCW (Starter Bundle, MVP)

This is a one-tap deploy starter for the Sandboxed Code Writer (SCW):
- `api/` → FastAPI with `/healthz`, `/v1/projects`, `/v1/runs`
- `worker/` → background worker consuming a Redis queue
- `ui/` → minimal Next.js front-end that calls the API
- `render.yaml` → Render.com blueprint for iPhone-friendly deployment (no local Docker needed)

## 🚀 Deploy on Render (from iPhone)
1) Push this repo to GitHub.
2) Open Render → **Blueprints → New from Blueprint** → select this repo.
3) Render provisions:
   - Redis
   - API (FastAPI)
   - Worker
   - Static UI
4) Set env vars:
   - API: `API_PORT=8080` (Redis auto-links)
   - Worker: `REDIS_URL` (auto-linked)
   - UI: `NEXT_PUBLIC_API_URL=https://<your-api>.onrender.com`
5) Deploy. Open UI → test.

## Local (optional)
```bash
docker compose -f infra/docker-compose.yml up --build