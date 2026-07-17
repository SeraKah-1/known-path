"""Simple, light web demo for known-path.

Goal: anyone can understand what this is, what to click, and what to look at.
Every run still goes through the real CLI (cli_bridge).
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
    assets = demo_catalog()
    samples = list_sample_files()
    asset_cards = []
    for a in assets:
        if a.deprecated or a.quality_fail:
            kind, label, color = "bad", "JANGAN dipakai (jebakan)", "#b91c1c"
        elif a.certified and "revenue" in a.name:
            kind, label, color = "good", "BENAR — tabel resmi Finance", "#047857"
        elif a.certified:
            kind, label, color = "ok", "OK — dimensi bantu", "#0369a1"
        else:
            kind, label, color = "noise", "Bukan revenue (noise)", "#64748b"
        asset_cards.append(
            f"""
            <div class="asset {kind}">
              <div class="asset-name">{_esc(a.name)}</div>
              <div class="asset-tag" style="color:{color}">{label}</div>
              <div class="asset-desc">{_esc(a.description[:120])}{"…" if len(a.description)>120 else ""}</div>
            </div>"""
        )

    sample_bits = "".join(
        f"<details><summary>Isi file data: {_esc(s['name'])}</summary>"
        f"<pre>{_esc(s['preview'])}</pre></details>"
        for s in samples
    )

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>known-path — demo mudah</title>
<style>
  :root {{
    --bg: #f7f8fa;
    --card: #ffffff;
    --text: #0f172a;
    --muted: #475569;
    --line: #e2e8f0;
    --blue: #1d4ed8;
    --blue-soft: #eff6ff;
    --green: #047857;
    --green-soft: #ecfdf5;
    --red: #b91c1c;
    --red-soft: #fef2f2;
    --amber: #b45309;
    --amber-soft: #fffbeb;
    --radius: 14px;
    --shadow: 0 1px 2px rgba(15,23,42,.06), 0 8px 24px rgba(15,23,42,.04);
    --font: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    --mono: ui-monospace, "Cascadia Code", "SF Mono", Menlo, monospace;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; font-family: var(--font); color: var(--text); background: var(--bg);
    line-height: 1.5; font-size: 16px;
  }}
  a {{ color: var(--blue); }}
  .wrap {{ max-width: 920px; margin: 0 auto; padding: 20px 16px 64px; }}

  /* header */
  header {{
    background: var(--card); border: 1px solid var(--line); border-radius: var(--radius);
    padding: 20px 22px; box-shadow: var(--shadow); margin-bottom: 18px;
  }}
  .badge {{
    display: inline-block; background: var(--blue-soft); color: var(--blue);
    font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 999px;
    margin-bottom: 10px;
  }}
  h1 {{ margin: 0 0 8px; font-size: 1.6rem; line-height: 1.25; }}
  .lead {{ margin: 0; color: var(--muted); font-size: 1.02rem; }}

  /* simple steps explainer */
  .howto {{
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 18px 0;
  }}
  @media (max-width: 720px) {{ .howto {{ grid-template-columns: 1fr; }} }}
  .step {{
    background: var(--card); border: 1px solid var(--line); border-radius: var(--radius);
    padding: 14px 16px; box-shadow: var(--shadow);
  }}
  .step .n {{
    width: 28px; height: 28px; border-radius: 50%; background: var(--blue); color: #fff;
    display: inline-flex; align-items: center; justify-content: center; font-weight: 700; font-size: 14px;
    margin-bottom: 8px;
  }}
  .step h3 {{ margin: 0 0 4px; font-size: 1rem; }}
  .step p {{ margin: 0; color: var(--muted); font-size: .92rem; }}

  .card {{
    background: var(--card); border: 1px solid var(--line); border-radius: var(--radius);
    padding: 18px 18px; margin-bottom: 16px; box-shadow: var(--shadow);
  }}
  .card h2 {{ margin: 0 0 6px; font-size: 1.15rem; }}
  .card .why {{ margin: 0 0 14px; color: var(--muted); font-size: .95rem; }}

  label {{ display: block; font-weight: 600; margin-bottom: 6px; font-size: .95rem; }}
  textarea, input[type=text] {{
    width: 100%; border: 1px solid #cbd5e1; border-radius: 10px; padding: 12px 14px;
    font: inherit; background: #fff; color: var(--text);
  }}
  textarea:focus, input:focus {{ outline: 3px solid #bfdbfe; border-color: #60a5fa; }}

  .btns {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 12px; }}
  button {{
    border: 0; border-radius: 10px; padding: 12px 16px; font: inherit; font-weight: 700;
    cursor: pointer;
  }}
  button:disabled {{ opacity: .55; cursor: wait; }}
  .btn-main {{ background: var(--blue); color: #fff; }}
  .btn-main:hover {{ background: #1e40af; }}
  .btn-alt {{ background: #e2e8f0; color: var(--text); }}
  .btn-alt:hover {{ background: #cbd5e1; }}
  .btn-warn {{ background: var(--amber-soft); color: var(--amber); border: 1px solid #fcd34d; }}
  .btn-danger {{ background: var(--red-soft); color: var(--red); border: 1px solid #fecaca; }}

  .hint {{
    margin-top: 12px; padding: 12px 14px; background: var(--blue-soft); border-radius: 10px;
    color: #1e3a8a; font-size: .92rem;
  }}
  .status {{
    margin-top: 10px; min-height: 1.4em; font-weight: 600; color: var(--muted);
  }}
  .status.busy {{ color: var(--blue); }}
  .status.err {{ color: var(--red); }}

  /* result boxes */
  .result {{
    border-radius: var(--radius); border: 2px solid var(--line); padding: 16px; margin-top: 14px;
    background: #fff;
  }}
  .result.ok {{ border-color: #6ee7b7; background: var(--green-soft); }}
  .result.bad {{ border-color: #fca5a5; background: var(--red-soft); }}
  .result.warn {{ border-color: #fcd34d; background: var(--amber-soft); }}
  .result h3 {{ margin: 0 0 8px; font-size: 1.1rem; }}
  .big {{ font-size: 1.05rem; margin: 0 0 10px; }}
  .kv {{ display: grid; grid-template-columns: 140px 1fr; gap: 6px 10px; font-size: .95rem; margin: 10px 0; }}
  .kv b {{ color: var(--muted); font-weight: 600; }}

  /* simple bars */
  .bar-row {{ display: grid; grid-template-columns: 110px 1fr 48px; gap: 8px; align-items: center; margin: 8px 0; }}
  .bar-track {{ height: 18px; background: #e2e8f0; border-radius: 999px; overflow: hidden; }}
  .bar-fill {{ height: 100%; border-radius: 999px; transition: width .4s ease; }}
  .bar-fill.base {{ background: #f87171; }}
  .bar-fill.kp {{ background: #34d399; }}
  .bar-fill.blk {{ background: #fbbf24; }}

  /* nodes */
  .nodes {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0; }}
  .node {{
    border-radius: 10px; padding: 10px 12px; border: 1px solid var(--line); background: #fff; min-width: 140px;
  }}
  .node.on {{ border-color: #34d399; background: #ecfdf5; }}
  .node.off {{ opacity: .75; }}
  .node.red {{ border-color: #fca5a5; background: #fef2f2; }}
  .node .nm {{ font-family: var(--mono); font-size: .85rem; font-weight: 700; }}
  .node .meta {{ font-size: .8rem; color: var(--muted); margin-top: 2px; }}

  pre, .mono {{
    font-family: var(--mono); font-size: .82rem; background: #f1f5f9; border: 1px solid var(--line);
    border-radius: 10px; padding: 12px; overflow: auto; white-space: pre-wrap; color: #0f172a;
  }}
  details {{ margin-top: 8px; }}
  summary {{ cursor: pointer; color: var(--blue); font-weight: 600; }}

  .assets {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
  @media (max-width: 640px) {{ .assets {{ grid-template-columns: 1fr; }} }}
  .asset {{ border: 1px solid var(--line); border-radius: 12px; padding: 12px; background: #fff; }}
  .asset.good {{ border-color: #6ee7b7; background: #ecfdf5; }}
  .asset.bad {{ border-color: #fca5a5; background: #fef2f2; }}
  .asset.ok {{ border-color: #93c5fd; background: #eff6ff; }}
  .asset-name {{ font-family: var(--mono); font-weight: 700; font-size: .9rem; }}
  .asset-tag {{ font-size: .8rem; font-weight: 700; margin: 4px 0; }}
  .asset-desc {{ font-size: .85rem; color: var(--muted); }}

  .term-box {{
    background: #f8fafc; border: 1px solid var(--line); border-radius: 12px; padding: 12px;
  }}
  .term-box h3 {{ margin: 0 0 6px; font-size: .95rem; }}
  .term-out {{
    min-height: 120px; max-height: 260px; overflow: auto; background: #0f172a; color: #e2e8f0;
    border-radius: 8px; padding: 12px; font-family: var(--mono); font-size: .78rem; white-space: pre-wrap;
  }}
  .cmd-row {{ display: flex; gap: 8px; margin-top: 10px; }}
  .cmd-row input {{ flex: 1; }}

  footer {{ margin-top: 24px; color: var(--muted); font-size: .88rem; }}
</style>
</head>
<body>
<div class="wrap">

<header>
  <div class="badge">DEMO · known-path</div>
  <h1>Cari tabel data yang benar — jangan sampai AI salah pilih</h1>
  <p class="lead">
    Aplikasi ini menunjukkan bedanya: AI yang <b>asal cocokkan nama</b> vs AI yang
    <b>ikut daftar resmi + cek aman dulu</b>. Cocok untuk hackathon DataHub.
  </p>
</header>

<section class="howto">
  <div class="step">
    <div class="n">1</div>
    <h3>Pahami datanya</h3>
    <p>Scroll ke bawah: ada tabel <b>benar</b> (hijau) dan tabel <b>jebakan</b> (merah).</p>
  </div>
  <div class="step">
    <div class="n">2</div>
    <h3>Klik salah satu tombol</h3>
    <p>Mulai dari <b>Cara bodoh</b>, lalu <b>Cara known-path</b>, lalu <b>Kalau data rusak</b>.</p>
  </div>
  <div class="step">
    <div class="n">3</div>
    <h3>Lihat hasilnya</h3>
    <p>Perhatikan: tabel mana yang dipilih, berapa kali ambil data, dan SQL-nya.</p>
  </div>
</section>

<section class="card">
  <h2>Apa yang ditanyakan ke AI?</h2>
  <p class="why">Ini permintaan bisnis. Biarkan dulu seperti ini — tidak perlu diubah untuk demo pertama.</p>
  <label for="intent">Pertanyaan</label>
  <textarea id="intent" rows="2">{_esc(DEFAULT_INTENT)}</textarea>

  <div class="btns">
    <button class="btn-warn" id="b1" onclick="go('baseline')">
      ① Cara bodoh (sering salah tabel)
    </button>
    <button class="btn-main" id="b2" onclick="go('known-path')">
      ② Cara known-path (benar)
    </button>
    <button class="btn-danger" id="b3" onclick="go('blocked')">
      ③ Kalau data rusak → berhenti
    </button>
    <button class="btn-alt" id="b4" onclick="goDemo()">
      Jalankan ketiganya
    </button>
  </div>

  <div class="hint">
    <b>Tips:</b> Klik urut ① → ② → ③. Kamu akan lihat:
    <b>salah</b> dulu, lalu <b>benar</b>, lalu <b>berhenti aman</b>.
    Di belakang layar, web memanggil perintah CLI yang sama dengan agent.
  </div>
  <div class="status" id="status">Siap. Belum ada yang dijalankan.</div>
  <div id="result"></div>
</section>

<section class="card">
  <h2>Perbandingan biaya “baca catalog”</h2>
  <p class="why">
    Angka = berapa kali sistem mengambil detail tabel.
    <b>Lebih kecil biasanya lebih bagus</b> (lebih fokus, lebih murah).
  </p>
  <div class="bar-row">
    <div>① Cara bodoh</div>
    <div class="bar-track"><div class="bar-fill base" id="barBase" style="width:0%"></div></div>
    <div id="nBase">0</div>
  </div>
  <div class="bar-row">
    <div>② Known-path</div>
    <div class="bar-track"><div class="bar-fill kp" id="barKp" style="width:0%"></div></div>
    <div id="nKp">0</div>
  </div>
  <div class="bar-row">
    <div>③ Data rusak</div>
    <div class="bar-track"><div class="bar-fill blk" id="barBlk" style="width:0%"></div></div>
    <div id="nBlk">0</div>
  </div>
</section>

<section class="card">
  <h2>Data demo (ini yang dipakai)</h2>
  <p class="why">
    Dataset fiktif <code>demo-finance</code> di folder
    <code>{_esc(dataset_dir())}</code>. Tidak perlu DataHub online untuk coba.
  </p>
  <div class="assets">{''.join(asset_cards)}</div>
  {sample_bits}
</section>

<section class="card">
  <h2>Terminal (untuk yang penasaran)</h2>
  <p class="why">
    Opsional. Ini log perintah yang benar-benar dijalankan di komputer
    (<code>python -m known_path.cli …</code>). Kalau bingung, abaikan bagian ini.
  </p>
  <div class="term-box">
    <h3>Log perintah</h3>
    <div class="term-out" id="term">Belum ada perintah.
Klik tombol di atas, log akan muncul di sini.
</div>
    <div class="cmd-row">
      <input id="cmd" type="text" placeholder="contoh: doctor   atau   run known-path"/>
      <button class="btn-alt" type="button" onclick="sendCmd()">Kirim</button>
    </div>
  </div>
</section>

<footer>
  <p>
    Repo: <a href="https://github.com/SeraKah-1/known-path">github.com/SeraKah-1/known-path</a>
    · Hackathon: <a href="https://datahub.devpost.com">datahub.devpost.com</a>
  </p>
  <p>
    <b>Cara pakai singkat:</b> buka halaman ini → klik ① → baca hasil merah/salah →
    klik ② → baca hasil hijau/benar → klik ③ → sistem berhenti (tidak nebak tabel lain).
  </p>
</footer>

</div>

<script>
const $ = (id) => document.getElementById(id);
const scores = {{ baseline: 0, 'known-path': 0, blocked: 0 }};
const MAX_BAR = 8;

function setBusy(on, msg) {{
  ['b1','b2','b3','b4'].forEach(id => $(id).disabled = on);
  $('status').className = 'status' + (on ? ' busy' : '');
  if (msg) $('status').textContent = msg;
}}

function log(t) {{
  const el = $('term');
  el.textContent += t;
  el.scrollTop = el.scrollHeight;
}}

function updateBars() {{
  const max = Math.max(MAX_BAR, scores.baseline, scores['known-path'], scores.blocked, 1);
  const set = (key, barId, nId) => {{
    const v = scores[key] || 0;
    $(barId).style.width = Math.round(100 * v / max) + '%';
    $(nId).textContent = v;
  }};
  set('baseline', 'barBase', 'nBase');
  set('known-path', 'barKp', 'nKp');
  set('blocked', 'barBlk', 'nBlk');
}}

function humanStatus(st) {{
  if (st === 'SUCCESS') return 'Berhasil';
  if (st === 'BLOCKED_TRUST') return 'Dihentikan (data tidak aman)';
  if (st === 'NO_ROUTE') return 'Tidak ketemu rute';
  return st || '—';
}}

function isTrap(name) {{
  return /revenue_old|rev_backup|old|backup/i.test(name || '');
}}

function renderPlan(plan, title) {{
  if (!plan) return '<p>Tidak ada hasil.</p>';
  const st = plan.status || '';
  let cls = 'warn';
  if (st === 'SUCCESS') cls = 'ok';
  if (st === 'BLOCKED_TRUST') cls = 'bad';

  const activated = (plan.nodes || []).filter(n => n.activated);
  const traps = activated.filter(n => isTrap(n.name));
  let story = '';
  if (st === 'BLOCKED_TRUST') {{
    story = 'Sistem <b>berhenti</b>. Tabel yang dibutuhkan gagal cek aman (mis. deprecated). '
      + '<b>Tidak menebak</b> tabel lain.';
  }} else if (traps.length) {{
    story = '⚠️ AI memilih tabel yang <b>kelihatan mirip namanya</b> tapi <b>salah / tidak layak</b>: '
      + traps.map(t => '<code>' + t.name + '</code>').join(', ') + '.';
  }} else if (st === 'SUCCESS') {{
    story = '✅ AI memakai tabel <b>resmi</b> yang dipercaya Finance. SQL di bawah siap jadi contoh output.';
  }} else {{
    story = plan.message || '';
  }}

  const nodes = (plan.nodes || []).map(n => {{
    let c = 'node off';
    if (n.trust === 'red') c = 'node red';
    else if (n.activated) c = 'node on';
    const lamp = n.activated ? 'NYALA' : (n.trust === 'red' ? 'MERAH' : 'mati');
    return `<div class="${{c}}">
      <div class="nm">${{n.name || ''}}</div>
      <div class="meta">${{lamp}} · trust: ${{n.trust}} · skor ${{n.relevance}}</div>
    </div>`;
  }}).join('');

  const sql = plan.sql_artifact
    ? `<p><b>SQL yang dihasilkan</b></p><pre>${{escapeHtml(plan.sql_artifact)}}</pre>`
    : '<p><i>Tidak ada SQL (berhenti sebelum generate).</i></p>';

  return `<div class="result ${{cls}}">
    <h3>${{title || plan.mode || 'Hasil'}}</h3>
    <p class="big">${{story}}</p>
    <div class="kv">
      <b>Status</b><div>${{humanStatus(st)}} <code>(${{st}})</code></div>
      <b>Ambil detail</b><div>${{plan.entity_fetches ?? '—'}} kali</div>
      <b>Tabel nyala</b><div>${{activated.length}} buah</div>
      <b>Pesan sistem</b><div>${{escapeHtml(plan.message || '—')}}</div>
    </div>
    <p><b>Peta singkat tabel</b> (hijau = dipakai, merah = ditolak, abu = tidak dipakai)</p>
    <div class="nodes">${{nodes}}</div>
    ${{sql}}
  </div>`;
}}

function escapeHtml(s) {{
  return String(s ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
}}

async function go(mode) {{
  const intent = $('intent').value.trim();
  const titles = {{
    baseline: '① Hasil cara bodoh',
    'known-path': '② Hasil known-path',
    blocked: '③ Hasil kalau data rusak'
  }};
  setBusy(true, 'Sedang menjalankan perintah di terminal…');
  log('\\n--- Menjalankan ' + mode + ' ---\\n');
  try {{
    const r = await fetch('/api/cli/run?mode=' + encodeURIComponent(mode)
      + '&intent=' + encodeURIComponent(intent));
    const data = await r.json();
    if (data.command) log('$ ' + data.command + '\\n');
    if (data.stdout) log(data.stdout + (data.stdout.endsWith('\\n') ? '' : '\\n'));
    if (data.stderr) log(data.stderr + '\\n');
    log('[selesai ' + data.duration_ms + ' ms, kode ' + data.exit_code + ']\\n');

    if (data.error && !data.plan) {{
      $('status').className = 'status err';
      $('status').textContent = 'Gagal: ' + data.error;
      $('result').innerHTML = '<div class="result bad"><p>' + escapeHtml(data.error) + '</p></div>';
      return;
    }}
    const plan = data.plan || {{}};
    const key = plan.mode === 'blocked' ? 'blocked' : (plan.mode || mode);
    scores[key] = plan.entity_fetches || 0;
    if (mode === 'blocked') scores.blocked = plan.entity_fetches || 0;
    if (mode === 'baseline') scores.baseline = plan.entity_fetches || 0;
    if (mode === 'known-path') scores['known-path'] = plan.entity_fetches || 0;
    updateBars();
    $('result').innerHTML = renderPlan(plan, titles[mode] || mode);
    $('status').className = 'status';
    $('status').textContent = 'Selesai. Baca kotak hasil di bawah tombol.';
    $('result').scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
  }} catch (e) {{
    $('status').className = 'status err';
    $('status').textContent = String(e);
  }} finally {{
    setBusy(false);
  }}
}}

async function goDemo() {{
  setBusy(true, 'Menjalankan 3 cara berurutan…');
  log('\\n--- Full demo (3x CLI) ---\\n');
  try {{
    const r = await fetch('/api/cli/demo?intent=' + encodeURIComponent($('intent').value.trim()));
    const data = await r.json();
    if (data.command) log('$ ' + data.command + '\\n');
    if (data.stdout) log(data.stdout + '\\n');
    const plans = data.plans || [];
    plans.forEach(p => {{
      const m = p.mode || '';
      if (m === 'baseline') scores.baseline = p.entity_fetches || 0;
      if (m === 'known-path') scores['known-path'] = p.entity_fetches || 0;
      if (m === 'blocked') scores.blocked = p.entity_fetches || 0;
    }});
    updateBars();
    const titles = ['① Cara bodoh', '② Known-path', '③ Data rusak'];
    $('result').innerHTML = plans.map((p, i) => renderPlan(p, titles[i] || p.mode)).join('');
    $('status').textContent = 'Ketiga demo selesai. Bandingkan kotak hasilnya.';
  }} catch (e) {{
    $('status').className = 'status err';
    $('status').textContent = String(e);
  }} finally {{
    setBusy(false);
  }}
}}

async function sendCmd() {{
  const cmd = $('cmd').value.trim();
  if (!cmd) return;
  $('cmd').value = '';
  log('\\n$ ' + cmd + '\\n');
  setBusy(true, 'Menjalankan perintah agent…');
  try {{
    const r = await fetch('/api/agent', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{ command: cmd, intent: $('intent').value }})
    }});
    const data = await r.json();
    if (data.stdout) log(data.stdout + '\\n');
    if (data.stderr) log(data.stderr + '\\n');
    if (data.error) log('error: ' + data.error + '\\n');
    if (data.plan) {{
      $('result').innerHTML = renderPlan(data.plan, 'Hasil perintah');
      const m = data.plan.mode || 'known-path';
      scores[m] = data.plan.entity_fetches || 0;
      updateBars();
    }}
    $('status').textContent = data.ok ? 'Perintah selesai.' : (data.error || 'Selesai dengan error.');
  }} catch (e) {{
    $('status').className = 'status err';
    $('status').textContent = String(e);
  }} finally {{
    setBusy(false);
  }}
}}
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
                    "name": a.name,
                    "certified": a.certified,
                    "deprecated": a.deprecated,
                    "quality_fail": a.quality_fail,
                    "description": a.description,
                }
                for a in demo_catalog()
            ]
            self._json(200, {"assets": assets, "samples": list_sample_files()})
            return

        if path in ("/api/run", "/api/cli/run"):
            mode = (qs.get("mode") or ["known-path"])[0]
            intent = (qs.get("intent") or [DEFAULT_INTENT])[0]
            self._json(200, result_to_dict(run_mode_via_cli(mode, intent)))
            return

        if path in ("/api/cli/demo", "/api/demo"):
            intent = (qs.get("intent") or [DEFAULT_INTENT])[0]
            self._json(200, result_to_dict(run_demo_via_cli(intent=intent)))
            return

        self._send(404, b"not found", "text/plain; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path or "/"
        if path == "/api/agent":
            body = self._read_json()
            cmd = (body.get("command") or "").strip()
            if cmd.lower() in ("run known-path", "run baseline", "run blocked") and body.get("intent"):
                cmd = f"{cmd} {body['intent']}"
            self._json(200, result_to_dict(agent_command(cmd)))
            return
        self._send(404, b"not found", "text/plain; charset=utf-8")


def serve(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, open_browser: bool = False) -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print(f"known-path demo (mudah dibaca) → {url}")
    print(f"dataset → {dataset_dir()}")
    print("Tekan Ctrl+C untuk berhenti.")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nberhenti.")
    finally:
        httpd.server_close()


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="known-path simple web demo")
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--open", action="store_true")
    args = p.parse_args()
    serve(host=args.host, port=args.port, open_browser=args.open)


if __name__ == "__main__":
    main()
