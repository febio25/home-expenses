// Vinted → Riepilogo (0.8.0; rebuilt in 0.18.1 like the Riepilogo of the
// household): the month as a ledger (sales, Vinted expenses with purchases
// and extras, the difference), the bars of six months (a tap shows that
// month) with the way to Esplora, the year's sales against the DAC7
// thresholds. The gain on the items sold lives in Esplora, for a month, a
// year, six months or any dates. Deeper analysis stays on the CSV.

import { api } from '../api.js';
import { h, formatEuro, formatSignedEuro, monthLabel, currentMonth, shiftMonth, loadingBlock, errorBlock } from '../ui.js';
import { monthSwitcher, monthFromQuery } from './movements.js';
import { ledgerLine, monthBars, signClass } from './summary.js';
import { explorePath } from './explore.js';
import { vintedHead } from './vinted.js';

const TREND_MONTHS = 6;
// DAC7 (D.Lgs. 32/2023): a seller is left out of the platform's report
// only with fewer than 30 sales AND at most 2,000 EUR in the calendar year;
// 30 sales, or more than 2,000 EUR, and the data reach the tax office.
const DAC7_SALES = 30;
const DAC7_CENTS = 200000;

export function vintedSummaryPath(month) {
  return month === currentMonth() ? '/vinted/riepilogo' : `/vinted/riepilogo?mese=${month}`;
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

// 0.18.1: the month as a ledger, like the Riepilogo of the household.
// Vendite (to the items sold), Spese Vinted with their purchases and extras
// indented, the Differenza double underlined.
function monthLedger(summary, month) {
  const lines = [
    ledgerLine({
      name: 'Vendite', count: summary.sales_count, amount: formatEuro(summary.sales_cents),
      href: '/vinted?filtro=venduti', label: `Vendite: ${formatEuro(summary.sales_cents)}. Vedi gli articoli venduti`,
    }),
    ledgerLine({
      name: 'Spese Vinted', count: summary.expense_count,
      amount: summary.expense_cents ? `− ${formatEuro(summary.expense_cents)}` : formatEuro(0),
    }),
  ];
  if (summary.purchase_count && summary.extra_count) {
    lines.push(ledgerLine({ name: 'di cui acquisti', amount: formatEuro(summary.purchase_cents), kind: 'is-detail' }));
    lines.push(ledgerLine({ name: 'di cui extra', amount: formatEuro(summary.extra_cents), kind: 'is-detail' }));
  }
  if (summary.sales_count || summary.expense_count) {
    lines.push(ledgerLine({
      name: 'Differenza', amount: formatSignedEuro(summary.balance_cents).replace(/^([+−])/, '$1 '),
      kind: `is-sum is-final ledger-diff ${signClass(summary.balance_cents)}`,
    }));
  }
  return h('div', { class: 'card ledger', 'aria-label': `Vinted, ${monthLabel(month)}` }, lines);
}

export async function mount(root, ctx) {
  let month = monthFromQuery(ctx.query);
  let windowEnd = month; // the newest of the six columns, as in the Riepilogo
  let request = 0;
  const switcherSlot = h('div');
  const body = h('div');
  root.append(...vintedHead('summary', ctx.navigate), switcherSlot, body);

  function placeWindow(next) {
    if (next > windowEnd) windowEnd = next;
    else if (next < shiftMonth(windowEnd, -(TREND_MONTHS - 1))) windowEnd = shiftMonth(next, TREND_MONTHS - 1);
  }

  // quiet: see the same option in movements.js.
  async function show(nextMonth, { quiet = false } = {}) {
    placeWindow(nextMonth);
    month = nextMonth;
    const mine = ++request;
    history.replaceState(history.state, '', vintedSummaryPath(month));
    switcherSlot.replaceChildren(monthSwitcher(month, show));
    if (!quiet) body.replaceChildren(loadingBlock());
    let summary;
    let trend;
    try {
      [summary, trend] = await Promise.all([
        api.get(`/vinted/summary?month=${month}`),
        api.get(`/vinted/summary/trend?month=${windowEnd}&months=${TREND_MONTHS}`),
      ]);
    } catch (error) {
      if (!quiet && ctx.isCurrent() && mine === request) body.replaceChildren(errorBlock(error, () => show(month)));
      return;
    }
    if (!ctx.isCurrent() || mine !== request) return; // a newer request took over
    body.replaceChildren(
      monthLedger(summary, month),
      monthBars(trend, month, (picked) => show(picked), explorePath('vinted', month),
        { income: 'Vendite', expense: 'Spese' }),
      ...yearCard(summary));
  }

  ctx.onResume(({ longAway }) => { if (longAway) show(month, { quiet: true }); });
  await show(month);
}
