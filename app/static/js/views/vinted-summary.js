// Vinted → Riepilogo (0.8.0): the month of the section. Sales, Vinted
// expenses (purchases and extras such as shipping supplies) and their
// difference; the gain on the items sold in the month; the six-month chart
// of the household summary with the section's figures; the year's sales
// against the DAC7 thresholds. Deeper analysis stays on the CSV.

import { api } from '../api.js';
import { h, formatEuro, euroParts, formatSignedEuro, monthLabel, currentMonth, loadingBlock, errorBlock } from '../ui.js';
import { monthSwitcher, monthFromQuery } from './movements.js';
import { trendChart, exploreLink } from './summary.js';
import { explorePath } from './explore.js';
import { vintedHead } from './vinted.js';

const TREND_MONTHS = 6;
// DAC7 (D.Lgs. 32/2023): a seller is left out of the platform's report
// only with fewer than 30 sales AND at most 2,000 EUR in the calendar year;
// 30 sales, or more than 2,000 EUR, and the data reach the tax office.
const DAC7_SALES = 30;
const DAC7_CENTS = 200000;

// The words of the chart for the section: sales and Vinted expenses; a
// month with purchases only has a real, negative difference.
const VINTED_TREND = {
  title: 'Vendite e spese Vinted',
  income: 'Vendite',
  expense: 'Spese',
  noIncome: 'Nessuna vendita',
  incomeWord: 'vendite',
  noIncomeAria: 'nessuna',
  note: 'Sotto ogni mese: vendite meno spese.',
  hasDifference: (item) => item.income_count > 0 || item.expense_count > 0,
};

export function vintedSummaryPath(month) {
  return month === currentMonth() ? '/vinted/riepilogo' : `/vinted/riepilogo?mese=${month}`;
}

const plural = (count, one, many) => (count === 1 ? `1 ${one}` : `${count} ${many}`);

function signClass(cents) {
  if (cents > 0) return 'is-positive';
  return cents < 0 ? 'is-negative' : '';
}

function row(name, meta, amount, amountClass = '') {
  return h('div', { class: 'balance-row' },
    h('span', { class: 'balance-main' },
      h('span', { class: 'balance-name' }, name),
      h('span', { class: 'balance-meta' }, meta)),
    h('span', { class: `balance-amount ${amountClass}`.trim() }, amount));
}

function spentMeta(summary) {
  if (!summary.expense_count) return 'Nessuna spesa Vinted nel mese';
  const parts = [];
  if (summary.purchase_count) parts.push(plural(summary.purchase_count, 'articolo comprato', 'articoli comprati'));
  if (summary.extra_count) parts.push(plural(summary.extra_count, 'costo extra', 'costi extra'));
  return parts.join(' e ');
}

function meter(label, value, share) {
  const fill = h('span', { class: 'bar-fill' });
  fill.style.width = `${Math.min(100, share > 0 ? Math.max(2, Math.round(share * 100)) : 0)}%`;
  return h('div', { class: 'meter' },
    h('div', { class: 'meter-head' }, h('span', {}, label), h('span', { class: 'meter-value' }, value)),
    h('span', { class: 'bar-track' }, fill));
}

function yearCard(summary) {
  return [
    h('h2', { class: 'section-title' }, `Anno ${summary.year} e soglie DAC7`),
    h('div', { class: 'card' },
      meter('Vendite', `${summary.year_sales_count} su ${DAC7_SALES}`, summary.year_sales_count / DAC7_SALES),
      meter('Incassi', `${formatEuro(summary.year_sales_cents)} su 2.000 €`, summary.year_sales_cents / DAC7_CENTS),
      h('p', { class: 'card-note' },
        'Indicativo: fa fede il conteggio di Vinted. Con almeno 30 vendite o più di 2.000 € nell’anno, i dati delle vendite arrivano all’Agenzia delle Entrate.')),
  ];
}

export async function mount(root, ctx) {
  let month = monthFromQuery(ctx.query);
  const switcherSlot = h('div');
  const body = h('div');
  root.append(...vintedHead('summary', ctx.navigate), switcherSlot, body);

  // quiet: see the same option in movements.js.
  async function show(nextMonth, { quiet = false } = {}) {
    month = nextMonth;
    history.replaceState(history.state, '', vintedSummaryPath(month));
    switcherSlot.replaceChildren(monthSwitcher(month, show));
    if (!quiet) body.replaceChildren(loadingBlock());
    let summary;
    let trend;
    try {
      [summary, trend] = await Promise.all([
        api.get(`/vinted/summary?month=${month}`),
        api.get(`/vinted/summary/trend?month=${month}&months=${TREND_MONTHS}`),
      ]);
    } catch (error) {
      if (!quiet && ctx.isCurrent() && month === nextMonth) body.replaceChildren(errorBlock(error, () => show(month)));
      return;
    }
    if (!ctx.isCurrent() || month !== nextMonth) return; // a newer request took over

    const parts = [
      h('div', { class: 'receipt receipt-total' },
        h('span', { class: 'receipt-label' }, `Vendite di ${monthLabel(month)}`),
        h('span', { class: 'receipt-figure' }, ...euroParts(summary.sales_cents)),
        h('span', { class: 'receipt-sub' },
          summary.sales_count ? plural(summary.sales_count, 'vendita', 'vendite') : 'Nessuna vendita')),
    ];
    const rows = [row('Spese Vinted', spentMeta(summary), formatEuro(summary.expense_cents))];
    if (summary.sales_count || summary.expense_count) {
      rows.push(row('Differenza', 'Vendite meno spese del mese',
        formatSignedEuro(summary.balance_cents), `balance-diff ${signClass(summary.balance_cents)}`));
    }
    parts.push(h('div', { class: 'card balance' }, rows));

    parts.push(h('h2', { class: 'section-title' }, 'Articoli venduti'));
    parts.push(h('div', { class: 'card balance balance-flush' }, summary.sold_count
      ? row('Guadagno',
        `${plural(summary.sold_count, 'articolo', 'articoli')}: incassati ${formatEuro(summary.sold_cents)}, pagati ${formatEuro(summary.sold_cost_cents)} per comprarli; le cose già vostre costano zero`,
        formatSignedEuro(summary.gain_cents), `balance-diff ${signClass(summary.gain_cents)}`)
      : row('Guadagno', 'Nessun articolo venduto nel mese', '–')));

    // The chart is left out only when the six months are all empty; the
    // link to "Esplora" stays.
    const explore = explorePath('vinted', month);
    if (trend.some((item) => item.income_count || item.expense_count)) {
      parts.push(trendChart(trend, VINTED_TREND, { explore }));
    } else {
      parts.push(h('div', { class: 'card explore-card' }, exploreLink(explore)));
    }
    parts.push(...yearCard(summary));
    body.replaceChildren(...parts);
  }

  ctx.onResume(({ longAway }) => { if (longAway) show(month, { quiet: true }); });
  await show(month);
}
