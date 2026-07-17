"""Enterprise web workbench for known-path (stdlib only).

UI direction: Anthropic / big-tech calm dark product + DesignMotionHQ tokens.
Every run goes through the real CLI via cli_bridge (web → agent shell → CLI).
"""

from __future__ import annotations

import json
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from known_path.cli_bridge import agent_command, result_to_dict, run_demo_via_cli, run_mode_via_cli
from known_path.fixtures import dataset_dir, demo_catalog, list_sample_files

DEFAULT_INTENT = "revenue by region last quarter Finance canonical"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8088


def _esc(s: object) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _html_page() -> str:
    assets = demo_catalog()
    samples = list_sample_files()
    max_usage = max((a.usage_score for a in assets), default=1) or 1
    catalog_rows = []
    for a in assets:
        role = "trap" if a.deprecated or a.quality_fail else ("canonical" if a.certified else "context")
        bar = int(100 * a.usage_score / max_usage)
        catalog_rows.append(
            f"""<tr data-role="{role}">
            <td><span class="dot {role}"></span><code>{_esc(a.name)}</code></td>
            <td><span class="pill {role}">{role}</span></td>
            <td>{"yes" if a.certified else "—"}</td>
            <td>{"yes" if a.deprecated else "—"}</td>
            <td>{"fail" if a.quality_fail else "ok"}</td>
            <td><div class="usage"><i style="width:{bar}%"></i><span>{a.usage_score}</span></div></td>
            </tr>"""
        )
    sample_html = "".join(
        f"<details class='sample'><summary>{_esc(s['name'])}</summary><pre>{_esc(s['preview'])}</pre></details>"
        for s in samples
    )
    chart_bars = "".join(
        f"""<div class="hbar-row">
          <span class="hbar-label">{_esc(a.name.split('.')[-1])}</span>
          <div class="hbar-track"><div class="hbar-fill {'warn' if a.deprecated or a.quality_fail else 'ok'}" style="width:{int(100*a.usage_score/max_usage)}%"></div></div>
          <span class="hbar-val">{a.usage_score}</span>
        </div>"""
        for a in sorted(assets, key=lambda x: -x.usage_score)
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>known-path — workbench</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%231a1a1a'/%3E%3Cpath d='M18 40 L30 22 L38 34 L48 18' stroke='%23f5f0e8' stroke-width='5' fill='none' stroke-linecap='round'/%3E%3Ccircle cx='48' cy='18' r='4' fill='%23d4a574'/%3E%3C/svg%3E"/>
<style>
/* —— Design tokens (DesignMotionHQ: design system kit / tokens) —— */
:root {{
  --bg: #0c0c0c;
  --bg-elev: #141414;
  --bg-soft: #1a1a1a;
  --border: #2a2a2a;
  --border-soft: #222;
  --text: #f5f0e8;
  --text-muted: #9a958c;
  --text-dim: #6b6760;
  --accent: #d4a574;
  --accent-2: #c4785a;
  --good: #6b9f7a;
  --bad: #c45c5c;
  --warn: #c9a227;
  --trap: #c45c5c;
  --canonical: #6b9f7a;
  --context: #7a8a9a;
  --radius: 12px;
  --radius-sm: 8px;
  --font: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
  --mono: "IBM Plex Mono", "SF Mono", ui-monospace, monospace;
  --shadow: 0 0 0 1px var(--border), 0 12px 40px rgba(0,0,0,.35);
  --ease: cubic-bezier(.22,1,.36,1);
}}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; background: var(--bg); color: var(--text); font-family: var(--font); }}
a {{ color: var(--accent); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
button, input, textarea {{ font: inherit; }}
button:focus-visible, input:focus-visible, textarea:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}

/* shell */
.app {{ min-height: 100vh; display: grid; grid-template-rows: auto 1fr; }}
.top {{
  display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  padding: .85rem 1.5rem; border-bottom: 1px solid var(--border);
  background: rgba(12,12,12,.9); backdrop-filter: blur(10px); position: sticky; top: 0; z-index: 20;
}}
.brand {{ display: flex; align-items: center; gap: .7rem; font-weight: 600; letter-spacing: -.02em; }}
.brand svg {{ display: block; }}
.brand span {{ color: var(--text-muted); font-weight: 400; font-size: .9rem; margin-left: .35rem; }}
.nav {{ display: flex; gap: 1.1rem; font-size: .9rem; color: var(--text-muted); }}
.nav a {{ color: var(--text-muted); }}
.nav a:hover {{ color: var(--text); text-decoration: none; }}
.pill-live {{ font-size: .72rem; font-weight: 600; letter-spacing: .04em; text-transform: uppercase;
  color: var(--good); border: 1px solid rgba(107,159,122,.35); background: rgba(107,159,122,.08);
  padding: .25rem .55rem; border-radius: 999px; }}

.main {{
  display: grid; grid-template-columns: 1.15fr .85fr; gap: 0;
  max-width: 1400px; width: 100%; margin: 0 auto;
}}
@media (max-width: 980px) {{ .main {{ grid-template-columns: 1fr; }} }}

.panel {{ padding: 1.5rem 1.5rem 2.5rem; }}
.panel + .panel {{ border-left: 1px solid var(--border); }}
@media (max-width: 980px) {{ .panel + .panel {{ border-left: 0; border-top: 1px solid var(--border); }} }}

.eyebrow {{ font-size: .75rem; letter-spacing: .12em; text-transform: uppercase; color: var(--accent); margin: 0 0 .5rem; }}
h1 {{ font-size: clamp(1.6rem, 2.4vw, 2.1rem); font-weight: 500; letter-spacing: -.03em; margin: 0 0 .6rem; line-height: 1.15; }}
.lede {{ color: var(--text-muted); font-size: 1rem; line-height: 1.55; margin: 0 0 1.4rem; max-width: 40rem; }}

.card {{
  background: var(--bg-elev); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 1rem 1.1rem; margin-bottom: 1rem; box-shadow: var(--shadow);
  transition: border-color .2s var(--ease), transform .2s var(--ease);
}}
.card:hover {{ border-color: #3a3a3a; }}
.card h2 {{ margin: 0 0 .75rem; font-size: .95rem; font-weight: 600; letter-spacing: -.01em; }}
.card h2 .hint {{ color: var(--text-dim); font-weight: 400; margin-left: .4rem; }}

.intent-box {{
  width: 100%; background: var(--bg-soft); color: var(--text); border: 1px solid var(--border);
  border-radius: var(--radius-sm); padding: .85rem 1rem; resize: vertical; min-height: 72px;
}}
.actions {{ display: flex; flex-wrap: wrap; gap: .5rem; margin-top: .75rem; }}
.btn {{
  appearance: none; border: 1px solid var(--border); background: var(--bg-soft); color: var(--text);
  border-radius: 999px; padding: .55rem 1rem; cursor: pointer; font-size: .9rem; font-weight: 500;
  transition: background .15s var(--ease), border-color .15s var(--ease), transform .15s var(--ease);
}}
.btn:hover {{ border-color: #444; background: #222; }}
.btn:active {{ transform: scale(.98); }}
.btn.primary {{ background: var(--text); color: #111; border-color: var(--text); }}
.btn.primary:hover {{ background: #fff; }}
.btn.danger {{ border-color: rgba(196,92,92,.45); color: #f0b4b4; }}
.btn.ghost {{ background: transparent; }}
.btn:disabled {{ opacity: .55; cursor: wait; }}

.metrics {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: .6rem; margin-bottom: 1rem; }}
@media (max-width: 640px) {{ .metrics {{ grid-template-columns: 1fr; }} }}
.metric {{
  background: var(--bg-soft); border: 1px solid var(--border-soft); border-radius: var(--radius-sm);
  padding: .75rem .85rem;
}}
.metric .k {{ font-size: .72rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: .08em; }}
.metric .v {{ font-size: 1.35rem; font-weight: 600; margin-top: .2rem; letter-spacing: -.02em; }}
.metric .v.good {{ color: var(--good); }}
.metric .v.bad {{ color: var(--bad); }}
.metric .v.warn {{ color: var(--warn); }}

/* graph */
.graph-wrap {{ display: grid; grid-template-columns: 1fr 1fr; gap: .75rem; }}
@media (max-width: 720px) {{ .graph-wrap {{ grid-template-columns: 1fr; }} }}
.svg-card {{ background: var(--bg-soft); border-radius: var(--radius-sm); border: 1px solid var(--border-soft); padding: .5rem; min-height: 220px; }}
#nodeGraph {{ width: 100%; height: 220px; display: block; }}
.hbar-row {{ display: grid; grid-template-columns: 90px 1fr 40px; gap: .5rem; align-items: center; margin: .35rem 0; font-size: .8rem; }}
.hbar-label {{ color: var(--text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.hbar-track {{ height: 8px; background: #222; border-radius: 99px; overflow: hidden; }}
.hbar-fill {{ height: 100%; border-radius: 99px; background: var(--good); transition: width .5s var(--ease); }}
.hbar-fill.warn {{ background: var(--bad); }}
.hbar-val {{ color: var(--text-dim); text-align: right; font-variant-numeric: tabular-nums; }}

/* compare bars */
.compare {{ display: flex; flex-direction: column; gap: .55rem; }}
.compare-row {{ display: grid; grid-template-columns: 100px 1fr 48px; gap: .5rem; align-items: center; font-size: .85rem; }}
.compare-track {{ height: 14px; background: #1e1e1e; border-radius: 6px; overflow: hidden; border: 1px solid var(--border-soft); }}
.compare-fill {{ height: 100%; border-radius: 6px; transition: width .55s var(--ease); }}
.compare-fill.base {{ background: linear-gradient(90deg, #8a4a4a, var(--bad)); }}
.compare-fill.kp {{ background: linear-gradient(90deg, #3d6b4a, var(--good)); }}
.compare-fill.blk {{ background: linear-gradient(90deg, #6b5a20, var(--warn)); }}

table.data {{ width: 100%; border-collapse: collapse; font-size: .82rem; }}
table.data th {{ text-align: left; color: var(--text-dim); font-weight: 500; padding: .45rem .35rem; border-bottom: 1px solid var(--border); }}
table.data td {{ padding: .5rem .35rem; border-bottom: 1px solid var(--border-soft); vertical-align: middle; }}
.dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: .4rem; background: var(--context); }}
.dot.canonical {{ background: var(--good); }}
.dot.trap {{ background: var(--bad); }}
.pill {{ font-size: .68rem; text-transform: uppercase; letter-spacing: .06em; padding: .15rem .4rem; border-radius: 999px; border: 1px solid var(--border); color: var(--text-muted); }}
.pill.canonical {{ color: var(--good); border-color: rgba(107,159,122,.35); }}
.pill.trap {{ color: var(--bad); border-color: rgba(196,92,92,.4); }}
.usage {{ display: flex; align-items: center; gap: .4rem; }}
.usage i {{ display: block; height: 6px; background: var(--accent); border-radius: 99px; min-width: 2px; flex: 0 0 auto; max-width: 80px; }}
.usage span {{ color: var(--text-dim); font-variant-numeric: tabular-nums; }}

/* terminal */
.term {{
  background: #080808; border: 1px solid var(--border); border-radius: var(--radius);
  overflow: hidden; box-shadow: var(--shadow); display: flex; flex-direction: column; min-height: 320px;
}}
.term-bar {{
  display: flex; align-items: center; gap: .4rem; padding: .55rem .8rem; border-bottom: 1px solid var(--border);
  background: #111; color: var(--text-dim); font-size: .75rem;
}}
.term-dot {{ width: 10px; height: 10px; border-radius: 50%; }}
.term-dot.r {{ background: #c45c5c; }} .term-dot.y {{ background: #c9a227; }} .term-dot.g {{ background: #6b9f7a; }}
.term-body {{
  flex: 1; margin: 0; padding: .85rem 1rem; font-family: var(--mono); font-size: .78rem; line-height: 1.45;
  color: #c8e6c9; white-space: pre-wrap; word-break: break-word; max-height: 420px; overflow: auto;
}}
.term-input-row {{ display: flex; gap: .4rem; padding: .55rem .7rem; border-top: 1px solid var(--border); background: #0e0e0e; }}
.term-input-row span {{ color: var(--accent); font-family: var(--mono); padding-top: .45rem; }}
.term-input {{
  flex: 1; background: transparent; border: 0; color: var(--text); font-family: var(--mono); font-size: .82rem; padding: .4rem 0;
}}
.term-input:focus {{ outline: none; }}

.status-line {{ min-height: 1.3rem; color: var(--text-dim); font-size: .85rem; margin-top: .55rem; }}
.status-line.busy {{ color: var(--accent); }}
.status-line.err {{ color: var(--bad); }}

.skel {{ display: none; gap: .4rem; flex-direction: column; }}
.skel.on {{ display: flex; }}
.skel i {{ display: block; height: 10px; border-radius: 6px; background: linear-gradient(90deg,#1a1a1a,#2a2a2a,#1a1a1a); background-size: 200% 100%; animation: shimmer 1.1s infinite linear; }}
@keyframes shimmer {{ 0% {{ background-position: 200% 0; }} 100% {{ background-position: -200% 0; }} }}

.sample summary {{ cursor: pointer; color: var(--accent); font-size: .85rem; }}
.sample pre {{ background: #0a0a0a; border: 1px solid var(--border-soft); border-radius: 8px; padding: .7rem; color: #cfc9bc; font-size: .75rem; overflow: auto; }}

.footer-note {{ color: var(--text-dim); font-size: .78rem; margin-top: 1.5rem; line-height: 1.5; }}
.sql-box {{ margin-top: .75rem; background: #0a0a0a; border: 1px solid var(--border-soft); border-radius: 8px; padding: .75rem; font-family: var(--mono); font-size: .75rem; color: #d7d0c3; white-space: pre-wrap; max-height: 200px; overflow: auto; }}
</style>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet"/>
</head>
<body>
<div class="app">
  <header class="top">
    <div class="brand">
      <svg width="28" height="28" viewBox="0 0 64 64" aria-hidden="true"><rect width="64" height="64" rx="14" fill="#1a1a1a"/><path d="M18 40 L30 22 L38 34 L48 18" stroke="#f5f0e8" stroke-width="5" fill="none" stroke-linecap="round"/><circle cx="48" cy="18" r="4" fill="#d4a574"/></svg>
      known-path <span>workbench</span>
    </div>
    <nav class="nav">
      <a href="https://github.com/SeraKah-1/known-path" target="_blank" rel="noreferrer">GitHub</a>
      <a href="https://datahub.devpost.com" target="_blank" rel="noreferrer">Hackathon</a>
      <a href="https://docs.datahub.com/docs/features/feature-guides/mcp" target="_blank" rel="noreferrer">DataHub MCP</a>
    </nav>
    <div class="pill-live">CLI bridge live</div>
  </header>

  <div class="main">
    <section class="panel">
      <p class="eyebrow">Data job activation</p>
      <h1>Only light the catalog assets you can trust.</h1>
      <p class="lede">
        Enterprise workbench for the DataHub Agent Hackathon. Every button shells into the real
        <code style="color:var(--accent)">known-path</code> CLI — the same path an AI agent would call.
        Dataset: <code style="color:var(--text-muted)">{_esc(dataset_dir().name)}</code> ({len(assets)} assets).
      </p>

      <div class="card">
        <h2>Job intent <span class="hint">serial-position: start here</span></h2>
        <textarea id="intent" class="intent-box" rows="3">{_esc(DEFAULT_INTENT)}</textarea>
        <div class="actions">
          <button class="btn" id="btnBase" onclick="runMode('baseline')">Baseline thrash</button>
          <button class="btn primary" id="btnKp" onclick="runMode('known-path')">Known path</button>
          <button class="btn danger" id="btnBlk" onclick="runMode('blocked')">Fail closed</button>
          <button class="btn ghost" id="btnAll" onclick="runDemo()">Full demo</button>
        </div>
        <div class="status-line" id="status">Ready. Actions run via <code>python -m known_path.cli …</code></div>
        <div class="skel" id="skel"><i style="width:90%"></i><i style="width:70%"></i><i style="width:55%"></i></div>
      </div>

      <div class="metrics" id="metrics">
        <div class="metric"><div class="k">Status</div><div class="v" id="mStatus">—</div></div>
        <div class="metric"><div class="k">Entity fetches</div><div class="v" id="mFetches">—</div></div>
        <div class="metric"><div class="k">Activated / trap</div><div class="v" id="mAct">—</div></div>
      </div>

      <div class="card">
        <h2>Activation graph <span class="hint">nodes lit by the last CLI run</span></h2>
        <div class="graph-wrap">
          <div class="svg-card"><svg id="nodeGraph" viewBox="0 0 400 220" role="img" aria-label="Activation graph"></svg></div>
          <div>
            <p style="margin:0 0 .5rem;color:var(--text-muted);font-size:.85rem">Catalog usage (honest scale 0–max)</p>
            {chart_bars}
          </div>
        </div>
        <div id="sqlOut" class="sql-box" style="display:none"></div>
      </div>

      <div class="card">
        <h2>Fetch cost comparison <span class="hint">charts that don’t lie — shared axis</span></h2>
        <div class="compare" id="compare">
          <div class="compare-row"><span>baseline</span><div class="compare-track"><div class="compare-fill base" id="cBase" style="width:0%"></div></div><span id="cBaseN">0</span></div>
          <div class="compare-row"><span>known-path</span><div class="compare-track"><div class="compare-fill kp" id="cKp" style="width:0%"></div></div><span id="cKpN">0</span></div>
          <div class="compare-row"><span>blocked</span><div class="compare-track"><div class="compare-fill blk" id="cBlk" style="width:0%"></div></div><span id="cBlkN">0</span></div>
        </div>
      </div>

      <div class="card">
        <h2>Catalog · demo-finance</h2>
        <table class="data">
          <thead><tr><th>Asset</th><th>Role</th><th>Certified</th><th>Deprecated</th><th>Quality</th><th>Usage</th></tr></thead>
          <tbody>{''.join(catalog_rows)}</tbody>
        </table>
        <div style="margin-top:.8rem">{sample_html}</div>
      </div>

      <p class="footer-note">
        UX: DesignMotionHQ tokens, hierarchy, loading skeletons, data tables, peak–end metrics.
        Resources path: offline demo-finance + CLI/MCP story (see docs/UX_AND_RESOURCES.md).
        Not a DataHub rebuild — activation layer with fail-closed trust.
      </p>
    </section>

    <aside class="panel">
      <div class="card" style="margin-top:0">
        <h2>Agent terminal <span class="hint">web → CLI</span></h2>
        <p style="margin:0 0 .75rem;color:var(--text-muted);font-size:.88rem;line-height:1.45">
          Commands are allow-listed and executed by the real CLI process.
          Try: <code>run known-path</code>, <code>run baseline</code>, <code>demo</code>, <code>doctor</code>, <code>dataset</code>
        </p>
        <div class="term">
          <div class="term-bar">
            <span class="term-dot r"></span><span class="term-dot y"></span><span class="term-dot g"></span>
            <span style="margin-left:.5rem">agent@known-path — bridged shell</span>
          </div>
          <pre class="term-body" id="term">$ ready
# Web buttons and this prompt both call:
#   python -m known_path.cli …
# so demos match automation and MCP hosts.

</pre>
          <form class="term-input-row" onsubmit="return agentSubmit(event)">
            <span>$</span>
            <input class="term-input" id="agentCmd" autocomplete="off" placeholder="run known-path :: revenue by region last quarter"/>
            <button class="btn primary" type="submit" style="padding:.4rem .85rem">Enter</button>
          </form>
        </div>
        <div class="status-line" id="agentStatus"></div>
      </div>

      <div class="card">
        <h2>Last CLI command</h2>
        <pre class="term-body" id="lastCmd" style="max-height:120px;border-radius:8px;border:1px solid var(--border-soft)">—</pre>
      </div>
    </aside>
  </div>
</div>

<script>
const $ = (id) => document.getElementById(id);
const state = {{ lastPlans: {{}}, compareMax: 8 }};

function setBusy(on, msg) {{
  ['btnBase','btnKp','btnBlk','btnAll'].forEach(id => {{ const b=$(id); if(b) b.disabled = on; }});
  $('skel').classList.toggle('on', on);
  $('status').className = 'status-line' + (on ? ' busy' : '');
  if (msg) $('status').textContent = msg;
}}

function appendTerm(text) {{
  const el = $('term');
  el.textContent += text;
  el.scrollTop = el.scrollHeight;
}}

function showCliEnvelope(data) {{
  $('lastCmd').textContent = data.command || '—';
  if (data.command) appendTerm(`\\n$ ${{data.command}}\\n`);
  if (data.stdout) appendTerm(data.stdout.endsWith('\\n') ? data.stdout : data.stdout + '\\n');
  if (data.stderr) appendTerm(data.stderr + '\\n');
  if (data.duration_ms != null) appendTerm(`[exit ${{data.exit_code}} · ${{data.duration_ms}}ms]\\n`);
}}

function trapHit(plan) {{
  return (plan.nodes || []).some(n => n.activated && /revenue_old|rev_backup|old|backup/i.test(n.name || ''));
}}

function paintMetrics(plan) {{
  const st = plan.status || '—';
  const el = $('mStatus');
  el.textContent = st;
  el.className = 'v ' + (st === 'SUCCESS' ? 'good' : st === 'BLOCKED_TRUST' ? 'bad' : 'warn');
  $('mFetches').textContent = plan.entity_fetches ?? '—';
  const act = (plan.nodes || []).filter(n => n.activated).length;
  $('mAct').textContent = act + (trapHit(plan) ? ' · trap' : ' · clean');
  $('mAct').className = 'v ' + (trapHit(plan) ? 'bad' : 'good');
  if (plan.sql_artifact) {{
    $('sqlOut').style.display = 'block';
    $('sqlOut').textContent = plan.sql_artifact;
  }} else {{
    $('sqlOut').style.display = 'none';
  }}
  drawGraph(plan);
}}

function drawGraph(plan) {{
  const svg = $('nodeGraph');
  const nodes = plan.nodes || [];
  const W = 400, H = 220;
  // layout: activated on left arc, inactive on right
  let html = `<rect width="${{W}}" height="${{H}}" fill="#121212"/>`;
  html += `<text x="12" y="18" fill="#6b6760" font-size="11" font-family="IBM Plex Sans,sans-serif">activation map</text>`;
  if (!nodes.length) {{
    html += `<text x="50%" y="50%" text-anchor="middle" fill="#6b6760" font-size="13">Run a mode to light nodes</text>`;
    svg.innerHTML = html;
    return;
  }}
  const act = nodes.filter(n => n.activated);
  const rest = nodes.filter(n => !n.activated);
  const place = (list, x0, color) => {{
    list.forEach((n, i) => {{
      const y = 50 + i * Math.min(36, 160 / Math.max(list.length, 1));
      const r = n.activated ? 16 : 11;
      const fill = n.trust === 'red' ? '#c45c5c' : (n.activated ? '#6b9f7a' : '#3a3a3a');
      const stroke = n.trust === 'yellow' ? '#c9a227' : (n.activated ? '#8fbf9a' : '#2a2a2a');
      html += `<circle cx="${{x0}}" cy="${{y}}" r="${{r}}" fill="${{fill}}" stroke="${{stroke}}" stroke-width="2" opacity="${{n.activated ? 1 : .55}}"/>`;
      const label = (n.name || '').split('.').slice(-2).join('.');
      html += `<text x="${{x0 + 24}}" y="${{y + 4}}" fill="#cfc9bc" font-size="11" font-family="IBM Plex Mono,monospace">${{label}}</text>`;
      html += `<text x="${{x0 + 24}}" y="${{y + 16}}" fill="#6b6760" font-size="9" font-family="IBM Plex Sans,sans-serif">rel ${{n.relevance}} · ${{n.trust}}${{n.activated ? ' · ON' : ''}}</text>`;
    }});
  }};
  place(act.length ? act : nodes.slice(0, 4), 48, '#6b9f7a');
  place(rest.slice(0, 5), 220, '#3a3a3a');
  // edges from intent hub
  html += `<circle cx="200" cy="200" r="6" fill="#d4a574"/>`;
  html += `<text x="212" y="204" fill="#9a958c" font-size="10">intent</text>`;
  (act.length ? act : []).forEach((n, i) => {{
    const y = 50 + i * Math.min(36, 160 / Math.max(act.length, 1));
    html += `<path d="M200 194 Q 120 ${{(y+200)/2}} 64 ${{y}}" stroke="#d4a57455" fill="none" stroke-width="1.5"/>`;
  }});
  svg.innerHTML = html;
}}

function updateCompare(mode, fetches) {{
  state.lastPlans[mode] = fetches;
  const vals = [state.lastPlans['baseline']||0, state.lastPlans['known-path']||0, state.lastPlans['blocked']||0];
  const max = Math.max(state.compareMax, ...vals, 1);
  const set = (id, nId, v, cls) => {{
    const pct = Math.round(100 * v / max);
    $(id).style.width = pct + '%';
    $(nId).textContent = v;
  }};
  set('cBase','cBaseN', state.lastPlans['baseline']||0);
  set('cKp','cKpN', state.lastPlans['known-path']||0);
  set('cBlk','cBlkN', state.lastPlans['blocked']||0);
}}

async function runMode(mode) {{
  const intent = $('intent').value.trim();
  setBusy(true, 'Shelling to CLI: run --mode ' + mode + ' …');
  appendTerm(`\\n# web → CLI bridge\\n`);
  try {{
    const r = await fetch('/api/cli/run?mode=' + encodeURIComponent(mode) + '&intent=' + encodeURIComponent(intent));
    const data = await r.json();
    showCliEnvelope(data);
    if (data.error && !data.plan) {{
      $('status').className = 'status-line err';
      $('status').textContent = data.error;
      return;
    }}
    const plan = data.plan || {{}};
    paintMetrics(plan);
    updateCompare(plan.mode || mode, plan.entity_fetches || 0);
    $('status').className = 'status-line';
    $('status').textContent = (plan.status || 'done') + ' · via CLI in ' + data.duration_ms + 'ms';
  }} catch (e) {{
    $('status').className = 'status-line err';
    $('status').textContent = String(e);
  }} finally {{
    setBusy(false);
  }}
}}

async function runDemo() {{
  setBusy(true, 'Full demo via CLI (3 sequential runs)…');
  appendTerm('\\n# web → CLI full demo\\n');
  try {{
    const r = await fetch('/api/cli/demo?intent=' + encodeURIComponent($('intent').value.trim()));
    const data = await r.json();
    showCliEnvelope(data);
    (data.plans || []).forEach(p => {{
      updateCompare(p.mode, p.entity_fetches || 0);
    }});
    const last = (data.plans || [])[(data.plans||[]).length - 1] || (data.plans||[])[1];
    if (data.plans && data.plans[1]) paintMetrics(data.plans[1]);
    else if (last) paintMetrics(last);
    $('status').textContent = 'Full demo complete · ' + data.duration_ms + 'ms CLI time';
  }} catch (e) {{
    $('status').className = 'status-line err';
    $('status').textContent = String(e);
  }} finally {{
    setBusy(false);
  }}
}}

async function agentSubmit(ev) {{
  ev.preventDefault();
  const cmd = $('agentCmd').value.trim();
  if (!cmd) return false;
  $('agentStatus').textContent = 'Running…';
  $('agentCmd').value = '';
  appendTerm('\\n$ ' + cmd + '\\n');
  try {{
    const r = await fetch('/api/agent', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{ command: cmd, intent: $('intent').value }})
    }});
    const data = await r.json();
    // command already echoed; show output only
    if (data.stdout) appendTerm(data.stdout.endsWith('\\n') ? data.stdout : data.stdout + '\\n');
    if (data.stderr) appendTerm(data.stderr + '\\n');
    if (data.error) appendTerm('error: ' + data.error + '\\n');
    appendTerm(`[exit ${{data.exit_code}} · ${{data.duration_ms}}ms]\\n`);
    $('lastCmd').textContent = data.command || cmd;
    if (data.plan) {{
      paintMetrics(data.plan);
      updateCompare(data.plan.mode || 'known-path', data.plan.entity_fetches || 0);
    }}
    if (data.plans) {{
      data.plans.forEach(p => updateCompare(p.mode, p.entity_fetches || 0));
      if (data.plans[1]) paintMetrics(data.plans[1]);
    }}
    $('agentStatus').textContent = data.ok ? 'ok' : (data.error || 'finished with errors');
  }} catch (e) {{
    $('agentStatus').textContent = String(e);
  }}
  return false;
}}

// empty graph initially
drawGraph({{ nodes: [] }});
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print("[web]", fmt % args)

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: object) -> None:
        self._send(code, json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8")

    def _read_json(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        raw = self.rfile.read(n)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path or "/"
        qs = parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            self._send(200, _html_page().encode("utf-8"), "text/html; charset=utf-8")
            return

        if path == "/api/health":
            self._json(
                200,
                {
                    "ok": True,
                    "dataset": str(dataset_dir()),
                    "assets": len(demo_catalog()),
                    "bridge": "cli",
                },
            )
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
                    "usage_score": a.usage_score,
                    "glossary_terms": a.glossary_terms,
                    "columns": a.columns,
                }
                for a in demo_catalog()
            ]
            self._json(200, {"assets": assets, "samples": list_sample_files()})
            return

        # Legacy alias still goes through CLI
        if path == "/api/run":
            mode = (qs.get("mode") or ["known-path"])[0]
            intent = (qs.get("intent") or [DEFAULT_INTENT])[0]
            r = run_mode_via_cli(mode, intent)
            self._json(200, result_to_dict(r))
            return

        if path == "/api/cli/run":
            mode = (qs.get("mode") or ["known-path"])[0]
            intent = (qs.get("intent") or [DEFAULT_INTENT])[0]
            r = run_mode_via_cli(mode, intent)
            self._json(200, result_to_dict(r))
            return

        if path in ("/api/cli/demo", "/api/demo"):
            intent = (qs.get("intent") or [DEFAULT_INTENT])[0]
            r = run_demo_via_cli(intent=intent)
            self._json(200, result_to_dict(r))
            return

        self._send(404, b"not found", "text/plain; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path or "/"
        if path == "/api/agent":
            body = self._read_json()
            cmd = (body.get("command") or "").strip()
            # Optional intent injection for bare "run known-path"
            if cmd.lower() in ("run known-path", "run baseline", "run blocked") and body.get("intent"):
                cmd = f"{cmd} {body['intent']}"
            r = agent_command(cmd)
            self._json(200, result_to_dict(r))
            return
        self._send(404, b"not found", "text/plain; charset=utf-8")


def serve(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, open_browser: bool = False) -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print(f"known-path enterprise workbench → {url}")
    print(f"dataset → {dataset_dir()}")
    print("bridge → python -m known_path.cli (allow-listed)")
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

    p = argparse.ArgumentParser(description="known-path enterprise web workbench")
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--open", action="store_true")
    args = p.parse_args()
    serve(host=args.host, port=args.port, open_browser=args.open)


if __name__ == "__main__":
    main()
