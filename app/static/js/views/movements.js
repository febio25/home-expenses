// "Movimenti": the month's expenses, newest first, grouped by day.

import { api } from '../api.js';
import {
  h, icon, formatEuro, monthLabel, dayLabel, currentMonth, shiftMonth,
  PAYMENT_LABELS, loadingBlock, errorBlock,
} from '../ui.js';

const MONTH_SHAPE = /^\d{4}-(0[1-9]|1[0-2])$/;

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

function expenseRow(expense) {
  const title = expense.merchant_name || expense.category_name;
  const meta = [
    expense.merchant_name ? expense.category_name : null,
    expense.paid_by_name,
    PAYMENT_LABELS[expense.payment_method].toLowerCase(),
  ].filter(Boolean).join(', ');
  return h('a', { class: 'row', href: `/spesa/${expense.id}`, dataset: { link: '' } },
    h('span', { class: 'row-main' },
      h('span', { class: 'row-title' }, title),
      h('span', { class: 'row-meta' }, meta),
      expense.note ? h('span', { class: 'row-note' }, expense.note) : null),
    h('span', { class: 'row-amount' }, formatEuro(expense.amount_cents)));
}

export async function mount(root, ctx) {
  const requested = ctx.query.get('mese');
  let month = requested && MONTH_SHAPE.test(requested) ? requested : currentMonth();
  const head = h('header', { class: 'page-head' }, h('h1', { class: 'page-title' }, 'Movimenti'));
  const switcherSlot = h('div');
  const body = h('div');
  root.append(head, switcherSlot, body);

  // quiet: refresh in place (back from the background), keeping what is on
  // screen until the new data arrives, and keeping it if the refresh fails.
  async function show(nextMonth, { quiet = false } = {}) {
    month = nextMonth;
    history.replaceState(null, '', month === currentMonth() ? '/movimenti' : `/movimenti?mese=${month}`);
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

    const total = expenses.reduce((sum, expense) => sum + expense.amount_cents, 0);
    const groups = new Map(); // date -> expenses, insertion order = newest day first
    for (const expense of expenses) {
      if (!groups.has(expense.expense_date)) groups.set(expense.expense_date, []);
      groups.get(expense.expense_date).push(expense);
    }

    body.replaceChildren(
      h('p', { class: 'month-total' },
        h('span', { class: 'month-total-amount' }, formatEuro(total)),
        h('span', { class: 'month-total-count' },
          expenses.length === 1 ? '1 spesa' : `${expenses.length} spese`)),
      ...Array.from(groups, ([date, items]) => h('section', { class: 'day' },
        h('h2', { class: 'day-head' },
          h('span', {}, dayLabel(date)),
          h('span', { class: 'day-total' },
            formatEuro(items.reduce((sum, expense) => sum + expense.amount_cents, 0)))),
        h('div', { class: 'card rows' }, items.map(expenseRow)))));
  }

  ctx.onResume(({ longAway }) => { if (longAway) show(month, { quiet: true }); });
  await show(month);
}
