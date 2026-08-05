import fs from 'node:fs';
import path from 'node:path';
import yaml from 'js-yaml';

export function deriveTitleFromFilename(filename) {
  const base = path.basename(filename, path.extname(filename));
  const cleaned = base.replace(/^\d+[-_]?/, '').replace(/[-_]+/g, ' ').trim();
  const words = cleaned.length > 0 ? cleaned : base;
  return words.replace(/\b\w/g, (c) => c.toUpperCase());
}

// YAML implicit typing can turn unquoted sidecar values into non-strings
// (e.g. `date: 2026-03-12` -> Date, `technique: no` -> false). The interface
// promises opaque display strings, so coerce present values back to strings.
function asDisplayString(value) {
  if (value === undefined || value === null) return null;
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  return String(value);
}

export function loadImageMetadata(imagePath) {
  const sidecarPath = imagePath.slice(0, -path.extname(imagePath).length) + '.yml';
  if (fs.existsSync(sidecarPath)) {
    let data;
    try {
      data = yaml.load(fs.readFileSync(sidecarPath, 'utf8')) || {};
    } catch (err) {
      // js-yaml's message describes the syntax but never says which file, and
      // one bad sidecar aborts the whole build. Anyone adding a drawing hits
      // this the first time a title contains a quote, so name the file.
      throw new Error(`${sidecarPath}: hibás YAML - ${err.message}`);
    }
    return {
      title: asDisplayString(data.title) || deriveTitleFromFilename(imagePath),
      technique: asDisplayString(data.technique) || null,
      date: asDisplayString(data.date) || null,
      // Marks a work for the opening view. Anything truthy counts so `featured: yes`
      // works too, which is what someone writes when they are not thinking about YAML.
      featured: Boolean(data.featured),
    };
  }
  return {
    title: deriveTitleFromFilename(imagePath),
    technique: null,
    date: null,
    featured: false,
  };
}

export function loadBio(bioPath) {
  const data = yaml.load(fs.readFileSync(bioPath, 'utf8'));
  if (!data || !data.name) {
    throw new Error(`bio.yml at ${bioPath} must include at least a "name" field`);
  }
  return { name: data.name, age: data.age ?? null, intro: data.intro || '', categories: data.categories || {} };
}
