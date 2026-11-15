// usage: node scripts/shot.mjs http://localhost:8000/login out.png [width] [height]
//
// Three settings here are load-bearing: the bundled Playwright browser is
// version-mismatched so executablePath must be given, Chrome refuses to start
// as root without --no-sandbox, and a short viewport makes fullPage stop at
// the fold, so the height is set tall rather than relying on fullPage.
//
// playwright-core is not installed standalone on this host, only inside
// @playwright/cli. PLAYWRIGHT_CORE overrides the path; installing it into the
// project would mean an npm dependency, which the stack does not have.
const PW = process.env.PLAYWRIGHT_CORE
  || '/usr/lib/node_modules/@playwright/cli/node_modules/playwright-core/index.mjs';
const { chromium } = await import(PW);

const [, , url, out, w = '390', h = '1400'] = process.argv;
const browser = await chromium.launch({
  executablePath: '/usr/bin/google-chrome',
  args: ['--no-sandbox'],
});
const page = await browser.newPage({
  viewport: { width: Number(w), height: Number(h) },
  deviceScaleFactor: 2,
});
const errors = [];
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
page.on('requestfailed', (r) => errors.push(`failed: ${r.url()}`));
await page.goto(url, { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);   // an early capture catches mid-reflow
await page.screenshot({ path: out });
await browser.close();
if (errors.length) console.error(errors.join('\n'));
