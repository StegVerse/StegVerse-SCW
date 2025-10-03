#!/usr/bin/env python3
"""
Patches all workflows in .github/workflows:
- Adds manual dispatch, file-triggered push on .github/trigger/<name>/**
- Adds optional nightly schedule (can be removed post-run)
- Adds top-level env kill switch if missing
- Adds job 'if: ${{ env.RUN_THIS_WORKFLOW == 'true' }}' where missing

Skips files starting with '_' (reusables).
"""
from ruamel.yaml import YAML
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
WF_DIR = ROOT / ".github" / "workflows"

yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=2, offset=2)

def patch_on_block(data, wf_stem):
    onb = data.get('on') or data.get(u'on')
    if onb is None:
        onb = {}
        data['on'] = onb
    # workflow_dispatch
    if 'workflow_dispatch' not in onb:
        onb['workflow_dispatch'] = {}

    # push paths trigger
    push = onb.get('push')
    if push is None:
        push = {}
        onb['push'] = push
    branches = push.get('branches')
    if not branches:
        push['branches'] = ['main']
    paths = push.get('paths') or []
    wanted = f".github/trigger/{wf_stem}/**"
    if wanted not in paths:
        paths.append(wanted)
    push['paths'] = paths

    # schedule (keep one default)
    if 'schedule' not in onb:
        onb['schedule'] = [{'cron': '17 4 * * *'}]  # daily 04:17 UTC

def patch_env_kill_switch(data):
    if 'env' not in data:
        data['env'] = {}
    if 'RUN_THIS_WORKFLOW' not in data['env']:
        data['env']['RUN_THIS_WORKFLOW'] = "${{ vars.RUN_THIS_WORKFLOW || 'true' }}"

def patch_job_guards(data):
    jobs = data.get('jobs', {})
    for jname, jdef in jobs.items():
        if isinstance(jdef, dict) and 'if' not in jdef:
            jdef['if'] = "${{ env.RUN_THIS_WORKFLOW == 'true' }}"

def main():
    changed = []
    for p in sorted(WF_DIR.glob("*.y*ml")):
        if p.name.startswith("_"):
            continue
        text = p.read_text(encoding="utf-8")
        try:
            data = yaml.load(text)
        except Exception as e:
            print(f"[warn] cannot parse {p}: {e}", file=sys.stderr)
            continue
        wf_stem = p.stem
        before = yaml.dump(data, sys.stdout) if False else None  # noop

        patch_on_block(data, wf_stem)
        patch_env_kill_switch(data)
        patch_job_guards(data)

        new_text = ""
        from io import StringIO
        buf = StringIO()
        yaml.dump(data, buf)
        new_text = buf.getvalue()
        if new_text != text:
            p.write_text(new_text, encoding="utf-8")
            changed.append(p.name)

    print({"changed": changed})

if __name__ == "__main__":
    main()
