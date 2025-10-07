import pathlib, datetime

def ensure_session(slug: str, base: str = "hybrid-collab-bridge/sessions") -> pathlib.Path:
    date = datetime.date.today().isoformat()
    p = pathlib.Path(base) / date / slug
    p.mkdir(parents=True, exist_ok=True)
    (p / "artifacts").mkdir(exist_ok=True)
    return p

def write_text(path: pathlib.Path, name: str, text: str):
    (path / name).write_text(text or "", encoding="utf-8")
    return str(path / name)
