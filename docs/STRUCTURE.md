# Repository Structure

```text
.
|-- ATTIC
|   `-- README.md
|-- api
|   |-- app
|   |   `-- main.py
|   |-- routes
|   |   |-- legal.py
|   |   |-- ops.py
|   |   `-- routes_queue_and_metrics.py
|   |-- __init__.py
|   |-- dockerfile
|   |-- friendly
|   |-- main.py
|   |-- observability.py
|   |-- ops.py
|   |-- procfile
|   |-- requirements.txt
|   |-- routes_admin.py
|   `-- whoami
|-- docs
|   |-- ADR_TEMPLATE.md
|   |-- DECISIONS.md
|   |-- IDEAS.md
|   |-- OPENAPI_NOTES.md
|   |-- RUNBOOK_worker.md
|   |-- STRUCTURE.md
|   |-- WORKFLOWS.md
|   |-- operations.md
|   `-- rotations.md
|-- infra
|   `-- docker-compose.yml
|-- patches
|   |-- snippets
|   |   |-- concurrency_standard.yml
|   |   |-- last_two_status_step.yml
|   |   |-- on_standard.yml
|   |   `-- permissions_standard.yml
|   |-- README.md
|   `-- manifest.json
|-- public
|   |-- _headers
|   |-- diag.html
|   |-- quicktriggers.html
|   `-- trigger-supercheck.html
|-- scripts
|   |-- README.md
|   |-- apply_canonical_fixes.py
|   |-- apply_patches.py
|   |-- auto_fix_known_issues.py
|   |-- auto_patch.py
|   |-- auto_triage.py
|   |-- autopatch_catalog.json
|   |-- autopatch_runner.py
|   |-- collect_self_healing.py
|   |-- enqueue_test.py
|   |-- generate_tree.sh
|   |-- intent_guard.py
|   |-- known_fixes.json
|   |-- make_rebuild_bundle.sh
|   |-- patch_workflow_triggers.py
|   |-- repo_audit.py
|   |-- requirements-yaml.txt
|   |-- scan_readme_meta.sh
|   |-- topic_drift_audit.py
|   |-- triage_rules.json
|   |-- validate_and_fix.py
|   `-- yaml_corrector_v2.py
|-- specs
|   `-- REPO-SPEC.json
|-- tests
|   |-- __init__.py
|   |-- test_ops.py
|   `-- test_smoke.py
|-- ui
|   |-- pages
|   |   `-- index.js
|   |-- public
|   |   |-- Index.html
|   |   |-- diag.html
|   |   |-- manifest.json
|   |   |-- se.js
|   |   |-- stegtalk.html
|   |   `-- sw.js
|   |-- ui
|   |   `-- next.config.js
|   |-- next.config.js
|   `-- package.json
|-- worker
|   |-- dockerfile
|   |-- legal_alerts.py
|   |-- procfile
|   |-- requirements.txt
|   `-- worker.py
|-- AUTONOMY_POLICY.md
|-- CI requirements-dev.txt
|-- CONTRIBUTING.md
|-- README.md
|-- README_DEV.md
|-- README_LAYMAN.md
|-- README_OPS.md
|-- auto_patch.yml
|-- install_self_healing.sh
|-- install_self_healing_pack.sh
|-- pyproject.toml
|-- render.yaml
|-- renovate.json
|-- requirements-dev.txt
|-- security.md
`-- structure-scw.ini

18 directories, 92 files
```

Last updated: 2025-10-03T23:47:18Z
