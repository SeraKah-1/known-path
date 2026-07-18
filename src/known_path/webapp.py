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

/* Shell: 2/3 JIT work (left) + 1/3 task/agent (right) */
.shell {{
  display: grid;
  grid-template-columns: minmax(0, 66%) minmax(300px, 34%);
  min-height: 0;
}}
@media (max-width: 900px) {{
  .shell {{ grid-template-columns: 1fr; grid-template-rows: 52vh 1fr; }}
}}

.work {{
  display: flex; flex-direction: column; min-height: 0;
  background: var(--paper);
  border-right: 1px solid var(--line);
  order: 1;
}}
.task {{
  display: flex; flex-direction: column; min-height: 0;
  background: var(--surface);
  order: 2;
}}
@media (max-width: 900px) {{
  .work {{ order: 1; border-right: 0; border-bottom: 1px solid var(--line); }}
  .task {{ order: 2; }}
}}

/* Just-in-time live feed */
.jit-now {{
  display: flex; align-items: flex-start; gap: .85rem;
  padding: 1rem 1.15rem;
  background: linear-gradient(135deg, var(--clay-soft), var(--surface));
  border: 1px solid #e8cfc2;
  border-radius: var(--r);
  margin-bottom: .25rem;
}}
.jit-pulse {{
  width: 12px; height: 12px; border-radius: 50%; background: var(--clay);
  margin-top: .35rem; flex-shrink: 0;
  box-shadow: 0 0 0 0 rgba(201,100,66,.45);
  animation: pulse 1.6s ease-out infinite;
}}
.jit-pulse.idle {{ background: var(--line-2); box-shadow: none; animation: none; }}
.jit-pulse.ok {{ background: var(--sage); animation: none; }}
.jit-pulse.fail {{ background: var(--rose); animation: none; }}
@keyframes pulse {{
  0% {{ box-shadow: 0 0 0 0 rgba(201,100,66,.45); }}
  70% {{ box-shadow: 0 0 0 12px rgba(201,100,66,0); }}
  100% {{ box-shadow: 0 0 0 0 rgba(201,100,66,0); }}
}}
.jit-now .label {{ font-size: .7rem; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: var(--clay-deep); }}
.jit-now .title {{ font-family: var(--serif); font-size: 1.35rem; color: var(--ink); margin: .15rem 0; letter-spacing: -.02em; }}
.jit-now .detail {{ font-size: .85rem; color: var(--ink-2); line-height: 1.45; }}
.jit-feed {{
  display: flex; flex-direction: column; gap: .45rem;
  max-height: 200px; overflow: auto;
}}
.jit-event {{
  display: grid; grid-template-columns: 64px 1fr; gap: .5rem;
  padding: .5rem .65rem; border-radius: 10px;
  background: var(--surface); border: 1px solid var(--line);
  font-size: .78rem; animation: rise .3s var(--ease) both;
}}
.jit-event .t {{ color: var(--ink-3); font-variant-numeric: tabular-nums; }}
.jit-event .b {{ color: var(--ink-2); word-break: break-word; }}
.jit-event .b strong {{ color: var(--ink); font-weight: 600; }}
.node-cards {{
  display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: .55rem;
}}
.node-card {{
  background: var(--paper); border: 1px solid var(--line); border-radius: 12px;
  padding: .7rem .8rem; min-width: 0;
}}
.node-card.on {{ border-color: #b7d4c0; background: var(--sage-soft); }}
.node-card.off {{ opacity: .55; }}
.node-card.red {{ border-color: #e0b4b0; background: var(--rose-soft); }}
.node-card .nn {{ font-weight: 600; font-size: .85rem; color: var(--ink); word-break: break-word; }}
.node-card .nm {{ font-size: .72rem; color: var(--ink-3); margin-top: .2rem; }}
.node-card .meta {{
  display: flex; flex-wrap: wrap; gap: .3rem; margin-top: .45rem;
}}
.node-card .tag {{
  font-size: .65rem; font-weight: 600; text-transform: uppercase; letter-spacing: .04em;
  padding: .15rem .4rem; border-radius: 999px; background: var(--surface); border: 1px solid var(--line); color: var(--ink-2);
}}
.node-card .tag.hot {{ background: var(--clay-soft); border-color: #e8cfc2; color: var(--clay-deep); }}
.data-snip {{
  margin-top: .45rem; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: .68rem; color: var(--ink-3); background: var(--surface);
  border-radius: 8px; padding: .4rem .5rem; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; max-width: 100%;
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

/* Markdown / LaTeX inside chat frame — prevent layout break */
.msg.assistant .md {{
  max-width: 100%; overflow-wrap: anywhere; word-break: break-word;
  font-size: .92rem; line-height: 1.55; color: var(--ink-2);
}}
.msg.assistant .md > :first-child {{ margin-top: 0; }}
.msg.assistant .md > :last-child {{ margin-bottom: 0; }}
.msg.assistant .md h1, .msg.assistant .md h2, .msg.assistant .md h3 {{
  font-family: var(--serif); font-weight: 400; color: var(--ink);
  margin: .9rem 0 .4rem; letter-spacing: -.02em; line-height: 1.2;
}}
.msg.assistant .md h1 {{ font-size: 1.25rem; }}
.msg.assistant .md h2 {{ font-size: 1.12rem; }}
.msg.assistant .md h3 {{ font-size: 1.02rem; }}
.msg.assistant .md p {{ margin: .45rem 0; }}
.msg.assistant .md ul, .msg.assistant .md ol {{ margin: .4rem 0 .5rem; padding-left: 1.2rem; }}
.msg.assistant .md li {{ margin: .2rem 0; }}
.msg.assistant .md code {{
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: .82em; background: var(--paper-2); border: 1px solid var(--line);
  border-radius: 6px; padding: .1rem .35rem;
}}
.msg.assistant .md pre {{
  margin: .55rem 0; padding: .75rem .85rem; overflow-x: auto; max-width: 100%;
  background: #1f1e1c; color: #f3eee6; border-radius: 12px; font-size: .78rem; line-height: 1.45;
}}
.msg.assistant .md pre code {{ background: none; border: 0; padding: 0; color: inherit; font-size: inherit; }}
.msg.assistant .md table {{
  display: block; width: 100%; max-width: 100%; overflow-x: auto;
  border-collapse: collapse; margin: .55rem 0; font-size: .8rem;
}}
.msg.assistant .md th, .msg.assistant .md td {{
  border: 1px solid var(--line); padding: .4rem .55rem; text-align: left; vertical-align: top;
  white-space: nowrap;
}}
.msg.assistant .md th {{ background: var(--paper-2); color: var(--ink); font-weight: 600; }}
.msg.assistant .md blockquote {{
  margin: .5rem 0; padding: .35rem .75rem; border-left: 3px solid var(--clay);
  color: var(--ink-3); background: var(--paper-2); border-radius: 0 8px 8px 0;
}}
.msg.assistant .md .katex-display {{
  margin: .6rem 0; overflow-x: auto; overflow-y: hidden; max-width: 100%;
}}
.msg.assistant .md img {{ max-width: 100%; height: auto; border-radius: 10px; }}
.msg.assistant .md hr {{ border: 0; border-top: 1px solid var(--line); margin: .8rem 0; }}

.think {{
  align-self: stretch; background: var(--paper-2); border: 1px solid var(--line);
  border-radius: 14px; overflow: hidden; font-size: .82rem;
}}
.think summary {{
  cursor: pointer; list-style: none; padding: .65rem .85rem; font-weight: 600; color: var(--ink-2);
  display: flex; align-items: center; gap: .45rem; user-select: none;
}}
.think summary::-webkit-details-marker {{ display: none; }}
.think[open] summary {{ border-bottom: 1px solid var(--line); }}
.think-body {{ padding: .55rem .85rem .75rem; display: flex; flex-direction: column; gap: .45rem; max-height: 280px; overflow: auto; }}
.think-row {{
  display: grid; grid-template-columns: 16px 1fr; gap: .5rem; align-items: start;
  padding: .4rem .5rem; border-radius: 10px; background: var(--surface); border: 1px solid var(--line);
}}
.think-row .ph {{
  width: 10px; height: 10px; border-radius: 50%; margin-top: .3rem;
  background: var(--line-2);
}}
.think-row.reason .ph {{ background: var(--amber); }}
.think-row.tool .ph {{ background: var(--clay); }}
.think-row.done .ph {{ background: var(--sage); }}
.think-row.error .ph {{ background: var(--rose); }}
.think-row .tt {{ font-weight: 600; color: var(--ink); font-size: .8rem; }}
.think-row .td {{ color: var(--ink-3); font-size: .75rem; margin-top: .15rem; white-space: pre-wrap; word-break: break-word; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}

.quick-grid {{
  display: grid; grid-template-columns: 1fr 1fr; gap: .4rem; margin: 0 1.25rem .65rem;
}}
@media (max-width: 520px) {{ .quick-grid {{ grid-template-columns: 1fr; }} }}
.qbtn {{
  text-align: left; padding: .65rem .75rem; border-radius: 12px;
  border: 1px solid var(--line); background: var(--paper);
  transition: border-color .15s, background .15s, transform .15s var(--ease);
}}
.qbtn:hover {{ border-color: #e0c4b6; background: var(--clay-soft); transform: translateY(-1px); }}
.qbtn .qt {{ font-size: .8rem; font-weight: 600; color: var(--ink); display: block; }}
.qbtn .qd {{ font-size: .7rem; color: var(--ink-3); margin-top: .15rem; line-height: 1.3; }}

.mode-switch {{
  display: flex; gap: .25rem; margin: 0 1.25rem .55rem; padding: .25rem;
  background: var(--paper-2); border-radius: 999px; border: 1px solid var(--line);
}}
.mode-switch button {{
  flex: 1; border-radius: 999px; padding: .4rem .5rem; font-size: .75rem; font-weight: 600;
  color: var(--ink-3); border: 0; background: transparent;
}}
.mode-switch button.on {{ background: var(--surface); color: var(--ink); box-shadow: var(--shadow); }}
.term-pad {{ display: none; flex: 1; flex-direction: column; min-height: 0; padding: 0 1rem 1rem; gap: .55rem; }}
.term-pad.on {{ display: flex; }}
.task.ai-on .chat, .task.ai-on .composer, .task.ai-on .quick-grid {{ display: flex; }}
.task.ai-on .quick-grid {{ display: grid; }}
.task.term-on .chat, .task.term-on .composer, .task.term-on .quick-grid {{ display: none !important; }}
.task.term-on .term-pad {{ display: flex; }}
.term-shell {{
  flex: 1; min-height: 200px; display: flex; flex-direction: column;
  background: #1c1b19; color: #e8e2d6; border-radius: 14px; border: 1px solid #2e2c28; overflow: hidden;
}}
.term-shell pre {{
  flex: 1; margin: 0; padding: .75rem .85rem; overflow: auto;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .72rem; line-height: 1.45;
  white-space: pre-wrap; word-break: break-word;
}}
.term-shell form {{
  display: flex; gap: .4rem; padding: .5rem .6rem; border-top: 1px solid #2e2c28; background: #141311;
}}
.term-shell input {{
  flex: 1; background: transparent; border: 0; color: #f3eee6;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .8rem;
}}
.term-shell input:focus {{ outline: none; }}
.ds-bar {{
  display: flex; flex-wrap: wrap; gap: .4rem; align-items: center;
  margin: 0 1.25rem .5rem; padding: .55rem .65rem;
  background: var(--paper); border: 1px solid var(--line); border-radius: 12px;
}}
.ds-bar select {{
  flex: 1; min-width: 120px; background: var(--surface); border: 1px solid var(--line);
  border-radius: 8px; padding: .35rem .5rem; font-size: .8rem;
}}
.ds-bar .btn {{ font-size: .72rem; padding: .35rem .6rem; }}
.key-status {{
  font-size: .72rem; color: var(--sage); font-weight: 600; white-space: nowrap;
}}
.key-status.off {{ color: var(--rose); }}
.cfg-pill {{
  font-size: .72rem; color: var(--ink-3); background: var(--paper-2);
  border: 1px solid var(--line); border-radius: 999px; padding: .2rem .55rem;
  max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}}
.cfg-pill.ok {{ color: var(--sage); border-color: #c5ddc9; background: var(--sage-soft); }}
.cfg-pill.bad {{ color: var(--rose); border-color: #e8c5c0; background: var(--rose-soft); }}
.field.secret-locked input:disabled {{
  opacity: .65; background: var(--paper-2);
}}
.secret-row {{
  display: flex; gap: .5rem; align-items: center; flex-wrap: wrap;
  margin: -.25rem 0 .65rem; font-size: .78rem; color: var(--ink-3);
}}
.secret-row label {{ display: flex; gap: .35rem; align-items: center; cursor: pointer; }}
.secret-row .hint-saved {{
  color: var(--sage); font-weight: 600;
}}
.toggle-row {{
  display: flex; flex-direction: column; gap: .4rem;
  margin: 0 0 .85rem; padding: .65rem .75rem;
  background: var(--paper); border: 1px solid var(--line); border-radius: 12px;
}}
.toggle-row label {{
  display: flex; gap: .45rem; align-items: center;
  font-size: .82rem; color: var(--ink-2); cursor: pointer;
}}
.msg.think {{ align-self: stretch; max-width: 100%; }}
.msg.think .think {{ margin: 0; }}
</style>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css"/>
<script defer src="https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/dompurify@3.1.6/dist/purify.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"></script>
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
      <span class="cfg-pill" id="cfgModel" title="Active model">model · —</span>
      <span class="cfg-pill" id="cfgKey" title="API key status on server">key · —</span>
      <span class="pill" id="dsLabel">demo-finance</span>
      <button class="icon-btn" onclick="openSettings()" title="Settings" aria-label="Settings">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
          <circle cx="12" cy="12" r="3"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>
        </svg>
      </button>
    </div>
  </header>

  <div class="shell">
    <!-- LEFT 2/3: Just-in-time process view -->
    <section class="work">
      <div class="work-head">
        <div>
          <h2>Just in time</h2>
          <p>What is happening right now — active nodes, trust, and data in use. Not a dump of the whole catalog.</p>
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

      <div class="work-body" style="grid-template-columns:1fr 1fr">
        <div style="display:flex;flex-direction:column;gap:1rem;min-width:0">
          <div class="jit-now" id="jitNow">
            <div class="jit-pulse idle" id="jitPulse"></div>
            <div>
              <div class="label">Now</div>
              <div class="title" id="jitTitle">Waiting for a task</div>
              <div class="detail" id="jitDetail">Start from the panel on the right. This area updates live as tools run.</div>
            </div>
          </div>

          <div class="card">
            <h3>Live feed</h3>
            <div class="jit-feed" id="jitFeed">
              <div class="jit-event"><span class="t">—</span><span class="b">Idle · no steps yet</span></div>
            </div>
          </div>

          <div class="card">
            <h3>Nodes in play <span style="font-weight:400;text-transform:none;letter-spacing:0;color:var(--ink-3)">what is used right now</span></h3>
            <div class="node-cards" id="nodeCards">
              <div class="node-card off"><div class="nn">No nodes yet</div><div class="nm">Run a path to see assets light up</div></div>
            </div>
          </div>

          <div class="card">
            <h3>Activation map</h3>
            <svg id="graph" viewBox="0 0 520 220" role="img" aria-label="Activation map"></svg>
          </div>
        </div>

        <div style="display:flex;flex-direction:column;gap:1rem;min-width:0">
          <div class="card">
            <h3>Pipeline steps</h3>
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
            <h3>Fetch cost</h3>
            <div class="bars">
              <div class="bar-row"><span>Baseline</span><div class="bar-track"><div class="bar-fill b" id="fb"></div></div><span class="bar-n" id="fbn">0</span></div>
              <div class="bar-row"><span>Known path</span><div class="bar-track"><div class="bar-fill k" id="fk"></div></div><span class="bar-n" id="fkn">0</span></div>
              <div class="bar-row"><span>Blocked</span><div class="bar-track"><div class="bar-fill x" id="fx"></div></div><span class="bar-n" id="fxn">0</span></div>
            </div>
          </div>
          <div class="card">
            <h3>Trust mix</h3>
            <svg id="donut" viewBox="0 0 200 140"></svg>
          </div>
          <div class="card">
            <h3>CLI</h3>
            <pre class="trace" id="cliTrace">Ready — actions shell into known-path CLI.</pre>
          </div>
        </div>
      </div>
    </section>

    <!-- RIGHT 1/3: Task / agent input OR terminal-only -->
    <section class="task ai-on" id="taskPane">
      <div class="section-label">Task</div>
      <div class="mode-switch">
        <button type="button" class="on" id="modeAi" onclick="setUiMode('ai')">AI agent</button>
        <button type="button" id="modeTerm" onclick="setUiMode('terminal')">Terminal only</button>
      </div>
      <div class="ds-bar">
        <select id="dsSelectMain" onchange="switchDataset(this.value)" title="Active dataset"></select>
        <button type="button" class="btn" onclick="document.getElementById('fileCat').click()">+ catalog</button>
        <button type="button" class="btn" onclick="document.getElementById('fileCsv').click()">+ CSV</button>
        <span class="key-status off" id="keyStatus">key · off</span>
      </div>
      <div class="quick-grid" id="quickGrid">
        <button type="button" class="qbtn" onclick="quick('Activate trusted tables for revenue by region last quarter')"><span class="qt">Trusted path</span><span class="qd">known-path activation</span></button>
        <button type="button" class="qbtn" onclick="quick('Compare baseline thrash vs known-path for revenue by region')"><span class="qt">Compare paths</span><span class="qd">baseline vs trusted</span></button>
        <button type="button" class="qbtn" onclick="quick('fail closed when trust is red')"><span class="qt">Fail closed</span><span class="qd">block bad trust</span></button>
        <button type="button" class="qbtn" onclick="quick('doctor')"><span class="qt">Doctor</span><span class="qd">catalog connectivity</span></button>
        <button type="button" class="qbtn" onclick="quick('dataset')"><span class="qt">List dataset</span><span class="qd">active pack assets</span></button>
        <button type="button" class="qbtn" onclick="runTool('known-path')"><span class="qt">Run path now</span><span class="qd">CLI only</span></button>
      </div>
      <div class="chat" id="chat">
        <div class="msg assistant"><div class="md" id="welcomeMd"></div></div>
      </div>
      <div class="composer">
        <div class="composer-box">
          <textarea id="prompt" rows="3" placeholder="Describe the data job… or click an option above"></textarea>
          <div class="composer-foot">
            <div class="suggestions">
              <button type="button" class="chip" onclick="quick('Activate trusted tables for revenue by region last quarter')">Trusted path</button>
              <button type="button" class="chip" onclick="quick('Compare baseline thrash vs known-path for revenue by region')">Compare</button>
              <button type="button" class="chip" onclick="quick('fail closed when trust is red')">Fail closed</button>
              <button type="button" class="chip" onclick="quick('doctor')">Doctor</button>
            </div>
            <button type="button" class="btn-send" id="sendBtn" onclick="sendAgent()" title="Send" aria-label="Send">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M5 12h14M13 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </button>
          </div>
        </div>
      </div>
      <div class="term-pad" id="termPad">
        <div class="quick-grid" style="margin:0">
          <button type="button" class="qbtn" onclick="termRun('run known-path')"><span class="qt">run known-path</span><span class="qd">trusted activation</span></button>
          <button type="button" class="qbtn" onclick="termRun('run baseline')"><span class="qt">run baseline</span><span class="qd">thrash path</span></button>
          <button type="button" class="qbtn" onclick="termRun('run blocked')"><span class="qt">run blocked</span><span class="qd">fail closed</span></button>
          <button type="button" class="qbtn" onclick="termRun('demo')"><span class="qt">demo</span><span class="qd">all three modes</span></button>
          <button type="button" class="qbtn" onclick="termRun('doctor')"><span class="qt">doctor</span><span class="qd">health</span></button>
          <button type="button" class="qbtn" onclick="termRun('dataset')"><span class="qt">dataset</span><span class="qd">list pack</span></button>
        </div>
        <div class="term-shell">
          <pre id="termOut">$ terminal mode — AI disabled
# click a command or type below
# allowed: run <mode>, demo, doctor, dataset, cards, version
</pre>
          <form onsubmit="return termSubmit(event)">
            <span style="color:#c96442;font-family:ui-monospace,monospace;padding-top:.35rem">$</span>
            <input id="termIn" autocomplete="off" placeholder="run known-path :: revenue by region"/>
            <button type="submit" class="btn primary" style="padding:.35rem .7rem">Run</button>
          </form>
        </div>
      </div>
    </section>
  </div>
</div>

<div class="modal-bg" id="settingsModal" role="dialog" aria-modal="true" aria-labelledby="setTitle">
  <div class="modal">
    <h2 id="setTitle">Settings</h2>
    <p class="sub">Keys are stored on the <strong>server</strong> under <code>.known-path/</code> — not wiped on browser refresh. Leave secret fields blank to keep the saved value.</p>
    <div class="field"><label>Model endpoint (OpenAI-compatible)</label><input id="sBase" placeholder="https://api.openai.com/v1"/></div>
    <div class="field secret-locked" id="sKeyField">
      <label>API key</label>
      <input id="sKey" type="password" placeholder="Stored on server only" autocomplete="off"/>
    </div>
    <div class="secret-row">
      <span class="hint-saved" id="sKeySaved">No API key saved yet.</span>
      <label><input type="checkbox" id="sKeyReplace" onchange="toggleSecretReplace('key')"/> Replace key</label>
      <button type="button" class="btn quiet" style="font-size:.72rem;padding:.25rem .5rem" onclick="clearApiKey()">Clear key</button>
    </div>
    <div style="display:flex;gap:.5rem;margin-bottom:.8rem;align-items:center">
      <button type="button" class="btn" onclick="fetchModels()">Fetch models</button>
      <select id="sModel" style="flex:1;background:var(--paper);border:1px solid var(--line-2);border-radius:10px;padding:.55rem .7rem"></select>
    </div>
    <div class="field"><label>DataHub GMS URL</label><input id="sGms" placeholder="http://localhost:8080"/></div>
    <div class="field secret-locked" id="sTokField">
      <label>Personal Access Token</label>
      <input id="sTok" type="password" placeholder="Bearer PAT" autocomplete="off"/>
    </div>
    <div class="secret-row">
      <span class="hint-saved" id="sTokSaved">No PAT saved.</span>
      <label><input type="checkbox" id="sTokReplace" onchange="toggleSecretReplace('tok')"/> Replace PAT</label>
    </div>
    <p class="hint">Automation uses a <strong>PAT</strong>, not browser OAuth. Create one in DataHub → Settings → Access Tokens.</p>
    <div style="display:flex;gap:.75rem;align-items:center;margin-bottom:.75rem">
      <label style="display:flex;gap:.4rem;align-items:center;font-size:.85rem;color:var(--ink-2)"><input type="checkbox" id="sLive"/> Use live DataHub</label>
      <button type="button" class="btn quiet" onclick="testDh()">Test</button>
    </div>
    <div class="field"><label>Active dataset pack</label><select id="sDs"></select></div>
    <div style="display:flex;gap:.4rem;flex-wrap:wrap;margin:0 0 .75rem">
      <button type="button" class="btn" onclick="document.getElementById('fileCat').click()">Upload catalog JSON</button>
      <button type="button" class="btn" onclick="document.getElementById('fileCsv').click()">Upload CSV</button>
      <button type="button" class="btn quiet" onclick="createEmptyPack()">New empty pack</button>
    </div>
    <div class="toggle-row">
      <label><input type="checkbox" id="sShowThink" checked/> Show Thinking panel (tools + model reasoning)</label>
      <label><input type="checkbox" id="sStreamThink" checked/> Prefer stream for model thinking (SSE). Off = stream:false JSON only</label>
      <p class="hint" style="margin:0">Tool steps always show even when the model returns no reasoning field. Stream is preferred because many gateways only emit thinking over SSE.</p>
    </div>
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
  return String(s ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
}}
function renderMarkdown(text) {{
  const src = String(text ?? '');
  let html = '';
  try {{
    if (window.marked) {{
      marked.setOptions({{ gfm: true, breaks: true }});
      html = marked.parse(src);
    }} else {{
      html = '<p>' + escapeHtml(src).replaceAll('\\n', '<br/>') + '</p>';
    }}
  }} catch (e) {{
    html = '<p>' + escapeHtml(src).replaceAll('\\n', '<br/>') + '</p>';
  }}
  if (window.DOMPurify) {{
    html = DOMPurify.sanitize(html, {{
      ADD_TAGS: ['mjx-container'],
      ADD_ATTR: ['class', 'style', 'aria-hidden', 'focusable', 'role', 'xmlns']
    }});
  }}
  return html;
}}
function enhanceMath(el) {{
  if (!el || !window.renderMathInElement) return;
  try {{
    renderMathInElement(el, {{
      delimiters: [
        {{left: '$$', right: '$$', display: true}},
        {{left: '\\\\[', right: '\\\\]', display: true}},
        {{left: '$', right: '$', display: false}},
        {{left: '\\\\(', right: '\\\\)', display: false}}
      ],
      throwOnError: false,
      strict: 'ignore'
    }});
  }} catch (e) {{}}
}}
function addMsg(role, content, opts) {{
  opts = opts || {{}};
  const d = document.createElement('div');
  d.className = 'msg ' + role;
  if (role === 'assistant' && opts.markdown !== false) {{
    const wrap = document.createElement('div');
    wrap.className = 'md';
    wrap.innerHTML = typeof content === 'string' ? renderMarkdown(content) : '';
    d.appendChild(wrap);
    $('chat').appendChild(d);
    enhanceMath(wrap);
  }} else if (role === 'think') {{
    d.className = 'msg think';
    d.innerHTML = content;
    $('chat').appendChild(d);
  }} else {{
    d.innerHTML = content;
    $('chat').appendChild(d);
  }}
  $('chat').scrollTop = $('chat').scrollHeight;
  return d;
}}
function renderThinkingPanel(thinking, reasoning) {{
  const rows = [];
  (thinking || []).forEach(t => {{
    const ph = t.phase === 'tool' ? 'tool'
      : (t.phase === 'reason' ? 'reason'
      : (t.phase === 'done' ? 'done'
      : (t.phase === 'error' || t.status === 'error' ? 'error' : 'tool')));
    rows.push(`<div class="think-row ${{ph}}"><div class="ph"></div><div><div class="tt">${{escapeHtml(t.title || t.phase || 'step')}}</div><div class="td">${{escapeHtml(t.detail || '')}}</div></div></div>`);
  }});
  if (reasoning && !(thinking || []).some(t => t.phase === 'reason')) {{
    rows.unshift(`<div class="think-row reason"><div class="ph"></div><div><div class="tt">Reasoning</div><div class="td">${{escapeHtml(reasoning)}}</div></div></div>`);
  }}
  if (!rows.length) {{
    rows.push(`<div class="think-row"><div class="ph"></div><div><div class="tt">No steps yet</div><div class="td">Waiting for tools or model reasoning…</div></div></div>`);
  }}
  return `<details class="think" open><summary>Thinking &amp; tools · ${{rows.length}} steps</summary><div class="think-body">${{rows.join('')}}</div></details>`;
}}
function trapHit(plan) {{
  return (plan.nodes || []).some(n => n.activated && /old|backup|tmp/i.test(n.name || ''));
}}

function setJit(title, detail, pulse) {{
  $('jitTitle').textContent = title;
  $('jitDetail').textContent = detail;
  const p = $('jitPulse');
  p.className = 'jit-pulse ' + (pulse || '');
}}
function pushFeed(msg) {{
  const feed = $('jitFeed');
  if (feed.children.length === 1 && feed.textContent.includes('Idle')) feed.innerHTML = '';
  const t = new Date();
  const ts = String(t.getHours()).padStart(2,'0') + ':' + String(t.getMinutes()).padStart(2,'0') + ':' + String(t.getSeconds()).padStart(2,'0');
  const row = document.createElement('div');
  row.className = 'jit-event';
  row.innerHTML = `<span class="t">${{ts}}</span><span class="b">${{msg}}</span>`;
  feed.prepend(row);
  while (feed.children.length > 40) feed.removeChild(feed.lastChild);
}}
function renderNodeCards(plan) {{
  const nodes = plan.nodes || [];
  const box = $('nodeCards');
  if (!nodes.length) {{
    box.innerHTML = '<div class="node-card off"><div class="nn">No nodes yet</div><div class="nm">Run a path to see assets light up</div></div>';
    return;
  }}
  // Show activated first, then a few off nodes
  const sorted = [...nodes].sort((a,b) => (b.activated?1:0) - (a.activated?1:0));
  box.innerHTML = sorted.slice(0, 8).map(n => {{
    const trap = /old|backup|tmp/i.test(n.name || '');
    const cls = n.trust === 'red' ? 'red' : (n.activated ? 'on' : 'off');
    const snip = (n.reasons || []).slice(0, 3).join(' · ') || (n.role ? 'role: ' + n.role : '—');
    const tags = [
      n.activated ? '<span class="tag hot">ON</span>' : '<span class="tag">off</span>',
      n.trust ? `<span class="tag">${{escapeHtml(n.trust)}}</span>` : '',
      n.role ? `<span class="tag">${{escapeHtml(n.role)}}</span>` : '',
      trap ? '<span class="tag hot">trap?</span>' : '',
      `rel ${{n.relevance}}`
    ].filter(Boolean).join('');
    return `<div class="node-card ${{cls}}">
      <div class="nn">${{escapeHtml(n.name || n.urn || 'node')}}</div>
      <div class="nm">${{escapeHtml((n.urn || '').slice(0, 56))}}${{(n.urn||'').length>56?'…':''}}</div>
      <div class="meta">${{tags}}</div>
      <div class="data-snip" title="${{escapeHtml(snip)}}">${{escapeHtml(snip)}}</div>
    </div>`;
  }}).join('');
}}

function setTimeline(plan) {{
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
  renderNodeCards(plan);
  updateFetchBar(plan.mode, plan.entity_fetches || 0);

  // JIT headline from final plan
  if (st === 'BLOCKED_TRUST') {{
    setJit('Stopped · trust red', plan.message || 'Required asset failed trust. No invented replacement.', 'fail');
    pushFeed(`<strong>Blocked</strong> · ${{escapeHtml(plan.message || 'trust fail')}}`);
  }} else if (st === 'SUCCESS') {{
    const names = act.map(n => n.name).join(', ') || 'none';
    setJit('Done · shortlist ready', `Using ${{act.length}} node(s): ${{names}}. ${{plan.entity_fetches}} fetch(es).`, 'ok');
    pushFeed(`<strong>Activated</strong> · ${{escapeHtml(names)}} · ${{plan.entity_fetches}} fetches`);
    act.forEach(n => pushFeed(`<strong>Node ON</strong> · ${{escapeHtml(n.name)}} · trust ${{escapeHtml(n.trust)}} · rel ${{n.relevance}}`));
  }} else {{
    setJit(st, plan.message || 'Run finished', '');
    pushFeed(`<strong>${{escapeHtml(st)}}</strong> · ${{escapeHtml(plan.message || '')}}`);
  }}
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
  setJit('Running · ' + mode, 'Shelling into CLI with intent: ' + intent, '');
  pushFeed(`<strong>Start</strong> · mode <code>${{escapeHtml(mode)}}</code>`);
  pushFeed(`<strong>Intent</strong> · ${{escapeHtml(intent)}}`);
  addMsg('step', `<span class="badge">Working</span><div class="cmd">run --mode ${{escapeHtml(mode)}}</div>`);
  try {{
    const r = await fetch('/api/cli/run?mode=' + encodeURIComponent(mode) + '&intent=' + encodeURIComponent(intent));
    const data = await r.json();
    appendCli(data.command, data);
    pushFeed(`<strong>CLI</strong> · ${{escapeHtml(data.command || '')}} · ${{data.duration_ms || 0}}ms`);
    if (data.plan) {{
      paintPlan(data.plan);
      addMsg('assistant', summarizePlan(data.plan), {{ markdown: true }});
    }}
  }} catch (e) {{ toast(String(e)); setJit('Error', String(e), 'fail'); }}
  finally {{ setBusy(false); }}
}}

function summarizePlan(plan) {{
  const act = (plan.nodes || []).filter(n => n.activated).map(n => '`' + n.name + '`').join(', ') || 'none';
  const trap = trapHit(plan) ? '\\n\\nA trap asset was lit — review carefully.' : '';
  if (plan.status === 'BLOCKED_TRUST') {{
    return `**Stopped on trust.**\\n\\n${{plan.message || ''}}\\n\\nNo replacement table was invented.`;
  }}
  return `**${{plan.status === 'SUCCESS' ? 'Ready for review' : plan.status}}**\\n\\n- Assets lit: ${{act}}\\n- Fetches: ${{plan.entity_fetches}}${{trap}}`;
}}

async function sendAgent() {{
  const text = $('prompt').value.trim();
  if (!text) return;
  addMsg('user', escapeHtml(text), {{ markdown: false }});
  $('prompt').value = '';
  setBusy(true);
  setJit('Agent thinking…', text, '');
  pushFeed(`<strong>User</strong> · ${{escapeHtml(text)}}`);
  const thinking = addMsg('assistant', '', {{ markdown: false }});
  thinking.innerHTML = '<div class="md"><p><span class="loading-dots">Working</span></p></div>';
  try {{
    const r = await fetch('/api/agent/chat', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ message: text }})
    }});
    const data = await r.json();
    thinking.remove();
    // Always show Thinking panel (tools + reasoning) so stream:false still surfaces steps
    const thinkHtml = renderThinkingPanel(data.thinking || [], data.reasoning || '');
    if (thinkHtml) addMsg('think', thinkHtml, {{ markdown: false }});
    (data.thinking || []).forEach(t => {{
      if (t.phase === 'tool' || t.phase === 'reason') {{
        pushFeed(`<strong>${{t.phase === 'reason' ? 'Think' : 'Tool'}}</strong> · ${{escapeHtml(t.title || '')}} — ${{escapeHtml((t.detail||'').slice(0,120))}}`);
      }}
    }});
    if (data.reasoning) pushFeed(`<strong>Reasoning</strong> · ${{escapeHtml(String(data.reasoning).slice(0, 160))}}`);
    (data.tool_traces || []).forEach(tr => {{
      if (tr.command) appendCli(tr.command, {{ exit_code: tr.exit_code, duration_ms: tr.duration_ms }});
      pushFeed(`<strong>CLI</strong> · ${{escapeHtml(tr.command || tr.tool || '')}} · ${{tr.duration_ms||0}}ms`);
    }});
    if (data.plan) paintPlan(data.plan);
    if (data.plans) data.plans.forEach(p => updateFetchBar(p.mode, p.entity_fetches || 0));
    if (data.content) addMsg('assistant', data.content, {{ markdown: true }});
    else if (data.error) {{
      const err = typeof data.error === 'string' ? data.error : JSON.stringify(data.error, null, 2);
      setJit('Error', err.slice(0, 160), 'fail');
      addMsg('assistant', '**Something went wrong**\\n\\n```\\n' + err + '\\n```', {{ markdown: true }});
    }}
  }} catch (e) {{
    thinking.remove();
    setJit('Error', String(e), 'fail');
    addMsg('assistant', '**Request failed**\\n\\n' + String(e), {{ markdown: true }});
  }} finally {{
    setBusy(false);
  }}
}}

function quick(t) {{ $('prompt').value = t; sendAgent(); }}

function updateKeyStatus() {{
  const s = BOOT.settings || {{}};
  const el = $('keyStatus');
  const cfgKey = $('cfgKey');
  const cfgModel = $('cfgModel');
  const keyOk = !!(s.llm && s.llm.api_key_set);
  const model = (s.llm && s.llm.model) || '';
  if (el) {{
    if (keyOk) {{
      el.textContent = 'key · ' + (s.llm.api_key_hint || 'saved');
      el.className = 'key-status';
    }} else {{
      el.textContent = 'key · not set';
      el.className = 'key-status off';
    }}
  }}
  if (cfgKey) {{
    cfgKey.textContent = keyOk ? ('key · ' + (s.llm.api_key_hint || 'saved')) : 'key · not set';
    cfgKey.className = 'cfg-pill ' + (keyOk ? 'ok' : 'bad');
  }}
  if (cfgModel) {{
    cfgModel.textContent = model ? ('model · ' + model) : 'model · not set';
    cfgModel.className = 'cfg-pill ' + (model ? 'ok' : 'bad');
    cfgModel.title = (s.llm && s.llm.base_url) ? s.llm.base_url : 'No base URL';
  }}
}}
function setUiMode(mode, opts) {{
  const persist = !(opts && opts.persist === false);
  const pane = $('taskPane');
  const ai = mode !== 'terminal';
  pane.classList.toggle('ai-on', ai);
  pane.classList.toggle('term-on', !ai);
  $('modeAi').classList.toggle('on', ai);
  $('modeTerm').classList.toggle('on', !ai);
  if (!persist) return;
  // persist mode only — never touch secrets
  fetch('/api/settings', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify({{ ui: {{ mode: ai ? 'ai' : 'terminal' }} }})
  }}).then(r => r.json()).then(d => {{
    if (d.public) {{ BOOT.settings = d.public; updateKeyStatus(); }}
  }}).catch(() => {{}});
}}
async function switchDataset(id) {{
  if (!id) return;
  await loadDatasetPack(id);
}}
async function termRun(cmd) {{
  $('termIn').value = cmd;
  return termSubmit({{ preventDefault: () => {{}} }});
}}
async function termSubmit(ev) {{
  if (ev && ev.preventDefault) ev.preventDefault();
  const cmd = ($('termIn').value || '').trim();
  if (!cmd) return false;
  const out = $('termOut');
  out.textContent += '\\n$ ' + cmd + '\\n';
  setJit('Terminal', cmd, '');
  pushFeed(`<strong>Terminal</strong> · ${{escapeHtml(cmd)}}`);
  try {{
    const r = await fetch('/api/agent', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ command: cmd }})
    }});
    const data = await r.json();
    if (data.stdout) out.textContent += data.stdout + (data.stdout.endsWith('\\n') ? '' : '\\n');
    if (data.stderr) out.textContent += data.stderr + '\\n';
    if (data.error) out.textContent += 'error: ' + data.error + '\\n';
    out.textContent += `[exit ${{data.exit_code}} · ${{data.duration_ms || 0}}ms]\\n`;
    out.scrollTop = out.scrollHeight;
    if (data.plan) paintPlan(data.plan);
    if (data.plans) data.plans.forEach(p => updateFetchBar(p.mode, p.entity_fetches || 0));
    appendCli(data.command || cmd, data);
  }} catch (e) {{
    out.textContent += String(e) + '\\n';
  }}
  $('termIn').value = '';
  return false;
}}

function toggleSecretReplace(which) {{
  if (which === 'key') {{
    const on = $('sKeyReplace').checked;
    $('sKey').disabled = !on;
    if (!on) $('sKey').value = '';
    else $('sKey').focus();
  }} else {{
    const on = $('sTokReplace').checked;
    $('sTok').disabled = !on;
    if (!on) $('sTok').value = '';
    else $('sTok').focus();
  }}
}}
async function clearApiKey() {{
  if (!confirm('Remove the saved API key from the server?')) return;
  const r = await fetch('/api/settings', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify({{ llm: {{ clear_api_key: true }} }})
  }});
  const data = await r.json();
  BOOT.settings = data.public || BOOT.settings;
  updateKeyStatus();
  openSettings();
  toast('API key cleared');
}}
function openSettings() {{
  const s = BOOT.settings || {{}};
  $('sBase').value = (s.llm && s.llm.base_url) || '';
  // Never put secret into the input — locked unless "Replace" is checked
  $('sKeyReplace').checked = false;
  $('sKey').value = '';
  $('sKey').disabled = true;
  $('sKey').placeholder = (s.llm && s.llm.api_key_set)
    ? ((s.llm.api_key_hint || '•••• saved') + ' — check Replace to change')
    : 'Paste new API key (saved on server)';
  $('sKeySaved').textContent = (s.llm && s.llm.api_key_set)
    ? ('Saved on server: ' + (s.llm.api_key_hint || '••••'))
    : 'No API key saved yet.';
  $('sGms').value = (s.datahub && s.datahub.gms_url) || '';
  $('sTokReplace').checked = false;
  $('sTok').value = '';
  $('sTok').disabled = true;
  $('sTok').placeholder = (s.datahub && s.datahub.token_set)
    ? ((s.datahub.token_hint || '•••• saved') + ' — check Replace to change')
    : 'PAT';
  $('sTokSaved').textContent = (s.datahub && s.datahub.token_set)
    ? ('Saved on server: ' + (s.datahub.token_hint || '••••'))
    : 'No PAT saved.';
  $('sLive').checked = !!(s.datahub && s.datahub.use_live);
  $('sShowThink').checked = !s.ui || s.ui.show_thinking !== false;
  $('sStreamThink').checked = !s.ui || s.ui.stream_thinking !== false;
  const models = $('sModel'); models.innerHTML = '';
  if (s.llm && s.llm.model) {{
    const o = document.createElement('option'); o.value = s.llm.model; o.textContent = s.llm.model; models.appendChild(o);
  }}
  refreshDsSelect();
  updateKeyStatus();
  $('setMsg').textContent = (s.llm && s.llm.api_key_set)
    ? 'Key survives refresh. Blank + Save keeps it. Use Replace only to change the key.'
    : 'No API key saved yet — check Replace, paste key, then Save.';
  $('settingsModal').classList.add('open');
}}
function closeSettings() {{ $('settingsModal').classList.remove('open'); }}
function refreshDsSelect() {{
  const fill = (sel) => {{
    if (!sel) return;
    const cur = sel.value || BOOT.active;
    sel.innerHTML = '';
    (BOOT.datasets || []).forEach(d => {{
      const o = document.createElement('option');
      o.value = d.id; o.textContent = d.id + ' · ' + d.assets + ' assets' + (d.csv_files && d.csv_files.length ? ' · ' + d.csv_files.length + ' csv' : '');
      if (d.id === (BOOT.active || cur)) o.selected = true;
      sel.appendChild(o);
    }});
  }};
  fill($('sDs'));
  fill($('dsSelectMain'));
  $('dsLabel').textContent = BOOT.active || 'dataset';
  updateKeyStatus();
}}
async function fetchModels() {{
  $('setMsg').textContent = 'Fetching…';
  // Save base URL only; do not wipe key/model
  await saveSettings(true);
  const r = await fetch('/api/settings/models');
  const data = await r.json();
  if (!data.ok) {{
    const err = data.error;
    $('setMsg').textContent = typeof err === 'string' ? err : (err && err.error) ? String(err.error) : 'Could not fetch models';
    return;
  }}
  const sel = $('sModel');
  const prev = sel.value || ((BOOT.settings && BOOT.settings.llm && BOOT.settings.llm.model) || '');
  sel.innerHTML = '';
  (data.models || []).forEach(id => {{
    const o = document.createElement('option'); o.value = id; o.textContent = id;
    if (id === prev) o.selected = true;
    sel.appendChild(o);
  }});
  if (!sel.value && data.models && data.models.length) sel.value = data.models[0];
  $('setMsg').textContent = (data.models || []).length + ' models · pick one then Save';
}}
async function testDh() {{
  await saveSettings(true);
  const r = await fetch('/api/settings/datahub/test');
  const data = await r.json();
  $('setMsg').textContent = data.message || JSON.stringify(data);
}}
async function saveSettings(quiet) {{
  // Secrets only sent when Replace is checked AND field non-empty.
  // Blank secret fields are never posted → server keeps existing key.
  const body = {{
    llm: {{
      base_url: $('sBase').value.trim(),
    }},
    datahub: {{
      use_live: $('sLive').checked,
    }},
    dataset: {{ active: $('sDs').value || BOOT.active }},
    ui: {{
      mode: ($('taskPane').classList.contains('term-on') ? 'terminal' : 'ai'),
      show_thinking: !!$('sShowThink').checked,
      stream_thinking: !!$('sStreamThink').checked,
    }}
  }};
  const model = ($('sModel').value || '').trim();
  if (model) body.llm.model = model;
  const gms = $('sGms').value.trim();
  if (gms) body.datahub.gms_url = gms;
  if ($('sKeyReplace') && $('sKeyReplace').checked) {{
    const key = ($('sKey').value || '').trim();
    if (key && !key.startsWith('•') && !key.startsWith('*')) body.llm.api_key = key;
  }}
  if ($('sTokReplace') && $('sTokReplace').checked) {{
    const tok = ($('sTok').value || '').trim();
    if (tok && !tok.startsWith('•') && !tok.startsWith('*')) body.datahub.token = tok;
  }}

  const r = await fetch('/api/settings', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(body) }});
  const data = await r.json();
  BOOT.settings = data.public || BOOT.settings;
  if (data.datasets) BOOT.datasets = data.datasets;
  if (body.dataset && body.dataset.active) BOOT.active = body.dataset.active;
  refreshDsSelect();
  updateKeyStatus();
  if (!quiet) {{
    const kept = BOOT.settings.llm && BOOT.settings.llm.api_key_set;
    toast(kept ? 'Saved · key still on server' : 'Saved');
    closeSettings();
  }}
  return data;
}}
async function loadDatasetPack(id) {{
  const r = await fetch('/api/datasets/active', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ id }}) }});
  const data = await r.json();
  if (data.ok) {{
    BOOT.active = id;
    BOOT.datasets = data.datasets || BOOT.datasets;
    refreshDsSelect();
    toast('Using ' + id);
    pushFeed(`<strong>Dataset</strong> · ${{escapeHtml(id)}}`);
    setJit('Dataset switched', 'Active pack: ' + id, 'ok');
  }} else toast(data.error || 'Failed');
}}
async function createEmptyPack() {{
  const name = prompt('New pack id (letters, numbers, _ -)', 'pack-' + Date.now().toString(36).slice(-5));
  if (!name) return;
  const stub = JSON.stringify({{ id: name, title: name, assets: [] }}, null, 2);
  const r = await fetch('/api/datasets/upload/catalog', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ name, content: stub, allow_empty: true }}) }});
  const data = await r.json();
  if (data.ok) {{
    BOOT.active = name;
    BOOT.datasets = await (await fetch('/api/datasets')).json();
    refreshDsSelect();
    toast('Created pack ' + name + ' — upload catalog with assets or CSV next');
    pushFeed(`<strong>Dataset</strong> · new pack ${{escapeHtml(name)}}`);
  }} else toast(data.error || 'Failed');
}}
async function onUploadCatalog(ev) {{
  const f = ev.target.files[0]; if (!f) return;
  const text = await f.text();
  const name = prompt('Name this pack (letters, numbers, _ -)', 'upload-' + Date.now().toString(36).slice(-5));
  if (!name) return;
  const r = await fetch('/api/datasets/upload/catalog', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ name, content: text }}) }});
  const data = await r.json();
  toast(data.ok ? 'Catalog pack ready: ' + name : (data.error || 'Failed'));
  if (data.ok) {{
    BOOT.active = name;
    BOOT.datasets = await (await fetch('/api/datasets')).json();
    refreshDsSelect();
    pushFeed(`<strong>Upload</strong> · catalog pack ${{escapeHtml(name)}}`);
  }}
  ev.target.value = '';
}}
async function onUploadCsv(ev) {{
  const f = ev.target.files[0]; if (!f) return;
  const text = await f.text();
  const pack = prompt('Save CSV into which dataset pack?', BOOT.active || 'demo-finance');
  if (!pack) return;
  const r = await fetch('/api/datasets/upload/csv', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ dataset_id: pack, filename: f.name, content: text }}) }});
  const data = await r.json();
  toast(data.ok ? 'CSV saved to ' + pack : (data.error || 'Failed'));
  if (data.ok) {{
    BOOT.datasets = await (await fetch('/api/datasets')).json();
    refreshDsSelect();
    pushFeed(`<strong>Upload</strong> · CSV ${{escapeHtml(f.name)}} → ${{escapeHtml(pack)}}`);
  }}
  ev.target.value = '';
}}

async function hydrateSettings() {{
  try {{
    const r = await fetch('/api/settings');
    const s = await r.json();
    BOOT.settings = s;
    if (s.dataset && s.dataset.active) BOOT.active = s.dataset.active;
    const packs = await (await fetch('/api/datasets')).json();
    if (Array.isArray(packs)) BOOT.datasets = packs;
  }} catch (e) {{ /* keep BOOT */ }}
  refreshDsSelect();
  updateKeyStatus();
  const mode = (BOOT.settings && BOOT.settings.ui && BOOT.settings.ui.mode) || 'ai';
  setUiMode(mode === 'terminal' ? 'terminal' : 'ai', {{ persist: false }});
}}

// boot
refreshDsSelect();
updateKeyStatus();
drawGraph({{ nodes: [] }});
drawDonut({{ nodes: [] }});
hydrateSettings();
$('prompt').addEventListener('keydown', (e) => {{
  if (e.key === 'Enter' && !e.shiftKey) {{ e.preventDefault(); sendAgent(); }}
}});
function paintWelcome() {{
  const el = $('welcomeMd');
  if (!el) return;
  el.innerHTML = renderMarkdown(
    'Give **known-path** a goal — tools run through the real CLI.\\n\\n' +
    '**AI agent** = chat + tools. **Terminal only** = command pad, no LLM.\\n\\n' +
    'API keys live on the **server** (`.known-path/`) and survive refresh. Empty key field + Save = keep existing key.\\n\\n' +
    'Switch dataset packs from the bar above, or upload catalog JSON / CSV.\\n\\n' +
    '| Action | What it does |\\n|---|---|\\n' +
    '| Trusted path | Activate certified tables |\\n' +
    '| Compare | Baseline thrash vs known-path |\\n' +
    '| Fail closed | Stop on red trust |\\n' +
    '| Doctor | Connectivity check |'
  );
  enhanceMath(el);
}}
if (document.readyState === 'loading') {{
  document.addEventListener('DOMContentLoaded', paintWelcome);
}} else {{
  setTimeout(paintWelcome, 50);
  setTimeout(paintWelcome, 300);
}}
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
                upload_catalog_json(
                    str(body.get("name") or ""),
                    str(body.get("content") or ""),
                    allow_empty=bool(body.get("allow_empty")),
                ),
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
                thinking = [
                    {
                        "phase": "think",
                        "title": "No LLM model configured",
                        "detail": "Using local router → CLI tools (set endpoint + model in Settings for full agent)",
                    }
                ]
                if low in ("doctor", "dataset", "demo") or low.startswith("run "):
                    r = agent_command(msg)
                    thinking.append(
                        {
                            "phase": "tool",
                            "title": f"CLI `{msg.split()[0]}`",
                            "detail": r.command_display,
                            "status": "ok" if r.ok else "error",
                            "duration_ms": r.duration_ms,
                            "exit_code": r.exit_code,
                        }
                    )
                    content = (
                        f"```\\n{(r.stdout or r.error or 'done')[:2000]}\\n```"
                        if low in ("doctor", "dataset")
                        else ((r.plan or {}).get("message") if r.plan else (r.error or "Done."))
                    )
                    self._json(
                        200,
                        {
                            "ok": r.ok,
                            "content": content,
                            "thinking": thinking,
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
                if "baseline" in low or "compare" in low:
                    r = run_mode_via_cli("baseline", msg)
                    r2 = run_mode_via_cli("known-path", DEFAULT_INTENT)
                    thinking.extend(
                        [
                            {
                                "phase": "tool",
                                "title": "Calling `run_activation` (baseline)",
                                "detail": r.command_display,
                                "status": "ok" if r.ok else "error",
                                "duration_ms": r.duration_ms,
                            },
                            {
                                "phase": "tool",
                                "title": "Calling `run_activation` (known-path)",
                                "detail": r2.command_display,
                                "status": "ok" if r2.ok else "error",
                                "duration_ms": r2.duration_ms,
                            },
                            {"phase": "done", "title": "Compare complete", "detail": "Baseline vs trusted path"},
                        ]
                    )
                    self._json(
                        200,
                        {
                            "ok": True,
                            "content": (
                                "### Compare complete\\n\\n"
                                f"- **Baseline** fetches: `{(r.plan or {}).get('entity_fetches')}`\\n"
                                f"- **Known-path** fetches: `{(r2.plan or {}).get('entity_fetches')}`\\n\\n"
                                "Trusted path uses certified tables only."
                            ),
                            "thinking": thinking,
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
                if (
                    "fail closed" in low
                    or "fail-closed" in low
                    or low.startswith("blocked")
                    or "run blocked" in low
                    or "simulate red" in low
                ):
                    r = run_mode_via_cli("blocked", DEFAULT_INTENT)
                else:
                    r = run_mode_via_cli("known-path", msg or DEFAULT_INTENT)
                thinking.append(
                    {
                        "phase": "tool",
                        "title": "Calling `run_activation`",
                        "detail": r.command_display,
                        "status": "ok" if r.ok else "error",
                        "duration_ms": r.duration_ms,
                        "exit_code": r.exit_code,
                    }
                )
                thinking.append({"phase": "done", "title": "Answer ready", "detail": (r.plan or {}).get("status", "")})
                self._json(
                    200,
                    {
                        "ok": r.ok,
                        "content": (r.plan or {}).get("message")
                        if r.plan
                        else (r.error or r.stdout[:500] or "Done."),
                        "thinking": thinking,
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
