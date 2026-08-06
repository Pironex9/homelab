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

test('lightbox has a zoom stage that only activates when the file has extra pixels', () => {
  const html = renderIndexHtml(sampleInput);

  assert.match(html, /id="lightbox-stage"/);
  assert.match(html, /naturalWidth > el\.clientWidth/);
  assert.match(html, /classList\.toggle\('zoomed'\)/);
});

test('renderIndexHtml escapes HTML-sensitive characters in bio and titles', () => {
  const html = renderIndexHtml({
    bio: { name: '<script>alert(1)</script>', age: null, intro: '' },
    categories: [],
  });

  assert.doesNotMatch(html, /<script>alert\(1\)<\/script>/);
  assert.match(html, /&lt;script&gt;/);
});
