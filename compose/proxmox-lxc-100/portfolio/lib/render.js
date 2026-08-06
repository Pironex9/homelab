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
  --label:600 .75rem/1.4 'Archivo Narrow',system-ui,sans-serif;
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
/* The one sentence on this page in Enci's own words. It was set in the grey
   typewriter face used for accession data, which made the only human voice
   here indistinguishable from machine metadata. */
.band p{
  margin:0;font-family:'Archivo Narrow',system-ui,sans-serif;
  font-weight:600;font-size:1rem;line-height:1.45;color:var(--ink);max-width:60ch;
}
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
/* Brass at rest, not only when pressed. The unfiltered first viewport used
   to contain no brass object at all, against the world's own description. */
.tab{
  appearance:none;cursor:pointer;white-space:nowrap;position:relative;
  font:var(--label);letter-spacing:.14em;text-transform:uppercase;
  color:#2a2213;
  background:linear-gradient(180deg,#c7a35d,var(--brass) 45%,#8a6c38);
  border:1px solid #d8b877;border-top-color:#e8ce97;border-radius:2px;
  padding:.5rem .8rem;
  box-shadow:0 1px 2px rgba(0,0,0,.5);
}
.tab:hover{background:linear-gradient(180deg,#d8b775,#c09b57 45%,#96773e)}
.tab[aria-pressed="true"]{
  background:linear-gradient(180deg,#f0dcae,#dcbd7c);
  color:#231b0c;border-color:#fff0cc;
  box-shadow:0 0 0 1px var(--ox-lit),0 2px 6px rgba(0,0,0,.6);
}

.work{padding:clamp(1.4rem,3vw,2.6rem) clamp(.9rem,3vw,2rem) 4rem;min-width:0}

/* ---- the lead: selected works ---------------------------------------- */
.lead{
  display:grid;gap:clamp(1.2rem,3vw,2.4rem);
  grid-template-columns:repeat(auto-fit,minmax(15rem,1fr));
  margin:0 0 clamp(2.4rem,5vw,4rem);
}
.lead figure{margin:0;display:flex;flex-direction:column;gap:.7rem}
/* The stamp belongs on the paper. Moved into a caption row it stops being a
   stamp and becomes a label, and three of them stop sharing a line the moment
   one title wraps. The work's title is not printed beside the lead images
   (the comp does not) - it lives in the img alt and in the detail view. */
.lead .sheet{position:relative}
.lead .sheet .stamp{position:absolute;right:1rem;bottom:.7rem;color:var(--stamp);z-index:1}
/* One height for all three, the way works are hung on a common centre line.
   Without it a portrait beside two landscapes makes the row twice as tall as
   it needs to be and leaves a hole where the short ones stop. */
.lead .sheet{
  background:#f4f2ec;box-shadow:var(--shadow);border-radius:2px;
  height:clamp(13rem,25vw,20rem);overflow:hidden;
  /* A deeper bottom margin on the mount, because the stamp lives there. Over
     the image it lands on whatever tone the drawing happens to have and the
     date - the one thing the page is arguing - becomes unreadable on a dark
     work. On the mount it is always violet on paper. */
  padding:.75rem .75rem 2.5rem;
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
.find{
  margin-left:auto;display:flex;align-items:center;gap:.5rem;
  text-transform:none;letter-spacing:0;
}
.find label{
  font:var(--label);letter-spacing:.14em;text-transform:uppercase;color:#2a2213;
  background:linear-gradient(180deg,#c7a35d,var(--brass) 45%,#8a6c38);
  padding:.4rem .7rem .35rem;
  clip-path:polygon(0 .3rem,.3rem 0,calc(100% - .3rem) 0,100% .3rem,100% 100%,0 100%);
}
.find input{
  font:var(--data);color:var(--board-ink);
  background:linear-gradient(180deg,#a6b2be,var(--board) 20%);
  border:none;border-top:2px solid var(--brass);
  padding:.4rem .55rem;width:11rem;
}
.find input::placeholder{color:#4a5361}
.find{margin-left:auto;gap:0}

/* A drawer, not a grid of thumbnails. Each work is a die-cut folder: a tab
   on the top-left, the body below it, and the rows interleaved so folders
   overlap their neighbours the way files lean in a real drawer. Built as a
   clip-path silhouette rather than a raster, because a folder is a countable
   flat shape - exactly what a session can specify exactly - and it then
   scales to any card width without a second asset.

   The comp dims its back rows to suggest depth. That is not carried over on
   purpose: the comp shows a drawer with a few files in it, this list is the
   entire collection, and fading real work the panel came to look at trades
   the product's job for an atmosphere effect. */
.drawer{
  display:grid;gap:.55rem .4rem;
  grid-template-columns:repeat(auto-fill,minmax(9.5rem,1fr));
  margin:0;padding:.9rem 0 0;list-style:none;
}
.drawer li{position:relative}
/* Odd columns sit a little proud, so the bank reads as leaning files rather
   than as a table. Neighbours overlap by the negative margin above. */
.drawer li:nth-child(even){transform:translateY(.55rem)}
.card{
  display:flex;flex-direction:column;gap:.45rem;
  background:linear-gradient(180deg,#a6b2be,var(--board) 18%,#8f9dab);
  padding:1.5rem .5rem .6rem;
  box-shadow:var(--shadow);
  cursor:pointer;text-align:left;width:100%;
  appearance:none;font-family:inherit;
  transition:transform .18s ease,box-shadow .18s ease,filter .18s ease;
  /* The die cut: a tab across the left 46% of the top edge, then a shoulder
     down to the full-width body. 2px corners are kept by the tiny steps. */
  clip-path:polygon(
    0 .55rem, .1rem .18rem, .5rem 0, 4.1rem 0, 4.5rem .18rem,
    4.6rem .55rem, 4.6rem 1.1rem, 100% 1.1rem, 100% 100%, 0 100%
  );
}
.card::before{
  /* Brass edge along the tab, the one dimensional material in the bank. */
  content:'';position:absolute;left:0;top:0;width:4.6rem;height:2px;
  background:linear-gradient(90deg,#e0be7d,var(--brass) 60%,var(--brass-dim));
  pointer-events:none;
}
.card:hover{transform:translateY(-4px);box-shadow:var(--shadow-lift);filter:brightness(1.06)}
.card:focus-visible{filter:brightness(1.06)}
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
/* Register furniture: a brass hairline around every cell, the way a ruled
   ledger page is printed, and an active row that stays marked after the
   pointer leaves it. */
table.ledger td{
  padding:.35rem .7rem;border:1px solid var(--brass-dim);
  font-variant-numeric:tabular-nums;vertical-align:middle;
}
table.ledger tbody tr{cursor:pointer}
table.ledger tbody tr:hover,table.ledger tbody tr.is-active{background:var(--ox)}
table.ledger tbody tr.is-active td{border-color:#e0be7d}
table.ledger .no,table.ledger .dt{font:var(--data);color:var(--ink-soft)}
table.ledger tbody tr:hover .no,table.ledger tbody tr:hover .dt,
table.ledger tbody tr.is-active .no,table.ledger tbody tr.is-active .dt{color:#e7d9c4}
table.ledger .t{font-weight:600}
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
/* An oxblood strip down the right edge with the years set into it and a
   machined brass fitting marking the active one - the drawer's index rail.
   Buttons rather than a slider: the composition is a rail either way, and a
   drag control only costs keyboard use. */
.years{
  display:flex;gap:.4rem;overflow-x:auto;align-items:center;
  padding:.7rem clamp(.9rem,3vw,2rem);
  background:var(--ox);border-top:1px solid var(--brass-dim);
}
@media (min-width:60rem){
  .years{
    flex-direction:column;overflow:visible;justify-content:flex-start;
    padding:1rem .55rem 2rem;border-top:none;
    border-left:1px solid var(--brass-dim);
  }
}
/* The rail's own hardware, present before anything is filtered. Same object
   as the active-year marker; a rail with no fitting is a coloured strip. */
.years::before{
  content:'';flex:0 0 auto;
  width:1.9rem;height:1.2rem;
  background:url(img/brass-fitting.png) center/100% 100% no-repeat;
}
@media (min-width:60rem){
  .years::before{width:1.7rem;height:3.4rem;margin-bottom:.9rem}
}
.year{
  appearance:none;cursor:pointer;position:relative;
  font:var(--data);font-weight:700;letter-spacing:.16em;color:#e7d9c4;
  background:transparent;border:none;border-radius:2px;
  padding:.4rem .55rem;white-space:nowrap;
}
@media (min-width:60rem){
  .year{writing-mode:vertical-rl;padding:.9rem .35rem}
}
.year:hover{color:#fff}
/* The fitting is a real object, photographed and keyed, not a CSS bevel. */
.year[aria-pressed="true"]{
  color:#2a2213;
  background:url(img/brass-fitting.png) center/100% 100% no-repeat;
  text-shadow:0 1px 0 rgba(255,244,214,.5);
  padding:.75rem .8rem;
}
@media (min-width:60rem){
  .year[aria-pressed="true"]{padding:1.3rem .7rem}
}

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
  /* The filmstrip from the approved detail comp: the works either side of this
   one as small folder tabs, so moving through the collection is a place you
   can see rather than two unlabelled buttons. */
.strip{
  display:flex;gap:.35rem;overflow-x:auto;align-items:flex-end;
  background:var(--ox);border-top:1px solid var(--brass-dim);
  padding:.6rem clamp(.9rem,3vw,2rem);
}
.strip button{
  appearance:none;cursor:pointer;flex:0 0 auto;
  width:4.2rem;padding:.55rem .25rem .3rem;
  background:linear-gradient(180deg,#a6b2be,var(--board) 20%,#8f9dab);
  border:none;
  clip-path:polygon(
    0 .3rem, .3rem 0, 2rem 0, 2.3rem .3rem, 2.3rem .55rem,
    100% .55rem, 100% 100%, 0 100%
  );
  opacity:.65;transition:opacity .15s ease,transform .15s ease;
}
.strip button:hover{opacity:1}
.strip button[aria-current="true"]{opacity:1;transform:translateY(-.3rem)}
.strip img{display:block;width:100%;height:2.6rem;object-fit:contain;background:#f4f2ec}
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
/* What comes out of Ctrl+P must not depend on which view happened to be open
   when someone pressed it. The register prints, always: three A/3 sheets of
   selected work first, then the full ledger. Everything interactive goes. */
@media print{
  @page{size:A3 portrait;margin:14mm}
  /* scrollbar-gutter reserves a strip that the print layout keeps, which
     pushes every sheet left until the first character of each line falls off
     the paper. It has no meaning without a scrollbar. */
  html{scrollbar-gutter:auto}
  body{background:#fff;color:#000;margin:0;padding:0}
  .rail,.tabs,.years,.detail,.views,.skip,footer,.find,.strip{display:none !important}
  .band{border:none;padding:0 0 8mm}
  .band p{color:#000;font-size:11pt}
  .band .age{color:#000}
  .shell{display:block}
  .work{padding:0}

  /* Both sections print regardless of the hidden attribute the view toggle
     leaves behind - hidden wins over display:block without the !important. */
  #view-fiok,#view-naplo{display:block !important}
  #view-fiok .drawer,#view-fiok .section-rule{display:none !important}

  /* Three across on one A/3 sheet. overflow and the fixed mount height are
     screen furniture: left on, they clip the stamp off a tall portrait,
     which is the one element this sheet exists to show. */
  .lead{
    page-break-after:always;margin-bottom:0;gap:10mm;
    grid-template-columns:repeat(3,1fr);
  }
  .lead .sheet{
    box-shadow:none;padding:0;background:none;
    height:auto;max-height:none;overflow:visible;
  }
  .lead .sheet .stamp{position:static;display:block;margin-top:3mm;font-size:12pt}
  .lead img{width:100%;height:auto;max-height:150mm;object-fit:contain}
  .lead .no{font-size:10pt}
  .stamp{color:#000;animation:none;transform:none}

  table.ledger{page-break-inside:auto}
  table.ledger tr{page-break-inside:avoid}
  table.ledger caption{color:#000;font-size:12pt}
  table.ledger th{color:#000;border:1px solid #000}
  table.ledger td{border:1px solid #999}
  table.ledger tbody tr.is-active{background:none}
  table.ledger .no,table.ledger .dt{color:#333}
}
`;

const CLIENT_JS = `
(function () {
  var shell = document.getElementById('shell');
  var cards = Array.prototype.slice.call(document.querySelectorAll('[data-work]'));
  var state = { cat: 'all', year: 'all', q: '' };

  function matches(el) {
    var q = state.q;
    return (state.cat === 'all' || el.dataset.cat === state.cat)
      && (state.year === 'all' || el.dataset.year === state.year)
      && (q === '' || (el.dataset.title + ' ' + el.dataset.tech + ' ' + el.dataset.no)
            .toLowerCase().indexOf(q) !== -1);
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

  var find = document.getElementById('find');
  find.addEventListener('input', function () {
    // Accent-insensitive would need a normalize() shim for older engines and
    // buys little: the titles and the query come from the same keyboard.
    state.q = find.value.trim().toLowerCase();
    applyFilter();
  });

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

  window.addEventListener('hashchange', readHash);

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

  function paintStrip() {
    var strip = document.getElementById('d-strip');
    strip.innerHTML = '';
    order.forEach(function (el, i) {
      var b = document.createElement('button');
      b.type = 'button';
      b.title = el.dataset.title;
      b.setAttribute('aria-label', el.dataset.no + ' ' + el.dataset.title);
      if (i === index) b.setAttribute('aria-current', 'true');
      var im = document.createElement('img');
      im.src = el.dataset.thumb;
      im.alt = '';
      b.appendChild(im);
      b.addEventListener('click', function () { index = i; fill(order[i]); });
      strip.appendChild(b);
    });
    var current = strip.children[index];
    if (current) current.scrollIntoView({ block: 'nearest', inline: 'center' });
  }

  function fill(el) {
    var d = el.dataset;
    // The ledger keeps its active row marked after the pointer leaves, so the
    // reader can see where they were when the overlay closes.
    cards.forEach(function (c) { c.classList.remove('is-active'); });
    var twin = cards.filter(function (c) { return c.dataset.no === d.no; });
    twin.forEach(function (c) { c.classList.add('is-active'); });
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
    paintStrip();
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

  // #tetel=CS.001/24 opens one work directly, so a single drawing can be sent
  // as its own link rather than as "the site, then scroll".
  function readHash() {
    var hash = decodeURIComponent(location.hash.replace('#', ''));
    if (hash.indexOf('tetel=') === 0) {
      var want = hash.slice(6);
      var hit = cards.filter(function (c) {
        return c.dataset.view === shell.dataset.view && c.dataset.no === want;
      })[0];
      if (hit) { open(hit); return; }
    }
    setView(hash);
  }
  if (location.hash) readHash();

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
    `data-thumb="${escapeHtml(image.thumb)}"`,
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
              ${image.date ? `<span class="stamp" style="animation-delay:${180 + i * 130}ms">${escapeHtml(stampDate(image.date))}</span>` : ''}
            </div>
            <figcaption>
              <span class="meta"><span class="no">${escapeHtml(image.accession)}</span></span>
            </figcaption>
          </figure>`).join('');

  const drawer = register.all.map((image) => `
          <li><button class="card" type="button" data-view="fiok"
              title="${escapeHtml(image.title)}"
              aria-label="${escapeHtml(image.accession)} – ${escapeHtml(image.title)}"
              ${workData(image, label(image.category))}>
            <img src="${escapeHtml(image.thumb)}" alt="${escapeHtml(image.title)}"
                 loading="lazy" decoding="async"
                 ${image.width ? `width="${Number(image.width)}" height="${Number(image.height)}"` : ''}>
            <span class="no">${escapeHtml(image.accession)}</span>
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

      <p class="section-rule">
        <span>Teljes leltár · <span id="drawer-count">${total}</span> tétel</span>
        <span class="find">
          <label for="find">Keresés</label>
          <input type="search" id="find" autocomplete="off" placeholder="cím vagy technika">
        </span>
      </p>
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
  <nav class="strip" id="d-strip" aria-label="Tételek"></nav>
</div>

<script>${CLIENT_JS}</script>
</body>
</html>`;
}
