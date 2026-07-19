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

// Subtle paper grain, self-contained (no external asset).
const GRAIN = `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='160' height='160' filter='url(%23n)' opacity='0.5'/%3E%3C/svg%3E")`;

const CSS = `
:root{
  --paper:#f5f0e6;
  --ink:#262218;
  --ink-soft:#6d6353;
  --accent:#c1502e;
  --mat:#fffdf8;
  --shadow:0 1px 2px rgba(38,34,24,.10),0 8px 24px rgba(38,34,24,.10);
  --shadow-hover:0 2px 4px rgba(38,34,24,.12),0 16px 40px rgba(38,34,24,.18);
}
*{box-sizing:border-box}
html{scrollbar-gutter:stable}
body{
  margin:0;padding:0 clamp(1rem,4vw,3rem) 4rem;
  font-family:'Karla',system-ui,sans-serif;
  color:var(--ink);background:var(--paper);
  -webkit-font-smoothing:antialiased;
}
body::before{
  content:'';position:fixed;inset:0;pointer-events:none;z-index:1;
  background-image:${GRAIN};opacity:.05;
}
header{max-width:640px;margin:clamp(3rem,8vh,6rem) auto 0;text-align:center}
header h1{
  font-family:'Young Serif',Georgia,serif;font-weight:400;
  font-size:clamp(2.6rem,8vw,4.5rem);line-height:1.05;margin:0;
  letter-spacing:-.01em;
}
header h1::after{content:'.';color:var(--accent)}
.age{
  display:inline-block;margin:1rem 0 0;
  font-size:.78rem;letter-spacing:.22em;text-transform:uppercase;
  color:var(--ink-soft);
}
.age::before,.age::after{content:'—';margin:0 .6em;color:var(--accent);opacity:.6}
.intro{color:var(--ink-soft);line-height:1.65;font-size:1.06rem;margin:1.1rem auto 0;max-width:34em}
.tabs{
  display:flex;flex-wrap:wrap;gap:.25rem 1.75rem;justify-content:center;
  margin:clamp(2rem,5vh,3.5rem) 0 2.5rem;
}
.tab{
  appearance:none;border:none;background:none;padding:.4rem 0;cursor:pointer;
  font-family:inherit;font-size:.85rem;letter-spacing:.14em;text-transform:uppercase;
  color:var(--ink-soft);position:relative;transition:color .2s;
}
.tab::after{
  content:'';position:absolute;left:0;right:0;bottom:0;height:2px;
  background:var(--accent);transform:scaleX(0);transform-origin:center;
  transition:transform .25s ease;
}
.tab:hover{color:var(--ink)}
.tab.active{color:var(--ink)}
.tab.active::after{transform:scaleX(1)}
#gallery{
  columns:3 300px;column-gap:1.75rem;
  max-width:1200px;margin:0 auto;position:relative;z-index:0;
}
#gallery figure{
  margin:0 0 1.75rem;break-inside:avoid;cursor:pointer;
  background:var(--mat);padding:12px 12px 10px;
  box-shadow:var(--shadow);border-radius:2px;
  transition:transform .25s ease,box-shadow .25s ease;
  animation:rise .5s ease backwards;
}
#gallery figure:hover{transform:translateY(-4px);box-shadow:var(--shadow-hover)}
#gallery img{width:100%;height:auto;display:block;border-radius:1px}
#gallery figcaption{
  margin-top:.65rem;display:flex;justify-content:space-between;
  align-items:baseline;gap:.75rem;
}
#gallery .t{font-family:'Young Serif',Georgia,serif;font-size:.95rem}
#gallery .m{font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-soft);white-space:nowrap}
.empty{text-align:center;color:var(--ink-soft);margin:4rem 0}
@keyframes rise{from{opacity:0;transform:translateY(16px)}}
@media (prefers-reduced-motion:reduce){#gallery figure{animation:none}}
footer{
  text-align:center;margin-top:5rem;color:var(--ink-soft);
  font-size:.78rem;letter-spacing:.18em;text-transform:uppercase;
}
.lightbox{
  position:fixed;inset:0;background:rgba(24,21,15,.94);
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  z-index:10;padding:1rem;
}
.lightbox.hidden{display:none}
.lightbox img{max-width:min(92vw,1100px);max-height:78vh;object-fit:contain;box-shadow:0 24px 80px rgba(0,0,0,.6)}
#lightbox-caption{color:#efe9dc;margin-top:1.25rem;text-align:center;font-size:.95rem}
#lightbox-caption .t{font-family:'Young Serif',Georgia,serif;font-size:1.15rem;display:block;margin-bottom:.3rem}
#lightbox-caption .m{color:#a89d89;letter-spacing:.1em;text-transform:uppercase;font-size:.72rem}
#lightbox-counter{position:absolute;top:1.25rem;left:1.5rem;color:#a89d89;font-size:.8rem;letter-spacing:.15em}
.lb-btn{
  position:absolute;background:none;border:none;color:#efe9dc;cursor:pointer;
  font-size:2rem;line-height:1;padding:.75rem;opacity:.7;transition:opacity .2s;
  font-family:inherit;
}
.lb-btn:hover{opacity:1}
#lightbox-close{top:.75rem;right:1rem}
#lightbox-prev{left:.5rem;top:50%;transform:translateY(-50%)}
#lightbox-next{right:.5rem;top:50%;transform:translateY(-50%)}
@media (max-width:600px){#lightbox-prev,#lightbox-next{top:auto;bottom:.5rem;transform:none}}
`;

const CLIENT_JS = `
let currentCategory = 'all';
let currentImages = [];
let currentIndex = 0;

function esc(str) {
  return String(str ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

function flatten(data, category) {
  const cats = category === 'all' ? data : data.filter(c => c.name === category);
  return cats.flatMap(c => c.images);
}

function renderGallery() {
  const gallery = document.getElementById('gallery');
  currentImages = flatten(DATA, currentCategory);

  if (currentImages.length === 0) {
    gallery.innerHTML = '<p class="empty">Meg nincsenek kepek ebben a kategoriaban.</p>';
    return;
  }

  gallery.innerHTML = currentImages.map((img, i) => \`
    <figure data-index="\${i}" style="animation-delay:\${Math.min(i * 45, 450)}ms">
      <img src="\${esc(img.thumb)}" alt="\${esc(img.title)}" loading="lazy"
        \${img.width ? \`width="\${Number(img.width)}" height="\${Number(img.height)}"\` : ''}>
      <figcaption>
        <span class="t">\${esc(img.title)}</span>
        \${img.technique ? \`<span class="m">\${esc(img.technique)}</span>\` : ''}
      </figcaption>
    </figure>
  \`).join('');

  gallery.querySelectorAll('figure').forEach(fig => {
    fig.addEventListener('click', () => openLightbox(Number(fig.dataset.index)));
  });
}

function openLightbox(index) {
  currentIndex = index;
  const img = currentImages[index];
  document.getElementById('lightbox-img').src = img.full;
  document.getElementById('lightbox-img').alt = img.title;
  const meta = [img.technique, img.date].filter(Boolean).join(' · ');
  const cap = document.getElementById('lightbox-caption');
  cap.innerHTML = '<span class="t">' + esc(img.title) + '</span>'
    + (meta ? '<span class="m">' + esc(meta) + '</span>' : '');
  document.getElementById('lightbox-counter').textContent =
    (index + 1) + ' / ' + currentImages.length;
  document.getElementById('lightbox').classList.remove('hidden');
}

function closeLightbox() {
  document.getElementById('lightbox').classList.add('hidden');
}

function stepLightbox(delta) {
  const n = currentImages.length;
  openLightbox((currentIndex + delta + n) % n);
}

document.getElementById('lightbox-close').addEventListener('click', closeLightbox);
document.getElementById('lightbox-prev').addEventListener('click', () => stepLightbox(-1));
document.getElementById('lightbox-next').addEventListener('click', () => stepLightbox(1));
document.getElementById('lightbox').addEventListener('click', (e) => {
  if (e.target.id === 'lightbox') closeLightbox();
});
document.addEventListener('keydown', (e) => {
  if (document.getElementById('lightbox').classList.contains('hidden')) return;
  if (e.key === 'Escape') closeLightbox();
  if (e.key === 'ArrowLeft') stepLightbox(-1);
  if (e.key === 'ArrowRight') stepLightbox(1);
});

document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    currentCategory = tab.dataset.category;
    renderGallery();
  });
});

renderGallery();
`;

export function renderIndexHtml({ bio, categories }) {
  const tabsHtml = [
    `<button class="tab active" data-category="all">Összes</button>`,
    ...categories.map((c) => `<button class="tab" data-category="${escapeHtml(c.name)}">${escapeHtml(displayName(c.name))}</button>`),
  ].join('\n');

  const dataJson = JSON.stringify(categories.map((c) => ({
    name: c.name,
    images: c.images.map((img) => ({
      title: img.title,
      technique: img.technique,
      date: img.date,
      full: img.full,
      thumb: img.thumb,
      width: img.width ?? null,
      height: img.height ?? null,
    })),
  }))).replace(/</g, '\\u003c');

  const year = new Date().getFullYear();

  return `<!DOCTYPE html>
<html lang="hu">
<head>
<meta charset="utf-8">
<title>${escapeHtml(bio.name)} – Portfólió</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Young+Serif&family=Karla:wght@400;500&display=swap" rel="stylesheet">
<style>${CSS}</style>
</head>
<body>
<header>
  <h1>${escapeHtml(bio.name)}</h1>
  ${bio.age ? `<p class="age">${escapeHtml(bio.age)} éves</p>` : ''}
  <p class="intro">${escapeHtml(bio.intro)}</p>
</header>
<nav class="tabs">${tabsHtml}</nav>
<main id="gallery"></main>
<footer>${escapeHtml(bio.name)} · ${year}</footer>
<div id="lightbox" class="lightbox hidden">
  <span id="lightbox-counter"></span>
  <button id="lightbox-close" class="lb-btn" aria-label="Bezárás">&times;</button>
  <button id="lightbox-prev" class="lb-btn" aria-label="Előző">&larr;</button>
  <button id="lightbox-next" class="lb-btn" aria-label="Következő">&rarr;</button>
  <img id="lightbox-img" src="" alt="">
  <div id="lightbox-caption"></div>
</div>
<script>
const DATA = ${dataJson};
${CLIENT_JS}
</script>
</body>
</html>`;
}
