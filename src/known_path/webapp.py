"""Dashboard workbench: 1/3 agent rail + 2/3 viz. CLI-bridged tools. Stdlib only."""

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
    # Minimal bootstrap JSON for first paint (viz fills from API)
    boot = {
        "datasets": list_datasets(),
        "active": active_dataset_id(),
        "settings": public_settings(),
        "asset_count": len(demo_catalog()),
    }
    boot_js = json.dumps(boot)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>known-path · dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet"/>
<style>
:root{{
  --bg:#0a0a0a;--panel:#111;--panel2:#161616;--line:#262626;--line2:#1c1c1c;
  --text:#f3eee6;--muted:#8f8a82;--dim:#5c5852;--accent:#d4a574;--good:#6b9f7a;--bad:#c45c5c;--warn:#c9a227;
  --r:12px;--font:"IBM Plex Sans",system-ui,sans-serif;--mono:"IBM Plex Mono",ui-monospace,monospace;
  --ease:cubic-bezier(.22,1,.36,1);
}}
*{{box-sizing:border-box}}html,body{{margin:0;height:100%;background:var(--bg);color:var(--text);font-family:var(--font)}}
button,input,select,textarea{{font:inherit;color:inherit}}
button{{cursor:pointer}}button:disabled{{opacity:.55;cursor:wait}}
button:focus-visible,input:focus-visible,textarea:focus-visible,select:focus-visible{{outline:2px solid var(--accent);outline-offset:2px}}
a{{color:var(--accent);text-decoration:none}}
.app{{height:100vh;display:grid;grid-template-rows:48px 1fr}}
.top{{display:flex;align-items:center;justify-content:space-between;padding:0 1rem;border-bottom:1px solid var(--line);background:rgba(10,10,10,.92);backdrop-filter:blur(8px)}}
.brand{{display:flex;align-items:center;gap:.55rem;font-weight:600;letter-spacing:-.02em}}
.brand small{{color:var(--muted);font-weight:400}}
.top-actions{{display:flex;gap:.45rem;align-items:center}}
.icon-btn{{background:var(--panel2);border:1px solid var(--line);border-radius:999px;width:34px;height:34px;display:grid;place-items:center}}
.icon-btn:hover{{border-color:#3a3a3a}}
.shell{{display:grid;grid-template-columns:minmax(300px,1fr) minmax(0,2fr);min-height:0}}
@media(max-width:900px){{.shell{{grid-template-columns:1fr;grid-template-rows:45vh 1fr}}}}
.rail,.stage{{min-height:0;overflow:hidden;display:flex;flex-direction:column}}
.rail{{border-right:1px solid var(--line);background:var(--panel)}}
.stage{{background:var(--bg)}}
.rail-head,.stage-head{{padding:.75rem 1rem;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;gap:.5rem}}
.rail-head h1,.stage-head h2{{margin:0;font-size:.95rem;font-weight:600}}
.muted{{color:var(--muted);font-size:.8rem}}
.chat{{flex:1;overflow:auto;padding:1rem;display:flex;flex-direction:column;gap:.75rem}}
.bubble{{max-width:95%;padding:.7rem .85rem;border-radius:12px;font-size:.9rem;line-height:1.45;border:1px solid var(--line)}}
.bubble.user{{align-self:flex-end;background:#1b1916;border-color:#2e2a24}}
.bubble.assistant{{align-self:flex-start;background:var(--panel2)}}
.bubble.tool{{align-self:stretch;background:#0d0d0d;border-color:#222;font-family:var(--mono);font-size:.72rem;color:#b7d7b9;white-space:pre-wrap}}
.composer{{border-top:1px solid var(--line);padding:.75rem;display:grid;gap:.5rem;background:var(--panel)}}
.composer textarea{{width:100%;min-height:72px;resize:vertical;background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:.7rem .8rem}}
.row{{display:flex;flex-wrap:wrap;gap:.4rem}}
.btn{{background:var(--panel2);border:1px solid var(--line);border-radius:999px;padding:.45rem .85rem;font-size:.82rem}}
.btn:hover{{border-color:#3a3a3a}}
.btn.primary{{background:var(--text);color:#111;border-color:var(--text)}}
.btn.ghost{{background:transparent}}
.btn.danger{{color:#f0b4b4;border-color:rgba(196,92,92,.4)}}
.chips .btn{{font-size:.75rem;padding:.35rem .65rem}}
.stage-body{{flex:1;overflow:auto;padding:1rem;display:grid;gap:1rem;grid-template-columns:1.1fr .9fr}}
@media(max-width:1100px){{.stage-body{{grid-template-columns:1fr}}}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:1rem;min-height:0}}
.card h3{{margin:0 0 .75rem;font-size:.85rem;font-weight:600;letter-spacing:-.01em}}
.card h3 span{{color:var(--dim);font-weight:400;margin-left:.35rem}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:.5rem}}
@media(max-width:700px){{.kpis{{grid-template-columns:repeat(2,1fr)}}}}
.kpi{{background:var(--panel2);border:1px solid var(--line2);border-radius:10px;padding:.7rem}}
.kpi .k{{font-size:.68rem;text-transform:uppercase;letter-spacing:.08em;color:var(--dim)}}
.kpi .v{{font-size:1.25rem;font-weight:600;margin-top:.2rem;letter-spacing:-.02em}}
.kpi .v.good{{color:var(--good)}}.kpi .v.bad{{color:var(--bad)}}.kpi .v.warn{{color:var(--warn)}}
#graph{{width:100%;height:240px;display:block;background:#0e0e0e;border-radius:10px;border:1px solid var(--line2)}}
.bars{{display:flex;flex-direction:column;gap:.45rem}}
.bar-row{{display:grid;grid-template-columns:88px 1fr 36px;gap:.4rem;align-items:center;font-size:.78rem}}
.bar-track{{height:10px;background:#1a1a1a;border-radius:99px;overflow:hidden}}
.bar-fill{{height:100%;border-radius:99px;transition:width .45s var(--ease)}}
.bar-fill.b{{background:linear-gradient(90deg,#6a3a3a,var(--bad))}}
.bar-fill.k{{background:linear-gradient(90deg,#2f5a3c,var(--good))}}
.bar-fill.x{{background:linear-gradient(90deg,#5a4a18,var(--warn))}}
.process{{display:flex;gap:.35rem;flex-wrap:wrap;margin-bottom:.75rem}}
.step{{font-size:.72rem;padding:.3rem .55rem;border-radius:999px;border:1px solid var(--line);color:var(--muted)}}
.step.on{{border-color:rgba(212,165,116,.45);color:var(--accent);background:rgba(212,165,116,.08)}}
.step.done{{border-color:rgba(107,159,122,.4);color:var(--good)}}
.step.fail{{border-color:rgba(196,92,92,.45);color:var(--bad)}}
table.t{{width:100%;border-collapse:collapse;font-size:.78rem}}
table.t th{{text-align:left;color:var(--dim);font-weight:500;padding:.4rem;border-bottom:1px solid var(--line)}}
table.t td{{padding:.45rem .4rem;border-bottom:1px solid var(--line2)}}
.dot{{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:.35rem;background:var(--dim)}}
.dot.on{{background:var(--good)}}.dot.trap{{background:var(--bad)}}.dot.red{{background:var(--bad)}}
.modal-bg{{position:fixed;inset:0;background:rgba(0,0,0,.55);display:none;place-items:center;z-index:50;padding:1rem}}
.modal-bg.open{{display:grid}}
.modal{{width:min(520px,100%);background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:1.1rem;max-height:90vh;overflow:auto}}
.modal h2{{margin:0 0 1rem;font-size:1.05rem}}
.field{{display:grid;gap:.3rem;margin-bottom:.75rem}}
.field label{{font-size:.75rem;color:var(--muted)}}
.field input,.field select{{background:var(--panel2);border:1px solid var(--line);border-radius:8px;padding:.55rem .7rem}}
.hint{{font-size:.75rem;color:var(--dim);line-height:1.4}}
.skel{{display:none;gap:.35rem}}.skel.on{{display:flex;flex-direction:column}}
.skel i{{height:10px;border-radius:6px;background:linear-gradient(90deg,#151515,#242424,#151515);background-size:200% 100%;animation:sh 1s infinite linear}}
@keyframes sh{{to{{background-position:-200% 0}}}}
.toast{{position:fixed;bottom:1rem;right:1rem;background:#1a1a1a;border:1px solid var(--line);padding:.65rem .9rem;border-radius:10px;font-size:.82rem;display:none;z-index:60}}
.toast.on{{display:block}}
</style>
</head>
<body>
<div class="app">
  <header class="top">
    <div class="brand">
      <svg width="22" height="22" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#1a1a1a"/><path d="M18 40 L30 22 L38 34 L48 18" stroke="#f3eee6" stroke-width="5" fill="none" stroke-linecap="round"/><circle cx="48" cy="18" r="4" fill="#d4a574"/></svg>
      known-path <small>dashboard</small>
    </div>
    <div class="top-actions">
      <span class="muted" id="dsLabel">dataset: —</span>
      <button class="icon-btn" title="Settings" onclick="openSettings()" aria-label="Settings">⚙</button>
    </div>
  </header>
  <div class="shell">
    <!-- LEFT 1/3: agent -->
    <aside class="rail">
      <div class="rail-head">
        <h1>Agent</h1>
        <span class="muted">tools via CLI</span>
      </div>
      <div class="chat" id="chat">
        <div class="bubble assistant">Ask for a data job. I’ll call allow-listed tools (<code>run</code>, <code>demo</code>, <code>doctor</code>, <code>dataset</code>) through the real CLI.<br/><br/>Skill: <code>skills/known-path/TOOLS.md</code></div>
      </div>
      <div class="composer">
        <div class="row chips">
          <button class="btn" onclick="quick('Compare baseline vs known-path for revenue by region')">Compare paths</button>
          <button class="btn" onclick="quick('Run known-path for revenue by region last quarter')">Activate trusted</button>
          <button class="btn" onclick="quick('Show fail-closed when trust is red')">Fail closed</button>
          <button class="btn" onclick="quick('doctor')">Doctor</button>
        </div>
        <textarea id="prompt" placeholder="e.g. Activate trusted tables for revenue by region last quarter"></textarea>
        <div class="row">
          <button class="btn primary" id="sendBtn" onclick="sendAgent()">Send to agent</button>
          <button class="btn" onclick="runTool('known-path')">Run known-path</button>
          <button class="btn danger" onclick="runTool('blocked')">Fail closed</button>
        </div>
        <div class="skel" id="skel"><i style="width:90%"></i><i style="width:70%"></i><i style="width:40%"></i></div>
      </div>
    </aside>

    <!-- RIGHT 2/3: visualization -->
    <main class="stage">
      <div class="stage-head">
        <h2>Process &amp; signals <span class="muted" id="statusLine">idle</span></h2>
        <div class="row">
          <button class="btn" onclick="loadDatasetPack('demo-finance')">Use demo-finance</button>
          <button class="btn" onclick="document.getElementById('fileCat').click()">Upload catalog.json</button>
          <button class="btn" onclick="document.getElementById('fileCsv').click()">Upload CSV</button>
          <input type="file" id="fileCat" accept="application/json,.json" hidden onchange="onUploadCatalog(event)"/>
          <input type="file" id="fileCsv" accept=".csv,text/csv" hidden onchange="onUploadCsv(event)"/>
        </div>
      </div>
      <div class="stage-body">
        <div style="display:flex;flex-direction:column;gap:1rem;min-width:0">
          <div class="card">
            <h3>Pipeline <span>only what matters</span></h3>
            <div class="process" id="process">
              <span class="step" data-s="intent">Intent</span>
              <span class="step" data-s="route">Route sheet</span>
              <span class="step" data-s="score">Score · top-K</span>
              <span class="step" data-s="ping">Trust ping</span>
              <span class="step" data-s="fetch">Fetch shortlist</span>
              <span class="step" data-s="sql">SQL artifact</span>
              <span class="step" data-s="write">Write-back</span>
            </div>
            <div class="kpis">
              <div class="kpi"><div class="k">Status</div><div class="v" id="kStatus">—</div></div>
              <div class="kpi"><div class="k">Fetches</div><div class="v" id="kFetches">—</div></div>
              <div class="kpi"><div class="k">Activated</div><div class="v" id="kAct">—</div></div>
              <div class="kpi"><div class="k">Trap hit</div><div class="v" id="kTrap">—</div></div>
            </div>
          </div>
          <div class="card">
            <h3>Activation map <span>nodes lit · not raw dumps</span></h3>
            <svg id="graph" viewBox="0 0 520 240" role="img" aria-label="activation graph"></svg>
          </div>
          <div class="card">
            <h3>Fetch cost <span>shared axis</span></h3>
            <div class="bars" id="fetchBars">
              <div class="bar-row"><span>baseline</span><div class="bar-track"><div class="bar-fill b" id="fb" style="width:0%"></div></div><span id="fbn">0</span></div>
              <div class="bar-row"><span>known-path</span><div class="bar-track"><div class="bar-fill k" id="fk" style="width:0%"></div></div><span id="fkn">0</span></div>
              <div class="bar-row"><span>blocked</span><div class="bar-track"><div class="bar-fill x" id="fx" style="width:0%"></div></div><span id="fxn">0</span></div>
            </div>
          </div>
        </div>
        <div style="display:flex;flex-direction:column;gap:1rem;min-width:0">
          <div class="card">
            <h3>Trust mix <span>last run</span></h3>
            <svg id="donut" viewBox="0 0 200 140" style="width:100%;height:140px"></svg>
          </div>
          <div class="card" style="flex:1">
            <h3>Shortlist table <span>activated only</span></h3>
            <table class="t"><thead><tr><th></th><th>Asset</th><th>Rel</th><th>Trust</th></tr></thead><tbody id="shortBody"><tr><td colspan="4" class="muted">Run a job to populate</td></tr></tbody></table>
          </div>
          <div class="card">
            <h3>CLI trace <span>web → agent tools → CLI</span></h3>
            <pre id="cliTrace" style="margin:0;max-height:160px;overflow:auto;font-family:var(--mono);font-size:.72rem;color:#b7d7b9;white-space:pre-wrap">$ idle</pre>
          </div>
        </div>
      </div>
    </main>
  </div>
</div>

<div class="modal-bg" id="settingsModal">
  <div class="modal">
    <h2>Settings</h2>
    <div class="field"><label>LLM base URL (OpenAI-compatible)</label><input id="sBase" placeholder="https://api.openai.com/v1"/></div>
    <div class="field"><label>API key</label><input id="sKey" type="password" placeholder="sk-… (stored locally only)"/></div>
    <div class="row" style="margin-bottom:.75rem">
      <button class="btn" onclick="fetchModels()">Fetch /v1/models</button>
      <select id="sModel" style="flex:1;background:var(--panel2);border:1px solid var(--line);border-radius:8px;padding:.45rem"></select>
    </div>
    <hr style="border:0;border-top:1px solid var(--line);margin:1rem 0"/>
    <div class="field"><label>DataHub GMS URL</label><input id="sGms" placeholder="http://localhost:8080"/></div>
    <div class="field"><label>DataHub Personal Access Token</label><input id="sTok" type="password" placeholder="PAT Bearer token"/></div>
    <p class="hint">Programmatic access uses <b>PAT</b> (<code>Authorization: Bearer</code>). Browser OAuth is for interactive UIs (Claude/Cursor MCP). Create tokens in DataHub → Settings → Access Tokens.</p>
    <div class="row" style="margin:.75rem 0">
      <label class="muted" style="display:flex;gap:.4rem;align-items:center"><input type="checkbox" id="sLive"/> Use live DataHub</label>
      <button class="btn" onclick="testDh()">Test connection</button>
    </div>
    <div class="field"><label>Active dataset pack</label><select id="sDs"></select></div>
    <div class="row" style="justify-content:flex-end;margin-top:1rem">
      <button class="btn ghost" onclick="closeSettings()">Cancel</button>
      <button class="btn primary" onclick="saveSettings()">Save</button>
    </div>
    <p class="hint" id="setMsg"></p>
  </div>
</div>
<div class="toast" id="toast"></div>

<script>
const BOOT = {boot_js};
const state = {{ fetches: {{}}, lastPlan: null }};

function $(id){{return document.getElementById(id)}}
function toast(m){{const t=$('toast');t.textContent=m;t.classList.add('on');setTimeout(()=>t.classList.remove('on'),2800)}}
function setBusy(on){{$('sendBtn').disabled=on;$('skel').classList.toggle('on',on)}}
function addBubble(role, html){{
  const d=document.createElement('div');
  d.className='bubble '+role;
  d.innerHTML=html;
  $('chat').appendChild(d);
  $('chat').scrollTop=$('chat').scrollHeight;
}}
function escapeHtml(s){{return String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')}}

function trapHit(plan){{
  return (plan.nodes||[]).some(n=>n.activated && /old|backup|tmp/i.test(n.name||''));
}}

function setProcess(plan){{
  const steps=['intent','route','score','ping','fetch','sql','write'];
  const st=plan.status;
  document.querySelectorAll('.step').forEach(el=>{{el.className='step'}});
  const mark=(name,cls)=>{{const el=document.querySelector('.step[data-s="'+name+'"]');if(el)el.classList.add(cls||'on')}};
  mark('intent','done'); mark('route','done'); mark('score','done');
  if(st==='BLOCKED_TRUST'){{ mark('ping','fail'); return; }}
  mark('ping','done'); mark('fetch','done');
  if(plan.sql_artifact) mark('sql','done');
  if(plan.write_back_note) mark('write','done');
}}

function paintPlan(plan){{
  if(!plan) return;
  state.lastPlan=plan;
  const st=plan.status||'—';
  const el=$('kStatus'); el.textContent=st;
  el.className='v '+(st==='SUCCESS'?'good':st==='BLOCKED_TRUST'?'bad':'warn');
  $('kFetches').textContent=plan.entity_fetches??'—';
  const act=(plan.nodes||[]).filter(n=>n.activated);
  $('kAct').textContent=act.length;
  const trap=trapHit(plan);
  $('kTrap').textContent=trap?'yes':'no';
  $('kTrap').className='v '+(trap?'bad':'good');
  setProcess(plan);
  drawGraph(plan);
  drawDonut(plan);
  const tb=$('shortBody');
  const rows=act.length?act: (plan.nodes||[]).slice(0,6);
  tb.innerHTML=rows.map(n=>`<tr>
    <td><span class="dot ${{n.activated?'on':''}} ${{n.trust==='red'?'red':''}} ${{/old|backup/i.test(n.name||'')?'trap':''}}"></span></td>
    <td><code>${{escapeHtml(n.name)}}</code></td>
    <td>${{n.relevance}}</td>
    <td>${{escapeHtml(n.trust)}}</td>
  </tr>`).join('') || '<tr><td colspan="4" class="muted">empty</td></tr>';
  updateFetchBar(plan.mode, plan.entity_fetches||0);
  $('statusLine').textContent=(plan.mode||'')+' · '+(plan.status||'');
}}

function updateFetchBar(mode, n){{
  state.fetches[mode]=n;
  const vals=['baseline','known-path','blocked'].map(m=>state.fetches[m]||0);
  const max=Math.max(8, ...vals, 1);
  const set=(id,nid,v)=>{{$(id).style.width=Math.round(100*v/max)+'%'; $(nid).textContent=v;}};
  set('fb','fbn', state.fetches['baseline']||0);
  set('fk','fkn', state.fetches['known-path']||0);
  set('fx','fxn', state.fetches['blocked']||0);
}}

function drawGraph(plan){{
  const nodes=plan.nodes||[];
  let h=`<rect width="520" height="240" fill="#0e0e0e"/>`;
  h+=`<text x="12" y="18" fill="#5c5852" font-size="11" font-family="IBM Plex Sans,sans-serif">activation · top-K shortlist</text>`;
  if(!nodes.length){{$('graph').innerHTML=h+`<text x="50%" y="50%" text-anchor="middle" fill="#5c5852" font-size="13">waiting for a run</text>`;return;}}
  const act=nodes.filter(n=>n.activated);
  const rest=nodes.filter(n=>!n.activated).slice(0,6);
  const col=(list,x)=>list.forEach((n,i)=>{{
    const y=48+i*28;
    const on=!!n.activated;
    const fill=n.trust==='red'?'#c45c5c':(on?'#6b9f7a':'#2a2a2a');
    h+=`<circle cx="${{x}}" cy="${{y}}" r="${{on?14:10}}" fill="${{fill}}" opacity="${{on?1:.5}}"/>`;
    h+=`<text x="${{x+22}}" y="${{y+4}}" fill="#cfc9bc" font-size="11" font-family="IBM Plex Mono,monospace">${{escapeHtml((n.name||'').split('.').slice(-2).join('.'))}}</text>`;
  }});
  col(act.length?act:nodes.slice(0,5), 40);
  col(rest, 280);
  h+=`<circle cx="250" cy="210" r="5" fill="#d4a574"/><text x="260" y="214" fill="#8f8a82" font-size="10">intent</text>`;
  (act.length?act:[]).forEach((n,i)=>{{
    const y=48+i*28;
    h+=`<path d="M250 205 Q 140 ${{(y+210)/2}} 54 ${{y}}" stroke="#d4a57444" fill="none"/>`;
  }});
  $('graph').innerHTML=h;
}}

function drawDonut(plan){{
  const nodes=plan.nodes||[];
  const c={{green:0,yellow:0,red:0}};
  nodes.forEach(n=>{{c[n.trust]=(c[n.trust]||0)+1}});
  const total=Math.max(1, c.green+c.yellow+c.red);
  const colors={{green:'#6b9f7a',yellow:'#c9a227',red:'#c45c5c'}};
  let a=-Math.PI/2, h='';
  ['green','yellow','red'].forEach(k=>{{
    const frac=c[k]/total;
    const a2=a+frac*Math.PI*2;
    const x1=100+40*Math.cos(a), y1=70+40*Math.sin(a);
    const x2=100+40*Math.cos(a2), y2=70+40*Math.sin(a2);
    const large=frac>0.5?1:0;
    if(frac>0) h+=`<path d="M100 70 L ${{x1}} ${{y1}} A 40 40 0 ${{large}} 1 ${{x2}} ${{y2}} Z" fill="${{colors[k]}}" opacity=".9"/>`;
    a=a2;
  }});
  h+=`<circle cx="100" cy="70" r="22" fill="#111"/>`;
  h+=`<text x="150" y="50" fill="#8f8a82" font-size="11">green ${{c.green}}</text>`;
  h+=`<text x="150" y="70" fill="#8f8a82" font-size="11">yellow ${{c.yellow}}</text>`;
  h+=`<text x="150" y="90" fill="#8f8a82" font-size="11">red ${{c.red}}</text>`;
  $('donut').innerHTML=h;
}}

function appendCli(cmd, data){{
  let t=`$ ${{cmd||data.command||''}}\\n`;
  if(data.stdout) t+=data.stdout.slice(0,4000)+(data.stdout.length>4000?'\\n…':'')+'\\n';
  if(data.stderr) t+=data.stderr.slice(0,800)+'\\n';
  t+=`[exit ${{data.exit_code}} · ${{data.duration_ms}}ms]\\n\\n`;
  const el=$('cliTrace'); el.textContent+=t; el.scrollTop=el.scrollHeight;
}}

async function runTool(mode){{
  setBusy(true);
  const intent=$('prompt').value.trim()||'{_esc(DEFAULT_INTENT)}';
  try{{
    const r=await fetch('/api/cli/run?mode='+encodeURIComponent(mode)+'&intent='+encodeURIComponent(intent));
    const data=await r.json();
    appendCli(data.command, data);
    if(data.plan) paintPlan(data.plan);
    addBubble('tool', escapeHtml(JSON.stringify({{mode, status:data.plan&&data.plan.status, fetches:data.plan&&data.plan.entity_fetches}},null,0)));
  }}catch(e){{toast(String(e))}}
  finally{{setBusy(false)}}
}}

async function sendAgent(){{
  const text=$('prompt').value.trim();
  if(!text) return;
  addBubble('user', escapeHtml(text));
  $('prompt').value='';
  setBusy(true);
  try{{
    const r=await fetch('/api/agent/chat',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{message:text}})}});
    const data=await r.json();
    (data.tool_traces||[]).forEach(tr=>{{
      addBubble('tool', escapeHtml((tr.command||tr.tool)+' · '+(tr.duration_ms||0)+'ms · exit '+(tr.exit_code??'—')));
      if(tr.command) appendCli(tr.command, {{stdout:'',stderr:'',exit_code:tr.exit_code,duration_ms:tr.duration_ms}});
    }});
    if(data.plan) paintPlan(data.plan);
    if(data.plans) data.plans.forEach(p=>updateFetchBar(p.mode, p.entity_fetches||0));
    if(data.content) addBubble('assistant', escapeHtml(data.content).replaceAll('\\n','<br/>'));
    else if(data.error) addBubble('assistant', 'Error: '+escapeHtml(typeof data.error==='string'?data.error:JSON.stringify(data.error)));
    // fallback: if no LLM configured, tools may still have run via simple path
  }}catch(e){{addBubble('assistant', escapeHtml(String(e)))}}
  finally{{setBusy(false)}}
}}

function quick(t){{$('prompt').value=t; sendAgent();}}

function openSettings(){{
  const s=BOOT.settings||{{}};
  $('sBase').value=(s.llm&&s.llm.base_url)||'';
  $('sKey').value='';
  $('sKey').placeholder=(s.llm&&s.llm.api_key_set)?'•••• saved — paste to replace':'sk-…';
  $('sGms').value=(s.datahub&&s.datahub.gms_url)||'';
  $('sTok').value='';
  $('sTok').placeholder=(s.datahub&&s.datahub.token_set)?'•••• saved — paste to replace':'PAT';
  $('sLive').checked=!!(s.datahub&&s.datahub.use_live);
  const models=$('sModel'); models.innerHTML='';
  if(s.llm&&s.llm.model){{const o=document.createElement('option');o.value=s.llm.model;o.textContent=s.llm.model;models.appendChild(o)}}
  refreshDsSelect();
  $('settingsModal').classList.add('open');
}}
function closeSettings(){{$('settingsModal').classList.remove('open')}}
function refreshDsSelect(){{
  const sel=$('sDs'); sel.innerHTML='';
  (BOOT.datasets||[]).forEach(d=>{{
    const o=document.createElement('option'); o.value=d.id; o.textContent=`${{d.id}} (${{d.assets}} assets)`;
    if(d.id===BOOT.active) o.selected=true;
    sel.appendChild(o);
  }});
  $('dsLabel').textContent='dataset: '+(BOOT.active||'—');
}}
async function fetchModels(){{
  $('setMsg').textContent='Fetching models…';
  // save base/key first lightly
  await saveSettings(true);
  const r=await fetch('/api/settings/models');
  const data=await r.json();
  if(!data.ok){{$('setMsg').textContent=typeof data.error==='string'?data.error:JSON.stringify(data.error);return}}
  const sel=$('sModel'); sel.innerHTML='';
  (data.models||[]).forEach(id=>{{const o=document.createElement('option');o.value=id;o.textContent=id;sel.appendChild(o)}});
  $('setMsg').textContent=(data.models||[]).length+' models';
}}
async function testDh(){{
  await saveSettings(true);
  const r=await fetch('/api/settings/datahub/test');
  const data=await r.json();
  $('setMsg').textContent=data.message||JSON.stringify(data);
}}
async function saveSettings(quiet){{
  const body={{
    llm:{{
      base_url:$('sBase').value.trim(),
      model:$('sModel').value,
    }},
    datahub:{{
      gms_url:$('sGms').value.trim(),
      use_live:$('sLive').checked,
    }},
    dataset:{{active:$('sDs').value}}
  }};
  if($('sKey').value) body.llm.api_key=$('sKey').value;
  if($('sTok').value) body.datahub.token=$('sTok').value;
  const r=await fetch('/api/settings',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});
  const data=await r.json();
  BOOT.settings=data.public||BOOT.settings;
  if(data.datasets) BOOT.datasets=data.datasets;
  if(body.dataset&&body.dataset.active) BOOT.active=body.dataset.active;
  refreshDsSelect();
  if(!quiet){{toast('Settings saved'); closeSettings();}}
  return data;
}}
async function loadDatasetPack(id){{
  const r=await fetch('/api/datasets/active',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{id}})}});
  const data=await r.json();
  if(data.ok){{BOOT.active=id;BOOT.datasets=data.datasets||BOOT.datasets;refreshDsSelect();toast('Active dataset: '+id)}}
  else toast(data.error||'failed');
}}
async function onUploadCatalog(ev){{
  const f=ev.target.files[0]; if(!f) return;
  const text=await f.text();
  const name=prompt('Dataset pack id','upload-'+Date.now().toString(36).slice(-5));
  if(!name) return;
  const r=await fetch('/api/datasets/upload/catalog',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{name, content:text}})}});
  const data=await r.json();
  toast(data.ok?('Uploaded '+name): (data.error||'fail'));
  if(data.ok){{BOOT.active=name; const lr=await fetch('/api/datasets'); BOOT.datasets=await lr.json(); refreshDsSelect();}}
  ev.target.value='';
}}
async function onUploadCsv(ev){{
  const f=ev.target.files[0]; if(!f) return;
  const text=await f.text();
  const r=await fetch('/api/datasets/upload/csv',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{dataset_id:BOOT.active||'demo-finance', filename:f.name, content:text}})}});
  const data=await r.json();
  toast(data.ok?('CSV saved '+data.path):(data.error||'fail'));
  ev.target.value='';
}}

// boot
refreshDsSelect();
drawGraph({{nodes:[]}});
drawDonut({{nodes:[]}});
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
            self._json(200, {"path": str(p), "content": p.read_text(encoding="utf-8") if p.exists() else ""})
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
            saved = save_settings(body)
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
            # If LLM not configured, fall back to heuristic CLI routing (still tools)
            s = load_settings()["llm"]
            if not s.get("model") or not s.get("base_url"):
                # simple router without LLM
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
                            "content": "LLM not configured — ran baseline + known-path via CLI. Open Settings to add endpoint/model.",
                            "tool_traces": [
                                {"tool": "run_activation", "command": r.command_display, "duration_ms": r.duration_ms, "exit_code": r.exit_code},
                                {"tool": "run_activation", "command": r2.command_display, "duration_ms": r2.duration_ms, "exit_code": r2.exit_code},
                            ],
                            "plan": r2.plan,
                            "plans": [r.plan, r2.plan] if r.plan and r2.plan else None,
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
                        else (r.error or r.stdout[:500] or "done"),
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
            result = agent_chat([{"role": "user", "content": msg}])
            self._json(200, result)
            return
        if path == "/api/agent":
            # raw CLI agent command
            cmd = (body.get("command") or "").strip()
            self._json(200, result_to_dict(agent_command(cmd)))
            return
        self._send(404, b"not found", "text/plain")


def serve(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, open_browser: bool = False) -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print(f"known-path dashboard → {url}")
    print(f"dataset → {dataset_dir()} ({active_dataset_id()})")
    print("layout → 1/3 agent | 2/3 process viz | settings → LLM + DataHub PAT")
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
