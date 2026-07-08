# Daughter's Art Portfolio Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a static, category-organized art portfolio gallery site for admission to a fine arts school, deployed as a new Docker Compose stack following the homelab's existing static-site pattern.

**Architecture:** A custom Node.js build script (`build.js`) walks a `content/` folder organized by category, resizes each image into full/thumb variants with `sharp`, and emits a single static `dist/index.html` (vanilla JS tabs + lightbox, no runtime API calls). Caddy serves `dist/` as static files, matching the existing `compose/proxmox-lxc-100/form/` stack.

**Tech Stack:** Node.js (ESM, built-in `node:test` runner), `sharp` (image resizing), `js-yaml` (metadata parsing), Caddy (static file server), Docker Compose.

## Global Constraints

- No backend, no database, no runtime API calls — the site is fully static (spec: Architecture)
- Custom minimal Node script, not a framework (Eleventy/Astro rejected) — spec: Build tooling choice
- `content/` and `build.js` are version-controlled; `dist/` is gitignored as a build artifact — spec: Data flow
- Public but not indexed: `robots.txt` disallows all crawlers — spec: Hosting
- Build must fail loudly (non-zero exit) if generated output is incomplete, never silently emit a broken site — spec: Testing
- Missing image metadata sidecar must never fail the build — falls back to a filename-derived title — spec: Error handling
- Follows the existing Caddy static-file stack pattern (`compose/proxmox-lxc-100/form/`) for Caddyfile/docker-compose.yml style — spec: Hosting, Deployment

---

## File Structure

```
compose/proxmox-lxc-100/portfolio/
  package.json
  build.js                  # orchestrator: build(), verifyBuildOutput()
  lib/
    metadata.js             # deriveTitleFromFilename, loadImageMetadata, loadBio
    scan.js                 # scanContent
    resize.js               # generateVariants
    render.js                # renderIndexHtml
  test/
    metadata.test.js
    scan.test.js
    resize.test.js
    render.test.js
    build.test.js
  content/                  # sample fixture categories (real artwork added later by the user)
    csendelet/
      01-alma.jpg
      01-alma.yml
  bio.yml
  Caddyfile
  docker-compose.yml
  .gitignore                # dist/, node_modules/
```

---

### Task 1: Project scaffold

**Files:**
- Create: `compose/proxmox-lxc-100/portfolio/package.json`
- Create: `compose/proxmox-lxc-100/portfolio/.gitignore`

**Interfaces:**
- Produces: an npm project at `compose/proxmox-lxc-100/portfolio/` with `sharp` and `js-yaml` as dependencies, `node --test` as the test runner.

- [ ] **Step 1: Create the directory and package.json**

```json
{
  "name": "portfolio-build",
  "private": true,
  "type": "module",
  "scripts": {
    "build": "node build.js",
    "test": "node --test"
  },
  "dependencies": {
    "sharp": "^0.33.0",
    "js-yaml": "^4.1.0"
  }
}
```

- [ ] **Step 2: Create .gitignore**

```
dist/
node_modules/
```

- [ ] **Step 3: Install dependencies**

Run: `cd compose/proxmox-lxc-100/portfolio && npm install`
Expected: `node_modules/` created, `package-lock.json` generated, no errors.

- [ ] **Step 4: Commit**

```bash
git add compose/proxmox-lxc-100/portfolio/package.json compose/proxmox-lxc-100/portfolio/package-lock.json compose/proxmox-lxc-100/portfolio/.gitignore
git commit -m "chore(portfolio): scaffold Node project for art portfolio build"
```

---

### Task 2: Metadata module (titles, sidecar YAML, bio)

**Files:**
- Create: `compose/proxmox-lxc-100/portfolio/lib/metadata.js`
- Test: `compose/proxmox-lxc-100/portfolio/test/metadata.test.js`

**Interfaces:**
- Produces:
  - `deriveTitleFromFilename(filename: string): string`
  - `loadImageMetadata(imagePath: string): { title: string, technique: string|null, date: string|null }`
  - `loadBio(bioPath: string): { name: string, age: number|null, intro: string }`
- Consumes: `node:fs`, `node:path`, `js-yaml` (installed in Task 1)

- [ ] **Step 1: Write the failing tests**

```js
// compose/proxmox-lxc-100/portfolio/test/metadata.test.js
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { deriveTitleFromFilename, loadImageMetadata, loadBio } from '../lib/metadata.js';

test('deriveTitleFromFilename strips numeric prefix and formats title case', () => {
  assert.equal(deriveTitleFromFilename('01-alma-piros.jpg'), 'Alma Piros');
  assert.equal(deriveTitleFromFilename('napfelkelte.png'), 'Napfelkelte');
});

test('loadImageMetadata reads a sidecar yml when present', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'meta-'));
  const imagePath = path.join(dir, '01-alma.jpg');
  fs.writeFileSync(imagePath, '');
  fs.writeFileSync(path.join(dir, '01-alma.yml'), 'title: "Csendelet almaval"\ntechnique: "ceruza"\ndate: "2026-03-12"\n');

  const meta = loadImageMetadata(imagePath);
  assert.deepEqual(meta, { title: 'Csendelet almaval', technique: 'ceruza', date: '2026-03-12' });
});

test('loadImageMetadata falls back to filename-derived title when sidecar is missing', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'meta-'));
  const imagePath = path.join(dir, '02-tajkep-nyari.jpg');
  fs.writeFileSync(imagePath, '');

  const meta = loadImageMetadata(imagePath);
  assert.deepEqual(meta, { title: 'Tajkep Nyari', technique: null, date: null });
});

test('loadBio reads name, age, intro', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'bio-'));
  const bioPath = path.join(dir, 'bio.yml');
  fs.writeFileSync(bioPath, 'name: "Enci"\nage: 13\nintro: "Szeretek rajzolni."\n');

  assert.deepEqual(loadBio(bioPath), { name: 'Enci', age: 13, intro: 'Szeretek rajzolni.' });
});

test('loadBio throws a clear error when name is missing', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'bio-'));
  const bioPath = path.join(dir, 'bio.yml');
  fs.writeFileSync(bioPath, 'age: 13\n');

  assert.throws(() => loadBio(bioPath), /must include at least a "name" field/);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd compose/proxmox-lxc-100/portfolio && node --test test/metadata.test.js`
Expected: FAIL with "Cannot find module '../lib/metadata.js'"

- [ ] **Step 3: Write the implementation**

```js
// compose/proxmox-lxc-100/portfolio/lib/metadata.js
import fs from 'node:fs';
import path from 'node:path';
import yaml from 'js-yaml';

export function deriveTitleFromFilename(filename) {
  const base = path.basename(filename, path.extname(filename));
  const cleaned = base.replace(/^\d+[-_]?/, '').replace(/[-_]+/g, ' ').trim();
  const words = cleaned.length > 0 ? cleaned : base;
  return words.replace(/\b\w/g, (c) => c.toUpperCase());
}

export function loadImageMetadata(imagePath) {
  const sidecarPath = imagePath.slice(0, -path.extname(imagePath).length) + '.yml';
  if (fs.existsSync(sidecarPath)) {
    const data = yaml.load(fs.readFileSync(sidecarPath, 'utf8')) || {};
    return {
      title: data.title || deriveTitleFromFilename(imagePath),
      technique: data.technique || null,
      date: data.date || null,
    };
  }
  return { title: deriveTitleFromFilename(imagePath), technique: null, date: null };
}

export function loadBio(bioPath) {
  const data = yaml.load(fs.readFileSync(bioPath, 'utf8'));
  if (!data || !data.name) {
    throw new Error(`bio.yml at ${bioPath} must include at least a "name" field`);
  }
  return { name: data.name, age: data.age ?? null, intro: data.intro || '' };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd compose/proxmox-lxc-100/portfolio && node --test test/metadata.test.js`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add compose/proxmox-lxc-100/portfolio/lib/metadata.js compose/proxmox-lxc-100/portfolio/test/metadata.test.js
git commit -m "feat(portfolio): add metadata loading with filename-derived title fallback"
```

---

### Task 3: Content scanner

**Files:**
- Create: `compose/proxmox-lxc-100/portfolio/lib/scan.js`
- Test: `compose/proxmox-lxc-100/portfolio/test/scan.test.js`

**Interfaces:**
- Consumes: `loadImageMetadata` from `lib/metadata.js` (Task 2)
- Produces: `scanContent(contentDir: string): Array<{ name: string, images: Array<{ file: string, path: string, title: string, technique: string|null, date: string|null }> }>`
  - Categories are subdirectories of `contentDir`, sorted alphabetically.
  - Only `.jpg`, `.jpeg`, `.png`, `.webp` files (case-insensitive) count as images; everything else is skipped.
  - Empty categories are omitted from the result.

- [ ] **Step 1: Write the failing test**

```js
// compose/proxmox-lxc-100/portfolio/test/scan.test.js
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { scanContent } from '../lib/scan.js';

function makeContentTree() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'content-'));
  fs.mkdirSync(path.join(dir, 'csendelet'));
  fs.writeFileSync(path.join(dir, 'csendelet', '01-alma.jpg'), '');
  fs.writeFileSync(path.join(dir, 'csendelet', '01-alma.yml'), 'title: "Alma"\n');
  fs.writeFileSync(path.join(dir, 'csendelet', '.DS_Store'), '');
  fs.mkdirSync(path.join(dir, 'tajkep'));
  fs.writeFileSync(path.join(dir, 'tajkep', '01-naplemente.png'), '');
  fs.mkdirSync(path.join(dir, 'ures-kategoria'));
  return dir;
}

test('scanContent groups images by category, skips non-images, omits empty categories', () => {
  const dir = makeContentTree();
  const categories = scanContent(dir);

  assert.equal(categories.length, 2);
  assert.equal(categories[0].name, 'csendelet');
  assert.equal(categories[0].images.length, 1);
  assert.equal(categories[0].images[0].title, 'Alma');
  assert.equal(categories[1].name, 'tajkep');
  assert.equal(categories[1].images[0].title, 'Naplemente');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd compose/proxmox-lxc-100/portfolio && node --test test/scan.test.js`
Expected: FAIL with "Cannot find module '../lib/scan.js'"

- [ ] **Step 3: Write the implementation**

```js
// compose/proxmox-lxc-100/portfolio/lib/scan.js
import fs from 'node:fs';
import path from 'node:path';
import { loadImageMetadata } from './metadata.js';

const IMAGE_EXTENSIONS = new Set(['.jpg', '.jpeg', '.png', '.webp']);

export function scanContent(contentDir) {
  const categories = [];
  const categoryNames = fs.readdirSync(contentDir, { withFileTypes: true })
    .filter((e) => e.isDirectory())
    .map((e) => e.name)
    .sort();

  for (const categoryName of categoryNames) {
    const categoryDir = path.join(contentDir, categoryName);
    const images = fs.readdirSync(categoryDir, { withFileTypes: true })
      .filter((e) => e.isFile() && IMAGE_EXTENSIONS.has(path.extname(e.name).toLowerCase()))
      .map((e) => e.name)
      .sort()
      .map((file) => {
        const imagePath = path.join(categoryDir, file);
        return { file, path: imagePath, ...loadImageMetadata(imagePath) };
      });

    if (images.length > 0) {
      categories.push({ name: categoryName, images });
    }
  }

  return categories;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd compose/proxmox-lxc-100/portfolio && node --test test/scan.test.js`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add compose/proxmox-lxc-100/portfolio/lib/scan.js compose/proxmox-lxc-100/portfolio/test/scan.test.js
git commit -m "feat(portfolio): add content scanner grouping images by category"
```

---

### Task 4: Image resizing

**Files:**
- Create: `compose/proxmox-lxc-100/portfolio/lib/resize.js`
- Test: `compose/proxmox-lxc-100/portfolio/test/resize.test.js`

**Interfaces:**
- Consumes: `sharp` (Task 1)
- Produces: `async generateVariants(srcImagePath: string, outDir: string, baseName: string): Promise<{ full: string, thumb: string }>`
  - Writes `${baseName}-full.jpg` (max width 1600, no upscaling) and `${baseName}-thumb.jpg` (max width 400) into `outDir`, creating it if needed.
  - Returns the two generated filenames (not full paths — callers join with `outDir`).

- [ ] **Step 1: Write the failing test**

```js
// compose/proxmox-lxc-100/portfolio/test/resize.test.js
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import sharp from 'sharp';
import { generateVariants } from '../lib/resize.js';

async function makeTestImage(destPath, width, height) {
  await sharp({
    create: { width, height, channels: 3, background: { r: 200, g: 100, b: 50 } },
  }).png().toFile(destPath);
}

test('generateVariants writes a full and thumb JPEG within their max widths', async () => {
  const srcDir = fs.mkdtempSync(path.join(os.tmpdir(), 'src-'));
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), 'out-'));
  const srcPath = path.join(srcDir, 'test.png');
  await makeTestImage(srcPath, 2000, 1000);

  const result = await generateVariants(srcPath, outDir, 'test');

  assert.equal(result.full, 'test-full.jpg');
  assert.equal(result.thumb, 'test-thumb.jpg');

  const fullMeta = await sharp(path.join(outDir, result.full)).metadata();
  const thumbMeta = await sharp(path.join(outDir, result.thumb)).metadata();
  assert.equal(fullMeta.width, 1600);
  assert.equal(thumbMeta.width, 400);
});

test('generateVariants never upscales a smaller source image', async () => {
  const srcDir = fs.mkdtempSync(path.join(os.tmpdir(), 'src-'));
  const outDir = fs.mkdtempSync(path.join(os.tmpdir(), 'out-'));
  const srcPath = path.join(srcDir, 'small.png');
  await makeTestImage(srcPath, 300, 200);

  const result = await generateVariants(srcPath, outDir, 'small');
  const fullMeta = await sharp(path.join(outDir, result.full)).metadata();
  assert.equal(fullMeta.width, 300);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd compose/proxmox-lxc-100/portfolio && node --test test/resize.test.js`
Expected: FAIL with "Cannot find module '../lib/resize.js'"

- [ ] **Step 3: Write the implementation**

```js
// compose/proxmox-lxc-100/portfolio/lib/resize.js
import fs from 'node:fs';
import path from 'node:path';
import sharp from 'sharp';

export async function generateVariants(srcImagePath, outDir, baseName) {
  fs.mkdirSync(outDir, { recursive: true });

  const fullFile = `${baseName}-full.jpg`;
  const thumbFile = `${baseName}-thumb.jpg`;

  await sharp(srcImagePath)
    .resize({ width: 1600, fit: 'inside', withoutEnlargement: true })
    .jpeg({ quality: 85 })
    .toFile(path.join(outDir, fullFile));

  await sharp(srcImagePath)
    .resize({ width: 400, fit: 'inside', withoutEnlargement: true })
    .jpeg({ quality: 80 })
    .toFile(path.join(outDir, thumbFile));

  return { full: fullFile, thumb: thumbFile };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd compose/proxmox-lxc-100/portfolio && node --test test/resize.test.js`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add compose/proxmox-lxc-100/portfolio/lib/resize.js compose/proxmox-lxc-100/portfolio/test/resize.test.js
git commit -m "feat(portfolio): add sharp-based full/thumb image resizing"
```

---

### Task 5: HTML rendering (gallery page)

**Files:**
- Create: `compose/proxmox-lxc-100/portfolio/lib/render.js`
- Test: `compose/proxmox-lxc-100/portfolio/test/render.test.js`

**Interfaces:**
- Produces: `renderIndexHtml({ bio: { name, age, intro }, categories: Array<{ name, images: Array<{ title, technique, date, full, thumb }> }> }): string`
  - Returns a complete standalone HTML document: bio header, category tabs (including an "Osszes" / all tab), a gallery grid, and a lightbox. Category data is embedded inline as JSON (no runtime fetch).

- [ ] **Step 1: Write the failing test**

```js
// compose/proxmox-lxc-100/portfolio/test/render.test.js
import test from 'node:test';
import assert from 'node:assert/strict';
import { renderIndexHtml } from '../lib/render.js';

const sampleInput = {
  bio: { name: 'Enci', age: 13, intro: 'Szeretek rajzolni.' },
  categories: [
    {
      name: 'csendelet',
      images: [
        { title: 'Alma', technique: 'ceruza', date: '2026-03-12', full: 'images/csendelet/01-full.jpg', thumb: 'images/csendelet/01-thumb.jpg' },
      ],
    },
    {
      name: 'anime-karakter',
      images: [
        { title: 'Harcos', technique: null, date: null, full: 'images/anime-karakter/02-full.jpg', thumb: 'images/anime-karakter/02-thumb.jpg' },
      ],
    },
  ],
};

test('renderIndexHtml includes bio, every category name, and embedded image data', () => {
  const html = renderIndexHtml(sampleInput);

  assert.match(html, /Enci/);
  assert.match(html, /Szeretek rajzolni\./);
  assert.match(html, /csendelet/);
  assert.match(html, /anime-karakter/);
  assert.match(html, /images\/csendelet\/01-thumb\.jpg/);
  assert.match(html, /images\/anime-karakter\/02-full\.jpg/);
});

test('renderIndexHtml escapes HTML-sensitive characters in bio and titles', () => {
  const html = renderIndexHtml({
    bio: { name: '<script>alert(1)</script>', age: null, intro: '' },
    categories: [],
  });

  assert.doesNotMatch(html, /<script>alert\(1\)<\/script>/);
  assert.match(html, /&lt;script&gt;/);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd compose/proxmox-lxc-100/portfolio && node --test test/render.test.js`
Expected: FAIL with "Cannot find module '../lib/render.js'"

- [ ] **Step 3: Write the implementation**

```js
// compose/proxmox-lxc-100/portfolio/lib/render.js
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

function flatten(data, category) {
  const cats = category === 'all' ? data : data.filter(c => c.name === category);
  return cats.flatMap(c => c.images);
}

function renderGallery() {
  const gallery = document.getElementById('gallery');
  const images = flatten(DATA, currentCategory);
  gallery.innerHTML = images.map((img, i) => \`
    <figure data-index="\${i}">
      <img src="\${img.thumb}" alt="\${img.title}">
      <figcaption>\${img.title}</figcaption>
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
  })));

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd compose/proxmox-lxc-100/portfolio && node --test test/render.test.js`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add compose/proxmox-lxc-100/portfolio/lib/render.js compose/proxmox-lxc-100/portfolio/test/render.test.js
git commit -m "feat(portfolio): render single-page gallery with tabs and lightbox"
```

---

### Task 6: Build orchestrator with self-check

**Files:**
- Create: `compose/proxmox-lxc-100/portfolio/build.js`
- Test: `compose/proxmox-lxc-100/portfolio/test/build.test.js`

**Interfaces:**
- Consumes: `scanContent` (Task 3), `loadBio` (Task 2), `generateVariants` (Task 4), `renderIndexHtml` (Task 5)
- Produces:
  - `async build({ contentDir, bioPath, distDir }): Promise<{ bio, categories }>` — defaults to the real `content/`, `bio.yml`, `dist/` next to `build.js` when called with no arguments; accepts overrides for testing.
  - `verifyBuildOutput(categories, distDir): void` — throws if `dist/index.html` doesn't mention every category name, or if any expected image variant file is missing.
  - When run directly (`node build.js`), builds with defaults, prints a summary, and exits non-zero with the error message on failure.

- [ ] **Step 1: Write the failing tests**

```js
// compose/proxmox-lxc-100/portfolio/test/build.test.js
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import sharp from 'sharp';
import { build, verifyBuildOutput } from '../build.js';

async function makeTestProject() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'project-'));
  const contentDir = path.join(root, 'content');
  const bioPath = path.join(root, 'bio.yml');
  const distDir = path.join(root, 'dist');

  fs.mkdirSync(path.join(contentDir, 'csendelet'), { recursive: true });
  await sharp({ create: { width: 800, height: 600, channels: 3, background: { r: 10, g: 20, b: 30 } } })
    .jpeg().toFile(path.join(contentDir, 'csendelet', '01-alma.jpg'));

  fs.writeFileSync(bioPath, 'name: "Enci"\nage: 13\nintro: "Szeretek rajzolni."\n');

  return { contentDir, bioPath, distDir };
}

test('build produces index.html, robots.txt, and resized images that pass verification', async () => {
  const { contentDir, bioPath, distDir } = await makeTestProject();

  const { categories } = await build({ contentDir, bioPath, distDir });

  assert.ok(fs.existsSync(path.join(distDir, 'index.html')));
  assert.ok(fs.existsSync(path.join(distDir, 'robots.txt')));
  assert.equal(categories[0].images[0].full, 'images/csendelet/01-alma-full.jpg');
  assert.doesNotThrow(() => verifyBuildOutput(categories, distDir));
});

test('verifyBuildOutput throws when an expected image file is missing', () => {
  const distDir = fs.mkdtempSync(path.join(os.tmpdir(), 'dist-'));
  fs.writeFileSync(path.join(distDir, 'index.html'), '<html>csendelet</html>');

  const categories = [{
    name: 'csendelet',
    images: [{ full: 'images/csendelet/missing-full.jpg', thumb: 'images/csendelet/missing-thumb.jpg' }],
  }];

  assert.throws(() => verifyBuildOutput(categories, distDir), /missing (full|thumb) image/);
});

test('verifyBuildOutput throws when a category name is missing from index.html', () => {
  const distDir = fs.mkdtempSync(path.join(os.tmpdir(), 'dist-'));
  fs.mkdirSync(path.join(distDir, 'images', 'tajkep'), { recursive: true });
  fs.writeFileSync(path.join(distDir, 'images', 'tajkep', 'a-full.jpg'), '');
  fs.writeFileSync(path.join(distDir, 'images', 'tajkep', 'a-thumb.jpg'), '');
  fs.writeFileSync(path.join(distDir, 'index.html'), '<html>nincs itt semmi kategoria</html>');

  const categories = [{
    name: 'tajkep',
    images: [{ full: 'images/tajkep/a-full.jpg', thumb: 'images/tajkep/a-thumb.jpg' }],
  }];

  assert.throws(() => verifyBuildOutput(categories, distDir), /category "tajkep" missing/);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd compose/proxmox-lxc-100/portfolio && node --test test/build.test.js`
Expected: FAIL with "Cannot find module '../build.js'"

- [ ] **Step 3: Write the implementation**

```js
// compose/proxmox-lxc-100/portfolio/build.js
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { scanContent } from './lib/scan.js';
import { loadBio } from './lib/metadata.js';
import { generateVariants } from './lib/resize.js';
import { renderIndexHtml } from './lib/render.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_CONTENT_DIR = path.join(__dirname, 'content');
const DEFAULT_BIO_PATH = path.join(__dirname, 'bio.yml');
const DEFAULT_DIST_DIR = path.join(__dirname, 'dist');

export async function build({
  contentDir = DEFAULT_CONTENT_DIR,
  bioPath = DEFAULT_BIO_PATH,
  distDir = DEFAULT_DIST_DIR,
} = {}) {
  const bio = loadBio(bioPath);
  const categories = scanContent(contentDir);

  fs.rmSync(distDir, { recursive: true, force: true });
  fs.mkdirSync(path.join(distDir, 'images'), { recursive: true });

  for (const category of categories) {
    const outDir = path.join(distDir, 'images', category.name);
    for (const image of category.images) {
      const baseName = path.basename(image.file, path.extname(image.file));
      const variants = await generateVariants(image.path, outDir, baseName);
      image.full = `images/${category.name}/${variants.full}`;
      image.thumb = `images/${category.name}/${variants.thumb}`;
    }
  }

  const html = renderIndexHtml({ bio, categories });
  fs.writeFileSync(path.join(distDir, 'index.html'), html);
  fs.writeFileSync(path.join(distDir, 'robots.txt'), 'User-agent: *\nDisallow: /\n');

  verifyBuildOutput(categories, distDir);

  return { bio, categories };
}

export function verifyBuildOutput(categories, distDir) {
  const indexHtml = fs.readFileSync(path.join(distDir, 'index.html'), 'utf8');

  for (const category of categories) {
    if (!indexHtml.includes(category.name)) {
      throw new Error(`Build check failed: category "${category.name}" missing from index.html`);
    }
    for (const image of category.images) {
      const fullPath = path.join(distDir, image.full);
      const thumbPath = path.join(distDir, image.thumb);
      if (!fs.existsSync(fullPath)) {
        throw new Error(`Build check failed: missing full image ${fullPath}`);
      }
      if (!fs.existsSync(thumbPath)) {
        throw new Error(`Build check failed: missing thumb image ${thumbPath}`);
      }
    }
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  build()
    .then(({ categories }) => {
      const total = categories.reduce((sum, c) => sum + c.images.length, 0);
      console.log(`Build ok: ${categories.length} categories, ${total} images.`);
    })
    .catch((err) => {
      console.error(err.message);
      process.exit(1);
    });
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd compose/proxmox-lxc-100/portfolio && node --test test/build.test.js`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the full test suite**

Run: `cd compose/proxmox-lxc-100/portfolio && npm test`
Expected: All tests across metadata/scan/resize/render/build pass.

- [ ] **Step 6: Commit**

```bash
git add compose/proxmox-lxc-100/portfolio/build.js compose/proxmox-lxc-100/portfolio/test/build.test.js
git commit -m "feat(portfolio): add build orchestrator with fail-loud output verification"
```

---

### Task 7: Caddy stack and deployment files

**Files:**
- Create: `compose/proxmox-lxc-100/portfolio/Caddyfile`
- Create: `compose/proxmox-lxc-100/portfolio/docker-compose.yml`

**Interfaces:**
- Consumes: `dist/` produced by `build.js` (Task 6)
- Produces: a deployable Docker Compose stack matching `compose/proxmox-lxc-100/form/`'s pattern.

- [ ] **Step 1: Create the Caddyfile**

```
# compose/proxmox-lxc-100/portfolio/Caddyfile
:80 {
    root * /usr/share/caddy
    file_server
}
```

- [ ] **Step 2: Create docker-compose.yml**

```yaml
services:
  portfolio:
    image: caddy:alpine
    container_name: portfolio
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - ./dist:/usr/share/caddy
    ports:
      - 3008:80
    restart: unless-stopped
```

- [ ] **Step 3: Verify the port is free**

Run: `ssh root@192.168.0.110 "ss -tlnp | grep 3008"`
Expected: no output (port free). If it's taken, pick the next free port in the 300x range used by other stacks and update both this file and the Pangolin target later.

- [ ] **Step 4: Commit**

```bash
git add compose/proxmox-lxc-100/portfolio/Caddyfile compose/proxmox-lxc-100/portfolio/docker-compose.yml
git commit -m "feat(portfolio): add Caddy static-file stack for deployment"
```

---

### Task 8: Sample content, bio, and end-to-end verification

**Files:**
- Create: `compose/proxmox-lxc-100/portfolio/content/csendelet/01-alma.jpg` (placeholder — replaced with real scans later)
- Create: `compose/proxmox-lxc-100/portfolio/content/csendelet/01-alma.yml`
- Create: `compose/proxmox-lxc-100/portfolio/bio.yml`
- Create: `compose/proxmox-lxc-100/portfolio/README.md`

**Interfaces:**
- Consumes: `build()` (Task 6)
- Produces: a working end-to-end build the user can run locally before deploying, plus instructions for adding real drawings later.

- [ ] **Step 1: Create a placeholder sample image and metadata**

Run:
```bash
cd compose/proxmox-lxc-100/portfolio
mkdir -p content/csendelet
node -e "
import('sharp').then(({ default: sharp }) =>
  sharp({ create: { width: 1200, height: 900, channels: 3, background: { r: 220, g: 200, b: 180 } } })
    .jpeg()
    .toFile('content/csendelet/01-alma.jpg')
);
"
```

```yaml
# content/csendelet/01-alma.yml
title: "Csendelet almaval"
technique: "ceruza"
date: "2026-07-08"
```

- [ ] **Step 2: Create bio.yml**

```yaml
# bio.yml
name: "Enci"
age: 13
intro: "Szeretek rajzolni, kulonosen anime-stilusu karaktereket."
```

- [ ] **Step 3: Run the real build against this sample content**

Run: `cd compose/proxmox-lxc-100/portfolio && npm run build`
Expected: `Build ok: 1 categories, 1 images.` printed, `dist/index.html` and `dist/images/csendelet/01-alma-full.jpg` / `01-alma-thumb.jpg` exist.

- [ ] **Step 4: Open dist/index.html in a browser and visually confirm**

Run: `python3 -m http.server 8899 --directory dist` (from `compose/proxmox-lxc-100/portfolio`), then open `http://<this-host>:8899/` in a browser.
Expected: bio header with "Enci", one tab besides "Osszes" ("csendelet"), one thumbnail, clicking it opens the lightbox with the full image and "Csendelet almaval - ceruza - 2026-07-08" caption. Stop the server with Ctrl+C when done.

- [ ] **Step 5: Write the README for future maintenance**

```markdown
# Portfolio site build

Static art portfolio for [daughter's] school admission. No backend, no database.

## Adding a new drawing

1. Photograph/scan the drawing (not covered by this tool).
2. Copy the image into `content/<category>/`, e.g. `content/tajkep/03-hegyek.jpg`.
   New categories are just new folders under `content/` — no code changes needed.
3. Optionally add a sidecar YAML file next to it with the same base name, e.g. `content/tajkep/03-hegyek.yml`:
   ```yaml
   title: "Hegyi tajkep"
   technique: "akvarell"
   date: "2026-09-01"
   ```
   If you skip this file, the title is derived from the filename.
4. Run `npm run build`.
5. Redeploy the stack (see repo root `compose/CLAUDE.md` for the Komodo GitOps flow, or `docker compose up -d` locally as a manual fallback).

## Editing the bio

Edit `bio.yml` (name, age, intro), then rebuild.

## Running tests

`npm test`
```

- [ ] **Step 6: Commit**

```bash
git add compose/proxmox-lxc-100/portfolio/content compose/proxmox-lxc-100/portfolio/bio.yml compose/proxmox-lxc-100/portfolio/README.md
git commit -m "feat(portfolio): add sample content, bio, and maintenance README"
```

---

## Post-plan: deployment (not part of this plan's tasks — do after Task 8 is reviewed)

1. Replace the placeholder sample image/metadata in `content/csendelet/` with real digitized drawings, organized into whatever categories actually apply (csendelet, tajkep, anime-karakter, portre, etc.).
2. Push the branch, then in Komodo: Pull + Deploy the `portfolio` stack on LXC 100 (per `compose/CLAUDE.md`).
3. In Pangolin, add a new resource/target pointing at `192.168.0.110:3008`, on the chosen subdomain.
4. Confirm `robots.txt` is served (`curl https://<subdomain>/robots.txt` should show `Disallow: /`).
