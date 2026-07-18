"""known-path workbench UI — Claude Cowork–inspired product design.

Warm Anthropic palette, soft surfaces, artifact-style work panel.
Functionality unchanged: agent rail, CLI bridge, settings, viz.
"""

from __future__ import annotations

import json
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from known_path.agent_runtime import chat as agent_chat
from known_path.agent_runtime import fetch_models, test_datahub
from known_path.cli_bridge import agent_command, result_to_dict, run_demo_via_cli, run_mode_via_cli
from known_path.dataset_io import (
    active_dataset_id,
    list_datasets,
    set_active_dataset,
    upload_catalog_json,
    upload_csv,
)
from known_path.fixtures import dataset_dir, demo_catalog, list_sample_files
from known_path.settings_store import load_settings, public_settings, save_settings

DEFAULT_INTENT = "revenue by region last quarter Finance canonical"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8090


def _esc(s: object) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _html_page() -> str:
    boot = {
        "datasets": list_datasets(),
        "active": active_dataset_id(),
        "settings": public_settings(),
        "asset_count": len(demo_catalog()),
        "default_intent": DEFAULT_INTENT,
    }
    boot_js = json.dumps(boot)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>known-path</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600&display=swap" rel="stylesheet"/>
<style>
/* Claude / Anthropic–inspired tokens: warm paper, clay accent, soft chrome */
:root {{
  --paper: #f7f4ef;
  --paper-2: #f0ebe3;
  --surface: #fffcf7;
  --ink: #1f1e1c;
  --ink-2: #4a4640;
  --ink-3: #8a847a;
  --line: #e6e0d6;
  --line-2: #ddd6ca;
  --clay: #c96442;
  --clay-soft: #f3e4dc;
  --clay-deep: #a84f32;
  --sage: #3d6b4f;
  --sage-soft: #e3efe7;
  --rose: #a33b3b;
  --rose-soft: #f6e4e2;
  --amber: #9a7420;
  --amber-soft: #f5edd6;
  --r: 16px;
  --r-sm: 10px;
  --shadow: 0 1px 2px rgba(31,30,28,.04), 0 8px 24px rgba(31,30,28,.06);
  --shadow-lg: 0 4px 8px rgba(31,30,28,.04), 0 24px 48px rgba(31,30,28,.08);
  --font: "Inter", system-ui, -apple-system, sans-serif;
  --serif: "Instrument Serif", Georgia, serif;
  --ease: cubic-bezier(.22, 1, .36, 1);
}}
* {{ box-sizing: border-box; }}
html, body {{ height: 100%; margin: 0; }}
body {{
  font-family: var(--font);
  background: var(--paper);
  color: var(--ink);
  -webkit-font-smoothing: antialiased;
}}
button, input, select, textarea {{ font: inherit; color: inherit; }}
button {{ cursor: pointer; border: 0; background: none; }}
button:disabled {{ opacity: .5; cursor: wait; }}
a {{ color: var(--clay); text-decoration: none; }}
a:hover {{ text-decoration: underline; text-underline-offset: 3px; }}
:focus-visible {{ outline: 2px solid var(--clay); outline-offset: 2px; }}

.app {{ height: 100vh; display: grid; grid-template-rows: 56px 1fr; }}

/* Top bar — minimal, product-like */
.top {{
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 1.25rem;
  background: rgba(247,244,239,.85);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--line);
  z-index: 10;
}}
.brand {{
  display: flex; align-items: center; gap: .65rem;
  font-weight: 600; font-size: .95rem; letter-spacing: -.02em;
}}
.brand-mark {{
  width: 28px; height: 28px; border-radius: 8px;
  background: linear-gradient(145deg, #d47850, var(--clay-deep));
  display: grid; place-items: center;
  box-shadow: inset 0 1px 0 rgba(255,255,255,.25);
}}
.brand-mark svg {{ display: block; }}
.brand em {{
  font-family: var(--serif); font-style: italic; font-weight: 400;
  color: var(--ink-2); font-size: 1.05rem;
}}
.top-right {{ display: flex; align-items: center; gap: .5rem; }}
.pill {{
  font-size: .72rem; font-weight: 500; color: var(--ink-2);
  background: var(--surface); border: 1px solid var(--line);
  padding: .3rem .65rem; border-radius: 999px;
}}
.icon-btn {{
  width: 36px; height: 36px; border-radius: 999px;
  display: grid; place-items: center;
  color: var(--ink-2); border: 1px solid transparent;
  transition: background .15s var(--ease), border-color .15s var(--ease);
}}
.icon-btn:hover {{ background: var(--surface); border-color: var(--line); }}

/* Shell: ~1/3 task + 2/3 work (Cowork: steer task | see work) */
.shell {{
  display: grid;
  grid-template-columns: minmax(320px, 34%) minmax(0, 66%);
  min-height: 0;
}}
@media (max-width: 900px) {{
  .shell {{ grid-template-columns: 1fr; grid-template-rows: 48vh 1fr; }}
}}

.task {{
  display: flex; flex-direction: column; min-height: 0;
  background: var(--surface);
  border-right: 1px solid var(--line);
}}
.work {{
  display: flex; flex-direction: column; min-height: 0;
  background: var(--paper);
}}

.section-label {{
  padding: 1rem 1.25rem .5rem;
  font-size: .7rem; font-weight: 600; letter-spacing: .08em;
  text-transform: uppercase; color: var(--ink-3);
}}

/* Chat */
.chat {{
  flex: 1; overflow: auto; padding: .5rem 1.25rem 1rem;
  display: flex; flex-direction: column; gap: .85rem;
}}
.msg {{
  max-width: 100%; animation: rise .35s var(--ease) both;
}}
@keyframes rise {{
  from {{ opacity: 0; transform: translateY(6px); }}
  to {{ opacity: 1; transform: none; }}
}}
.msg.user {{
  align-self: flex-end; max-width: 92%;
  background: var(--ink); color: var(--paper);
  padding: .75rem 1rem; border-radius: 18px 18px 6px 18px;
  font-size: .92rem; line-height: 1.45;
}}
.msg.assistant {{
  align-self: stretch;
  font-size: .95rem; line-height: 1.55; color: var(--ink-2);
  padding: .15rem 0;
}}
.msg.assistant strong {{ color: var(--ink); font-weight: 600; }}
.msg.step {{
  align-self: stretch;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: .7rem .9rem;
  font-size: .8rem; color: var(--ink-2);
}}
.msg.step .cmd {{
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: .72rem; color: var(--ink-3);
  margin-top: .35rem; word-break: break-all;
}}
.msg.step .badge {{
  display: inline-flex; align-items: center; gap: .3rem;
  font-size: .68rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: .04em; color: var(--clay);
}}

.composer {{
  padding: .85rem 1.1rem 1.15rem;
  border-top: 1px solid var(--line);
  background: linear-gradient(180deg, transparent, var(--surface) 20%);
}}
.composer-box {{
  background: var(--paper);
  border: 1px solid var(--line-2);
  border-radius: 18px;
  padding: .65rem .75rem .55rem;
  box-shadow: var(--shadow);
  transition: border-color .15s var(--ease), box-shadow .15s var(--ease);
}}
.composer-box:focus-within {{
  border-color: #d2c4b4;
  box-shadow: 0 0 0 3px rgba(201,100,66,.12), var(--shadow);
}}
.composer-box textarea {{
  width: 100%; border: 0; background: transparent; resize: none;
  min-height: 64px; max-height: 160px; padding: .25rem .35rem;
  line-height: 1.45; font-size: .95rem;
}}
.composer-box textarea:focus {{ outline: none; }}
.composer-box textarea::placeholder {{ color: var(--ink-3); }}
.composer-foot {{
  display: flex; align-items: center; justify-content: space-between;
  gap: .5rem; margin-top: .35rem; padding: 0 .2rem;
}}
.suggestions {{ display: flex; flex-wrap: wrap; gap: .35rem; }}
.chip {{
  font-size: .72rem; font-weight: 500; color: var(--ink-2);
  background: var(--surface); border: 1px solid var(--line);
  padding: .28rem .6rem; border-radius: 999px;
  transition: background .15s, border-color .15s;
}}
.chip:hover {{ background: var(--clay-soft); border-color: #e8cfc2; color: var(--clay-deep); }}
.btn-send {{
  width: 36px; height: 36px; border-radius: 999px;
  background: var(--clay); color: white;
  display: grid; place-items: center;
  box-shadow: 0 1px 2px rgba(168,79,50,.25);
  transition: background .15s var(--ease), transform .15s var(--ease);
}}
.btn-send:hover {{ background: var(--clay-deep); }}
.btn-send:active {{ transform: scale(.96); }}

/* Work panel */
.work-head {{
  padding: 1.1rem 1.5rem .75rem;
  display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem;
}}
.work-head h2 {{
  margin: 0; font-family: var(--serif); font-weight: 400;
  font-size: 1.65rem; letter-spacing: -.02em; line-height: 1.15; color: var(--ink);
}}
.work-head p {{ margin: .35rem 0 0; color: var(--ink-3); font-size: .88rem; max-width: 36rem; line-height: 1.45; }}
.work-actions {{ display: flex; flex-wrap: wrap; gap: .4rem; justify-content: flex-end; }}
.btn {{
  font-size: .8rem; font-weight: 500;
  padding: .45rem .85rem; border-radius: 999px;
  border: 1px solid var(--line); background: var(--surface); color: var(--ink-2);
  transition: background .15s, border-color .15s, color .15s;
}}
.btn:hover {{ background: var(--paper-2); border-color: var(--line-2); }}
.btn.primary {{ background: var(--ink); color: var(--paper); border-color: var(--ink); }}
.btn.primary:hover {{ background: #2c2a27; }}
.btn.quiet {{ background: transparent; }}

.work-body {{
  flex: 1; overflow: auto; padding: 0 1.5rem 1.75rem;
  display: grid; gap: 1rem;
  grid-template-columns: 1.15fr .85fr;
  align-content: start;
}}
@media (max-width: 1100px) {{ .work-body {{ grid-template-columns: 1fr; }} }}

.card {{
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--r);
  padding: 1.1rem 1.15rem;
  box-shadow: var(--shadow);
}}
.card h3 {{
  margin: 0 0 .85rem;
  font-size: .78rem; font-weight: 600; letter-spacing: .06em;
  text-transform: uppercase; color: var(--ink-3);
}}

/* Timeline process — Cowork “see the work as it happens” */
.timeline {{ display: flex; flex-direction: column; gap: 0; }}
.tl-item {{
  display: grid; grid-template-columns: 20px 1fr; gap: .75rem;
  padding: .55rem 0;
}}
.tl-rail {{
  display: flex; flex-direction: column; align-items: center;
}}
.tl-dot {{
  width: 12px; height: 12px; border-radius: 50%;
  background: var(--paper-2); border: 2px solid var(--line-2);
  flex-shrink: 0; margin-top: 3px;
  transition: background .25s, border-color .25s, box-shadow .25s;
}}
.tl-item.done .tl-dot {{ background: var(--sage); border-color: var(--sage); }}
.tl-item.active .tl-dot {{
  background: var(--clay); border-color: var(--clay);
  box-shadow: 0 0 0 4px var(--clay-soft);
}}
.tl-item.fail .tl-dot {{ background: var(--rose); border-color: var(--rose); }}
.tl-line {{
  width: 2px; flex: 1; min-height: 12px; background: var(--line);
  margin: 4px 0 0;
}}
.tl-item:last-child .tl-line {{ display: none; }}
.tl-body {{ min-width: 0; padding-bottom: .15rem; }}
.tl-title {{ font-size: .9rem; font-weight: 500; color: var(--ink); }}
.tl-desc {{ font-size: .8rem; color: var(--ink-3); margin-top: .15rem; line-height: 1.4; }}

/* KPIs — quiet, not neon */
.stats {{
  display: grid; grid-template-columns: repeat(4, 1fr); gap: .55rem;
  margin-top: 1rem;
}}
@media (max-width: 640px) {{ .stats {{ grid-template-columns: repeat(2, 1fr); }} }}
.stat {{
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: .7rem .75rem;
}}
.stat .k {{ font-size: .68rem; font-weight: 500; color: var(--ink-3); text-transform: uppercase; letter-spacing: .05em; }}
.stat .v {{ font-family: var(--serif); font-size: 1.45rem; margin-top: .2rem; letter-spacing: -.02em; color: var(--ink); }}
.stat .v.good {{ color: var(--sage); }}
.stat .v.bad {{ color: var(--rose); }}
.stat .v.warn {{ color: var(--amber); }}

#graph {{
  width: 100%; height: 220px; display: block;
  background: var(--paper); border-radius: 12px; border: 1px solid var(--line);
}}
#donut {{ width: 100%; height: 148px; display: block; }}

.bars {{ display: flex; flex-direction: column; gap: .55rem; }}
.bar-row {{
  display: grid; grid-template-columns: 92px 1fr 28px; gap: .5rem; align-items: center;
  font-size: .8rem; color: var(--ink-2);
}}
.bar-track {{
  height: 8px; background: var(--paper-2); border-radius: 99px; overflow: hidden;
}}
.bar-fill {{
  height: 100%; border-radius: 99px; width: 0%;
  transition: width .55s var(--ease);
}}
.bar-fill.b {{ background: #c47a6a; }}
.bar-fill.k {{ background: var(--sage); }}
.bar-fill.x {{ background: var(--amber); }}
.bar-n {{ font-variant-numeric: tabular-nums; color: var(--ink-3); text-align: right; }}

table.t {{ width: 100%; border-collapse: collapse; font-size: .82rem; }}
table.t th {{
  text-align: left; font-weight: 500; color: var(--ink-3);
  padding: .45rem .3rem; border-bottom: 1px solid var(--line);
  font-size: .72rem; text-transform: uppercase; letter-spacing: .04em;
}}
table.t td {{
  padding: .55rem .3rem; border-bottom: 1px solid var(--line);
  color: var(--ink-2); vertical-align: middle;
}}
table.t tr:last-child td {{ border-bottom: 0; }}
.dot {{
  width: 8px; height: 8px; border-radius: 50%; display: inline-block;
  margin-right: .4rem; background: var(--line-2); vertical-align: middle;
}}
.dot.on {{ background: var(--sage); }}
.dot.trap {{ background: var(--rose); }}
.dot.red {{ background: var(--rose); }}

.trace {{
  margin: 0; max-height: 140px; overflow: auto;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: .7rem; line-height: 1.45; color: var(--ink-3);
  white-space: pre-wrap; word-break: break-word;
  background: var(--paper); border-radius: 10px; padding: .75rem;
  border: 1px solid var(--line);
}}

.empty-work {{
  text-align: center; padding: 2.5rem 1.5rem; color: var(--ink-3);
}}
.empty-work h4 {{
  font-family: var(--serif); font-weight: 400; font-size: 1.35rem;
  color: var(--ink-2); margin: 0 0 .4rem;
}}
.empty-work p {{ margin: 0; font-size: .9rem; line-height: 1.5; }}

/* Modal */
.modal-bg {{
  position: fixed; inset: 0; z-index: 40;
  background: rgba(31,30,28,.35);
  display: none; place-items: center; padding: 1rem;
  backdrop-filter: blur(4px);
}}
.modal-bg.open {{ display: grid; }}
.modal {{
  width: min(480px, 100%); max-height: 90vh; overflow: auto;
  background: var(--surface); border-radius: 20px;
  border: 1px solid var(--line); box-shadow: var(--shadow-lg);
  padding: 1.35rem 1.4rem 1.25rem;
}}
.modal h2 {{
  margin: 0 0 .25rem; font-family: var(--serif); font-weight: 400;
  font-size: 1.5rem; letter-spacing: -.02em;
}}
.modal .sub {{ margin: 0 0 1.1rem; color: var(--ink-3); font-size: .88rem; }}
.field {{ display: grid; gap: .3rem; margin-bottom: .8rem; }}
.field label {{ font-size: .75rem; font-weight: 500; color: var(--ink-2); }}
.field input, .field select {{
  background: var(--paper); border: 1px solid var(--line-2);
  border-radius: 10px; padding: .6rem .75rem; font-size: .9rem;
}}
.field input:focus, .field select:focus {{
  outline: none; border-color: #d2b5a4;
  box-shadow: 0 0 0 3px rgba(201,100,66,.12);
}}
.hint {{ font-size: .75rem; color: var(--ink-3); line-height: 1.45; margin: 0 0 .75rem; }}
.modal-actions {{ display: flex; justify-content: flex-end; gap: .45rem; margin-top: 1rem; }}

.toast {{
  position: fixed; bottom: 1.25rem; left: 50%; transform: translateX(-50%) translateY(12px);
  background: var(--ink); color: var(--paper); font-size: .85rem; font-weight: 500;
  padding: .65rem 1.1rem; border-radius: 999px; opacity: 0; pointer-events: none;
  transition: opacity .25s, transform .25s var(--ease); z-index: 50;
  box-shadow: var(--shadow-lg);
}}
.toast.on {{ opacity: 1; transform: translateX(-50%) translateY(0); }}

.loading-dots::after {{
  content: '';
  animation: dots 1.2s steps(4,end) infinite;
}}
@keyframes dots {{ 0% {{ content: ''; }} 25% {{ content: '.'; }} 50% {{ content: '..'; }} 75% {{ content: '...'; }} }}
</style>
</head>
<body>
<div class="app">
  <header class="top">
    <div class="brand">
      <div class="brand-mark" aria-hidden="true">
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
          <path d="M2 11 L6 4 L9 8 L14 2" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      known-path <em>workbench</em>
    </div>
    <div class="top-right">
      <span class="pill" id="dsLabel">demo-finance</span>
      <button class="icon-btn" onclick="openSettings()" title="Settings" aria-label="Settings">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
          <circle cx="12" cy="12" r="3"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>
        </svg>
      </button>
    </div>
  </header>

  <div class="shell">
    <!-- Task / agent (Cowork: give it a goal) -->
    <section class="task">
      <div class="section-label">Task</div>
      <div class="chat" id="chat">
        <div class="msg assistant">
          Give known-path a goal — it activates trusted catalog assets, checks trust, and leaves a route you can review.
          <br/><br/>
          Tools run through the real CLI. Configure your model in settings when you want full agent chat.
        </div>
      </div>
      <div class="composer">
        <div class="composer-box">
          <textarea id="prompt" rows="3" placeholder="Describe the data job… e.g. Activate trusted tables for revenue by region"></textarea>
          <div class="composer-foot">
            <div class="suggestions">
              <button type="button" class="chip" onclick="quick('Activate trusted tables for revenue by region last quarter')">Trusted path</button>
              <button type="button" class="chip" onclick="quick('Compare baseline thrash vs known-path for revenue by region')">Compare</button>
              <button type="button" class="chip" onclick="quick('fail closed when trust is red')">Fail closed</button>
            </div>
            <button type="button" class="btn-send" id="sendBtn" onclick="sendAgent()" title="Send" aria-label="Send">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M5 12h14M13 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </button>
          </div>
        </div>
      </div>
    </section>

    <!-- Work (Cowork: see the work as it happens) -->
    <section class="work">
      <div class="work-head">
        <div>
          <h2>See the work</h2>
          <p>Each step lights only what the route sheet needs — no catalog dump, no invented tables.</p>
        </div>
        <div class="work-actions">
          <button class="btn quiet" onclick="loadDatasetPack('demo-finance')">Demo dataset</button>
          <button class="btn" onclick="document.getElementById('fileCat').click()">Upload catalog</button>
          <button class="btn" onclick="document.getElementById('fileCsv').click()">Upload CSV</button>
          <button class="btn primary" onclick="runTool('known-path')">Run path</button>
          <input type="file" id="fileCat" accept=".json,application/json" hidden onchange="onUploadCatalog(event)"/>
          <input type="file" id="fileCsv" accept=".csv,text/csv" hidden onchange="onUploadCsv(event)"/>
        </div>
      </div>

      <div class="work-body">
        <div style="display:flex;flex-direction:column;gap:1rem;min-width:0">
          <div class="card">
            <h3>Progress</h3>
            <div class="timeline" id="timeline">
              <div class="tl-item" data-s="intent"><div class="tl-rail"><div class="tl-dot"></div><div class="tl-line"></div></div><div class="tl-body"><div class="tl-title">Understand the goal</div><div class="tl-desc">Parse the data job intent</div></div></div>
              <div class="tl-item" data-s="route"><div class="tl-rail"><div class="tl-dot"></div><div class="tl-line"></div></div><div class="tl-body"><div class="tl-title">Open route sheet</div><div class="tl-desc">Match job card pointers (URNs)</div></div></div>
              <div class="tl-item" data-s="score"><div class="tl-rail"><div class="tl-dot"></div><div class="tl-line"></div></div><div class="tl-body"><div class="tl-title">Score &amp; shortlist</div><div class="tl-desc">Top-K only — cut the noise</div></div></div>
              <div class="tl-item" data-s="ping"><div class="tl-rail"><div class="tl-dot"></div><div class="tl-line"></div></div><div class="tl-body"><div class="tl-title">Trust ping</div><div class="tl-desc">Owner · deprecated · quality</div></div></div>
              <div class="tl-item" data-s="fetch"><div class="tl-rail"><div class="tl-dot"></div><div class="tl-line"></div></div><div class="tl-body"><div class="tl-title">Fetch shortlist</div><div class="tl-desc">Budgeted entity reads</div></div></div>
              <div class="tl-item" data-s="sql"><div class="tl-rail"><div class="tl-dot"></div><div class="tl-line"></div></div><div class="tl-body"><div class="tl-title">Build artifact</div><div class="tl-desc">SQL you could merge</div></div></div>
              <div class="tl-item" data-s="write"><div class="tl-rail"><div class="tl-dot"></div><div class="tl-line"></div></div><div class="tl-body"><div class="tl-title">Leave the route</div><div class="tl-desc">Write-back for the next run</div></div></div>
            </div>
            <div class="stats">
              <div class="stat"><div class="k">Status</div><div class="v" id="kStatus">—</div></div>
              <div class="stat"><div class="k">Fetches</div><div class="v" id="kFetches">—</div></div>
              <div class="stat"><div class="k">Lit</div><div class="v" id="kAct">—</div></div>
              <div class="stat"><div class="k">Trap</div><div class="v" id="kTrap">—</div></div>
            </div>
          </div>
          <div class="card">
            <h3>Activation map</h3>
            <svg id="graph" viewBox="0 0 520 220" role="img" aria-label="Activation map"></svg>
          </div>
        </div>
        <div style="display:flex;flex-direction:column;gap:1rem;min-width:0">
          <div class="card">
            <h3>Fetch cost</h3>
            <div class="bars">
              <div class="bar-row"><span>Baseline</span><div class="bar-track"><div class="bar-fill b" id="fb"></div></div><span class="bar-n" id="fbn">0</span></div>
              <div class="bar-row"><span>Known path</span><div class="bar-track"><div class="bar-fill k" id="fk"></div></div><span class="bar-n" id="fkn">0</span></div>
              <div class="bar-row"><span>Blocked</span><div class="bar-track"><div class="bar-fill x" id="fx"></div></div><span class="bar-n" id="fxn">0</span></div>
            </div>
          </div>
          <div class="card">
            <h3>Trust</h3>
            <svg id="donut" viewBox="0 0 200 140"></svg>
          </div>
          <div class="card" style="flex:1">
            <h3>Shortlist</h3>
            <table class="t">
              <thead><tr><th></th><th>Asset</th><th>Rel</th><th>Trust</th></tr></thead>
              <tbody id="shortBody">
                <tr><td colspan="4" style="color:var(--ink-3);padding:1rem .3rem">Hand off a task to fill this.</td></tr>
              </tbody>
            </table>
          </div>
          <div class="card">
            <h3>CLI</h3>
            <pre class="trace" id="cliTrace">Ready — actions shell into known-path CLI.</pre>
          </div>
        </div>
      </div>
    </section>
  </div>
</div>

<div class="modal-bg" id="settingsModal" role="dialog" aria-modal="true" aria-labelledby="setTitle">
  <div class="modal">
    <h2 id="setTitle">Settings</h2>
    <p class="sub">Connect a model and optional DataHub. Keys stay on this machine.</p>
    <div class="field"><label>Model endpoint (OpenAI-compatible)</label><input id="sBase" placeholder="https://api.openai.com/v1"/></div>
    <div class="field"><label>API key</label><input id="sKey" type="password" placeholder="Stored locally only"/></div>
    <div style="display:flex;gap:.5rem;margin-bottom:.8rem;align-items:center">
      <button type="button" class="btn" onclick="fetchModels()">Fetch models</button>
      <select id="sModel" style="flex:1;background:var(--paper);border:1px solid var(--line-2);border-radius:10px;padding:.55rem .7rem"></select>
    </div>
    <div class="field"><label>DataHub GMS URL</label><input id="sGms" placeholder="http://localhost:8080"/></div>
    <div class="field"><label>Personal Access Token</label><input id="sTok" type="password" placeholder="Bearer PAT"/></div>
    <p class="hint">Automation uses a <strong>PAT</strong>, not browser OAuth. Create one in DataHub → Settings → Access Tokens.</p>
    <div style="display:flex;gap:.75rem;align-items:center;margin-bottom:.75rem">
      <label style="display:flex;gap:.4rem;align-items:center;font-size:.85rem;color:var(--ink-2)"><input type="checkbox" id="sLive"/> Use live DataHub</label>
      <button type="button" class="btn quiet" onclick="testDh()">Test</button>
    </div>
    <div class="field"><label>Dataset pack</label><select id="sDs"></select></div>
    <p class="hint" id="setMsg"></p>
    <div class="modal-actions">
      <button type="button" class="btn quiet" onclick="closeSettings()">Cancel</button>
      <button type="button" class="btn primary" onclick="saveSettings()">Save</button>
    </div>
  </div>
</div>
<div class="toast" id="toast"></div>

<script>
const BOOT = {boot_js};
const state = {{ fetches: {{}}, lastPlan: null }};

const $ = (id) => document.getElementById(id);
function toast(m) {{
  const t = $('toast'); t.textContent = m; t.classList.add('on');
  clearTimeout(t._t); t._t = setTimeout(() => t.classList.remove('on'), 2600);
}}
function setBusy(on) {{
  $('sendBtn').disabled = on;
}}
function escapeHtml(s) {{
  return String(s ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
}}
function addMsg(role, html) {{
  const d = document.createElement('div');
  d.className = 'msg ' + role;
  d.innerHTML = html;
  $('chat').appendChild(d);
  $('chat').scrollTop = $('chat').scrollHeight;
  return d;
}}
function trapHit(plan) {{
  return (plan.nodes || []).some(n => n.activated && /old|backup|tmp/i.test(n.name || ''));
}}

function setTimeline(plan) {{
  const order = ['intent','route','score','ping','fetch','sql','write'];
  const st = plan.status;
  document.querySelectorAll('.tl-item').forEach(el => {{
    el.classList.remove('done','active','fail');
  }});
  const mark = (name, cls) => {{
    const el = document.querySelector('.tl-item[data-s="'+name+'"]');
    if (el) el.classList.add(cls);
  }};
  mark('intent','done'); mark('route','done'); mark('score','done');
  if (st === 'BLOCKED_TRUST') {{ mark('ping','fail'); return; }}
  mark('ping','done'); mark('fetch','done');
  if (plan.sql_artifact) mark('sql','done');
  if (plan.write_back_note) mark('write','done');
  else mark('write','active');
}}

function paintPlan(plan) {{
  if (!plan) return;
  state.lastPlan = plan;
  const st = plan.status || '—';
  const el = $('kStatus');
  el.textContent = st === 'SUCCESS' ? 'Ready' : st === 'BLOCKED_TRUST' ? 'Stopped' : st;
  el.className = 'v ' + (st === 'SUCCESS' ? 'good' : st === 'BLOCKED_TRUST' ? 'bad' : 'warn');
  $('kFetches').textContent = plan.entity_fetches ?? '—';
  const act = (plan.nodes || []).filter(n => n.activated);
  $('kAct').textContent = act.length;
  const trap = trapHit(plan);
  $('kTrap').textContent = trap ? 'Yes' : 'No';
  $('kTrap').className = 'v ' + (trap ? 'bad' : 'good');
  setTimeline(plan);
  drawGraph(plan);
  drawDonut(plan);
  const rows = act.length ? act : (plan.nodes || []).slice(0, 6);
  $('shortBody').innerHTML = rows.map(n => `<tr>
    <td><span class="dot ${{n.activated ? 'on' : ''}} ${{n.trust === 'red' ? 'red' : ''}} ${{/old|backup/i.test(n.name||'') ? 'trap' : ''}}"></span></td>
    <td>${{escapeHtml((n.name||'').replace(/^[^.]+\./,''))}}</td>
    <td>${{n.relevance}}</td>
    <td>${{escapeHtml(n.trust)}}</td>
  </tr>`).join('') || '<tr><td colspan="4" style="color:var(--ink-3)">Empty shortlist</td></tr>';
  updateFetchBar(plan.mode, plan.entity_fetches || 0);
}}

function updateFetchBar(mode, n) {{
  state.fetches[mode] = n;
  const vals = ['baseline','known-path','blocked'].map(m => state.fetches[m] || 0);
  const max = Math.max(8, ...vals, 1);
  const set = (id, nid, v) => {{ $(id).style.width = Math.round(100 * v / max) + '%'; $(nid).textContent = v; }};
  set('fb','fbn', state.fetches['baseline'] || 0);
  set('fk','fkn', state.fetches['known-path'] || 0);
  set('fx','fxn', state.fetches['blocked'] || 0);
}}

function drawGraph(plan) {{
  const nodes = plan.nodes || [];
  const ink = '#1f1e1c', mute = '#8a847a', clay = '#c96442', sage = '#3d6b4f', rose = '#a33b3b', line = '#e6e0d6';
  let h = `<rect width="520" height="220" rx="12" fill="#f7f4ef"/>`;
  if (!nodes.length) {{
    h += `<text x="50%" y="48%" text-anchor="middle" fill="${{mute}}" font-size="14" font-family="Instrument Serif,Georgia,serif">Hand off a task to light the map</text>`;
    h += `<text x="50%" y="58%" text-anchor="middle" fill="${{mute}}" font-size="11" font-family="Inter,sans-serif">Nodes appear as the route sheet activates</text>`;
    $('graph').innerHTML = h; return;
  }}
  const act = nodes.filter(n => n.activated);
  const rest = nodes.filter(n => !n.activated).slice(0, 5);
  const drawCol = (list, x0) => list.forEach((n, i) => {{
    const y = 42 + i * 32;
    const on = !!n.activated;
    const fill = n.trust === 'red' ? rose : (on ? sage : '#d8d2c8');
    h += `<circle cx="${{x0}}" cy="${{y}}" r="${{on ? 13 : 9}}" fill="${{fill}}" opacity="${{on ? 1 : .55}}"/>`;
    const label = (n.name || '').split('.').slice(-2).join('.');
    h += `<text x="${{x0 + 20}}" y="${{y + 4}}" fill="${{ink}}" font-size="12" font-family="Inter,sans-serif">${{escapeHtml(label)}}</text>`;
  }});
  drawCol(act.length ? act : nodes.slice(0, 4), 36);
  drawCol(rest, 280);
  h += `<circle cx="248" cy="198" r="5" fill="${{clay}}"/>`;
  h += `<text x="258" y="202" fill="${{mute}}" font-size="11" font-family="Inter,sans-serif">goal</text>`;
  (act.length ? act : []).forEach((n, i) => {{
    const y = 42 + i * 32;
    h += `<path d="M248 192 Q 140 ${{(y + 198) / 2}} 49 ${{y}}" stroke="${{clay}}" stroke-opacity=".28" fill="none" stroke-width="1.5"/>`;
  }});
  $('graph').innerHTML = h;
}}

function drawDonut(plan) {{
  const nodes = plan.nodes || [];
  const c = {{ green: 0, yellow: 0, red: 0 }};
  nodes.forEach(n => {{ c[n.trust] = (c[n.trust] || 0) + 1; }});
  const total = Math.max(1, c.green + c.yellow + c.red);
  const colors = {{ green: '#3d6b4f', yellow: '#9a7420', red: '#a33b3b' }};
  let a = -Math.PI / 2, h = '';
  ['green','yellow','red'].forEach(k => {{
    const frac = c[k] / total;
    const a2 = a + frac * Math.PI * 2;
    const x1 = 72 + 38 * Math.cos(a), y1 = 70 + 38 * Math.sin(a);
    const x2 = 72 + 38 * Math.cos(a2), y2 = 70 + 38 * Math.sin(a2);
    const large = frac > 0.5 ? 1 : 0;
    if (frac > 0) h += `<path d="M72 70 L ${{x1}} ${{y1}} A 38 38 0 ${{large}} 1 ${{x2}} ${{y2}} Z" fill="${{colors[k]}}"/>`;
    a = a2;
  }});
  h += `<circle cx="72" cy="70" r="22" fill="#fffcf7"/>`;
  h += `<text x="128" y="52" fill="#8a847a" font-size="12" font-family="Inter,sans-serif">Trusted  ${{c.green}}</text>`;
  h += `<text x="128" y="74" fill="#8a847a" font-size="12" font-family="Inter,sans-serif">Caution  ${{c.yellow}}</text>`;
  h += `<text x="128" y="96" fill="#8a847a" font-size="12" font-family="Inter,sans-serif">Blocked  ${{c.red}}</text>`;
  $('donut').innerHTML = h;
}}

function appendCli(cmd, data) {{
  let t = `$ ${{cmd || data.command || ''}}\\n`;
  if (data.duration_ms != null) t += `// ${{data.duration_ms}}ms  exit ${{data.exit_code}}\\n\\n`;
  const el = $('cliTrace');
  el.textContent = (el.textContent.startsWith('Ready') ? '' : el.textContent) + t;
  el.scrollTop = el.scrollHeight;
}}

async function runTool(mode) {{
  setBusy(true);
  const intent = $('prompt').value.trim() || BOOT.default_intent;
  addMsg('step', `<span class="badge">Working</span><div class="cmd">run --mode ${{escapeHtml(mode)}}</div>`);
  try {{
    const r = await fetch('/api/cli/run?mode=' + encodeURIComponent(mode) + '&intent=' + encodeURIComponent(intent));
    const data = await r.json();
    appendCli(data.command, data);
    if (data.plan) {{
      paintPlan(data.plan);
      addMsg('assistant', summarizePlan(data.plan));
    }}
  }} catch (e) {{ toast(String(e)); }}
  finally {{ setBusy(false); }}
}}

function summarizePlan(plan) {{
  const act = (plan.nodes || []).filter(n => n.activated).map(n => n.name).join(', ') || 'none';
  const trap = trapHit(plan) ? ' A trap asset was lit — review carefully.' : '';
  if (plan.status === 'BLOCKED_TRUST') {{
    return `<strong>Stopped on trust.</strong> ${{escapeHtml(plan.message || '')}} No replacement table was invented.`;
  }}
  return `<strong>${{plan.status === 'SUCCESS' ? 'Ready for review.' : escapeHtml(plan.status)}}</strong> Lit ${{escapeHtml(act)}}. ${{plan.entity_fetches}} catalog fetch(es).${{trap}}`;
}}

async function sendAgent() {{
  const text = $('prompt').value.trim();
  if (!text) return;
  addMsg('user', escapeHtml(text));
  $('prompt').value = '';
  setBusy(true);
  const thinking = addMsg('assistant', '<span class="loading-dots">Working</span>');
  try {{
    const r = await fetch('/api/agent/chat', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ message: text }})
    }});
    const data = await r.json();
    thinking.remove();
    (data.tool_traces || []).forEach(tr => {{
      addMsg('step', `<span class="badge">Tool</span> ${{escapeHtml(tr.tool || 'cli')}} · ${{tr.duration_ms || 0}}ms<div class="cmd">${{escapeHtml(tr.command || '')}}</div>`);
      if (tr.command) appendCli(tr.command, {{ exit_code: tr.exit_code, duration_ms: tr.duration_ms }});
    }});
    if (data.plan) paintPlan(data.plan);
    if (data.plans) data.plans.forEach(p => updateFetchBar(p.mode, p.entity_fetches || 0));
    if (data.content) addMsg('assistant', escapeHtml(data.content).replaceAll('\\n', '<br/>'));
    else if (data.error) addMsg('assistant', 'Something went wrong: ' + escapeHtml(typeof data.error === 'string' ? data.error : JSON.stringify(data.error)));
  }} catch (e) {{
    thinking.remove();
    addMsg('assistant', escapeHtml(String(e)));
  }} finally {{
    setBusy(false);
  }}
}}

function quick(t) {{ $('prompt').value = t; sendAgent(); }}

function openSettings() {{
  const s = BOOT.settings || {{}};
  $('sBase').value = (s.llm && s.llm.base_url) || '';
  $('sKey').value = '';
  $('sKey').placeholder = (s.llm && s.llm.api_key_set) ? '•••• saved' : 'API key';
  $('sGms').value = (s.datahub && s.datahub.gms_url) || '';
  $('sTok').value = '';
  $('sTok').placeholder = (s.datahub && s.datahub.token_set) ? '•••• saved' : 'PAT';
  $('sLive').checked = !!(s.datahub && s.datahub.use_live);
  const models = $('sModel'); models.innerHTML = '';
  if (s.llm && s.llm.model) {{
    const o = document.createElement('option'); o.value = s.llm.model; o.textContent = s.llm.model; models.appendChild(o);
  }}
  refreshDsSelect();
  $('settingsModal').classList.add('open');
}}
function closeSettings() {{ $('settingsModal').classList.remove('open'); }}
function refreshDsSelect() {{
  const sel = $('sDs'); sel.innerHTML = '';
  (BOOT.datasets || []).forEach(d => {{
    const o = document.createElement('option');
    o.value = d.id; o.textContent = d.id + ' · ' + d.assets + ' assets';
    if (d.id === BOOT.active) o.selected = true;
    sel.appendChild(o);
  }});
  $('dsLabel').textContent = BOOT.active || 'dataset';
}}
async function fetchModels() {{
  $('setMsg').textContent = 'Fetching…';
  await saveSettings(true);
  const r = await fetch('/api/settings/models');
  const data = await r.json();
  if (!data.ok) {{ $('setMsg').textContent = typeof data.error === 'string' ? data.error : 'Could not fetch models'; return; }}
  const sel = $('sModel'); sel.innerHTML = '';
  (data.models || []).forEach(id => {{ const o = document.createElement('option'); o.value = id; o.textContent = id; sel.appendChild(o); }});
  $('setMsg').textContent = (data.models || []).length + ' models available';
}}
async function testDh() {{
  await saveSettings(true);
  const r = await fetch('/api/settings/datahub/test');
  const data = await r.json();
  $('setMsg').textContent = data.message || JSON.stringify(data);
}}
async function saveSettings(quiet) {{
  const body = {{
    llm: {{ base_url: $('sBase').value.trim(), model: $('sModel').value }},
    datahub: {{ gms_url: $('sGms').value.trim(), use_live: $('sLive').checked }},
    dataset: {{ active: $('sDs').value }}
  }};
  if ($('sKey').value) body.llm.api_key = $('sKey').value;
  if ($('sTok').value) body.datahub.token = $('sTok').value;
  const r = await fetch('/api/settings', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(body) }});
  const data = await r.json();
  BOOT.settings = data.public || BOOT.settings;
  if (data.datasets) BOOT.datasets = data.datasets;
  if (body.dataset && body.dataset.active) BOOT.active = body.dataset.active;
  refreshDsSelect();
  if (!quiet) {{ toast('Saved'); closeSettings(); }}
  return data;
}}
async function loadDatasetPack(id) {{
  const r = await fetch('/api/datasets/active', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ id }}) }});
  const data = await r.json();
  if (data.ok) {{ BOOT.active = id; BOOT.datasets = data.datasets || BOOT.datasets; refreshDsSelect(); toast('Using ' + id); }}
  else toast(data.error || 'Failed');
}}
async function onUploadCatalog(ev) {{
  const f = ev.target.files[0]; if (!f) return;
  const text = await f.text();
  const name = prompt('Name this pack', 'upload-' + Date.now().toString(36).slice(-5));
  if (!name) return;
  const r = await fetch('/api/datasets/upload/catalog', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ name, content: text }}) }});
  const data = await r.json();
  toast(data.ok ? 'Catalog ready' : (data.error || 'Failed'));
  if (data.ok) {{ BOOT.active = name; BOOT.datasets = await (await fetch('/api/datasets')).json(); refreshDsSelect(); }}
  ev.target.value = '';
}}
async function onUploadCsv(ev) {{
  const f = ev.target.files[0]; if (!f) return;
  const text = await f.text();
  const r = await fetch('/api/datasets/upload/csv', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ dataset_id: BOOT.active || 'demo-finance', filename: f.name, content: text }}) }});
  const data = await r.json();
  toast(data.ok ? 'CSV saved' : (data.error || 'Failed'));
  ev.target.value = '';
}}

// boot
refreshDsSelect();
drawGraph({{ nodes: [] }});
drawDonut({{ nodes: [] }});
$('prompt').addEventListener('keydown', (e) => {{
  if (e.key === 'Enter' && !e.shiftKey) {{ e.preventDefault(); sendAgent(); }}
}});
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print("[web]", fmt % args)

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: object) -> None:
        self._send(code, json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8")

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def do_GET(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        path = u.path or "/"
        qs = parse_qs(u.query)

        if path in ("/", "/index.html"):
            self._send(200, _html_page().encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/api/health":
            self._json(
                200,
                {
                    "ok": True,
                    "dataset": str(dataset_dir()),
                    "active": active_dataset_id(),
                    "assets": len(demo_catalog()),
                    "bridge": "cli",
                },
            )
            return
        if path == "/api/datasets":
            self._json(200, list_datasets())
            return
        if path == "/api/settings":
            self._json(200, public_settings())
            return
        if path == "/api/settings/models":
            self._json(200, fetch_models())
            return
        if path == "/api/settings/datahub/test":
            self._json(200, test_datahub())
            return
        if path == "/api/skill":
            from pathlib import Path

            from known_path.runner import default_repo_root

            p = default_repo_root() / "skills" / "known-path" / "TOOLS.md"
            self._json(
                200,
                {"path": str(p), "content": p.read_text(encoding="utf-8") if p.exists() else ""},
            )
            return
        if path in ("/api/cli/run", "/api/run"):
            mode = (qs.get("mode") or ["known-path"])[0]
            intent = (qs.get("intent") or [DEFAULT_INTENT])[0]
            self._json(200, result_to_dict(run_mode_via_cli(mode, intent)))
            return
        if path in ("/api/cli/demo", "/api/demo"):
            intent = (qs.get("intent") or [DEFAULT_INTENT])[0]
            self._json(200, result_to_dict(run_demo_via_cli(intent=intent)))
            return
        if path == "/api/catalog":
            assets = [
                {
                    "name": a.name,
                    "urn": a.urn,
                    "certified": a.certified,
                    "deprecated": a.deprecated,
                    "quality_fail": a.quality_fail,
                    "usage_score": a.usage_score,
                }
                for a in demo_catalog()
            ]
            self._json(200, {"assets": assets, "samples": list_sample_files()})
            return
        self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path or "/"
        body = self._body()

        if path == "/api/settings":
            save_settings(body)
            if body.get("dataset", {}).get("active"):
                set_active_dataset(str(body["dataset"]["active"]))
            self._json(200, {"ok": True, "public": public_settings(), "datasets": list_datasets()})
            return
        if path == "/api/datasets/active":
            self._json(200, set_active_dataset(str(body.get("id") or "")))
            return
        if path == "/api/datasets/upload/catalog":
            self._json(
                200,
                upload_catalog_json(str(body.get("name") or ""), str(body.get("content") or "")),
            )
            return
        if path == "/api/datasets/upload/csv":
            self._json(
                200,
                upload_csv(
                    str(body.get("dataset_id") or active_dataset_id()),
                    str(body.get("filename") or "upload.csv"),
                    str(body.get("content") or ""),
                ),
            )
            return
        if path == "/api/agent/chat":
            msg = (body.get("message") or "").strip()
            s = load_settings()["llm"]
            if not s.get("model") or not s.get("base_url"):
                low = msg.lower()
                if low in ("doctor", "dataset", "demo") or low.startswith("run "):
                    r = agent_command(msg)
                elif "baseline" in low or "compare" in low:
                    r = run_mode_via_cli("baseline", msg)
                    r2 = run_mode_via_cli("known-path", DEFAULT_INTENT)
                    self._json(
                        200,
                        {
                            "ok": True,
                            "content": "Compared baseline thrash to the trusted path. Configure a model in Settings for freer chat.",
                            "tool_traces": [
                                {
                                    "tool": "run_activation",
                                    "command": r.command_display,
                                    "duration_ms": r.duration_ms,
                                    "exit_code": r.exit_code,
                                },
                                {
                                    "tool": "run_activation",
                                    "command": r2.command_display,
                                    "duration_ms": r2.duration_ms,
                                    "exit_code": r2.exit_code,
                                },
                            ],
                            "plan": r2.plan,
                            "plans": [p for p in (r.plan, r2.plan) if p],
                        },
                    )
                    return
                elif (
                    "fail closed" in low
                    or "fail-closed" in low
                    or low.startswith("blocked")
                    or "run blocked" in low
                    or "simulate red" in low
                ):
                    r = run_mode_via_cli("blocked", DEFAULT_INTENT)
                else:
                    r = run_mode_via_cli("known-path", msg or DEFAULT_INTENT)
                self._json(
                    200,
                    {
                        "ok": r.ok,
                        "content": (r.plan or {}).get("message")
                        if r.plan
                        else (r.error or r.stdout[:500] or "Done."),
                        "tool_traces": [
                            {
                                "tool": "cli",
                                "command": r.command_display,
                                "duration_ms": r.duration_ms,
                                "exit_code": r.exit_code,
                                "ok": r.ok,
                            }
                        ],
                        "plan": r.plan,
                        "plans": r.plans,
                    },
                )
                return
            self._json(200, agent_chat([{"role": "user", "content": msg}]))
            return
        if path == "/api/agent":
            cmd = (body.get("command") or "").strip()
            self._json(200, result_to_dict(agent_command(cmd)))
            return
        self._send(404, b"not found", "text/plain")


def serve(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, open_browser: bool = False) -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print(f"known-path → {url}")
    print(f"dataset → {dataset_dir()} ({active_dataset_id()})")
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

    p = argparse.ArgumentParser()
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--open", action="store_true")
    args = p.parse_args()
    serve(args.host, args.port, args.open)


if __name__ == "__main__":
    main()
