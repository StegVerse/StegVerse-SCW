import { useState, useEffect } from "react";

function heuristicFromRenderHost() {
  if (typeof window === "undefined") return "";
  const m = window.location.hostname.match(/^scw-ui-(.+)\.onrender\.com$/);
  return m && m[1] ? `https://scw-api-${m[1]}.onrender.com` : "";
}

function pickInitialApiUrl() {
  // 1) Build-time env var
  if (process.env.NEXT_PUBLIC_API_URL && process.env.NEXT_PUBLIC_API_URL.trim()) {
    return process.env.NEXT_PUBLIC_API_URL.trim();
  }
  // 2) Last good value
  if (typeof window !== "undefined") {
    const saved = localStorage.getItem("apiUrl");
    if (saved && saved.trim()) return saved.trim();
  }
  // 3) Render heuristic
  const guess = heuristicFromRenderHost();
  if (guess) return guess;
  // 4) Else empty; we'll try same-origin /whoami after mount
  return "";
}

export default function Home() {
  const [apiUrl, setApiUrl] = useState(pickInitialApiUrl());
  const [projectId, setProjectId] = useState("");
  const [code, setCode] = useState("print('auto smoke run')");
  const [runId, setRunId] = useState("");
  const [result, setResult] = useState(null);
  const [statusMsg, setStatusMsg] = useState("");
  const [discoveryNotes, setDiscoveryNotes] = useState([]);

  // Log how we’re deciding (for the “Discovery Guide” panel)
  useEffect(() => {
    const notes = [];
    notes.push("1) Look for NEXT_PUBLIC_API_URL at build time.");
    if (process.env.NEXT_PUBLIC_API_URL) {
      notes.push("→ Found build-time env var; using it.");
    } else {
      notes.push("→ Not set.");
    }
    notes.push("2) Look for saved value in localStorage.");
    if (typeof window !== "undefined" && localStorage.getItem("apiUrl")) {
      notes.push("→ Found saved value; will use it.");
    } else {
      notes.push("→ None saved.");
    }
    notes.push("3) If hosted on Render, map scw-ui-<hash>.onrender.com → scw-api-<hash>.onrender.com.");
    if (heuristicFromRenderHost()) {
      notes.push("→ Heuristic produced a candidate.");
    } else {
      notes.push("→ Not on Render or pattern not matched.");
    }
    notes.push("4) Probe same-origin /whoami (works if a reverse proxy routes API & UI together).");
    setDiscoveryNotes(notes);
  }, []);

  // Persist when changed
  useEffect(() => {
    if (apiUrl) localStorage.setItem("apiUrl", apiUrl);
  }, [apiUrl]);

  // 4) Same-origin probe for /whoami if still empty
  useEffect(() => {
    (async () => {
      if (apiUrl) return;
      try {
        const r = await fetch("/whoami");
        if (r.ok) {
          const j = await r.json();
          if (j && j.url) setApiUrl(j.url);
        }
      } catch (_) {/* ignore */}
    })();
  }, [apiUrl]);

  // Auto smoke on detect
  useEffect(() => {
    (async () => {
      if (!apiUrl) { setStatusMsg("API URL not detected. Paste or use Auto-detect."); return; }
      try {
        setStatusMsg("Pinging API...");
        const h = await fetch(`${apiUrl}/healthz`);
        if (!h.ok) throw new Error("healthz not ok");

        setStatusMsg("API OK. Creating project...");
        const p = await fetch(`${apiUrl}/v1/projects`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: "Auto Smoke" })
        }).then(r => r.json());
        if (!p.project_id) throw new Error("No project_id");
        setProjectId(p.project_id);

        setStatusMsg("Queuing run...");
        const run = await fetch(`${apiUrl}/v1/runs`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ project_id: p.project_id, language: "python", code })
        }).then(r => r.json());
        if (!run.run_id) throw new Error("No run_id");
        setRunId(run.run_id);

        setStatusMsg("Polling...");
        const poll = setInterval(async () => {
          try {
            const j = await fetch(`${apiUrl}/v1/runs/${run.run_id}`).then(r => r.json());
            setResult(j);
            if (j.status === "completed" || j.status === "failed") {
              clearInterval(poll);
              setStatusMsg(`Run ${j.status}.`);
            }
          } catch {
            clearInterval(poll);
            setStatusMsg("Polling error.");
          }
        }, 1000);
      } catch (e) {
        setStatusMsg("Auto-run failed. Paste API URL or tap Auto-detect.");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiUrl]);

  async function autoDetectNow() {
    setStatusMsg("Auto-detecting...");
    // try build-time env
    if (process.env.NEXT_PUBLIC_API_URL) { setStatusMsg("Using build-time env."); setApiUrl(process.env.NEXT_PUBLIC_API_URL); return; }
    // try saved
    const saved = (typeof window !== "undefined") ? localStorage.getItem("apiUrl") : "";
    if (saved && saved.trim()) { setStatusMsg("Using saved value."); setApiUrl(saved.trim()); return; }
    // try render heuristic
    const guess = heuristicFromRenderHost();
    if (guess) { setStatusMsg("Using Render heuristic."); setApiUrl(guess); return; }
    // try same-origin whoami
    try {
      const r = await fetch("/whoami");
      if (r.ok) {
        const j = await r.json();
        if (j && j.url) { setStatusMsg("Using same-origin /whoami."); setApiUrl(j.url); return; }
      }
    } catch {}
    setStatusMsg("Could not detect automatically. Please paste API URL.");
  }

  async function pingApi() {
    if (!apiUrl) { setStatusMsg("No API URL yet."); return; }
    setStatusMsg("Pinging API...");
    try {
      const r = await fetch(`${apiUrl}/healthz`);
      setStatusMsg(r.ok ? "API OK." : "API not healthy.");
    } catch {
      setStatusMsg("Ping failed.");
    }
  }

  async function copyApi() {
    if (!apiUrl) { setStatusMsg("No API URL to copy."); return; }
    try {
      await navigator.clipboard.writeText(apiUrl);
      setStatusMsg("API URL copied.");
    } catch {
      setStatusMsg("Copy failed.");
    }
  }

  return (
    <div style={{ maxWidth: 860, margin: "40px auto", fontFamily: "system-ui", lineHeight: 1.4 }}>
      <h1>StegVerse SCW MVP</h1>

      <p>
        API URL:{" "}
        <input
          value={apiUrl}
          onChange={(e) => setApiUrl(e.target.value)}
          placeholder="https://scw-api-abc123.onrender.com"
          style={{ width: "100%" }}
        />
      </p>

      <p>
        <button onClick={autoDetectNow}>Auto-detect</button>
        <button onClick={pingApi} style={{ marginLeft: 8 }}>Ping API</button>
        <button onClick={copyApi} style={{ marginLeft: 8 }}>Copy API</button>
        <a href="/whoami" target="_blank" rel="noreferrer" style={{ marginLeft: 12 }}>Open /whoami (same origin)</a>
      </p>

      {statusMsg && (
        <div style={{ padding: 10, background: "#222", color: "#fff", marginBottom: 10 }}>
          {statusMsg}
        </div>
      )}

      <details style={{ margin: "12px 0" }}>
        <summary><strong>Discovery Guide</strong> — where I look for the API and why</summary>
        <div style={{ paddingTop: 8, color: "#333" }}>
          {discoveryNotes.map((n, i) => <div key={i}>{n}</div>)}
          <div style={{ marginTop: 8 }}>
            <em>Rationale:</em> we favor baked-in config (env var), then stable local memory (saved value),
            then a safe heuristic for Render subdomains, and finally a same-origin probe for proxies.
          </div>
        </div>
      </details>

      <hr style={{ margin: "20px 0" }} />

      <button onClick={async () => {
        setStatusMsg("Creating project...");
        try {
          const p = await fetch(`${apiUrl}/v1/projects`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: "Manual" })
          }).then(r => r.json());
          setProjectId(p.project_id || "");
          setStatusMsg(p.project_id ? "Project created." : "Failed to create project.");
        } catch { setStatusMsg("Request failed."); }
      }} disabled={!apiUrl}>Create Project</button>

      {projectId && <p>Project: {projectId}</p>}

      <h3>Code</h3>
      <textarea
        value={code}
        onChange={(e) => setCode(e.target.value)}
        rows={10}
        style={{ width: "100%" }}
      />

      <p>
        <button onClick={async () => {
          setStatusMsg("Queuing run...");
          try {
            const run = await fetch(`${apiUrl}/v1/runs`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ project_id: projectId, language: "python", code })
            }).then(r => r.json());
            setRunId(run.run_id || "");
            setStatusMsg(run.run_id ? "Polling..." : "Failed to start run.");
          } catch { setStatusMsg("Request failed."); }
        }} disabled={!projectId || !apiUrl}>Run</button>
      </p>

      {runId && <p>Run ID: {runId}</p>}

      {result && (
        <div style={{ background: "#111", color: "#0f0", padding: 10, whiteSpace: "pre-wrap" }}>
          <strong>Status:</strong> {result.status}
          <br />
          {Array.isArray(result.logs) && result.logs.map((line, i) => <div key={i}>{line}</div>)}
          {result.result && <div>Result: {result.result}</div>}
        </div>
      )}

      <p style={{ marginTop: 30, fontSize: 12, color: "#666" }}>
        MVP: This simulates execution. Add sandbox containers later.
      </p>
    </div>
  );
}
