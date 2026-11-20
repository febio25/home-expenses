// "Movimenti → Entrate": the month's incomes (salaries, refunds, gifts...),
// newest first and grouped by day like the expenses. Same tab as the
// expense list: the switch at the top moves between the two, on the same
// month. "Nuova entrata" sits at the bottom, in reach of the thumb.

import { api } from '../api.js';
import { h, formatEuro, monthLabel, currentMonth, loadingBlock, errorBlock } from '../ui.js';
import { monthSwitcher, monthFromQuery, movementsSwitch, incomesPath, dayList } from './movements.js';

// From the list of a past month, a new income starts in that month.
export function newIncomePath(month) {
  return month === currentMonth() ? '/entrate/nuova' : `/entrate/nuova?mese=${month}`;
}

function incomeRow(income) {
  return h('a', { class: 'row', href: `/entrate/${income.id}`, dataset: { link: '' } },
    h('span', { class: 'row-main' },
      h('span', { class: 'row-title' }, income.category_name),
      h('span', { class: 'row-meta' }, income.received_by_name),
      income.note ? h('span', { class: 'row-note' }, income.note) : null),
    h('span', { class: 'row-amount' }, formatEuro(income.amount_cents)));
}

export async function mount(root, ctx) {
  let month = monthFromQuery(ctx.query);
  const tabSlot = h('div');
  const switcherSlot = h('div');
  const body = h('div');
  const addLink = h('a', { class: 'btn btn-primary btn-block', dataset: { link: '' } }, 'Nuova entrata');
  root.append(
    h('header', { class: 'page-head' }, h('h1', { class: 'page-title' }, 'Movimenti')),
    tabSlot, switcherSlot, body,
    h('div', { class: 'footer-bar' }, addLink));

  // quiet: see the same option in movements.js.
  async function show(nextMonth, { quiet = false } = {}) {
    month = nextMonth;
    history.replaceState(history.state, '', incomesPath(month));
    tabSlot.replaceChildren(movementsSwitch('incomes', month, ctx.navigate));
    switcherSlot.replaceChildren(monthSwitcher(month, show));
    addLink.href = newIncomePath(month);
    if (!quiet) body.replaceChildren(loadingBlock());
    let incomes;
    try {
      incomes = await api.get(`/incomes?month=${month}`);
    } catch (error) {
      if (!quiet && ctx.isCurrent() && month === nextMonth) body.replaceChildren(errorBlock(error, () => show(month)));
      return;
    }
    if (!ctx.isCurrent() || month !== nextMonth) return; // a newer request took over

    if (incomes.length === 0) {
      body.replaceChildren(h('div', { class: 'empty' },
        h('p', { class: 'empty-title' }, `Nessuna entrata a ${monthLabel(month)}`),
        h('p', { class: 'empty-text' },
          'Stipendi, rimborsi, regali, vendite: registrali qui e nel Riepilogo vedrai quanto resta ogni mese.')));
      return;
    }
    body.replaceChildren(...dayList(incomes, {
      dateOf: (income) => income.income_date,
      row: incomeRow,
      count: (number) => (number === 1 ? '1 entrata' : `${number} entrate`),
    }));
  }

  ctx.onResume(({ longAway }) => { if (longAway) show(month, { quiet: true }); });
  await show(month);
}
