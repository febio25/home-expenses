// The categories of the entry forms as icons, four to a row (0.15.0).
// Shared by the expense form and the income form.
//
// An icon alone is quick once learnt, so the name of the chosen category is
// always written somewhere in view:
// - in the label above the grid, «Categoria · Ristoranti e bar», close to
//   the amount and the merchant, in view with the keyboard open;
// - in a bubble over the icon for 1.5 s, where the thumb is: it confirms the
//   tap, and also shows what a known merchant picked on its own;
// - through `onName`, for the Save button («Salva in Ristoranti e bar»).
// Every button has the name as aria-label and title.

import { h } from './ui.js';
import { categoryIcon } from './category-icons.js';

const BUBBLE_MS = 1500;

// items: [{ key, name, icon }]; onPick(key) after a tap; onName(name|null)
// whenever the chosen category changes, by hand or not.
export function createCategoryPicker({ items, selected = null, labelId, onPick = () => {}, onName = () => {} }) {
  let current = selected;
  let list = items;
  let bubbleKey = null;
  let bubbleTimer = null;

  const nameSlot = h('b', { class: 'cat-chosen' });
  // aria-live: a screen reader hears the name chosen by a merchant too.
  const label = h('span', { class: 'label cat-label', id: labelId, 'aria-live': 'polite' }, 'Categoria');
  const grid = h('div', { class: 'cat-grid cat-grid-icons', role: 'group', 'aria-labelledby': labelId });

  function chosen() { return list.find((item) => item.key === current) || null; }

  function renderLabel() {
    const item = chosen();
    if (item) {
      nameSlot.textContent = item.name;
      label.replaceChildren('Categoria · ', nameSlot);
    } else {
      label.replaceChildren('Categoria');
    }
  }

  function render() {
    grid.replaceChildren(...list.map((item) => {
      const isSelected = item.key === current;
      return h('button', {
        class: `cat cat-icon-only${isSelected ? ' is-selected' : ''}`,
        type: 'button',
        title: item.name,
        'aria-label': item.name,
        'aria-pressed': String(isSelected),
        dataset: { key: String(item.key) },
        onclick: () => {
          set(item.key, { bubble: true });
          onPick(item.key);
        },
      }, categoryIcon(item.icon), item.key === bubbleKey
        ? h('span', { class: 'cat-bubble', 'aria-hidden': 'true' }, item.name)
        : null);
    }));
    renderLabel();
  }

  function showBubble(key) {
    clearTimeout(bubbleTimer);
    bubbleKey = key;
    bubbleTimer = setTimeout(() => { bubbleKey = null; render(); }, BUBBLE_MS);
  }

  // Choose a category (null: none). `bubble`: show its name over the icon.
  function set(key, { bubble = false } = {}) {
    const before = current;
    current = key;
    if (bubble && key !== null) showBubble(key);
    render();
    if (before !== current) {
      const item = chosen();
      onName(item ? item.name : null);
    }
  }

  function setItems(next) {
    list = next;
    render();
    const item = chosen();
    onName(item ? item.name : null);
  }

  render();
  return {
    label, grid, set, setItems,
    name: () => (chosen() ? chosen().name : null),
  };
}
