import fs from 'node:fs';
import path from 'node:path';
import sharp from 'sharp';

export async function generateVariants(srcImagePath, outDir, baseName) {
  fs.mkdirSync(outDir, { recursive: true });

  const fullFile = `${baseName}-full.jpg`;
  const thumbFile = `${baseName}-thumb.jpg`;

  // Portfolio standard: ~2000px long edge for the lightbox, so zooming shows
  // real brush/pencil detail instead of upscaled mush.
  const src = await sharp(srcImagePath).metadata();
  if (src.width < 1600) {
    console.warn(`  ! ${baseName}: a forráskép csak ${src.width}px széles - a nagyítás nem fog több részletet mutatni (ajánlott 2000px+)`);
  }

  await sharp(srcImagePath)
    .resize({ width: 2000, fit: 'inside', withoutEnlargement: true })
    .jpeg({ quality: 85 })
    .toFile(path.join(outDir, fullFile));

  // 640px so masonry columns stay sharp on 2x displays
  const thumbInfo = await sharp(srcImagePath)
    .resize({ width: 640, fit: 'inside', withoutEnlargement: true })
    .jpeg({ quality: 80 })
    .toFile(path.join(outDir, thumbFile));

  return { full: fullFile, thumb: thumbFile, width: thumbInfo.width, height: thumbInfo.height };
}
