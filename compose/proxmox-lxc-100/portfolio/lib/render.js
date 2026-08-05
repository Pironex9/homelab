import { buildRegister } from './register.js';

function escapeHtml(str) {
  return String(str ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

// Directory slugs ("anime-karakter") become display labels ("Anime karakter").
function displayName(slug) {
  const spaced = String(slug).replace(/[-_]+/g, ' ').trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

const MONTHS = [
  'jan', 'febr', 'márc', 'ápr', 'máj', 'jún',
  'júl', 'aug', 'szept', 'okt', 'nov', 'dec',
];

// Dates are opaque display strings by contract, so anything that is not a
// plain ISO date is shown exactly as it was typed rather than mangled.
function stampDate(date) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(date || ''));
  if (!m) return date || '';
  return `${m[1]} ${MONTHS[Number(m[2]) - 1]} ${Number(m[3])}.`;
}

function tableDate(date) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(date || ''));
  return m ? `${m[1]}.${m[2]}.${m[3]}` : (date || '—');
}

const CSS = `
:root{
  /* The cabinet, not the gallery wall. Colours are the register's own
     materials: japanned steel, oxblood buckram, conservation board, aniline
     stamp ink, brass. */
  --steel:#171a20;
  --steel-2:#1e222a;
  --steel-3:#262b35;
  --ox:#6e2029;
  --ox-lit:#8a2833;
  --board:#9aa7b4;
  --board-ink:#20242c;
  --brass:#b08d4f;
  --brass-dim:#7d6438;
  --ink:#dfe3e9;
  --ink-soft:#98a1af;
  /* Two violets, because one cannot carry both grounds: the dark ink is the
     stamp on the board card, the light one is the same stamp on steel.
     Using the dark one on steel fails contrast outright. */
  --stamp:#4a2d7a;
  --stamp-lit:#9b8ae0;
  --shadow:0 2px 4px rgba(0,0,0,.45),0 18px 44px rgba(0,0,0,.5);
  --shadow-lift:0 3px 6px rgba(0,0,0,.5),0 26px 60px rgba(0,0,0,.6);
  --label:600 .75rem/1.1 'Archivo Narrow',system-ui,sans-serif;
  --data:400 .75rem/1.4 'Courier Prime',ui-monospace,monospace;
}
*,*::before,*::after{box-sizing:border-box}
html{scrollbar-gutter:stable}
body{
  margin:0;
  background:var(--steel);
  color:var(--ink);
  font-family:'Archivo Narrow',system-ui,sans-serif;
  -webkit-font-smoothing:antialiased;
}
:focus-visible{outline:2px solid var(--brass);outline-offset:2px}

.skip{
  position:absolute;left:-9999px;top:0;z-index:60;
  background:var(--board);color:var(--board-ink);padding:.6rem 1rem;
  font:var(--label);letter-spacing:.14em;text-transform:uppercase;
}
.skip:focus{left:.5rem;top:.5rem}

/* ---- top rail: the drawer front ------------------------------------- */
.rail{
  display:flex;align-items:center;gap:1rem;flex-wrap:wrap;
  background:var(--ox);
  border-bottom:1px solid var(--brass-dim);
  padding:.7rem clamp(.9rem,3vw,2rem);
}
.rail .name{
  font-weight:700;font-size:1.9rem;letter-spacing:.1em;text-transform:uppercase;
  margin:0;
}
.rail .count{
  font:var(--data);color:#e7d9c4;letter-spacing:.06em;margin-left:auto;
}
.views{display:flex;gap:0}
.views button{
  appearance:none;cursor:pointer;
  font:var(--label);letter-spacing:.16em;text-transform:uppercase;
  color:#e7d9c4;background:transparent;
  border:1px solid rgba(231,217,196,.35);
  padding:.45rem .85rem;
}
.views button + button{border-left:none}
.views button[aria-pressed="true"]{
  background:var(--board);color:var(--board-ink);border-color:var(--board);
}

/* ---- register title band --------------------------------------------- */
.band{
  padding:1.4rem clamp(.9rem,3vw,2rem);
  border-bottom:1px solid var(--steel-3);
  display:flex;flex-wrap:wrap;align-items:baseline;gap:.4rem 1.4rem;
}
.band p{margin:0;font:var(--data);color:var(--ink-soft);max-width:68ch}
.band .age{
  font:var(--label);letter-spacing:.2em;text-transform:uppercase;color:var(--brass);
}

/* ---- shell: tabs | work | years -------------------------------------- */
.shell{
  display:grid;
  grid-template-columns:minmax(0,1fr);
  gap:0;
}
@media (min-width:60rem){
  .shell{grid-template-columns:auto minmax(0,1fr) auto}
}

/* Category tabs, standing up like drawer dividers. */
.tabs{
  display:flex;gap:.4rem;overflow-x:auto;
  padding:.9rem clamp(.9rem,3vw,2rem);
  border-bottom:1px solid var(--steel-3);
  /* Below the two-column breakpoint the tabs scroll sideways, and a hard cut
     at the right edge reads as a layout bug rather than as more content.
     The fade says there is more without spending a control on saying it. */
  -webkit-mask-image:linear-gradient(to right,#000 88%,transparent 100%);
  mask-image:linear-gradient(to right,#000 88%,transparent 100%);
}
@media (min-width:60rem){
  .tabs{
    flex-direction:column;overflow:visible;
    padding:1.8rem .5rem 1.8rem 1rem;border-bottom:none;
    border-right:1px solid var(--steel-3);
    -webkit-mask-image:none;mask-image:none;
  }
}
.tab{
  appearance:none;cursor:pointer;white-space:nowrap;
  font:var(--label);letter-spacing:.14em;text-transform:uppercase;
  color:var(--ink-soft);
  background:linear-gradient(180deg,var(--steel-3),var(--steel-2));
  border:1px solid var(--brass-dim);border-radius:2px;
  padding:.5rem .8rem;
}
.tab:hover{color:var(--ink)}
.tab[aria-pressed="true"]{
  background:linear-gradient(180deg,#d3ab63,var(--brass));
  color:#231b0c;border-color:#e0be7d;
}

.work{padding:clamp(1.4rem,3vw,2.6rem) clamp(.9rem,3vw,2rem) 4rem;min-width:0}

/* ---- the lead: selected works ---------------------------------------- */
.lead{
  display:grid;gap:clamp(1.2rem,3vw,2.4rem);
  grid-template-columns:repeat(auto-fit,minmax(15rem,1fr));
  margin:0 0 clamp(2.4rem,5vw,4rem);
}
.lead figure{margin:0;display:flex;flex-direction:column;gap:.7rem}
/* One height for all three, the way works are hung on a common centre line.
   Without it a portrait beside two landscapes makes the row twice as tall as
   it needs to be and leaves a hole where the short ones stop. */
.lead .sheet{
  background:#f4f2ec;padding:.75rem;box-shadow:var(--shadow);border-radius:2px;
  height:clamp(13rem,25vw,20rem);overflow:hidden;
}
/* The sheet is a mount: a fixed rectangle the drawing sits inside. Sizing the
   image itself and centring it looks equivalent and is not - max-height on a
   grid item does not hold, and a tall drawing then bursts out of its mount
   and over the caption below. Filling the box and letting object-fit do the
   letterboxing cannot overflow. */
.lead img{
  display:block;width:100%;height:100%;object-fit:contain;border-radius:1px;
}
.lead figcaption{display:flex;flex-direction:column;gap:.3rem}
.lead .t{
  font-weight:600;font-size:1rem;line-height:1.25;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;
}
.lead .meta{display:flex;align-items:baseline;gap:.8rem;flex-wrap:wrap}
.lead .no{font:var(--data);color:var(--brass)}

/* The one authored moment: the date stamps land, the way a stamp hits paper.
   They are legible before it runs and legible if it never runs. */
.stamp{
  font:700 1rem/1 'Courier Prime',ui-monospace,monospace;
  letter-spacing:.02em;color:var(--stamp-lit);
  display:inline-block;transform:rotate(-2.5deg);transform-origin:left center;
  animation:stamp .32s cubic-bezier(.16,1,.3,1) backwards;
}
@keyframes stamp{
  from{transform:rotate(-9deg) scale(1.7);opacity:0;filter:blur(1px)}
}
@media (prefers-reduced-motion:reduce){.stamp{animation:none}}

/* ---- the drawer: every work as a card -------------------------------- */
.section-rule{
  display:flex;align-items:center;gap:1rem;margin:0 0 1.4rem;
  font:var(--label);letter-spacing:.2em;text-transform:uppercase;color:var(--brass);
}
.section-rule::after{content:'';flex:1;height:1px;background:var(--brass-dim)}

.drawer{
  display:grid;gap:1rem;
  grid-template-columns:repeat(auto-fill,minmax(9.5rem,1fr));
  margin:0;padding:0;list-style:none;
}
.card{
  display:flex;flex-direction:column;gap:.45rem;
  background:var(--board);border-radius:2px;
  padding:.5rem .5rem .55rem;
  border:1px solid #7f8d9c;
  box-shadow:var(--shadow);
  cursor:pointer;text-align:left;width:100%;
  appearance:none;font-family:inherit;
  transition:transform .18s ease,box-shadow .18s ease;
}
.card:hover{transform:translateY(-3px);box-shadow:var(--shadow-lift)}
/* Cards in a drawer are the same size; that is what makes them a drawer
   rather than a pile. A fixed window with the drawing contained inside keeps
   the grid on one rhythm without cropping anything. */
.card img{
  display:block;width:100%;height:6.5rem;object-fit:contain;
  background:#f4f2ec;border-radius:1px;
}
.card .no{
  font:var(--data);color:var(--board-ink);letter-spacing:.03em;
}
.card .t{
  font-weight:600;font-size:1rem;line-height:1.25;color:var(--board-ink);
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;
}
.is-hidden{display:none !important}

.empty{font:var(--data);color:var(--ink-soft);margin:2rem 0}

/* ---- the ledger view -------------------------------------------------- */
.ledger-wrap{overflow-x:auto}
table.ledger{border-collapse:collapse;width:100%;min-width:38rem}
table.ledger caption{
  text-align:left;font:var(--label);letter-spacing:.2em;text-transform:uppercase;
  color:var(--brass);padding-bottom:.9rem;
}
table.ledger th{
  font:var(--label);letter-spacing:.16em;text-transform:uppercase;
  color:var(--brass);text-align:left;padding:.5rem .7rem;
  border-bottom:1px solid var(--brass-dim);white-space:nowrap;
}
table.ledger td{
  padding:.35rem .7rem;border-bottom:1px solid var(--steel-3);
  font-variant-numeric:tabular-nums;vertical-align:middle;
}
table.ledger tbody tr{cursor:pointer}
table.ledger tbody tr:hover{background:var(--ox)}
table.ledger .no,table.ledger .dt{font:var(--data);color:var(--ink-soft)}
table.ledger tbody tr:hover .no,table.ledger tbody tr:hover .dt{color:#e7d9c4}
table.ledger .t{font-weight:600}
table.ledger .t{
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;
}
table.ledger .th-img{width:3.6rem}
/* Fixed box, contained image: a register's rows have one rhythm, and letting
   each thumbnail set its own height turns the column into a ragged mess.
   contain rather than cover, because cropping a drawing to fit a table is
   the one thing this page must not do. */
table.ledger img{
  display:block;width:3.2rem;height:2.4rem;object-fit:contain;
  background:#f4f2ec;border-radius:1px;
}

/* ---- the year rail ---------------------------------------------------- */
.years{
  display:flex;gap:.4rem;overflow-x:auto;
  padding:.9rem clamp(.9rem,3vw,2rem);
  border-top:1px solid var(--steel-3);
}
@media (min-width:60rem){
  .years{
    flex-direction:column;overflow:visible;
    padding:1.8rem 1rem 1.8rem .5rem;border-top:none;
    border-left:1px solid var(--steel-3);
  }
}
.year{
  appearance:none;cursor:pointer;
  font:var(--data);letter-spacing:.14em;color:var(--ink-soft);
  background:transparent;border:1px solid transparent;border-radius:2px;
  padding:.35rem .6rem;white-space:nowrap;
}
.year:hover{color:var(--ink)}
.year[aria-pressed="true"]{color:#231b0c;background:var(--brass);border-color:#e0be7d}

/* ---- detail overlay: one work and its catalogue card ------------------ */
.detail{
  position:fixed;inset:0;z-index:50;
  background:rgba(11,13,17,.96);
  display:grid;grid-template-rows:auto 1fr;
  padding:0;
}
.detail[hidden]{display:none}
.detail-bar{
  display:flex;align-items:center;gap:1rem;
  background:var(--ox);border-bottom:1px solid var(--brass-dim);
  padding:.55rem clamp(.9rem,3vw,2rem);
}
.detail-bar .pos{font:var(--data);color:#e7d9c4;letter-spacing:.08em}
.detail-bar .spacer{flex:1}
.detail-bar button{
  appearance:none;cursor:pointer;background:transparent;
  border:1px solid rgba(231,217,196,.35);color:#e7d9c4;
  font:var(--label);letter-spacing:.12em;text-transform:uppercase;
  padding:.4rem .7rem;
}
.detail-bar button:hover{background:rgba(231,217,196,.12)}
.detail-body{
  display:grid;gap:clamp(1rem,3vw,2.5rem);align-content:start;
  grid-template-columns:minmax(0,1fr);
  padding:clamp(1rem,3vw,2.4rem);overflow:auto;
}
@media (min-width:56rem){
  .detail-body{grid-template-columns:minmax(0,1fr) 20rem;align-items:start}
}
.detail-stage{
  display:grid;place-items:center;min-height:0;
  background:#f4f2ec;padding:clamp(.6rem,2vw,1.1rem);
  box-shadow:var(--shadow);border-radius:2px;
}
.detail-stage img{display:block;max-width:100%;height:auto;border-radius:1px}
.detail-stage.zoomable img{cursor:zoom-in}
.detail-stage.zoomed{overflow:auto;place-items:start}
.detail-stage.zoomed img{max-width:none;cursor:zoom-out}

/* The catalogue card. Real text on real board - the stamp is a transform on
   a live date, never an image, so it stays selectable and translatable. */
.slip{
  background:var(--board);color:var(--board-ink);
  border:1px solid #7f8d9c;border-radius:2px;
  box-shadow:var(--shadow);padding:1.1rem 1.2rem 1.3rem;
}
.slip dl{margin:0;display:grid;grid-template-columns:auto minmax(0,1fr);gap:.55rem .9rem}
.slip dt{
  font:var(--label);letter-spacing:.14em;text-transform:uppercase;
  color:#4a5361;white-space:nowrap;
}
.slip dd{margin:0;font:var(--data);color:var(--board-ink);word-break:break-word}
.slip dd.title{font-family:'Archivo Narrow',system-ui,sans-serif;font-weight:600;font-size:1rem}
.slip .stamp{color:var(--stamp);animation:none}

footer{
  padding:2.5rem clamp(.9rem,3vw,2rem) 3rem;
  border-top:1px solid var(--steel-3);
  font:var(--data);color:var(--ink-soft);
}

/* ---- print: the ledger IS the school's sheet -------------------------- */
@media print{
  @page{size:A3 portrait;margin:14mm}
  body{background:#fff;color:#000}
  .rail,.tabs,.years,.detail,.views,.skip,footer,.section-rule{display:none !important}
  .band{border:none;padding:0 0 8mm}
  .band p,.band .age{color:#000}
  .shell{display:block}
  .work{padding:0}
  .lead{page-break-after:always;margin-bottom:0}
  .lead .sheet{box-shadow:none;padding:0;background:none}
  .stamp{color:#000;animation:none}
  #view-fiok .drawer{display:none}
  #view-naplo{display:block !important}
  table.ledger caption{color:#000}
  table.ledger th{color:#000;border-bottom:1px solid #000}
  table.ledger td{border-bottom:1px solid #bbb}
  table.ledger .no,table.ledger .dt{color:#333}
}
`;

const CLIENT_JS = `
(function () {
  var shell = document.getElementById('shell');
  var cards = Array.prototype.slice.call(document.querySelectorAll('[data-work]'));
  var state = { cat: 'all', year: 'all' };

  function matches(el) {
    return (state.cat === 'all' || el.dataset.cat === state.cat)
      && (state.year === 'all' || el.dataset.year === state.year);
  }

  function applyFilter() {
    var shown = 0;
    cards.forEach(function (el) {
      var ok = matches(el);
      el.classList.toggle('is-hidden', !ok);
      if (ok && el.dataset.view === 'fiok') shown++;
    });
    document.getElementById('drawer-empty').hidden = shown > 0;
    document.getElementById('drawer-count').textContent = shown;
  }

  function bindGroup(selector, key) {
    var buttons = Array.prototype.slice.call(document.querySelectorAll(selector));
    buttons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        // Clicking the active filter clears it, which is what people try first.
        state[key] = state[key] === btn.dataset.value ? 'all' : btn.dataset.value;
        buttons.forEach(function (b) {
          b.setAttribute('aria-pressed', String(b.dataset.value === state[key]));
        });
        applyFilter();
      });
    });
  }

  bindGroup('.tab', 'cat');
  bindGroup('.year', 'year');

  // The view lives in the hash so a link can point straight at the register -
  // useful when the whole list is what someone asked to see.
  function setView(view) {
    if (view !== 'naplo') view = 'fiok';
    shell.dataset.view = view;
    document.querySelectorAll('.views button').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.view === view));
    });
    document.getElementById('view-fiok').hidden = view !== 'fiok';
    document.getElementById('view-naplo').hidden = view !== 'naplo';
  }

  document.querySelectorAll('.views button').forEach(function (btn) {
    btn.addEventListener('click', function () {
      history.replaceState(null, '', btn.dataset.view === 'naplo' ? '#naplo' : '#fiok');
      setView(btn.dataset.view);
    });
  });

  window.addEventListener('hashchange', function () {
    setView(location.hash.replace('#', ''));
  });
  if (location.hash) setView(location.hash.replace('#', ''));

  /* ---- detail overlay ---- */
  var detail = document.getElementById('detail');
  var stage = document.getElementById('detail-stage');
  var img = document.getElementById('detail-img');
  var order = [];
  var index = 0;
  var lastFocus = null;

  function visibleOfView() {
    var view = shell.dataset.view;
    return cards.filter(function (el) {
      return el.dataset.view === view && !el.classList.contains('is-hidden');
    });
  }

  function fill(el) {
    var d = el.dataset;
    img.src = d.full;
    img.alt = d.title;
    stage.classList.remove('zoomed', 'zoomable');
    document.getElementById('d-no').textContent = d.no;
    document.getElementById('d-title').textContent = d.title;
    document.getElementById('d-cat').textContent = d.catLabel;
    var tech = document.getElementById('d-tech-row');
    document.getElementById('d-tech').textContent = d.tech || '';
    tech.hidden = !d.tech;
    var dateRow = document.getElementById('d-date-row');
    document.getElementById('d-date').textContent = d.stamp || '';
    dateRow.hidden = !d.stamp;
    document.getElementById('d-pos').textContent = (index + 1) + ' / ' + order.length;
  }

  function open(el) {
    order = visibleOfView();
    index = Math.max(0, order.indexOf(el));
    lastFocus = el;
    fill(el);
    detail.hidden = false;
    document.body.style.overflow = 'hidden';
    document.getElementById('d-close').focus();
  }

  function close() {
    detail.hidden = true;
    document.body.style.overflow = '';
    if (lastFocus) lastFocus.focus();
  }

  function step(delta) {
    if (order.length === 0) return;
    index = (index + delta + order.length) % order.length;
    fill(order[index]);
  }

  cards.forEach(function (el) {
    el.addEventListener('click', function () { open(el); });
  });

  document.getElementById('d-close').addEventListener('click', close);
  document.getElementById('d-prev').addEventListener('click', function () { step(-1); });
  document.getElementById('d-next').addEventListener('click', function () { step(1); });

  // Zoom is offered only when the file actually holds more pixels than we are
  // showing; blowing up a small scan just makes it blurry.
  img.addEventListener('load', function () {
    stage.classList.toggle('zoomable', img.naturalWidth > img.clientWidth + 8);
  });
  img.addEventListener('click', function () {
    if (stage.classList.contains('zoomable')) stage.classList.toggle('zoomed');
  });

  document.addEventListener('keydown', function (e) {
    if (detail.hidden) return;
    if (e.key === 'Escape') close();
    if (e.key === 'ArrowLeft') step(-1);
    if (e.key === 'ArrowRight') step(1);
  });

  applyFilter();
}());
`;

function workData(image, categoryLabel) {
  return [
    `data-work`,
    `data-cat="${escapeHtml(image.category)}"`,
    `data-cat-label="${escapeHtml(categoryLabel)}"`,
    `data-year="${escapeHtml(image.date ? String(image.date).slice(0, 4) : 'nincs')}"`,
    `data-no="${escapeHtml(image.accession)}"`,
    `data-title="${escapeHtml(image.title)}"`,
    `data-tech="${escapeHtml(image.technique || '')}"`,
    `data-stamp="${escapeHtml(image.date ? stampDate(image.date) : '')}"`,
    `data-full="${escapeHtml(image.full)}"`,
  ].join(' ');
}

export function renderIndexHtml({ bio, categories }) {
  const register = buildRegister(categories);
  const label = (slug) => bio.categories?.[slug] || displayName(slug);

  const tabs = categories.map((c) => `
        <button class="tab" type="button" data-value="${escapeHtml(c.name)}"
                aria-pressed="false">${escapeHtml(label(c.name))}</button>`).join('');

  const years = register.years.map((y) => `
        <button class="year" type="button" data-value="${escapeHtml(y)}"
                aria-pressed="false">${escapeHtml(y)}</button>`).join('');

  const lead = register.featured.map((image, i) => `
          <figure>
            <div class="sheet">
              <img src="${escapeHtml(image.thumb)}" alt="${escapeHtml(image.title)}"
                   ${image.width ? `width="${Number(image.width)}" height="${Number(image.height)}"` : ''}>
            </div>
            <figcaption>
              <span class="t">${escapeHtml(image.title)}</span>
              <span class="meta">
                <span class="no">${escapeHtml(image.accession)}</span>
                ${image.date ? `<span class="stamp" style="animation-delay:${180 + i * 130}ms">${escapeHtml(stampDate(image.date))}</span>` : ''}
              </span>
            </figcaption>
          </figure>`).join('');

  const drawer = register.all.map((image) => `
          <li><button class="card" type="button" data-view="fiok" ${workData(image, label(image.category))}>
            <img src="${escapeHtml(image.thumb)}" alt="${escapeHtml(image.title)}"
                 loading="lazy" decoding="async"
                 ${image.width ? `width="${Number(image.width)}" height="${Number(image.height)}"` : ''}>
            <span class="no">${escapeHtml(image.accession)}</span>
            <span class="t">${escapeHtml(image.title)}</span>
          </button></li>`).join('');

  const rows = register.all.map((image) => `
              <tr data-view="naplo" ${workData(image, label(image.category))}>
                <td class="no">${escapeHtml(image.accession)}</td>
                <td><img src="${escapeHtml(image.thumb)}" alt="" loading="lazy" decoding="async"></td>
                <td class="t">${escapeHtml(image.title)}</td>
                <td>${escapeHtml(label(image.category))}</td>
                <td>${escapeHtml(image.technique || '—')}</td>
                <td class="dt">${escapeHtml(tableDate(image.date))}</td>
              </tr>`).join('');

  const total = register.all.length;
  const since = register.firstDate
    ? `${String(register.firstDate).slice(0, 4)} óta`
    : 'dátum nélkül';

  return `<!DOCTYPE html>
<html lang="hu">
<head>
<meta charset="utf-8">
<title>${escapeHtml(bio.name)} – rajzok</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<meta name="theme-color" content="#171a20">
<meta name="description" content="${escapeHtml(bio.name)} rajzai, leltár szerint: ${total} tétel, ${escapeHtml(since)}.">
<link rel="stylesheet" href="fonts.css">
<style>${CSS}</style>
</head>
<body>
<!--
THESIS: a growing accession register, not a gallery wall. It refuses the
masonry-of-matted-thumbnails arrangement this category always ships.
OWN-WORLD: japanned steel #171a20 ground, oxblood buckram rails, blue-grey
conservation board cards, aniline violet reserved for dates only, brass
hairlines and tabs; Archivo Narrow caps over Courier Prime data, 2px corners.
STORY: the visitor sees selected work first, then that it is one numbered,
dated collection spanning years, then looks closely at one drawing.
FIRST VIEWPORT: oxblood rail with name and count; register band; selected
works across the full width, each date landing as a violet stamp; the drawer
of every work below; category tabs left, year rail right.
FORM: candidate 3 of the grounded list (accession register), seed d52c906f.
FINISH: unreviewed and undocumented is unfinished; this build ends with the
finish review, the verdict, and DESIGN.md.
-->
<a class="skip" href="#work">Ugrás a rajzokhoz</a>

<div class="rail">
  <p class="name">${escapeHtml(bio.name)}</p>
  <div class="views">
    <button type="button" data-view="fiok" aria-pressed="true">Fiók</button>
    <button type="button" data-view="naplo" aria-pressed="false">Napló</button>
  </div>
  <span class="count">${total} tétel · ${escapeHtml(since)}</span>
</div>

<div class="band">
  ${bio.age ? `<span class="age">${escapeHtml(bio.age)} éves</span>` : ''}
  <p>${escapeHtml(bio.intro)}</p>
</div>

<div class="shell" id="shell" data-view="fiok">

  <nav class="tabs" aria-label="Kategóriák">${tabs}
  </nav>

  <main class="work" id="work">

    <section id="view-fiok">
      <div class="lead">${lead}
      </div>

      <p class="section-rule"><span>Teljes leltár · <span id="drawer-count">${total}</span> tétel</span></p>
      <ul class="drawer">${drawer}
      </ul>
      <p class="empty" id="drawer-empty" hidden>Ebben a szűrésben nincs tétel.</p>
    </section>

    <section id="view-naplo" hidden>
      <div class="ledger-wrap">
        <table class="ledger">
          <caption>Gyarapodási napló · ${total} tétel</caption>
          <thead>
            <tr>
              <th scope="col">Leltári szám</th>
              <th scope="col" class="th-img"><span class="skip">Kép</span></th>
              <th scope="col">Cím</th>
              <th scope="col">Kategória</th>
              <th scope="col">Technika</th>
              <th scope="col">Dátum</th>
            </tr>
          </thead>
          <tbody>${rows}
          </tbody>
        </table>
      </div>
    </section>

  </main>

  <nav class="years" aria-label="Évek">${years}
  </nav>

</div>

<footer>${escapeHtml(bio.name)} · ${new Date().getFullYear()}</footer>

<div class="detail" id="detail" hidden role="dialog" aria-modal="true" aria-label="Tétel">
  <div class="detail-bar">
    <span class="pos" id="d-pos"></span>
    <span class="spacer"></span>
    <button type="button" id="d-prev">Előző</button>
    <button type="button" id="d-next">Következő</button>
    <button type="button" id="d-close">Bezárás</button>
  </div>
  <div class="detail-body">
    <!-- No src attribute: an empty one resolves to this page's own URL and
         the browser fetches the HTML again as an image. JS sets it on open. -->
    <div class="detail-stage" id="detail-stage"><img id="detail-img" alt=""></div>
    <div class="slip">
      <dl>
        <dt>Leltári szám</dt><dd id="d-no"></dd>
        <dt>Cím</dt><dd class="title" id="d-title"></dd>
        <dt>Kategória</dt><dd id="d-cat"></dd>
        <div id="d-tech-row" style="display:contents"><dt>Technika</dt><dd id="d-tech"></dd></div>
        <div id="d-date-row" style="display:contents"><dt>Dátum</dt><dd><span class="stamp" id="d-date"></span></dd></div>
      </dl>
    </div>
  </div>
</div>

<script>${CLIENT_JS}</script>
</body>
</html>`;
}
