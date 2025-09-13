// ui/pages/index.js
import { useState, useEffect } from "react";

function normalizeApiUrl(url) {
  if (!url) return "";
  return url.replace(/\/+$/, "");
}

function heuristicFromRenderHost() {
  if (typeof window === "undefined") return "";
  const h = window.location.hostname;
  if (h === "scw-ui.onrender.com") return "https://scw-api.onrender.com";
  return "";
}

function pickInitialApiUrlAndSource() {
  if (process.env.NEXT_PUBLIC_API_URL && process.env.NEXT_PUBLIC_API_URL.trim()) {
    return { url: normalizeApiUrl(process.env.NEXT_PUBLIC_API_URL.trim()), source: "env var" };
  }
  if (typeof window !== "undefined") {
    const saved = localStorage.getItem("apiUrl");
    if (saved && saved.trim()) return { url: normalizeApiUrl(saved.trim()), source: "localStorage" };
  }
  const guess = heuristicFromRenderHost();
  if (guess) return { url: normalizeApiUrl(guess), source: "heuristic" };
  return { url: "", source: "none" };
}

export default function Home() {
  const init = pickInitialApiUrlAndSource();
  const [apiUrl, setApiUrl] = useState(init.url);
  const [apiSource, setApiSource] = useState(init.source);
  const [projectId, setProjectId] = useState("");
  const [code, setCode] = useState("print('auto smoke run')");
  const [runId, setRunId] = useState("");
  const [result, setResult] = useState(null);
  const [statusMsg, setStatusMsg] = useState("");
  const [health, setHealth] = useState("unknown");

  useEffect(() => {
    if (apiUrl) {
      localStorage.setItem("apiUrl", normalizeApiUrl(apiUrl));
      setApiSource("manual input");
    }
  }, [apiUrl]);

  function resetApiUrl() {
    if (typeof window !== "undefined") {
      localStorage.removeItem("apiUrl");
      setApiSource("none");
      location.reload();
    }
  }

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

  // --- UI code for project/run creation omitted for brevity (unchanged from previous version) ---
  // (You can keep the rest of the project/run logic exactly as before)

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

      <p style={{ fontSize: 12, color: "#666" }}>
        <em>Using: {apiSource}</em>
      </p>

      {/* Rest of UI unchanged: buttons for Auto-detect, Ping, Copy, status banner, etc. */}
    </div>
  );
}
