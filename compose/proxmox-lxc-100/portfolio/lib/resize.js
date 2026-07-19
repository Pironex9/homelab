import fs from 'node:fs';
import path from 'node:path';
import sharp from 'sharp';

export async function generateVariants(srcImagePath, outDir, baseName) {
  fs.mkdirSync(outDir, { recursive: true });

  const fullFile = `${baseName}-full.jpg`;
  const thumbFile = `${baseName}-thumb.jpg`;

  await sharp(srcImagePath)
    .resize({ width: 1600, fit: 'inside', withoutEnlargement: true })
    .jpeg({ quality: 85 })
    .toFile(path.join(outDir, fullFile));

  await sharp(srcImagePath)
    .resize({ width: 400, fit: 'inside', withoutEnlargement: true })
    .jpeg({ quality: 80 })
    .toFile(path.join(outDir, thumbFile));

  return { full: fullFile, thumb: thumbFile };
}
