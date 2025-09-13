// ui/pages/index.js
import { useState, useEffect } from "react";

// --- helpers ----------------------------------------------------
function normalizeApiUrl(url) {
  if (!url) return "";
  return url.replace(/\/+$/, ""); // strip trailing slashes
}

function heuristicFromRenderHost() {
  if (typeof window === "undefined") return "";
  const h = window.location.hostname;
  // Your services use clean names (no hash)
  if (h === "scw-ui.onrender.com") return "https://scw-api.onrender.com";
  return "";
}

function pickInitialApiUrl() {
  // 1) Build-time env var
  if (process.env.NEXT_PUBLIC_API_URL && process.env.NEXT_PUBLIC_API_URL.trim()) {
    return normalizeApiUrl(process.env.NEXT_PUBLIC_API_URL.trim());
  }
  // 2) Saved value
  if (typeof window !== "undefined") {
    const saved = localStorage.getItem("apiUrl");
    if (saved && saved.trim()) return normalizeApiUrl(saved.trim());
  }
  // 3) Host heuristic (Render)
  const guess = heuristicFromRenderHost();
  if (guess) return normalizeApiUrl(guess);
  // 4) Empty; same-origin /whoami probe will try after mount
  return "";
}

// --- component --------------------------------------------------
export default function Home() {
  const [apiUrl, setApiUrl] = useState(pickInitialApiUrl());
  const [projectId, setProjectId] = useState("");
  const [code, setCode] = useState("print('auto smoke run')");
  const [runId, setRunId] = useState("");
  const [result, setResult] = useState(null);
  const [statusMsg, setStatusMsg] = useState("");
  const [discoveryNotes, setDiscoveryNotes] = useState([]);
  const [health, setHealth] = useState("unknown"); // "ok" | "bad" | "unknown"

  // Discovery guide (what we tried, in order)
  useEffect(() => {
    const notes = [];
    notes.push("1) Build-time env NEXT_PUBLIC_API_URL");
    notes.push(process.env.NEXT_PUBLIC_API_URL ? "→ Found; using it." : "→ Not set.");
    notes.push("2) Saved local value (localStorage)");
    notes.push((typeof window !== "undefined" && localStorage.getItem("apiUrl")) ? "→ Found; will use it." : "→ None saved.");
    notes.push("3) Host heuristic for Render naming");
    notes.push(heuristicFromRenderHost() ? "→ Produced a candidate." : "→ No candidate.");
    notes.push("4) Same-origin /whoami probe (works if a proxy routes API+UI together)");
    setDiscoveryNotes(notes);
  }, []);

  // Persist normalized URL locally
  useEffect(() => {
    if (apiUrl) localStorage.setItem("apiUrl", normalizeApiUrl(apiUrl));
  }, [apiUrl]);

  // Try same-origin /whoami if still empty
  useEffect(() => {
    (async () => {
      if (apiUrl) return;
      try {
        const r = await fetch("/whoami");
        if (r.ok) {
          const j = await r.json();
          if (j && j.url) setApiUrl(normalizeApiUrl(j.url));
        }
      } catch {}
    })();
  }, [apiUrl]);

  // Health indicator (debounced)
  useEffect(() => {
    let canceled = false;
    (async () => {
      if (!apiUrl) { setHealth("unknown"); return; }
      try {
        const r = await fetch(`${apiUrl}/healthz`);
        if (!canceled) setHealth(r.ok ? "ok" : "bad");
      } catch {
        if (!canceled) setHealth("bad");
      }
    })();
    return () => { canceled = true; };
  }, [apiUrl]);

  // Reset (Safari-safe): clear saved URL and reload page
  function resetApiUrl() {
    if (typeof window !== "undefined") {
      localStorage.removeItem("apiUrl");
      location.reload(); // fresh auto-detect on reload
    }
  }

  // Auto smoke test when apiUrl present
  useEffect(() => {
    (async () => {
      if (!apiUrl) { setStatusMsg("API URL not detected. Paste or use Auto-detect."); return; }
      try {
        setStatusMsg("Pinging API...");
        const h = await fetch(`${apiUrl}/healthz`);
        if (!h.ok) throw new Error(`healthz HTTP ${h.status}`);
        setHealth("ok");

        setStatusMsg("API OK. Creating project...");
        const res = await fetch(`${apiUrl}/v1/projects`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: "Auto Smoke" }),
        });
        const txt = await res.text();
        let data = {};
        try { data = JSON.parse(txt); } catch {}
        if (!res.ok || !data.project_id) {
          setStatusMsg(`Create failed (HTTP ${res.status}): ${txt.slice(0,200)}`);
          return;
        }
        setProjectId(data.project_id);

        setStatusMsg("Queuing run...");
        const res2 = await fetch(`${apiUrl}/v1/runs`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ project_id: data.project_id, language: "python", code }),
        });
        const txt2 = await res2.text();
        let d2 = {};
        try { d2 = JSON.parse(txt2); } catch {}
        if (!res2.ok || !d2.run_id) {
          setStatusMsg(`Run failed (HTTP ${res2.status}): ${txt2.slice(0,200)}`);
          return;
        }
        setRunId(d2.run_id);
        setStatusMsg("Polling...");

        const poll = setInterval(async () => {
          try {
            const jr = await fetch(`${apiUrl}/v1/runs/${d2.run_id}`);
            const j = await jr.json();
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
        setStatusMsg(`Auto-run failed: ${String(e)}`);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiUrl]);

  // --- UI actions ------------------------------------------------
  async function autoDetectNow() {
    setStatusMsg("Auto-detecting...");
    if (process.env.NEXT_PUBLIC_API_URL) {
      const v = normalizeApiUrl(process.env.NEXT_PUBLIC_API_URL.trim());
      setApiUrl(v); setStatusMsg("Using build-time env.");
      return;
    }
    const saved = (typeof window !== "undefined") ? localStorage.getItem("apiUrl") : "";
    if (saved && saved.trim()) {
      setApiUrl(normalizeApiUrl(saved.trim())); setStatusMsg("Using saved value.");
      return;
    }
    const guess = heuristicFromRenderHost();
    if (guess) { setApiUrl(normalizeApiUrl(guess)); setStatusMsg("Using host heuristic."); return; }
    try {
      const r = await fetch("/whoami");
      if (r.ok) {
        const j = await r.json();
        if (j && j.url) { setApiUrl(normalizeApiUrl(j.url)); setStatusMsg("Using same-origin /whoami."); return; }
      }
    } catch {}
    setStatusMsg("Could not detect automatically. Please paste API URL.");
  }

  async function pingApi() {
    if (!apiUrl) { setStatusMsg("No API URL yet."); setHealth("bad"); return; }
    setStatusMsg("Pinging API...");
    try {
      const r = await fetch(`${apiUrl}/healthz`);
      if (r.ok) { setStatusMsg("API OK."); setHealth("ok"); }
      else { setStatusMsg(`API not healthy (HTTP ${r.status}).`); setHealth("bad"); }
    } catch {
      setStatusMsg("Ping failed."); setHealth("bad");
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

  // --- render ----------------------------------------------------
  const dotStyle = {
    display: "inline-block",
    width: 10,
    height: 10,
    borderRadius: "50%",
    marginLeft: 8,
    background: health === "ok" ? "#19c37d" : health === "bad" ? "#ff4d4f" : "#999"
  };

  return (
    <div style={{ maxWidth: 860, margin: "40px auto", fontFamily: "system-ui", lineHeight: 1.4 }}>
      <h1>StegVerse SCW MVP</h1>

      <p>
        API URL:{" "}
        <input
          value={apiUrl}
          onChange={(e) => setApiUrl(normalizeApiUrl(e.target.value))}
          placeholder="https://scw-api.onrender.com"
          style={{ width: "60%" }}
        />
        <span style={dotStyle} title={health === "ok" ? "Healthy" : health === "bad" ? "Unhealthy" : "Unknown"} />
        <button onClick={resetApiUrl} style={{ marginLeft: 8 }}>Reset</button>
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
            <em>Rationale:</em> explicit config (env) → saved memory → host heuristic → same-origin probe.
          </div>
        </div>
      </details>

      <hr style={{ margin: "20px 0" }} />

      <button onClick={async () => {
        if (!apiUrl) return;
        setStatusMsg("Creating project...");
        try {
          const res = await fetch(`${apiUrl}/v1/projects`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: "Manual" })
          });
          const txt = await res.text();
          let data = {};
          try { data = JSON.parse(txt); } catch {}
          if (!res.ok || !data.project_id) {
            setStatusMsg(`Create failed (HTTP ${res.status}): ${txt.slice(0,200)}`);
            return;
          }
          setProjectId(data.project_id);
          setStatusMsg("Project created.");
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
          if (!apiUrl || !projectId) return;
          setStatusMsg("Queuing run...");
          try {
            const res = await fetch(`${apiUrl}/v1/runs`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ project_id: projectId, language: "python", code })
            });
            const txt = await res.text();
            let data = {};
            try { data = JSON.parse(txt); } catch {}
            if (!res.ok || !data.run_id) {
              setStatusMsg(`Run failed (HTTP ${res.status}): ${txt.slice(0,200)}`);
              return;
            }
            setRunId(data.run_id);
            setStatusMsg("Polling...");
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
