import { useState } from "react";

export default function Home() {
  const [apiUrl, setApiUrl] = useState(process.env.NEXT_PUBLIC_API_URL || "");
  const [projectId, setProjectId] = useState("");
  const [code, setCode] = useState("print('hello from SCW MVP')");
  const [runId, setRunId] = useState("");
  const [result, setResult] = useState(null);

  async function createProject() {
    if (!apiUrl) return;
    const res = await fetch(`${apiUrl}/v1/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "My First Project" })
    });
    const data = await res.json();
    setProjectId(data.project_id || "");
  }

  async function run() {
    if (!apiUrl || !projectId) return;
    const res = await fetch(`${apiUrl}/v1/runs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: projectId, language: "python", code })
    });
    const data = await res.json();
    setRunId(data.run_id || "");
    setResult(null);

    const interval = setInterval(async () => {
      const r = await fetch(`${apiUrl}/v1/runs/${data.run_id}`);
      const j = await r.json();
      setResult(j);
      if (j.status === "completed" || j.status === "failed") {
        clearInterval(interval);
      }
    }, 1000);
  }

  return (
    <div style={{ maxWidth: 800, margin: "40px auto", fontFamily: "system-ui" }}>
      <h1>StegVerse SCW MVP</h1>

      <p>
        API URL:{" "}
        <input
          value={apiUrl}
          onChange={(e) => setApiUrl(e.target.value)}
          placeholder="https://scw-api-xxxx.onrender.com"
          style={{ width: "100%" }}
        />
      </p>

      <button onClick={createProject} disabled={!apiUrl}>Create Project</button>
      {projectId && <p>Project: {projectId}</p>}

      <h3>Code</h3>
      <textarea
        value={code}
        onChange={(e) => setCode(e.target.value)}
        rows={10}
        style={{ width: "100%" }}
      />

      <p>
        <button onClick={run} disabled={!projectId || !apiUrl}>Run</button>
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
