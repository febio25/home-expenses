// Tags in the notes of the expenses (0.18.0, F2): "#vacanze" groups
// expenses of different categories under one purpose. The same rule as
// app/tags.py: "#" then a letter or a digit, then letters, digits, "-" or
// "_"; not right after a letter, a digit or "&". Equal without case and
// accents.

const TAG = /(?<![\p{L}\p{N}_&])#([\p{L}\p{N}][\p{L}\p{N}_-]*)/gu;
const MAX_TAG = 40;

export function fold(text) {
  return text.normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase();
}

// The tags of a note, without "#", each once, as written.
export function tagsIn(note) {
  if (!note || !note.includes('#')) return [];
  const seen = new Set();
  const found = [];
  for (const match of note.matchAll(TAG)) {
    const tag = match[1].replace(/[-_]+$/, '').slice(0, MAX_TAG);
    const key = fold(tag);
    if (tag && !seen.has(key)) {
      seen.add(key);
      found.push(tag);
    }
  }
  return found;
}

// The note without its tags, for the line under a row: "Cena #vacanze"
// gives "Cena"; a note of tags only gives "".
export function noteWithoutTags(note) {
  if (!note) return '';
  return note.replace(TAG, '').replace(/\s+/g, ' ').replace(/^[\s,;·-]+|[\s,;·-]+$/g, '');
}

// The "#partial" being typed at the end of `text` (the note up to the
// cursor): { start, partial } or null.
export function typedTag(text) {
  const match = /(^|[\s(])#([\p{L}\p{N}_-]*)$/u.exec(text);
  if (!match) return null;
  return { start: match.index + match[1].length, partial: match[2] };
}
