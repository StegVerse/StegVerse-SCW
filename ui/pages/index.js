// ui/pages/index.js
import { useState, useEffect } from "react";

function heuristicFromRenderHost() {
  if (typeof window === "undefined") return "";
  const h = window.location.hostname;
  if (h === "scw-ui.onrender.com") return "https://scw-api.onrender.com";
  return "";
}

function pickInitialApiUrl() {
  if (process.env.NEXT_PUBLIC_API_URL && process.env.NEXT_PUBLIC_API_URL.trim()) {
    return process.env.NEXT_PUBLIC_API_URL.trim();
  }
  if (typeof window !== "undefined") {
    const saved = localStorage.getItem("apiUrl");
    if (saved && saved.trim()) return saved.trim();
  }
  const guess = heuristicFromRenderHost();
  if (guess) return guess;
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

  useEffect(() => {
    if (apiUrl) localStorage.setItem("apiUrl", apiUrl);
  }, [apiUrl]);

  useEffect(() => {
    (async () => {
      if (apiUrl) return;
      try {
        const r = await fetch("/whoami");
        if (r.ok) {
          const j = await r.json();
          if (j && j.url) setApiUrl(j.url);
        }
      } catch {}
    })();
  }, [apiUrl]);

  // --- Reset function to clear saved URL ---
  function resetApiUrl() {
    if (typeof window !== "undefined") {
      localStorage.removeItem("apiUrl");
      location.reload();
    }
  }

  useEffect(() => {
    (async () => {
      if (!apiUrl) { setStatusMsg("API URL not detected. Paste or use Auto-detect."); return; }
      try {
        setStatusMsg("Pinging API...");
        const h = await fetch(`${apiUrl}/healthz`);
        if (!h.ok) throw new Error(`healthz HTTP ${h.status}`);

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

  return (
    <div style={{ maxWidth: 860, margin: "40px auto", fontFamily: "system-ui", lineHeight: 1.4 }}>
      <h1>StegVerse SCW MVP</h1>

      <p>
        API URL:{" "}
        <input
          value={apiUrl}
          onChange={(e) => setApiUrl(e.target.value)}
          placeholder="https://scw-api.onrender.com"
          style={{ width: "70%" }}
        />
        <button onClick={resetApiUrl} style={{ marginLeft: 8 }}>Reset</button>
      </p>

      <p>
        <button onClick={() => { setApiUrl(pickInitialApiUrl()); setStatusMsg("Auto-detect attempted."); }}>Auto-detect</button>
        <button onClick={async () => {
          setStatusMsg("Pinging API...");
          try {
            const r = await fetch(`${apiUrl}/healthz`);
            setStatusMsg(r.ok ? "API OK." : `API not healthy (HTTP ${r.status}).`);
          } catch { setStatusMsg("Ping failed."); }
        }} style={{ marginLeft: 8 }}>Ping API</button>
        <button onClick={async () => {
          if (!apiUrl) { setStatusMsg("No API URL to copy."); return; }
          await navigator.clipboard.writeText(apiUrl);
          setStatusMsg("API URL copied.");
        }} style={{ marginLeft: 8 }}>Copy API</button>
      </p>

      {statusMsg && (
        <div style={{ padding: 10, background: "#222", color: "#fff", marginBottom: 10 }}>
          {statusMsg}
        </div>
      )}

      <details style={{ margin: "12px 0" }}>
        <summary><strong>Discovery Guide</strong></summary>
        <div style={{ paddingTop: 8, color: "#333" }}>
          {discoveryNotes.map((n, i) => <div key={i}>{n}</div>)}
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
}// ui/pages/index.js
import { useState, useEffect } from "react";

function heuristicFromRenderHost() {
  if (typeof window === "undefined") return "";
  const h = window.location.hostname;               // e.g. scw-ui.onrender.com (no hash)
  // If you ever rename with a hash, you could map scw-ui-<hash> -> scw-api-<hash> here.
  if (h === "scw-ui.onrender.com") return "https://scw-api.onrender.com";
  return "";
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
  // 4) Else empty; same-origin /whoami will try after mount
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

  // Persist URL locally
  useEffect(() => {
    if (apiUrl) localStorage.setItem("apiUrl", apiUrl);
  }, [apiUrl]);

  // Try same-origin /whoami if still empty
  useEffect(() => {
    (async () => {
      if (apiUrl) return;
      try {
        const r = await fetch("/whoami");
        if (r.ok) {
          const j = await r.json();
          if (j && j.url) setApiUrl(j.url);
        }
      } catch {}
    })();
  }, [apiUrl]);

  // Auto-smoke when apiUrl present
  useEffect(() => {
    (async () => {
      if (!apiUrl) { setStatusMsg("API URL not detected. Paste or use Auto-detect."); return; }
      try {
        setStatusMsg("Pinging API...");
        const h = await fetch(`${apiUrl}/healthz`);
        if (!h.ok) throw new Error(`healthz HTTP ${h.status}`);

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

  async function autoDetectNow() {
    setStatusMsg("Auto-detecting...");
    if (process.env.NEXT_PUBLIC_API_URL) { setApiUrl(process.env.NEXT_PUBLIC_API_URL.trim()); setStatusMsg("Using build-time env."); return; }
    const saved = (typeof window !== "undefined") ? localStorage.getItem("apiUrl") : "";
    if (saved && saved.trim()) { setApiUrl(saved.trim()); setStatusMsg("Using saved value."); return; }
    const guess = heuristicFromRenderHost();
    if (guess) { setApiUrl(guess); setStatusMsg("Using host heuristic."); return; }
    try {
      const r = await fetch("/whoami");
      if (r.ok) {
        const j = await r.json();
        if (j && j.url) { setApiUrl(j.url); setStatusMsg("Using same-origin /whoami."); return; }
      }
    } catch {}
    setStatusMsg("Could not detect automatically. Please paste API URL.");
  }

  async function pingApi() {
    if (!apiUrl) { setStatusMsg("No API URL yet."); return; }
    setStatusMsg("Pinging API...");
    try {
      const r = await fetch(`${apiUrl}/healthz`);
      setStatusMsg(r.ok ? "API OK." : `API not healthy (HTTP ${r.status}).`);
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
          placeholder="https://scw-api.onrender.com"
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
