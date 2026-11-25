// Last data shown by the main screens (0.14.0), in memory only: going back
// to Movimenti, Riepilogo or Vinted draws it at once, then refreshes it
// quietly. Any successful write (api.js) empties it, so a screen never
// shows a list that misses what was just saved: after a write the screen
// loads as before.

const entries = new Map();

export const viewCache = {
  get(key) {
    return entries.has(key) ? entries.get(key) : null;
  },
  set(key, data) {
    entries.set(key, data);
  },
  clear() {
    entries.clear();
  },
};

// True when two API answers carry the same data: a quiet refresh that
// brings nothing new does not redraw (the screen keeps its scroll).
export function sameData(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}
