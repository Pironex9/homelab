function escapeHtml(str) {
  return String(str ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

const CSS = `
:root{font-family:system-ui,sans-serif;color:#1a1a1a;background:#fff}
body{margin:0;padding:0 1rem 3rem}
header{max-width:700px;margin:2rem auto 1rem;text-align:center}
header h1{margin-bottom:.25rem}
.age{color:#666;margin:.25rem 0}
.intro{color:#333;line-height:1.5}
.tabs{display:flex;flex-wrap:wrap;gap:.5rem;justify-content:center;margin:2rem 0}
.tab{border:1px solid #ccc;background:#fff;padding:.5rem 1rem;border-radius:999px;cursor:pointer;font-size:.9rem}
.tab.active{background:#1a1a1a;color:#fff;border-color:#1a1a1a}
#gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:1rem;max-width:1100px;margin:0 auto}
#gallery figure{margin:0;cursor:pointer}
#gallery img{width:100%;height:200px;object-fit:cover;border-radius:4px;display:block}
#gallery figcaption{font-size:.85rem;color:#555;margin-top:.35rem}
.lightbox{position:fixed;inset:0;background:rgba(0,0,0,.9);display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:10}
.lightbox.hidden{display:none}
.lightbox img{max-width:90vw;max-height:80vh;object-fit:contain}
#lightbox-caption{color:#fff;margin-top:1rem;text-align:center}
#lightbox-close{position:absolute;top:1rem;right:1.5rem;background:none;border:none;color:#fff;font-size:2rem;cursor:pointer}
`;

const CLIENT_JS = `
let currentCategory = 'all';

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
  const images = flatten(DATA, currentCategory);
  gallery.innerHTML = images.map((img, i) => \`
    <figure data-index="\${i}">
      <img src="\${esc(img.thumb)}" alt="\${esc(img.title)}">
      <figcaption>\${esc(img.title)}</figcaption>
    </figure>
  \`).join('');

  gallery.querySelectorAll('figure').forEach(fig => {
    fig.addEventListener('click', () => openLightbox(images[Number(fig.dataset.index)]));
  });
}

function openLightbox(img) {
  document.getElementById('lightbox-img').src = img.full;
  const parts = [img.title];
  if (img.technique) parts.push(img.technique);
  if (img.date) parts.push(img.date);
  document.getElementById('lightbox-caption').textContent = parts.join(' - ');
  document.getElementById('lightbox').classList.remove('hidden');
}

document.getElementById('lightbox-close').addEventListener('click', () => {
  document.getElementById('lightbox').classList.add('hidden');
});
document.getElementById('lightbox').addEventListener('click', (e) => {
  if (e.target.id === 'lightbox') e.target.classList.add('hidden');
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
    `<button class="tab active" data-category="all">Osszes</button>`,
    ...categories.map((c) => `<button class="tab" data-category="${escapeHtml(c.name)}">${escapeHtml(c.name)}</button>`),
  ].join('\n');

  const dataJson = JSON.stringify(categories.map((c) => ({
    name: c.name,
    images: c.images.map((img) => ({
      title: img.title,
      technique: img.technique,
      date: img.date,
      full: img.full,
      thumb: img.thumb,
    })),
  }))).replace(/</g, '\\u003c');

  return `<!DOCTYPE html>
<html lang="hu">
<head>
<meta charset="utf-8">
<title>${escapeHtml(bio.name)} - Portfolio</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>${CSS}</style>
</head>
<body>
<header>
  <h1>${escapeHtml(bio.name)}</h1>
  ${bio.age ? `<p class="age">${escapeHtml(bio.age)} eves</p>` : ''}
  <p class="intro">${escapeHtml(bio.intro)}</p>
</header>
<nav class="tabs">${tabsHtml}</nav>
<main id="gallery"></main>
<div id="lightbox" class="lightbox hidden">
  <button id="lightbox-close">&times;</button>
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
