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
