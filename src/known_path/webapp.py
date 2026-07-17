"""Zero-dependency web demo (stdlib http.server only)."""

from __future__ import annotations

import json
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from known_path.fixtures import dataset_dir, demo_catalog, list_sample_files
from known_path.runner import run_modes

DEFAULT_INTENT = "revenue by region last quarter Finance canonical"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8088


def _html_page() -> str:
    assets = demo_catalog()
    samples = list_sample_files()
    asset_rows = "".join(
        f"<tr>"
        f"<td><code>{a.name}</code></td>"
        f"<td>{'yes' if a.certified else 'no'}</td>"
        f"<td>{'yes' if a.deprecated else 'no'}</td>"
        f"<td>{'yes' if a.has_owner else 'no'}</td>"
        f"<td>{'fail' if a.quality_fail else 'ok'}</td>"
        f"<td>{', '.join(a.glossary_terms) or '—'}</td>"
        f"</tr>"
        for a in assets
    )
    sample_blocks = "".join(
        f"<details><summary><code>{s['name']}</code></summary>"
        f"<pre>{_esc(s['preview'])}</pre></details>"
        for s in samples
    )
    ds = dataset_dir()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>known-path demo</title>
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='12' fill='%230f766e'/%3E%3Cpath d='M14 40 L28 20 L36 32 L50 14' stroke='%23ecfdf5' stroke-width='6' fill='none' stroke-linecap='round'/%3E%3Ccircle cx='50' cy='14' r='5' fill='%23fbbf24'/%3E%3C/svg%3E"/>
  <style>
    :root {{ font-family: ui-sans-serif, system-ui, sans-serif; color: #0f172a; background: #f1f5f9; }}
    body {{ max-width: 1040px; margin: 0 auto; padding: 1.5rem 1rem 3rem; }}
    h1 {{ font-size: 1.75rem; margin: 0 0 0.25rem; }}
    .sub {{ color: #475569; margin-bottom: 1.25rem; }}
    a {{ color: #0f766e; }}
    .row {{ display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 0.75rem 0 1rem; }}
    input[type=text] {{ flex: 1; min-width: 240px; padding: 0.65rem 0.8rem; border: 1px solid #cbd5e1; border-radius: 0.5rem; font-size: 1rem; }}
    button {{ background: #0f766e; color: #fff; border: 0; padding: 0.65rem 1rem; border-radius: 0.5rem; cursor: pointer; font-weight: 600; }}
    button.secondary {{ background: #334155; }}
    button.danger {{ background: #b91c1c; }}
    button:disabled {{ opacity: 0.6; cursor: wait; }}
    .card {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 0.75rem; padding: 1rem 1.1rem; margin-bottom: 1rem; box-shadow: 0 1px 2px rgba(15,23,42,.04); }}
    .card h2 {{ font-size: 1rem; margin: 0 0 0.75rem; color: #0f172a; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
    th, td {{ text-align: left; padding: 0.4rem 0.45rem; border-bottom: 1px solid #e2e8f0; vertical-align: top; }}
    th {{ color: #64748b; font-weight: 600; }}
    code {{ font-size: 0.85em; background: #f1f5f9; padding: 0.1rem 0.3rem; border-radius: 0.25rem; }}
    pre {{ background: #0f172a; color: #e2e8f0; padding: 0.9rem; border-radius: 0.5rem; overflow: auto; font-size: 0.8rem; margin: 0.5rem 0 0; }}
    .green {{ color: #047857; font-weight: 700; }}
    .red {{ color: #b91c1c; font-weight: 700; }}
    .yellow {{ color: #b45309; font-weight: 700; }}
    .badge {{ display: inline-block; background: #ccfbf1; color: #115e59; font-size: 0.75rem; font-weight: 700; padding: 0.2rem 0.55rem; border-radius: 999px; margin-bottom: 0.5rem; }}
    details {{ margin: 0.4rem 0; }}
    summary {{ cursor: pointer; color: #0f766e; font-weight: 600; }}
    .meta {{ color: #64748b; font-size: 0.9rem; }}
    #status {{ min-height: 1.25rem; color: #64748b; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <div class="badge">dataset: demo-finance · offline catalog ready</div>
  <h1>known-path</h1>
  <p class="sub">
    Light only trusted catalog assets for a data job.
    <a href="https://github.com/SeraKah-1/known-path" target="_blank" rel="noreferrer">GitHub</a>
    · <a href="https://datahub.devpost.com" target="_blank" rel="noreferrer">DataHub Hackathon</a>
  </p>

  <div class="card">
    <h2>Run demo</h2>
    <div class="row">
      <input id="intent" type="text" value="{_esc(DEFAULT_INTENT)}"/>
    </div>
    <div class="row">
      <button onclick="runOne('baseline')">1 · Baseline thrash</button>
      <button onclick="runOne('known-path')">2 · Known path</button>
      <button class="danger" onclick="runOne('blocked')">3 · Fail closed</button>
      <button class="secondary" onclick="runAll()">Run full demo</button>
    </div>
    <div id="status"></div>
  </div>

  <div id="out"></div>

  <div class="card">
    <h2>Demo catalog ({len(assets)} assets)</h2>
    <p class="meta">Loaded from <code>{_esc(str(ds))}</code> — trap table is <code>finance.revenue_old</code>.</p>
    <table>
      <thead><tr><th>Name</th><th>Certified</th><th>Deprecated</th><th>Owner</th><th>Quality</th><th>Glossary</th></tr></thead>
      <tbody>{asset_rows}</tbody>
    </table>
  </div>

  <div class="card">
    <h2>Sample rows (CSV)</h2>
    <p class="meta">Tiny synthetic rows for the web demo — not a full warehouse.</p>
    {sample_blocks or "<p class='meta'>No CSV samples found.</p>"}
  </div>

  <script>
    const $ = (id) => document.getElementById(id);
    function esc(s) {{
      return String(s ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
    }}
    function stClass(st) {{
      if (st === 'SUCCESS') return 'green';
      if (st === 'BLOCKED_TRUST') return 'red';
      return 'yellow';
    }}
    function renderPlan(p) {{
      const rows = (p.nodes || []).map(n => `<tr>
        <td>${{n.activated ? '●' : '·'}}</td>
        <td><code>${{esc(n.name)}}</code></td>
        <td>${{n.relevance}}</td>
        <td>${{esc(n.trust)}}</td>
        <td>${{esc((n.reasons||[]).slice(0,4).join(', '))}}</td>
      </tr>`).join('');
      const sql = p.sql_artifact ? `<pre>${{esc(p.sql_artifact)}}</pre>` : '';
      const act = (p.nodes||[]).filter(n => n.activated).length;
      return `<div class="card">
        <h2><span class="${{stClass(p.status)}}">${{esc(p.status)}}</span>
          · mode <b>${{esc(p.mode)}}</b>
          · fetches ${{p.entity_fetches}} · activated ${{act}}</h2>
        <p>${{esc(p.message || '')}}</p>
        <table>
          <thead><tr><th>On</th><th>Name</th><th>Rel</th><th>Trust</th><th>Reasons</th></tr></thead>
          <tbody>${{rows}}</tbody>
        </table>
        ${{sql}}
      </div>`;
    }}
    async function runOne(mode) {{
      const intent = $('intent').value;
      $('status').textContent = 'Running ' + mode + '…';
      const r = await fetch('/api/run?mode=' + encodeURIComponent(mode) + '&intent=' + encodeURIComponent(intent));
      const data = await r.json();
      if (data.error) {{
        $('status').textContent = data.error;
        return;
      }}
      $('out').innerHTML = renderPlan(data);
      $('status').textContent = 'Done: ' + data.status;
    }}
    async function runAll() {{
      $('status').textContent = 'Running full demo…';
      const r = await fetch('/api/demo?intent=' + encodeURIComponent($('intent').value));
      const data = await r.json();
      if (data.error) {{
        $('status').textContent = data.error;
        return;
      }}
      $('out').innerHTML = data.map(renderPlan).join('');
      $('status').textContent = 'Full demo complete';
    }}
  </script>
</body>
</html>
"""


def _esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # quieter
        print("[web]", fmt % args)

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: object) -> None:
        raw = json.dumps(obj, indent=None).encode("utf-8")
        self._send(code, raw, "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path or "/"
        qs = parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            body = _html_page().encode("utf-8")
            self._send(200, body, "text/html; charset=utf-8")
            return

        if path == "/api/health":
            self._json(200, {"ok": True, "dataset": str(dataset_dir()), "assets": len(demo_catalog())})
            return

        if path == "/api/catalog":
            assets = [
                {
                    "urn": a.urn,
                    "name": a.name,
                    "certified": a.certified,
                    "deprecated": a.deprecated,
                    "has_owner": a.has_owner,
                    "quality_fail": a.quality_fail,
                    "glossary_terms": a.glossary_terms,
                    "columns": a.columns,
                }
                for a in demo_catalog()
            ]
            self._json(200, {"assets": assets, "samples": list_sample_files()})
            return

        if path == "/api/run":
            mode = (qs.get("mode") or ["known-path"])[0]
            intent = (qs.get("intent") or [DEFAULT_INTENT])[0]
            try:
                plan = run_modes(intent, mode, no_commit=False)
                self._json(200, plan.model_dump())
            except Exception as e:  # pragma: no cover
                self._json(500, {"error": str(e)})
            return

        if path == "/api/demo":
            intent = (qs.get("intent") or [DEFAULT_INTENT])[0]
            try:
                plans = [
                    run_modes(intent, "baseline", no_commit=False).model_dump(),
                    run_modes(intent, "known-path", no_commit=False).model_dump(),
                    run_modes(intent, "blocked", no_commit=False).model_dump(),
                ]
                self._json(200, plans)
            except Exception as e:  # pragma: no cover
                self._json(500, {"error": str(e)})
            return

        self._send(404, b"not found", "text/plain; charset=utf-8")


def serve(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, open_browser: bool = False) -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print(f"known-path web demo → {url}")
    print(f"dataset → {dataset_dir()}")
    print("Press Ctrl+C to stop.")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        httpd.server_close()


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="known-path web demo")
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--open", action="store_true", help="Open browser")
    args = p.parse_args()
    serve(host=args.host, port=args.port, open_browser=args.open)


if __name__ == "__main__":
    main()
