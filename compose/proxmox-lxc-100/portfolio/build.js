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
const ASSETS_DIR = path.join(__dirname, 'assets');

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
    const usedBaseNames = new Map();
    for (const image of category.images) {
      const baseName = path.basename(image.file, path.extname(image.file));
      if (usedBaseNames.has(baseName)) {
        throw new Error(
          `Build check failed: duplicate output basename "${baseName}" in category "${category.name}" ` +
          `(from files ${usedBaseNames.get(baseName)} and ${image.file}) - rename one of them`,
        );
      }
      usedBaseNames.set(baseName, image.file);
      const variants = await generateVariants(image.path, outDir, baseName);
      image.full = `images/${category.name}/${variants.full}`;
      image.thumb = `images/${category.name}/${variants.thumb}`;
      image.width = variants.width;
      image.height = variants.height;
    }
  }

  // The two faces are self-hosted: the page must make no third-party request,
  // and Hungarian needs the latin-ext subsets that a system stack cannot
  // promise. fonts.css sits beside index.html so its relative url()s resolve.
  if (fs.existsSync(ASSETS_DIR)) {
    fs.cpSync(ASSETS_DIR, distDir, { recursive: true });
  }

  const html = renderIndexHtml({ bio, categories });
  fs.writeFileSync(path.join(distDir, 'index.html'), html);
  fs.writeFileSync(path.join(distDir, 'robots.txt'), 'User-agent: *\nDisallow: /\n');

  verifyBuildOutput(categories, distDir);
  warnAboutMissingDates(categories);

  return { bio, categories };
}

// The whole page argues chronology, so an undated work is a hole in the
// argument rather than a cosmetic gap: it cannot sit on the year rail and it
// sorts to the end of the register. Warn rather than fail - a drawing whose
// date nobody remembers should still be publishable.
export function warnAboutMissingDates(categories) {
  const undated = [];
  for (const category of categories) {
    for (const image of category.images) {
      if (!image.date) undated.push(`${category.name}/${image.file}`);
    }
  }
  if (undated.length === 0) return;
  console.warn(`  ! ${undated.length} rajzon nincs dátum, ezek az évsávon nem jelennek meg:`);
  for (const file of undated.slice(0, 10)) console.warn(`      ${file}`);
  if (undated.length > 10) console.warn(`      ... és még ${undated.length - 10}`);
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
  build({
    contentDir: process.env.PORTFOLIO_CONTENT_DIR || undefined,
    bioPath: process.env.PORTFOLIO_BIO_PATH || undefined,
  })
    .then(({ categories }) => {
      const total = categories.reduce((sum, c) => sum + c.images.length, 0);
      console.log(`Build ok: ${categories.length} categories, ${total} images.`);
    })
    .catch((err) => {
      console.error(err.message);
      process.exit(1);
    });
}
