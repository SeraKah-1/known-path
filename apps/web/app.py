"""Thin FastAPI demo — same library as CLI/MCP."""

from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

from known_path.runner import run_modes

app = FastAPI(title="known-path demo", version="0.1.0")

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>known-path</title>
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='12' fill='%230f766e'/%3E%3Cpath d='M14 40 L28 20 L36 32 L50 14' stroke='%23ecfdf5' stroke-width='6' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3Ccircle cx='50' cy='14' r='5' fill='%23fbbf24'/%3E%3C/svg%3E"/>
  <style>
    :root { font-family: ui-sans-serif, system-ui, sans-serif; color: #0f172a; background: #f8fafc; }
    body { max-width: 960px; margin: 2rem auto; padding: 0 1rem; }
    h1 { font-size: 1.75rem; margin-bottom: 0.25rem; }
    .sub { color: #475569; margin-bottom: 1.5rem; }
    .row { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1rem; }
    button { background: #0f766e; color: white; border: 0; padding: 0.6rem 1rem; border-radius: 0.5rem; cursor: pointer; font-weight: 600; }
    button.secondary { background: #334155; }
    button.danger { background: #b91c1c; }
    input { flex: 1; min-width: 240px; padding: 0.6rem 0.75rem; border: 1px solid #cbd5e1; border-radius: 0.5rem; }
    .card { background: white; border: 1px solid #e2e8f0; border-radius: 0.75rem; padding: 1rem; margin-bottom: 1rem; }
    table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
    th, td { text-align: left; padding: 0.4rem 0.5rem; border-bottom: 1px solid #e2e8f0; }
    .green { color: #047857; font-weight: 700; }
    .red { color: #b91c1c; font-weight: 700; }
    pre { background: #0f172a; color: #e2e8f0; padding: 1rem; border-radius: 0.5rem; overflow: auto; font-size: 0.85rem; }
    a { color: #0f766e; }
  </style>
</head>
<body>
  <h1>known-path</h1>
  <p class="sub">Light only the trusted catalog assets for a data job. Built for the
    <a href="https://datahub.devpost.com">DataHub Agent Hackathon</a>.</p>
  <div class="row">
    <input id="intent" value="revenue by region last quarter Finance canonical"/>
  </div>
  <div class="row">
    <button onclick="run('baseline')">1 · Baseline thrash</button>
    <button onclick="run('known-path')">2 · Known path</button>
    <button class="danger" onclick="run('blocked')">3 · Fail closed</button>
    <button class="secondary" onclick="runDemo()">Run full demo</button>
  </div>
  <div id="out"></div>
  <script>
    async function run(mode) {
      const intent = document.getElementById('intent').value;
      const r = await fetch('/api/run?mode=' + encodeURIComponent(mode) + '&intent=' + encodeURIComponent(intent));
      const data = await r.json();
      render(data);
    }
    async function runDemo() {
      const r = await fetch('/api/demo');
      const data = await r.json();
      document.getElementById('out').innerHTML = data.map(renderCard).join('');
    }
    function render(data) {
      document.getElementById('out').innerHTML = renderCard(data);
    }
    function renderCard(p) {
      const st = p.status === 'SUCCESS' ? 'green' : (p.status === 'BLOCKED_TRUST' ? 'red' : '');
      const rows = (p.nodes || []).map(n => `<tr>
        <td>${n.activated ? '●' : '·'}</td>
        <td>${n.name}</td>
        <td>${n.relevance}</td>
        <td>${n.trust}</td>
        <td>${(n.reasons||[]).slice(0,4).join(', ')}</td>
      </tr>`).join('');
      const sql = p.sql_artifact ? `<pre>${escapeHtml(p.sql_artifact)}</pre>` : '';
      return `<div class="card">
        <div><span class="${st}">${p.status}</span> · mode <b>${p.mode}</b> · fetches ${p.entity_fetches} · activated ${(p.nodes||[]).filter(n=>n.activated).length}</div>
        <p>${escapeHtml(p.message || '')}</p>
        <table><thead><tr><th>On</th><th>Name</th><th>Rel</th><th>Trust</th><th>Reasons</th></tr></thead>
        <tbody>${rows}</tbody></table>
        ${sql}
      </div>`;
    }
    function escapeHtml(s) {
      return String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
    }
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return HTML


@app.get("/api/run")
def api_run(
    mode: str = Query("known-path"),
    intent: str = Query("revenue by region last quarter Finance canonical"),
) -> dict:
    plan = run_modes(intent, mode, no_commit=False)
    return plan.model_dump()  # type: ignore[return-value]


@app.get("/api/demo")
def api_demo() -> list:
    intent = "revenue by region last quarter Finance canonical"
    return [
        run_modes(intent, "baseline", no_commit=False).model_dump(),
        run_modes(intent, "known-path", no_commit=False).model_dump(),
        run_modes(intent, "blocked", no_commit=False).model_dump(),
    ]


def main() -> None:
    import uvicorn

    uvicorn.run("apps.web.app:app", host="0.0.0.0", port=8088, reload=False)


if __name__ == "__main__":
    main()
