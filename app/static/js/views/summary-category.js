// Riepilogo → one category: the expenses behind a category total, newest
// first and grouped by day as in "Movimenti". A row opens the expense, and
// back from there returns here. The month can be changed without leaving
// the category, to compare it with the months before.

import { api } from '../api.js';
import { loadCategories } from '../store.js';
import { h, monthLabel, loadingBlock, errorBlock } from '../ui.js';
import { monthSwitcher, monthFromQuery, expenseList } from './movements.js';
import { categoryPath, summaryPath } from './summary.js';

// The category's name comes from the category list, so it is known in a
// month with no expenses too, and for a category deactivated since. A
// category created a moment ago by the other person may be missing from the
// cached list: look once more before giving up.
async function findCategory(categoryId) {
  let category = (await loadCategories()).find((item) => item.id === categoryId);
  if (!category) category = (await loadCategories({ force: true })).find((item) => item.id === categoryId);
  return category || null;
}

export async function mount(root, ctx) {
  const categoryId = Number(ctx.params[0]);
  let month = monthFromQuery(ctx.query);

  const title = h('h1', { class: 'page-title' }, 'Categoria');
  const backLink = h('a', {
    class: 'page-back', href: summaryPath(month), 'aria-label': 'Torna al riepilogo',
    onclick: (event) => { event.preventDefault(); ctx.back(summaryPath(month)); },
  }, '‹');
  const switcherSlot = h('div');
  const body = h('div');
  root.append(h('header', { class: 'page-head' }, backLink, title), switcherSlot, body);

  // quiet: see the same option in movements.js.
  async function show(nextMonth, { quiet = false } = {}) {
    month = nextMonth;
    history.replaceState(history.state, '', categoryPath(categoryId, month));
    backLink.href = summaryPath(month);
    switcherSlot.replaceChildren(monthSwitcher(month, show));
    if (!quiet) body.replaceChildren(loadingBlock());
    let category;
    let expenses;
    try {
      [category, expenses] = await Promise.all([
        findCategory(categoryId),
        api.get(`/expenses?month=${month}&category_id=${categoryId}`),
      ]);
    } catch (error) {
      if (!quiet && ctx.isCurrent() && month === nextMonth) body.replaceChildren(errorBlock(error, () => show(month)));
      return;
    }
    if (!ctx.isCurrent() || month !== nextMonth) return; // a newer request took over

    if (!category) {
      title.textContent = 'Categoria';
      switcherSlot.replaceChildren();
      body.replaceChildren(h('div', { class: 'empty' },
        h('p', { class: 'empty-title' }, 'Categoria non trovata'),
        h('a', { class: 'btn btn-primary', href: '/riepilogo', dataset: { link: '' } }, 'Torna al riepilogo')));
      return;
    }
    title.textContent = category.name;

    if (expenses.length === 0) {
      body.replaceChildren(h('div', { class: 'empty' },
        h('p', { class: 'empty-title' }, `Nessuna spesa in «${category.name}» a ${monthLabel(month)}`)));
      return;
    }
    body.replaceChildren(...expenseList(expenses, { showCategory: false }));
  }

  ctx.onResume(({ longAway }) => { if (longAway) show(month, { quiet: true }); });
  await show(month);
}
