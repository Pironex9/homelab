import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { build, loadData } from '../build.js';

test('build embeds every node with badge, ip and detail data', () => {
  const distDir = fs.mkdtempSync(path.join(os.tmpdir(), 'topology-'));
  const data = build({ distDir });
  const html = fs.readFileSync(path.join(distDir, 'index.html'), 'utf8');

  for (const node of data.nodes) {
    assert.ok(html.includes(`data-node="${node.name}"`), `card for ${node.name}`);
    if (node.ip) assert.ok(html.includes(node.ip), `ip for ${node.name}`);
  }
  const embedded = JSON.parse(html.match(/var DATA = (.*);/)[1]);
  assert.equal(embedded.nodes.length, data.nodes.length);
  assert.ok(!html.includes('undefined'));
  fs.rmSync(distDir, { recursive: true, force: true });
});

test('loadData rejects a node with an unknown kind', () => {
  const tmp = path.join(os.tmpdir(), 'bad-nodes.yml');
  fs.writeFileSync(tmp, [
    'sites:', '  - {id: lan, label: L, subnet: s}',
    'kinds:', '  lxc: {label: LXC, color: "#fff"}',
    'nodes:', '  - {badge: B, name: x, site: lan, kind: nope, role: r, detail: d, head: true}',
  ].join('\n'));
  assert.throws(() => loadData(tmp), /unknown kind/);
  fs.rmSync(tmp);
});
