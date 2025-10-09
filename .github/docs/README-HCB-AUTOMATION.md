# 🧩 Hybrid-Collab-Bridge Automation Workflows

This repository includes a fully automated export pipeline for synchronizing the **`hybrid-collab-bridge/`** module from the main `StegVerse-SCW` repository into its dedicated repository (`StegVerse/hybrid-collab-bridge`).  
All automation is handled through three coordinated GitHub Actions workflows.

---

<details>
<summary><strong>🔹 1. <code>export-hcb.yml</code></strong> — Core Export Workflow</summary>

### Purpose  
Performs the actual export, packaging, and (optionally) pushing or opening a PR to the target repository.

### Usage  
Run manually from **Actions → export-hcb → Run workflow**.

### Inputs

| Input | Description | Default |
|-------|--------------|----------|
| `repos_csv` | Comma-separated list of target repositories (`owner/repo`) | `StegVerse/hybrid-collab-bridge` |
| `export_branch` | Target branch to export to (created if missing) | `main` |
| `sync_mode` | `mirror` = replace contents, `overlay` = merge only new files | `mirror` |
| `push_strategy` | `direct` = push commits, `pr` = open pull request | `direct` |
| `version_tag` | Version tag for commit/release | `v1.2` |
| `dry_run` | `true` = build only, no push | `true` |
| `tag_repo` | `true` = create/force-push version tag | `true` |
| `release_create` | `true` = create GitHub release | `true` |

### Secrets Required
- `STEGVERSE_BOT_TOKEN` → Fine-grained PAT with:
  - Repository: *Read & Write*  
  - Actions: *Read*  
  - Metadata: *Read*

### Outputs
- Uploads a tarball (`hcb-export.tar.gz`) containing the exported bridge snapshot.  
- Optionally pushes to the target repo or opens a PR.

</details>

---

<details>
<summary><strong>🔹 2. <code>export-hcb-nightly.yml</code></strong> — Nightly Validation Workflow</summary>

### Purpose  
Performs a **nightly dry-run validation** of the export logic to detect issues early without modifying any remote repository.

### Schedule  
Runs every night at **03:15 UTC** (configurable via CRON).

### Actions  
- Calls `export-hcb.yml` using `dry_run: true`  
- Does **not** push, tag, or release  
- Validates directory structure and file changes  
- Uploads the nightly export artifact for inspection

### Manual Run  
You can trigger this workflow manually from the Actions page to perform a one-off validation.

</details>

---

<details>
<summary><strong>🔹 3. <code>export-hcb-weekly.yml</code></strong> — Weekly Two-Stage Release</summary>

### Purpose  
Executes a two-stage **weekly release routine** every Sunday:
1. Stage 1: Dry-run validation (`precheck`)
2. Stage 2: Actual push/tag/release (`push`) if validation succeeds

### Schedule  
Runs every Sunday at **03:30 UTC** (configurable via CRON).

### Manual Option  
Run manually and pass `force_push=true` to skip the dry-run and push immediately.

### Flow Summary
1. Nightly workflow validates daily.  
2. Weekly workflow confirms the Sunday snapshot is valid.  
3. Push triggers automatically (or via `force_push=true`).  
4. A new tag (`v1.2`, or specified) and release are created.

</details>

---

## 🧠 Design Notes & Best Practices

- **Single Source of Truth:**  
  `export-hcb.yml` is the reusable core. Both scheduled jobs reuse it via `workflow_call`.

- **Autonomous CI/CD:**  
  Nightly and weekly workflows automatically inherit any future updates to `export-hcb.yml`.

- **Self-Healing Export:**  
  If `StegVerse/hybrid-collab-bridge` doesn’t exist, it’s automatically created via the bot token.

- **Auditable & Traceable:**  
  Each export produces logs and artifacts showing whether files changed, tags were pushed, or PRs opened.

- **Clear Error Output:**  
  Guard clauses produce GitHub-native annotations (`::error title=...::message`) for rapid debugging.

---

## 🧾 Visual Flow Overview

```text
┌────────────────────────────┐
│ StegVerse-SCW repository   │
│  └── hybrid-collab-bridge/ │
└────────────┬───────────────┘
             │  export-hcb.yml
             ▼
     Build + Package snapshot
             │
             ▼
    export-hcb-nightly (03:15 UTC)
    export-hcb-weekly (03:30 UTC)
             │
             ▼
   ┌─────────────────────────────┐
   │ StegVerse/hybrid-collab-bridge │
   │   • PR / Direct Commit         │
   │   • Tag / Release (v1.2)       │
   └─────────────────────────────┘
