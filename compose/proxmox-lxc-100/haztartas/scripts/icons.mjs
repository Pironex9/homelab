// usage: node scripts/icons.mjs [outdir]   (default app/static)
//
// Renders the tile mark (login.html's .mark: moss tall left, brick top right,
// slate bottom right) into the PWA icons. The same load-bearing settings as
// shot.mjs: executablePath, --no-sandbox, and the playwright-core path.
//
// One icon serves as "any maskable": the ground is full bleed and the mark
// sits inside the maskable safe zone (a centred circle of 80% diameter), so a
// launcher's circle or squircle crop never cuts a tile. The mark is 54% of the
// icon: its corners then lie at 76% of the diameter. Gap and corner radius
// scale from the 56px login mark (3px, 4px).
const PW = process.env.PLAYWRIGHT_CORE
  || '/usr/lib/node_modules/@playwright/cli/node_modules/playwright-core/index.mjs';
const { chromium } = await import(PW);

const out = process.argv[2] || 'app/static';
const browser = await chromium.launch({
  executablePath: '/usr/bin/google-chrome',
  args: ['--no-sandbox'],
});
for (const size of [180, 192, 512]) {
  const mark = Math.round(size * 0.54);
  const gap = Math.max(2, Math.round(mark * 3 / 56));
  const radius = Math.round(mark * 4 / 56);
  const page = await browser.newPage({
    viewport: { width: size, height: size }, deviceScaleFactor: 1,
  });
  await page.setContent(`<!doctype html><style>
    html, body { margin: 0; width: ${size}px; height: ${size}px; background: #f3f1ec; }
    body { display: grid; place-items: center; }
    .mark { display: grid; grid-template-columns: 1.6fr 1fr; grid-template-rows: 1fr 1fr;
            gap: ${gap}px; width: ${mark}px; height: ${mark}px; }
    .mark i { border-radius: ${radius}px; }
    .mark i:first-child { grid-row: 1 / 3; background: #2e6b4f; }
    .mark i:nth-child(2) { background: #b2532d; }
    .mark i:nth-child(3) { background: #3c5a9a; }
  </style><div class="mark"><i></i><i></i><i></i></div>`);
  await page.screenshot({ path: `${out}/icon-${size}.png` });
  await page.close();
}
await browser.close();
