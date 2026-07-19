import fs from 'node:fs';
import path from 'node:path';
import yaml from 'js-yaml';

export function deriveTitleFromFilename(filename) {
  const base = path.basename(filename, path.extname(filename));
  const cleaned = base.replace(/^\d+[-_]?/, '').replace(/[-_]+/g, ' ').trim();
  const words = cleaned.length > 0 ? cleaned : base;
  return words.replace(/\b\w/g, (c) => c.toUpperCase());
}

export function loadImageMetadata(imagePath) {
  const sidecarPath = imagePath.slice(0, -path.extname(imagePath).length) + '.yml';
  if (fs.existsSync(sidecarPath)) {
    const data = yaml.load(fs.readFileSync(sidecarPath, 'utf8')) || {};
    return {
      title: data.title || deriveTitleFromFilename(imagePath),
      technique: data.technique || null,
      date: data.date || null,
    };
  }
  return { title: deriveTitleFromFilename(imagePath), technique: null, date: null };
}

export function loadBio(bioPath) {
  const data = yaml.load(fs.readFileSync(bioPath, 'utf8'));
  if (!data || !data.name) {
    throw new Error(`bio.yml at ${bioPath} must include at least a "name" field`);
  }
  return { name: data.name, age: data.age ?? null, intro: data.intro || '' };
}
