#!/usr/bin/env python3
"""
Self-healing config seeder for Steg API.

Env:
  API_URL            (required) e.g. https://scw-api.onrender.com
  CONFIG_PATH        (optional) default: .github/config/steg.json
  ADMIN_TOKEN        (optional) current admin token; if invalid we will bootstrap
  BOOTSTRAP_ALLOWED  (optional) "1"/"true" to allow auto-bootstrap (default true)

Behavior:
  1) POST config with X-Admin-Token if provided.
  2) If 403, call /v1/ops/config/bootstrap to obtain a fresh token, then retry once.
  3) Exits 0 on success; non-zero on failure with clear messages.
"""
import os, sys, json, urllib.request, urllib.error, pathlib

API_URL = os.environ.get("API_URL", "").rstrip("/")
CONFIG_PATH = os.environ.get("CONFIG_PATH", ".github/config/steg.json")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
BOOTSTRAP_ALLOWED = os.environ.get("BOOTSTRAP_ALLOWED", "true").lower() in ("1","true","yes","y")

def http(method, url, headers=None, data=None):
    req = urllib.request.Request(url, data=data, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            ctype = r.headers.get("Content-Type","")
            if "application/json" in ctype:
                try:
                    body = json.loads(body.decode("utf-8") or "{}")
                except Exception:
                    pass
            return r.getcode(), body
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = ""
        return e.code, body
    except Exception as e:
        return 0, str(e)

def load_config(path):
    p = pathlib.Path(path)
    if not p.exists():
        print(f"::error title=Config missing::File not found: {path}")
        sys.exit(2)
    try:
        return p.read_bytes()
    except Exception as e:
        print(f"::error title=Read failed::{e}")
        sys.exit(2)

def bootstrap_token():
    # Try GET then POST, accept JSON or plaintext
    for verb in ("GET","POST"):
        code, body = http(verb, f"{API_URL}/v1/ops/config/bootstrap")
        if code == 200:
            if isinstance(body, dict) and "admin_token" in body:
                return str(body["admin_token"])
            if isinstance(body, str) and body.strip():
                return body.strip()
    return ""

def post_config(token, payload):
    headers = {"Content-Type":"application/json"}
    if token:
        headers["X-Admin-Token"] = token
    return http("POST", f"{API_URL}/v1/ops/config/bootstrap", headers=headers, data=payload)

def main():
    if not API_URL:
        print("::error title=Missing API_URL::Set API_URL to your service base URL")
        return 2

    payload = load_config(CONFIG_PATH)

    # First attempt (with existing token if any)
    print("Seeding config …")
    code, body = post_config(ADMIN_TOKEN, payload)
    if code in (200,201):
        print("✔ Config applied.")
        return 0

    print(f"First attempt failed: HTTP {code}")
    if code == 403 and BOOTSTRAP_ALLOWED:
        print("Trying auto-bootstrap to fetch a fresh admin token …")
        new_token = bootstrap_token()
        if not new_token:
            print("::error title=Bootstrap failed::Could not obtain a new admin token")
            return 3
        # Retry once with new token
        code2, body2 = post_config(new_token, payload)
        if code2 in (200,201):
            print("✔ Config applied after bootstrap.")
            # Emit output for GitHub Actions to optionally store/rotate token
            print(f"::notice title=New admin token fetched::{new_token[:4]}… (masked in logs)")
            # Also write to a file (masked unless you upload it—don’t)
            pathlib.Path("self_healing_out").mkdir(parents=True, exist_ok=True)
            (pathlib.Path("self_healing_out")/"NEW_ADMIN_TOKEN.txt").write_text(new_token, encoding="utf-8")
            return 0
        print(f"::error title=Retry failed::HTTP {code2} {body2}")
        return 4

    print(f"::error title=Seeding failed::HTTP {code} {body}")
    return 5

if __name__ == "__main__":
    sys.exit(main())
