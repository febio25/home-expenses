// Riepilogo → Entrate: the incomes of the month by category (a donut with
// colors of its own, then one bar per category), then the incomes themselves,
// grouped by day as in "Movimenti". Opened from the "Entrate" row of the
// Riepilogo; the month can be changed here too. A row opens the income, and
// back from there returns here. Meal vouchers are the category "Buoni pasto",
// always in the light green they have in the Riepilogo chart.

import { api } from '../api.js';
import { h, formatEuro, formatShare, monthLabel, loadingBlock, errorBlock } from '../ui.js';
import { monthSwitcher, monthFromQuery, dayList } from './movements.js';
import { donut, INCOME_SLICES, summaryPath, incomeSummaryPath } from './summary.js';
import { incomeRow, newIncomePath } from './incomes.js';

const countLabel = (number) => (number === 1 ? '1 entrata' : `${number} entrate`);

// Not links: the incomes behind each total are listed right below.
function categoryBars(summary) {
  const largest = summary.by_category[0].total_cents;
  return h('ul', { class: 'card bars' }, summary.by_category.map((category) => {
    const fill = h('span', { class: 'bar-fill' });
    // Bars are relative to the largest category, so the top one is full width.
    fill.style.width = `${Math.max(2, Math.round((category.total_cents / largest) * 100))}%`;
    return h('li', { class: 'bar' },
      h('span', { class: 'bar-head' },
        h('span', { class: 'bar-name' }, category.category_name),
        h('span', { class: 'bar-amount' }, formatEuro(category.total_cents))),
      h('span', { class: 'bar-track' }, fill),
      h('span', { class: 'bar-meta' },
        `${formatShare(category.total_cents, summary.total_cents)} del mese, ${countLabel(category.income_count)}`));
  }));
}

export async function mount(root, ctx) {
  let month = monthFromQuery(ctx.query);
  const backLink = h('a', {
    class: 'page-back', href: summaryPath(month), 'aria-label': 'Torna al riepilogo',
    onclick: (event) => { event.preventDefault(); ctx.back(summaryPath(month)); },
  }, '‹');
  const switcherSlot = h('div');
  const body = h('div');
  root.append(
    h('header', { class: 'page-head' }, backLink, h('h1', { class: 'page-title' }, 'Entrate')),
    switcherSlot, body);

  // quiet: see the same option in movements.js.
  async function show(nextMonth, { quiet = false } = {}) {
    month = nextMonth;
    history.replaceState(history.state, '', incomeSummaryPath(month));
    backLink.href = summaryPath(month);
    switcherSlot.replaceChildren(monthSwitcher(month, show));
    if (!quiet) body.replaceChildren(loadingBlock());
    let summary;
    let incomes;
    try {
      [summary, incomes] = await Promise.all([
        api.get(`/summary/incomes?month=${month}`),
        api.get(`/incomes?month=${month}`),
      ]);
    } catch (error) {
      if (!quiet && ctx.isCurrent() && month === nextMonth) body.replaceChildren(errorBlock(error, () => show(month)));
      return;
    }
    if (!ctx.isCurrent() || month !== nextMonth) return; // a newer request took over

    const receipt = h('div', { class: 'receipt receipt-total' },
      h('span', { class: 'receipt-label' }, `Entrate di ${monthLabel(month)}`),
      h('span', { class: 'receipt-figure' }, formatEuro(summary.total_cents)),
      h('span', { class: 'receipt-sub' }, summary.income_count ? countLabel(summary.income_count) : 'Nessuna entrata'));
    if (!summary.income_count) {
      body.replaceChildren(receipt, h('div', { class: 'empty' },
        h('p', { class: 'empty-title' }, `Nessuna entrata a ${monthLabel(month)}`),
        h('p', { class: 'empty-text' }, 'Stipendi, rimborsi, buoni pasto: registrali e qui vedrai come si dividono.'),
        h('a', { class: 'btn btn-primary', href: newIncomePath(month), dataset: { link: '' } }, 'Aggiungi un’entrata')));
      return;
    }

    body.replaceChildren(
      receipt,
      donut(summary, 'Entrate del mese per categoria', INCOME_SLICES),
      h('h2', { class: 'section-title' }, 'Entrate per categoria'),
      categoryBars(summary),
      h('h2', { class: 'section-title' }, 'Tutte le entrate'),
      ...dayList(incomes, {
        dateOf: (income) => income.income_date,
        row: incomeRow,
        count: countLabel,
        showTotal: false, // the receipt above already has it
      }));
  }

  ctx.onResume(({ longAway }) => { if (longAway) show(month, { quiet: true }); });
  await show(month);
}
