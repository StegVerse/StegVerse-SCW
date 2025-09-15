# ---------- worker maintenance (auth) ----------
@router.post("/worker/reset")
def worker_reset(payload: Dict[str, Any] | None = None,
                 x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")):
    """
    Safely reset worker state in Redis.
    - dry_run: true  => report what would be deleted
    - purge_runs: true => delete run queues and per-run logs/results
    """
    _auth(x_admin_token)
    dry = bool((payload or {}).get("dry_run", False))
    purge_runs = bool((payload or {}).get("purge_runs", True))

    summary = {"deleted": [], "kept": [], "notes": []}

    # Queue keys you use
    queue_keys = ["runs"]  # main queue list
    # collect run:* keys if purging
    run_keys = []
    if purge_runs:
        # Scan is safer than KEYS in prod
        cursor = 0
        while True:
            cursor, batch = r.scan(cursor=cursor, match="run:*", count=500)
            run_keys.extend(batch)
            if cursor == 0:
                break

    targets = []
    for k in queue_keys:
        if r.exists(k):
            targets.append(k)
    targets.extend(run_keys)

    summary["notes"].append(f"found {len(targets)} keys to remove")

    if dry:
        summary["deleted"] = targets
        return {"ok": True, "dry_run": True, "summary": summary}

    # Execute deletion
    deleted = 0
    for k in targets:
        try:
            r.delete(k)
            deleted += 1
            summary["deleted"].append(k)
        except Exception as e:
            summary["kept"].append({"key": k, "error": str(e)})

    summary["notes"].append(f"deleted {deleted} keys")
    return {"ok": True, "dry_run": False, "summary": summary}


# ---------- cloudflare config helpers (auth) ----------
@router.post("/config/cloudflare/set")
def cf_set(payload: Dict[str, str],
           x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")):
    """
    Set/rotate Cloudflare credentials safely (stored in Redis-backed config).
    Payload: { "CLOUDFLARE_ZONE_ID": "...", "CLOUDFLARE_API_TOKEN": "..." }
    """
    _auth(x_admin_token)
    zid = (payload or {}).get("CLOUDFLARE_ZONE_ID", "").strip()
    tok = (payload or {}).get("CLOUDFLARE_API_TOKEN", "").strip()
    changed = {}
    if zid:
        set_cfg("CLOUDFLARE_ZONE_ID", zid); changed["CLOUDFLARE_ZONE_ID"] = "<set>"
    if tok:
        set_cfg("CLOUDFLARE_API_TOKEN", tok); changed["CLOUDFLARE_API_TOKEN"] = "<set>"
    return {"ok": True, "changed": changed}

@router.post("/config/cloudflare/reset")
def cf_reset(payload: Dict[str, str] | None = None,
             x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token")):
    """
    Remove Cloudflare Zone/Token from active config (disables purge button until set again).
    """
    _auth(x_admin_token)
    set_cfg("CLOUDFLARE_ZONE_ID", "")
    set_cfg("CLOUDFLARE_API_TOKEN", "")
    return {"ok": True, "changed": {"CLOUDFLARE_ZONE_ID": None, "CLOUDFLARE_API_TOKEN": None}}
