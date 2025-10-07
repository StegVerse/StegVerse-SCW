import os
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from .models import RunRequest, ContinueRequest, RunResponse, Turn
from .registry import ProviderRegistry
from .session_writer import ensure_session, write_text
from .strategies import consensus
from pathlib import Path
DEFAULT_CFG = (Path(__file__).resolve().parents[2] / "providers.yaml").resolve()
env_cfg = os.getenv("HCB_PROVIDERS_PATH")
if env_cfg:
    cfg_path = Path(env_cfg)
    if not cfg_path.is_absolute():
        workspace = Path(os.getenv("GITHUB_WORKSPACE", DEFAULT_CFG.parents[1]))
        cfg_path = (workspace / env_cfg).resolve()
else:
    cfg_path = DEFAULT_CFG
REG = ProviderRegistry(cfg_path=str(cfg_path))

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
app = FastAPI(title="Hybrid Collab Bridge", version="0.1.0")

# Default: providers.yaml one level up from api/
DEFAULT_CFG = (Path(__file__).resolve().parents[2] / "providers.yaml").resolve()

# Allow override via env; if relative, treat as absolute to workspace
env_cfg = os.getenv("HCB_PROVIDERS_PATH")
if env_cfg:
    cfg_path = Path(env_cfg)
    if not cfg_path.is_absolute():
        # If CI passes a relative path, make it absolute from the repo workspace
        # (GITHUB_WORKSPACE in CI; fallback to two levels up from this file)
        workspace = Path(os.getenv("GITHUB_WORKSPACE", DEFAULT_CFG.parents[1]))
        cfg_path = (workspace / env_cfg).resolve()
else:
    cfg_path = DEFAULT_CFG

REG = ProviderRegistry(cfg_path=str(cfg_path))

@app.get("/health")
async def health():
    return {
        "ok": True,
        "version": "0.1.0",
        "providers": REG.list(),
        "providers_path": str(cfg_path),
    }

def auth_or_403(token: str | None):
    if not ADMIN_TOKEN:
        return
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden: bad admin token")

@app.post("/v1/run", response_model=RunResponse)
async def run_collab(req: RunRequest, x_admin_token: str | None = Header(default=None)):
    auth_or_403(x_admin_token)
    session_dir = ensure_session(req.slug)
    write_text(session_dir, "context.md", f"# Question\n{req.question}\n\n## Context\n{req.context or ''}\n")

    text_prompt = f"{req.question}\n\nContext:\n{req.context or ''}\n\nConstraints:\n- Tone: concise\n"
    opts = {"temperature": req.temperature}
    result = await consensus(REG, req.experts, text_prompt, opts)

    turns = []
    idx = 1
    for p in result["proposals"]:
        fname = f"{idx:02d}_{p['who']}.md"
        write_text(session_dir, fname, p["out"].get("text", ""))
        turns.append(Turn(who=p["who"], output=p["out"].get("text", "")))
        idx += 1

    final_text = result["final"].get("text", "")
    write_text(session_dir, "03_referee.md", final_text)

    status = "PAUSED_FOR_REVIEW" if req.human_gate else "OK"
    return JSONResponse(
        RunResponse(
            status=status,
            session_path=str(session_dir),
            strategy=req.strategy,
            turns=turns,
            final=final_text,
        ).model_dump()
    )

@app.post("/v1/continue", response_model=RunResponse)
async def continue_collab(req: ContinueRequest, x_admin_token: str | None = Header(default=None)):
    auth_or_403(x_admin_token)
    p = Path(req.session_path)
    if not p.exists():
        raise HTTPException(404, "Session path not found")
    final_text = ""
    ref = p / "03_referee.md"
    if ref.exists():
        final_text = ref.read_text(encoding="utf-8").strip()
    return JSONResponse(
        RunResponse(
            status="OK", session_path=str(p), strategy="consensus", final=final_text, turns=[]
        ).model_dump()
    )
