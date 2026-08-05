// The accession register: what turns a folder of files into a numbered,
// dated collection. Everything here is derived from data that already exists
// on disk - nothing is invented. A work with no date keeps its number and
// simply has no year, because a made-up year would be worse than a gap.

// Two letters is enough for four categories and keeps the code readable at a
// glance. Longer prefixes are handed out only when two categories would
// otherwise collide, so adding a "portre-2" folder cannot silently renumber
// everything that already exists.
export function categoryPrefixes(categoryNames) {
  const prefixes = new Map();
  const used = new Set();
  for (const name of categoryNames) {
    const letters = name.replace(/[^a-z]/gi, '').toUpperCase() || 'X';
    let width = 2;
    let prefix = letters.slice(0, width);
    while (used.has(prefix) && width < letters.length) {
      width += 1;
      prefix = letters.slice(0, width);
    }
    // Still colliding after using the whole name: fall back to a counter so
    // the build never emits two works under one accession number.
    let candidate = prefix;
    let n = 2;
    while (used.has(candidate)) candidate = `${prefix}${n++}`;
    used.add(candidate);
    prefixes.set(name, candidate);
  }
  return prefixes;
}

// Dates arrive as display strings (metadata.js coerces them), so sort on the
// string: ISO dates sort correctly that way and anything else sorts stably
// among its own kind rather than throwing.
function byDateThenFile(a, b) {
  const ad = a.date || '';
  const bd = b.date || '';
  if (ad && bd && ad !== bd) return ad < bd ? -1 : 1;
  if (ad && !bd) return -1; // undated works sort last: they cannot be placed
  if (!ad && bd) return 1;
  return a.file < b.file ? -1 : a.file > b.file ? 1 : 0;
}

// Picks `count` items spaced evenly from first to last, always including both
// ends. With fewer items than asked for, every item is returned rather than
// padding the row out with repeats.
export function spreadAcross(items, count) {
  if (items.length <= count) return items.slice();
  if (count <= 1) return items.slice(0, count);
  const step = (items.length - 1) / (count - 1);
  return Array.from({ length: count }, (_, i) => items[Math.round(i * step)]);
}

/**
 * Numbers every work in arrival order across the whole collection, the way a
 * real accession register does - not per category. That ordering is the point:
 * the number itself records how the collection grew.
 *
 * Mutates and returns the same category objects scan.js produced.
 */
export function buildRegister(categories, { featuredCount = 3 } = {}) {
  const prefixes = categoryPrefixes(categories.map((c) => c.name));

  const all = [];
  for (const category of categories) {
    for (const image of category.images) {
      image.category = category.name;
      all.push(image);
    }
  }
  all.sort(byDateThenFile);

  all.forEach((image, i) => {
    const seq = String(i + 1).padStart(3, '0');
    const year = image.date ? String(image.date).slice(2, 4) : null;
    image.seq = i + 1;
    image.accession = year
      ? `${prefixes.get(image.category)}.${seq}/${year}`
      : `${prefixes.get(image.category)}.${seq}`;
  });

  const dated = all.filter((image) => image.date);

  // Explicit `featured: true` wins. With none marked, spread the stand-ins
  // evenly across the collection's whole span rather than taking the newest
  // three: the opening view's job is to show that this runs over years, and
  // three works from the same month cannot say that. Recency and spread are
  // both facts we hold; a quality judgement is not, so the default never
  // claims to be picking the best.
  const marked = all.filter((image) => image.featured);
  const featured = marked.length > 0
    ? marked.slice(0, featuredCount)
    : spreadAcross(dated.length > 0 ? dated : all, featuredCount);
  const years = [...new Set(dated.map((image) => String(image.date).slice(0, 4)))].sort();

  return {
    all,
    featured,
    years,
    undatedCount: all.length - dated.length,
    firstDate: dated.length > 0 ? dated[0].date : null,
    prefixes,
  };
}
