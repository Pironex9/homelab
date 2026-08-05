import test from 'node:test';
import assert from 'node:assert/strict';
import { buildRegister, categoryPrefixes, spreadAcross } from '../lib/register.js';

function work(file, date, extra = {}) {
  return { file, date, title: file, technique: null, featured: false, ...extra };
}

test('categoryPrefixes lengthens a prefix rather than handing out a duplicate', () => {
  const p = categoryPrefixes(['csendelet', 'csontvaz', 'tajkep']);
  assert.equal(p.get('csendelet'), 'CS');
  assert.equal(p.get('csontvaz'), 'CSO');
  assert.equal(p.get('tajkep'), 'TA');
  assert.equal(new Set([...p.values()]).size, 3);
});

test('accession numbers follow arrival order across the whole collection', () => {
  const categories = [
    { name: 'tajkep', images: [work('b.jpg', '2025-06-01')] },
    { name: 'csendelet', images: [work('a.jpg', '2024-09-01'), work('c.jpg', '2026-01-15')] },
  ];
  const reg = buildRegister(categories);

  assert.deepEqual(reg.all.map((i) => i.accession), [
    'CS.001/24', 'TA.002/25', 'CS.003/26',
  ]);
});

test('an undated work sorts last and gets a number but no year', () => {
  const categories = [
    { name: 'csendelet', images: [work('a.jpg', null), work('b.jpg', '2025-02-02')] },
  ];
  const reg = buildRegister(categories);

  assert.equal(reg.all[0].accession, 'CS.001/25');
  assert.equal(reg.all[1].accession, 'CS.002');
  assert.equal(reg.undatedCount, 1);
  assert.deepEqual(reg.years, ['2025']);
});

test('featured falls back to works spread across the whole span, not the newest', () => {
  const images = ['2024-01-01', '2024-06-01', '2025-01-01', '2025-06-01', '2026-01-01']
    .map((d, i) => work(`${i}.jpg`, d));
  const reg = buildRegister([{ name: 'csendelet', images }]);

  // First, middle and last - otherwise the opening view cannot show that the
  // collection spans years, which is the whole argument.
  assert.deepEqual(reg.featured.map((i) => i.date), ['2024-01-01', '2025-01-01', '2026-01-01']);
});

test('an explicit featured flag wins over the spread', () => {
  const images = [
    work('a.jpg', '2024-01-01'),
    work('b.jpg', '2025-01-01', { featured: true }),
    work('c.jpg', '2026-01-01'),
  ];
  const reg = buildRegister([{ name: 'csendelet', images }]);

  assert.deepEqual(reg.featured.map((i) => i.file), ['b.jpg']);
});

test('spreadAcross always keeps both ends and never repeats an item', () => {
  const items = [1, 2, 3, 4, 5, 6, 7, 8, 9];
  const picked = spreadAcross(items, 3);

  assert.equal(picked[0], 1);
  assert.equal(picked[picked.length - 1], 9);
  assert.equal(new Set(picked).size, 3);
  assert.deepEqual(spreadAcross([1, 2], 3), [1, 2]);
});
