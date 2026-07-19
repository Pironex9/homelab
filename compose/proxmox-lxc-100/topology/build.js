import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import yaml from 'js-yaml';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_NODES_PATH = path.join(__dirname, 'nodes.yml');
const DEFAULT_DIST_DIR = path.join(__dirname, 'dist');

export function loadData(nodesPath = DEFAULT_NODES_PATH) {
  const data = yaml.load(fs.readFileSync(nodesPath, 'utf8'));
  for (const key of ['sites', 'kinds', 'nodes']) {
    if (!data?.[key]) throw new Error(`nodes.yml: missing "${key}"`);
  }
  const siteIds = new Set(data.sites.map((s) => s.id));
  for (const node of data.nodes) {
    for (const field of ['badge', 'name', 'site', 'kind', 'role', 'detail']) {
      if (!node[field]) throw new Error(`nodes.yml: node "${node.name || node.badge || '?'}" missing "${field}"`);
    }
    if (!data.kinds[node.kind]) throw new Error(`nodes.yml: node "${node.name}" has unknown kind "${node.kind}"`);
    if (!siteIds.has(node.site)) throw new Error(`nodes.yml: node "${node.name}" has unknown site "${node.site}"`);
    if (node.ip) node.ip = String(node.ip);
  }
  for (const site of data.sites) {
    const heads = data.nodes.filter((n) => n.site === site.id && n.head);
    if (heads.length !== 1) throw new Error(`nodes.yml: site "${site.id}" needs exactly one head node, found ${heads.length}`);
  }
  return data;
}

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

function nodeCard(node, kinds) {
  const cls = node.head ? 'card head-card' : 'card';
  return `<button class="${cls}" type="button" data-node="${esc(node.name)}" style="--c:${esc(kinds[node.kind].color)}">
    <span class="badge">${esc(node.badge)}</span>
    <span class="nname">${esc(node.name)}</span>
    <span class="nip">${esc(node.ip || 'dhcp')}</span>
    <span class="nrole">${esc(node.role)}</span>
  </button>`;
}

function siteSection(site, nodes, kinds) {
  const head = nodes.find((n) => n.head);
  const children = nodes.filter((n) => !n.head);
  return `<section class="site" data-site="${esc(site.id)}">
    <header class="site-h">
      <h2>${esc(site.label)}</h2>
      <span class="subnet">${esc(site.subnet)}</span>
    </header>
    <svg class="wires" aria-hidden="true"></svg>
    <div class="head-row">${nodeCard(head, kinds)}</div>
    <div class="node-grid">${children.map((n) => nodeCard(n, kinds)).join('\n')}</div>
  </section>`;
}

export function renderHtml(data) {
  const built = new Date().toISOString().slice(0, 10);
  const legend = Object.values(data.kinds)
    .map((k) => `<li><span class="dot" style="--c:${esc(k.color)}"></span>${esc(k.label)}</li>`)
    .join('');
  const sections = [];
  for (const site of data.sites) {
    // a site's `link` is how it is reached, so the uplink renders above it
    if (site.link) sections.push(`<div class="uplink"><span>${esc(site.link)}</span></div>`);
    const nodes = data.nodes.filter((n) => n.site === site.id);
    sections.push(siteSection(site, nodes, data.kinds));
  }
  const json = JSON.stringify(data).replace(/</g, '\\u003c');

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>homelab.topology</title>
<meta name="description" content="Interactive network topology map of a self-hosted Proxmox homelab.">
<meta name="robots" content="noindex">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@500;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #0b1120;
  --panel: #101a30;
  --line: #22304d;
  --text: #d6e2f0;
  --muted: #7d8fa9;
  --wire: rgba(125, 165, 220, .35);
}
* { box-sizing: border-box; margin: 0; }
html { scrollbar-gutter: stable; }
body {
  font-family: "IBM Plex Mono", monospace;
  color: var(--text);
  background:
    radial-gradient(1100px 480px at 50% -8%, rgba(92, 200, 255, .09), transparent 70%),
    linear-gradient(rgba(125, 165, 220, .055) 1px, transparent 1px) 0 0 / 34px 34px,
    linear-gradient(90deg, rgba(125, 165, 220, .055) 1px, transparent 1px) 0 0 / 34px 34px,
    var(--bg);
  min-height: 100vh;
}
.frame { max-width: 1280px; margin: 0 auto; padding: 40px 24px 80px; }

/* ---- header ---- */
.top { margin-bottom: 36px; }
.brand {
  font-family: "Big Shoulders Display", sans-serif;
  font-weight: 800;
  font-size: clamp(44px, 7vw, 84px);
  line-height: .95;
  letter-spacing: .01em;
  text-transform: uppercase;
}
.brand em { font-style: normal; color: #5cc8ff; }
.tagline { color: var(--muted); font-size: 13px; margin-top: 10px; }
.tagline b { color: var(--text); font-weight: 500; }
.meta-row {
  display: flex; flex-wrap: wrap; gap: 10px 28px; align-items: center;
  margin-top: 22px; padding-top: 16px; border-top: 1px solid var(--line);
}
.legend { display: flex; flex-wrap: wrap; gap: 8px 18px; list-style: none; padding: 0; font-size: 12px; color: var(--muted); }
.legend li { display: flex; align-items: center; gap: 7px; }
.dot { width: 9px; height: 9px; background: var(--c); box-shadow: 0 0 8px var(--c); }
.stats { margin-left: auto; font-size: 12px; color: var(--muted); }

/* ---- layout ---- */
.wrap { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 24px; align-items: start; }
.map { display: grid; gap: 0; }

/* ---- site panels ---- */
.site {
  position: relative;
  border: 1px solid var(--line);
  background: linear-gradient(180deg, rgba(16, 26, 48, .8), rgba(11, 17, 32, .55));
  padding: 20px 20px 24px;
}
.site[data-site="remote"] { border-style: dashed; }
.site-h { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; margin-bottom: 18px; }
.site-h h2 {
  font-family: "Big Shoulders Display", sans-serif;
  font-weight: 700; font-size: 20px; letter-spacing: .12em; text-transform: uppercase;
}
.subnet { font-size: 11px; color: var(--muted); border: 1px solid var(--line); padding: 3px 8px; }
.wires { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; }
.wires path { fill: none; stroke: var(--wire); stroke-width: 1.2; transition: stroke .2s; }
.wires path.active { stroke: var(--ac, #5cc8ff); stroke-width: 1.6; stroke-dasharray: 6 5; animation: flow 1.2s linear infinite; }
@keyframes flow { to { stroke-dashoffset: -22; } }

.head-row { display: flex; justify-content: center; margin-bottom: 46px; }
.node-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 40px 14px; }

/* ---- node cards ---- */
.card {
  position: relative; z-index: 1;
  display: grid; gap: 3px; text-align: left;
  font-family: inherit; color: var(--text); cursor: pointer;
  background: #0e1729;
  border: 1px solid var(--line); border-left: 3px solid var(--c);
  padding: 10px 12px 11px;
  transition: transform .15s, border-color .15s, box-shadow .15s;
}
.card:hover { transform: translateY(-2px); border-color: color-mix(in srgb, var(--c) 55%, var(--line)); }
.card:focus-visible { outline: 2px solid var(--c); outline-offset: 2px; }
.card.selected { border-color: var(--c); box-shadow: 0 0 0 1px var(--c), 0 0 22px -6px var(--c); }
.card .badge { font-size: 10px; letter-spacing: .14em; color: var(--c); }
.card .nname { font-family: "Big Shoulders Display", sans-serif; font-weight: 700; font-size: 19px; letter-spacing: .03em; }
.card .nip { font-size: 11px; color: var(--muted); }
.card .nrole { font-size: 10px; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; opacity: .8; }
.head-card { min-width: min(300px, 100%); border-left-width: 1px; border-top: 3px solid var(--c); text-align: center; justify-items: center; }
.head-card .nname { font-size: 26px; }

/* ---- uplink between sites ---- */
.uplink { display: flex; justify-content: center; padding: 4px 0; position: relative; }
.uplink::before { content: ""; position: absolute; top: 0; bottom: 0; left: 50%; border-left: 1px dashed var(--wire); }
.uplink span {
  position: relative; background: var(--bg); border: 1px dashed var(--line);
  color: var(--muted); font-size: 11px; letter-spacing: .18em; text-transform: uppercase;
  padding: 8px 16px; margin: 14px 0;
}

/* ---- detail panel ---- */
.panel {
  position: sticky; top: 24px;
  border: 1px solid var(--line); background: var(--panel);
  padding: 20px;
}
.panel-k { font-size: 10px; letter-spacing: .18em; text-transform: uppercase; color: var(--muted); margin-bottom: 14px; }
.panel h3 {
  font-family: "Big Shoulders Display", sans-serif; font-weight: 800;
  font-size: 34px; line-height: 1; letter-spacing: .02em; margin-bottom: 4px;
}
.panel h3::after { content: "_"; color: var(--ac, #5cc8ff); animation: blink 1.1s steps(1) infinite; }
@keyframes blink { 50% { opacity: 0; } }
.kind-chip {
  display: inline-block; font-size: 10px; letter-spacing: .12em; text-transform: uppercase;
  color: #0b1120; background: var(--ac, #5cc8ff); padding: 3px 8px; margin: 6px 0 16px;
}
.kv { display: grid; grid-template-columns: 64px 1fr; gap: 8px 12px; font-size: 12.5px; border-top: 1px solid var(--line); padding-top: 14px; }
.kv dt { color: var(--muted); text-transform: uppercase; font-size: 10px; letter-spacing: .12em; padding-top: 2px; }
.kv dd { word-break: break-word; }
.panel .detail { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--line); font-size: 12.5px; line-height: 1.65; color: #b7c6da; }
.panel-close { display: none; }

footer { margin-top: 40px; font-size: 11px; color: var(--muted); }
footer a { color: #5cc8ff; text-decoration: none; }
footer a:hover { text-decoration: underline; }

@media (max-width: 980px) {
  .wrap { grid-template-columns: 1fr; }
  .panel {
    position: fixed; inset: auto 0 0 0; z-index: 10; top: auto;
    max-height: 55vh; overflow-y: auto;
    border-left: 0; border-right: 0;
    transform: translateY(105%); transition: transform .25s ease;
  }
  .panel.open { transform: none; box-shadow: 0 -18px 40px rgba(0, 0, 0, .5); }
  .panel-close {
    display: block; position: absolute; top: 12px; right: 14px;
    background: none; border: 1px solid var(--line); color: var(--muted);
    font-family: inherit; font-size: 12px; padding: 4px 10px; cursor: pointer;
  }
}
@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; }
}
</style>
</head>
<body>
<div class="frame">
  <header class="top">
    <h1 class="brand">Homelab<em>.topology</em></h1>
    <p class="tagline">Self-hosted infrastructure map / <b>Proxmox VE 9.1</b> + <b>K3s</b> / generated ${built} from nodes.yml</p>
    <div class="meta-row">
      <ul class="legend">${legend}</ul>
      <span class="stats">${data.nodes.length} nodes / ${data.sites.length} sites</span>
    </div>
  </header>
  <div class="wrap">
    <main class="map">
      ${sections.join('\n')}
      <footer>Static build, no backend / part of <a href="https://docs.homelabor.net">docs.homelabor.net</a></footer>
    </main>
    <aside class="panel" id="panel" aria-live="polite">
      <button class="panel-close" type="button" id="panelClose">close</button>
      <p class="panel-k">// node detail</p>
      <h3 id="pName"></h3>
      <span class="kind-chip" id="pKind"></span>
      <dl class="kv">
        <dt>id</dt><dd id="pBadge"></dd>
        <dt>ip</dt><dd id="pIp"></dd>
        <dt>role</dt><dd id="pRole"></dd>
        <dt>hw</dt><dd id="pHw"></dd>
      </dl>
      <p class="detail" id="pDetail"></p>
    </aside>
  </div>
</div>
<script>
var DATA = ${json};
var byName = {};
DATA.nodes.forEach(function (n) { byName[n.name] = n; });

var panel = document.getElementById('panel');
function show(node) {
  var color = DATA.kinds[node.kind].color;
  panel.style.setProperty('--ac', color);
  document.getElementById('pName').textContent = node.name;
  document.getElementById('pKind').textContent = DATA.kinds[node.kind].label;
  document.getElementById('pBadge').textContent = node.badge;
  document.getElementById('pIp').textContent = node.ip || 'dhcp';
  document.getElementById('pRole').textContent = node.role;
  document.getElementById('pHw').textContent = node.hw || '-';
  document.getElementById('pDetail').textContent = node.detail;
  panel.classList.add('open');
  document.querySelectorAll('.card.selected').forEach(function (c) { c.classList.remove('selected'); });
  document.querySelectorAll('.wires path.active').forEach(function (p) { p.classList.remove('active'); });
  var card = document.querySelector('.card[data-node="' + node.name + '"]');
  if (card) {
    card.classList.add('selected');
    var wire = card.closest('.site').querySelector('path[data-for="' + node.name + '"]');
    if (wire) { wire.classList.add('active'); wire.style.setProperty('--ac', color); }
  }
}

document.querySelectorAll('.card').forEach(function (card) {
  card.addEventListener('click', function () { show(byName[card.dataset.node]); });
});
document.getElementById('panelClose').addEventListener('click', function () {
  panel.classList.remove('open');
});

function drawWires(site) {
  var svg = site.querySelector('.wires');
  var head = site.querySelector('.head-card');
  var rect = site.getBoundingClientRect();
  svg.setAttribute('viewBox', '0 0 ' + rect.width + ' ' + rect.height);
  var hr = head.getBoundingClientRect();
  var x1 = hr.left - rect.left + hr.width / 2;
  var y1 = hr.bottom - rect.top;
  var paths = [];
  site.querySelectorAll('.node-grid .card').forEach(function (card) {
    var cr = card.getBoundingClientRect();
    var x2 = cr.left - rect.left + cr.width / 2;
    var y2 = cr.top - rect.top;
    var my = y1 + (y2 - y1) * 0.55;
    paths.push('<path data-for="' + card.dataset.node + '" d="M' + x1 + ' ' + y1 +
      ' C' + x1 + ' ' + my + ', ' + x2 + ' ' + my + ', ' + x2 + ' ' + y2 + '"/>');
  });
  svg.innerHTML = paths.join('');
}
var sites = document.querySelectorAll('.site');
function drawAll() { sites.forEach(drawWires); }
drawAll();
var t;
window.addEventListener('resize', function () { clearTimeout(t); t = setTimeout(function () {
  drawAll();
  var sel = document.querySelector('.card.selected');
  if (sel) show(byName[sel.dataset.node]);
}, 100); });
document.fonts && document.fonts.ready.then(drawAll);

show(byName['${esc(data.nodes.find((n) => n.head).name)}']);
if (window.matchMedia('(max-width: 980px)').matches) panel.classList.remove('open');
</script>
</body>
</html>`;
}

export function build({ nodesPath = DEFAULT_NODES_PATH, distDir = DEFAULT_DIST_DIR } = {}) {
  const data = loadData(nodesPath);
  const html = renderHtml(data);
  fs.rmSync(distDir, { recursive: true, force: true });
  fs.mkdirSync(distDir, { recursive: true });
  fs.writeFileSync(path.join(distDir, 'index.html'), html);
  fs.writeFileSync(path.join(distDir, 'robots.txt'), 'User-agent: *\nDisallow: /\n');

  for (const node of data.nodes) {
    if (!html.includes(`data-node="${node.name}"`)) {
      throw new Error(`Build check failed: node "${node.name}" missing from index.html`);
    }
    if (node.ip && !html.includes(node.ip)) {
      throw new Error(`Build check failed: IP of "${node.name}" missing from index.html`);
    }
  }
  return data;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  try {
    const data = build();
    console.log(`Build ok: ${data.nodes.length} nodes, ${data.sites.length} sites.`);
  } catch (err) {
    console.error(err.message);
    process.exit(1);
  }
}
