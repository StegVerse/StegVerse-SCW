# hybrid-collab-bridge

A **stand-alone hybrid bridge**: API orchestration + human-coordination traces.
- **Modular adapters**: starts with **Claude**; add more experts later.
- **Human-friendly**: every run writes a Markdown session (`sessions/YYYY-MM-DD/<slug>/`)
  with `context.md`, expert drafts, and a referee merge for review.

## Quick start
```bash
# 1) env
cd hybrid-collab-bridge
cp .env.example .env
# Fill: ANTHROPIC_API_KEY, ADMIN_TOKEN

# 2) run API
cd api
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

### Endpoints
- `GET  /health`
- `POST /v1/run` — start a collaboration (writes session folder)
- `POST /v1/continue` — mark session reviewed and finalize

**Example**
```bash
export ADMIN_TOKEN=your_token
curl -s -X POST http://localhost:8080/v1/run \
  -H "Content-Type: application/json" \
  -H "X-ADMIN-TOKEN: $ADMIN_TOKEN" \
  -d '{
    "slug": "first-claude-run",
    "question": "Draft a 2-sentence pitch for StegTalk and list 3 next steps.",
    "context": "Audience: developers; emphasize privacy and onboarding.",
    "experts": ["claude"],
    "strategy": "consensus",
    "human_gate": true,
    "temperature": 0.3
  }' | jq .
```

Outputs go to `hybrid-collab-bridge/sessions/<today>/first-claude-run/`:
- `context.md`
- `01_claude.md` (draft)
- `03_referee.md` (merged / final draft)

## Add more experts later
1) Create a provider in `api/app/providers/your_adapter.py`
2) Register it in `api/app/registry.py`
3) Add an entry in `providers.yaml`

Adapters declare capabilities like `text-generate`, `image-generate`, `music-generate`.
