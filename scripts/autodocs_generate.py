# --- top of file (replace the existing TARGETs/markers section) ---
DOCS_DIR = pathlib.Path(".github/docs")
TARGET_DOC = DOCS_DIR / "AUTOPATCH_GUIDE.md"   # full operator guide (generated)
README = pathlib.Path("README.md")              # brief status block only

START = "<!-- autodocs:start -->"
END   = "<!-- autodocs:end -->"

def ensure_readme_markers():
    # make sure README has a small status slot
    txt = README.read_text(encoding="utf-8") if README.exists() else ""
    if START not in txt or END not in txt:
        README.parent.mkdir(parents=True, exist_ok=True)
        with README.open("a", encoding="utf-8") as w:
            if txt and not txt.endswith("\n"): w.write("\n")
            w.write("\n## Ops status\n")
            w.write(f"{START}\n")
            w.write("_No data yet — run **AutoDocs (on-demand)**._\n")
            w.write(f"{END}\n")
    return True

# after you compute `block_for_readme` and `full_guide_markdown`
DOCS_DIR.mkdir(parents=True, exist_ok=True)
TARGET_DOC.write_text(full_guide_markdown, encoding="utf-8")

# inject the small block into README between markers
txt = README.read_text(encoding="utf-8")
before, _, tail = txt.partition(START)
_, _, after = tail.partition(END)
README.write_text(
    before + START + "\n" + block_for_readme + "\n" + END + after,
    encoding="utf-8"
)
