import fs from 'node:fs';
import path from 'node:path';
import { loadImageMetadata } from './metadata.js';

const IMAGE_EXTENSIONS = new Set(['.jpg', '.jpeg', '.png', '.webp']);

export function scanContent(contentDir) {
  const categories = [];
  const categoryNames = fs.readdirSync(contentDir, { withFileTypes: true })
    .filter((e) => e.isDirectory())
    .map((e) => e.name)
    .sort();

  for (const categoryName of categoryNames) {
    const categoryDir = path.join(contentDir, categoryName);
    const images = fs.readdirSync(categoryDir, { withFileTypes: true })
      .filter((e) => e.isFile() && IMAGE_EXTENSIONS.has(path.extname(e.name).toLowerCase()))
      .map((e) => e.name)
      .sort()
      .map((file) => {
        const imagePath = path.join(categoryDir, file);
        return { file, path: imagePath, ...loadImageMetadata(imagePath) };
      });

    if (images.length > 0) {
      categories.push({ name: categoryName, images });
    }
  }

  return categories;
}
