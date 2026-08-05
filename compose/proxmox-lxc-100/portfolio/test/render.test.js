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

test('the detail view has a zoom stage that only activates when the file has extra pixels', () => {
  const html = renderIndexHtml(sampleInput);

  assert.match(html, /id="detail-stage"/);
  assert.match(html, /naturalWidth > img\.clientWidth/);
  assert.match(html, /classList\.toggle\('zoomed'\)/);
});

test('both views render every work, so the page works with JavaScript off', () => {
  const html = renderIndexHtml(sampleInput);

  // Once per drawer card and once per ledger row. Matched together with
  // data-cat so the querySelectorAll('[data-work]') inside the client script
  // is not counted as a fifth work.
  const cards = html.match(/data-work data-cat=/g) || [];
  assert.equal(cards.length, 4);
  assert.match(html, /id="view-fiok"/);
  assert.match(html, /id="view-naplo"/);
});

test('the register numbers every work and the numbers reach the page', () => {
  const html = renderIndexHtml(sampleInput);

  // csendelet is CS, anime-karakter is AN; the undated work sorts last and
  // therefore carries no year suffix.
  assert.match(html, /CS\.001\/26/);
  assert.match(html, /AN\.002(?!\/)/);
});

test('the date stamp is live text, never an image', () => {
  const html = renderIndexHtml(sampleInput);

  assert.match(html, /<span class="stamp"[^>]*>2026 márc 12\.<\/span>/);
});

test('renderIndexHtml escapes HTML-sensitive characters in bio and titles', () => {
  const html = renderIndexHtml({
    bio: { name: '<script>alert(1)</script>', age: null, intro: '' },
    categories: [],
  });

  assert.doesNotMatch(html, /<script>alert\(1\)<\/script>/);
  assert.match(html, /&lt;script&gt;/);
});
