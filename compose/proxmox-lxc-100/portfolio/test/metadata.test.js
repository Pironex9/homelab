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
