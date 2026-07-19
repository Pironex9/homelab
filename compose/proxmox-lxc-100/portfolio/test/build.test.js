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

test('build throws on duplicate output basename within a category', async () => {
  const { contentDir, bioPath, distDir } = await makeTestProject();
  await sharp({ create: { width: 800, height: 600, channels: 3, background: { r: 40, g: 50, b: 60 } } })
    .png().toFile(path.join(contentDir, 'csendelet', '01-alma.png'));

  await assert.rejects(
    () => build({ contentDir, bioPath, distDir }),
    /duplicate output basename "01-alma" in category "csendelet"/,
  );
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
