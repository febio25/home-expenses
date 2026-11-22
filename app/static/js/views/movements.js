// "Movimenti": the month's expenses, newest first, grouped by day. The
// switch at the top leads to the month's incomes (incomes.js), in the same tab.

import { api } from '../api.js';
import { state } from '../store.js';
import {
  h, icon, mainHead, formatEuro, monthLabel, dayLabel, currentMonth, shiftMonth,
  PAYMENT_LABELS, loadingBlock, errorBlock,
} from '../ui.js';

const MONTH_SHAPE = /^\d{4}-(0[1-9]|1[0-2])$/;

// The month asked for in the address (?mese=2026-10), or the current one.
export function monthFromQuery(query) {
  const requested = query.get('mese');
  return requested && MONTH_SHAPE.test(requested) ? requested : currentMonth();
}

// Addresses of the two lists; the month is left out when current.
export function movementsPath(month) {
  return month === currentMonth() ? '/movimenti' : `/movimenti?mese=${month}`;
}

export function incomesPath(month) {
  return month === currentMonth() ? '/entrate' : `/entrate?mese=${month}`;
}

// "Spese | Entrate" at the top of the two lists, on the same month. It acts
// like a tab: switching replaces the history entry instead of adding one, so
// Android's back button does not bounce between the two lists.
export function movementsSwitch(active, month, navigate) {
  const item = (id, label, pathFor) => h('a', {
    class: `seg-item${id === active ? ' is-selected' : ''}`,
    href: pathFor(month),
    'aria-current': id === active ? 'page' : null,
    onclick: (event) => {
      event.preventDefault();
      if (id !== active) navigate(pathFor(month), { replace: true });
    },
  }, label);
  return h('nav', { class: 'seg seg-links', 'aria-label': 'Spese o entrate' },
    item('expenses', 'Spese', movementsPath),
    item('incomes', 'Entrate', incomesPath));
}

// Shared with the summary screen: "‹  novembre 2026  ›"
export function monthSwitcher(month, onChange) {
  const isCurrent = month >= currentMonth();
  return h('div', { class: 'month-switch' },
    h('button', {
      class: 'month-step', type: 'button', 'aria-label': 'Mese precedente',
      onclick: () => onChange(shiftMonth(month, -1)),
    }, icon('left')),
    h('span', { class: 'month-name', 'aria-live': 'polite' }, monthLabel(month)),
    h('button', {
      class: 'month-step', type: 'button', 'aria-label': 'Mese successivo', disabled: isCurrent,
      onclick: () => onChange(shiftMonth(month, 1)),
    }, icon('right')));
}

// An expense or income that is the purchase or the sale of a Vinted item
// (0.8.0) names the item, and opens it: its price and date are edited from
// there, and its category stays Vinted.
export function vintedLine(title) {
  return h('span', { class: 'row-link-tag' }, icon('tag'), h('span', { class: 'row-link-text' }, title));
}

// showCategory: false in the list of a single category, where it would
// repeat the same name on every row.
function expenseRow(expense, { showCategory = true } = {}) {
  const title = expense.merchant_name || (showCategory ? expense.category_name : 'Senza esercente');
  const meta = [
    showCategory && expense.merchant_name ? expense.category_name : null,
    expense.paid_by_name,
    PAYMENT_LABELS[expense.payment_method].toLowerCase(),
  ].filter(Boolean).join(', ');
  const href = expense.vinted_item_id ? `/vinted/articolo/${expense.vinted_item_id}` : `/spesa/${expense.id}`;
  return h('a', { class: 'row', href, dataset: { link: '' } },
    h('span', { class: 'row-main' },
      h('span', { class: 'row-title' }, title),
      h('span', { class: 'row-meta' }, meta),
      expense.vinted_item_id ? vintedLine(expense.vinted_item_title) : null,
      expense.note ? h('span', { class: 'row-note' }, expense.note) : null),
    h('span', { class: 'row-amount' }, formatEuro(expense.amount_cents)));
}

// Total of the list, then one section per day (newest first) with its total.
// items must be newest first; dateOf gives an item's date, row draws it and
// count words the number ("3 spese"). Shared by expenses and incomes.
// showTotal: false where the screen already shows the total above.
export function dayList(items, { dateOf, row, count, showTotal = true }) {
  const sum = (list) => list.reduce((total, item) => total + item.amount_cents, 0);
  const groups = new Map(); // date -> items, insertion order = newest day first
  for (const item of items) {
    const date = dateOf(item);
    if (!groups.has(date)) groups.set(date, []);
    groups.get(date).push(item);
  }
  const total = h('p', { class: 'month-total' },
    h('span', { class: 'month-total-amount' }, formatEuro(sum(items))),
    h('span', { class: 'month-total-count' }, count(items.length)));
  return [
    ...(showTotal ? [total] : []), // the callers spread this into replaceChildren: no nulls
    ...Array.from(groups, ([date, dayItems]) => h('section', { class: 'day' },
      h('h2', { class: 'day-head' },
        h('span', {}, dayLabel(date)),
        h('span', { class: 'day-total' }, formatEuro(sum(dayItems)))),
      h('div', { class: 'card rows' }, dayItems.map(row)))),
  ];
}

// Shared with the summary of a single category.
export function expenseList(expenses, rowOptions) {
  return dayList(expenses, {
    dateOf: (expense) => expense.expense_date,
    row: (expense) => expenseRow(expense, rowOptions),
    count: (number) => (number === 1 ? '1 spesa' : `${number} spese`),
  });
}

export async function mount(root, ctx) {
  let month = monthFromQuery(ctx.query);
  const head = mainHead('Movimenti', state.me.display_name);
  const tabSlot = h('div');
  const switcherSlot = h('div');
  const body = h('div');
  root.append(head, tabSlot, switcherSlot, body);

  // quiet: refresh in place (back from the background), keeping what is on
  // screen until the new data arrives, and keeping it if the refresh fails.
  async function show(nextMonth, { quiet = false } = {}) {
    month = nextMonth;
    history.replaceState(history.state, '', movementsPath(month));
    tabSlot.replaceChildren(movementsSwitch('expenses', month, ctx.navigate));
    switcherSlot.replaceChildren(monthSwitcher(month, show));
    if (!quiet) body.replaceChildren(loadingBlock());
    let expenses;
    try {
      expenses = await api.get(`/expenses?month=${month}`);
    } catch (error) {
      if (!quiet && ctx.isCurrent() && month === nextMonth) body.replaceChildren(errorBlock(error, () => show(month)));
      return;
    }
    if (!ctx.isCurrent() || month !== nextMonth) return; // a newer request took over

    if (expenses.length === 0) {
      body.replaceChildren(h('div', { class: 'empty' },
        h('p', { class: 'empty-title' }, `Nessuna spesa a ${monthLabel(month)}`),
        month === currentMonth()
          ? h('a', { class: 'btn btn-primary', href: '/', dataset: { link: '' } }, 'Aggiungi una spesa')
          : null));
      return;
    }

    body.replaceChildren(...expenseList(expenses));
  }

  ctx.onResume(({ longAway }) => { if (longAway) show(month, { quiet: true }); });
  await show(month);
}
