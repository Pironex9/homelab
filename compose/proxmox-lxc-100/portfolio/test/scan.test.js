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
