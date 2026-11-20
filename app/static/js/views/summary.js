// "Riepilogo": expenses of the month, incomes and the difference, a small
// chart of the last six months, then the expenses per category.
// Deliberately simple: the real analysis happens on the exported CSV. Each
// category opens the list of its expenses (summary-category.js).

import { api } from '../api.js';
import {
  h, formatEuro, formatSignedEuro, formatShare, monthLabel, currentMonth, loadingBlock, errorBlock,
} from '../ui.js';
import { monthSwitcher, monthFromQuery, incomesPath } from './movements.js';

const TREND_MONTHS = 6;

// Donut of the month: the five largest categories plus "Altre". Colors go
// by rank within the month (largest first); the legend next to the ring
// names every slice with its share, so color is never the only cue.
// Palette checked with the dataviz validator (light surface, adjacent pairs).
const SLICE_COLORS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4'];
const OTHER_COLOR = '#8a9690';
const MAX_SLICES = 5;
const SVG = 'http://www.w3.org/2000/svg';

function svg(tag, attrs = {}) {
  const node = document.createElementNS(SVG, tag);
  for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, String(value));
  return node;
}

function slicesOf(summary) {
  const top = summary.by_category.slice(0, MAX_SLICES).map((category, index) => ({
    name: category.category_name, cents: category.total_cents, color: SLICE_COLORS[index],
  }));
  const rest = summary.by_category.slice(MAX_SLICES);
  if (rest.length) {
    top.push({
      name: rest.length === 1 ? rest[0].category_name : `Altre (${rest.length})`,
      cents: rest.reduce((sum, category) => sum + category.total_cents, 0),
      color: OTHER_COLOR,
    });
  }
  return top;
}

function donut(summary) {
  const slices = slicesOf(summary);
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const gap = slices.length > 1 ? 1.2 : 0; // thin surface gap between slices
  const ring = svg('svg', { viewBox: '0 0 100 100', class: 'donut-svg', 'aria-hidden': 'true' });
  ring.append(svg('circle', { cx: 50, cy: 50, r: radius, fill: 'none', stroke: '#EEF2F0', 'stroke-width': 16 }));
  let start = 0;
  for (const slice of slices) {
    const length = (slice.cents / summary.total_cents) * circumference;
    const arc = svg('circle', {
      cx: 50, cy: 50, r: radius, fill: 'none', stroke: slice.color, 'stroke-width': 16,
      'stroke-dasharray': `${Math.max(0.5, length - gap)} ${circumference}`,
      'stroke-dashoffset': -start,
      transform: 'rotate(-90 50 50)',
    });
    const tip = svg('title');
    tip.textContent = `${slice.name}: ${formatEuro(slice.cents)}`;
    arc.append(tip);
    ring.append(arc);
    start += length;
  }

  const legend = h('ul', { class: 'donut-legend' }, slices.map((slice) => {
    const swatch = h('span', { class: 'donut-swatch' });
    swatch.style.background = slice.color;
    return h('li', { class: 'donut-item' },
      swatch,
      h('span', { class: 'donut-name' }, slice.name),
      h('span', { class: 'donut-share' }, formatShare(slice.cents, summary.total_cents)));
  }));

  const label = slices.map((slice) =>
    `${slice.name} ${formatShare(slice.cents, summary.total_cents)}`).join(', ');
  // No figure in the hole: the total is written right above the chart, and a
  // five-digit amount did not fit inside the ring.
  return h('figure', { class: 'card donut', 'aria-label': `Ripartizione del mese: ${label}` },
    h('div', { class: 'donut-ring' }, ring),
    legend);
}

// --- incomes and difference -------------------------------------------------

function signClass(cents) {
  if (cents > 0) return 'is-positive';
  return cents < 0 ? 'is-negative' : 'is-zero';
}

// Incomes of the month (a link to their list) and, when there are any,
// incomes minus expenses. A month with no income recorded shows no
// difference: minus the expenses would read as a deficit that is not there.
function balanceCard(summary, month) {
  const hasIncome = summary.income_count > 0;
  const count = summary.income_count === 1 ? '1 entrata' : `${summary.income_count} entrate`;
  const rows = [h('a', {
    class: 'balance-row balance-link', href: incomesPath(month), dataset: { link: '' },
    'aria-label': hasIncome
      ? `Entrate: ${formatEuro(summary.income_cents)}, ${count}. Vedi le entrate`
      : 'Nessuna entrata registrata. Vedi o aggiungi le entrate',
  },
  h('span', { class: 'balance-main' },
    h('span', { class: 'balance-name' }, 'Entrate'),
    h('span', { class: 'balance-meta' }, hasIncome ? count : 'Stipendi, rimborsi, regali: aggiungili qui')),
  h('span', { class: 'balance-amount' }, hasIncome ? formatEuro(summary.income_cents) : 'Nessuna'),
  h('span', { class: 'bar-go', 'aria-hidden': 'true' }, '›'))];
  if (hasIncome) {
    rows.push(h('div', { class: 'balance-row' },
      h('span', { class: 'balance-main' },
        h('span', { class: 'balance-name' }, 'Differenza'),
        h('span', { class: 'balance-meta' }, 'Entrate meno spese')),
      h('span', { class: `balance-amount balance-diff ${signClass(summary.balance_cents)}` },
        formatSignedEuro(summary.balance_cents))));
  }
  return h('div', { class: 'card balance' }, rows);
}

// --- last six months ----------------------------------------------------------
//
// Two thin columns per month, incomes and expenses, on one shared scale, with
// the difference in whole euros under each month. The colours live in
// app.css (palette slots 6 and 7, validated: the donut already uses 1-5 on
// this screen). No value axis: the difference row carries the figures, and a
// tap on a month (or keyboard focus) writes its exact totals under the chart.

const wholeEuros = new Intl.NumberFormat('it-IT', { maximumFractionDigits: 0, useGrouping: 'always' });

// "+1.795", "−150", "0"; from ten thousand up "+12,3k", to fit the column.
function shortDifference(cents) {
  const euros = Math.round(cents / 100);
  if (!euros) return '0';
  const sign = euros > 0 ? '+' : '−';
  const size = Math.abs(euros);
  const text = size >= 10000
    ? `${new Intl.NumberFormat('it-IT', { maximumFractionDigits: 1 }).format(size / 1000)}k`
    : wholeEuros.format(size);
  return `${sign}${text}`;
}

function shortMonth(month) {
  const [year, number] = month.split('-').map(Number);
  return new Date(year, number - 1, 1).toLocaleDateString('it-IT', { month: 'short' }).replace('.', '');
}

function describeMonth(item) {
  const incomes = item.income_count ? formatEuro(item.income_cents) : 'nessuna registrata';
  const difference = item.income_count ? `, differenza ${formatSignedEuro(item.balance_cents)}` : '';
  return `${monthLabel(item.month)}: entrate ${incomes}, spese ${formatEuro(item.expense_cents)}${difference}`;
}

function trendChart(trend) {
  const largest = Math.max(1, ...trend.map((item) => Math.max(item.income_cents, item.expense_cents)));
  const readoutMonth = h('strong', { class: 'trend-readout-month' });
  const readoutValues = h('span', { class: 'trend-readout-values' });
  const readout = h('p', { class: 'trend-readout', 'aria-live': 'polite' }, readoutMonth, readoutValues);

  function bar(kind, cents) {
    const node = h('span', { class: `trend-bar is-${kind}` });
    // Shared scale; a value too small to see still gets a sliver.
    if (cents > 0) node.style.height = `max(2px, ${(cents / largest) * 100}%)`;
    else node.classList.add('is-empty');
    return node;
  }

  const columns = trend.map((item) => {
    const difference = item.income_count
      ? h('span', { class: `trend-diff ${signClass(item.balance_cents)}` }, shortDifference(item.balance_cents))
      : h('span', { class: 'trend-diff is-none' }, '–');
    return h('button', {
      class: 'trend-col', type: 'button', 'aria-pressed': 'false', 'aria-label': describeMonth(item),
      onclick: () => select(item),
      onfocus: () => select(item),
    },
    h('span', { class: 'trend-bars' }, bar('income', item.income_cents), bar('expense', item.expense_cents)),
    h('span', { class: 'trend-month' }, shortMonth(item.month)),
    difference);
  });

  function select(item) {
    trend.forEach((other, index) => {
      columns[index].classList.toggle('is-selected', other === item);
      columns[index].setAttribute('aria-pressed', String(other === item));
    });
    readoutMonth.textContent = monthLabel(item.month);
    readoutValues.textContent = `${item.income_count ? `Entrate ${formatEuro(item.income_cents)}` : 'Nessuna entrata'}`
      + ` · Spese ${formatEuro(item.expense_cents)}`;
  }
  select(trend[trend.length - 1]); // the month on screen

  return h('figure', { class: 'card trend', 'aria-label': `Entrate e spese degli ultimi ${trend.length} mesi` },
    h('figcaption', { class: 'trend-head' },
      h('span', { class: 'trend-title' }, `Ultimi ${trend.length} mesi`),
      h('span', { class: 'trend-legend' },
        h('span', { class: 'trend-key' }, h('span', { class: 'trend-swatch is-income' }), 'Entrate'),
        h('span', { class: 'trend-key' }, h('span', { class: 'trend-swatch is-expense' }), 'Spese'))),
    h('div', { class: 'trend-plot' }, columns),
    h('p', { class: 'trend-note' }, 'Sotto ogni mese: entrate meno spese.'),
    readout);
}

// "/riepilogo/categoria/3?mese=2026-10"; the month is left out when current.
export function categoryPath(categoryId, month) {
  const base = `/riepilogo/categoria/${categoryId}`;
  return month === currentMonth() ? base : `${base}?mese=${month}`;
}

function summaryPath(month) {
  return month === currentMonth() ? '/riepilogo' : `/riepilogo?mese=${month}`;
}

export async function mount(root, ctx) {
  // The month is kept in the address, so coming back from a category
  // shows the same month again.
  let month = monthFromQuery(ctx.query);
  const switcherSlot = h('div');
  const body = h('div');
  root.append(
    h('header', { class: 'page-head' }, h('h1', { class: 'page-title' }, 'Riepilogo')),
    switcherSlot, body);

  // quiet: see the same option in movements.js.
  async function show(nextMonth, { quiet = false } = {}) {
    month = nextMonth;
    history.replaceState(history.state, '', summaryPath(month));
    switcherSlot.replaceChildren(monthSwitcher(month, show));
    if (!quiet) body.replaceChildren(loadingBlock());
    let summary;
    let trend;
    try {
      [summary, trend] = await Promise.all([
        api.get(`/summary?month=${month}`),
        api.get(`/summary/trend?month=${month}&months=${TREND_MONTHS}`),
      ]);
    } catch (error) {
      if (!quiet && ctx.isCurrent() && month === nextMonth) body.replaceChildren(errorBlock(error, () => show(month)));
      return;
    }
    if (!ctx.isCurrent() || month !== nextMonth) return;

    const expenseCount = summary.expense_count === 1 ? '1 spesa' : `${summary.expense_count} spese`;
    const parts = [
      h('div', { class: 'receipt receipt-total' },
        h('span', { class: 'receipt-label' }, `Spese di ${monthLabel(month)}`),
        h('span', { class: 'receipt-figure' }, formatEuro(summary.total_cents)),
        h('span', { class: 'receipt-sub' }, summary.expense_count ? expenseCount : 'Nessuna spesa')),
      balanceCard(summary, month),
    ];
    // The chart is left out only when the six months are all empty.
    if (trend.some((item) => item.expense_count || item.income_count)) parts.push(trendChart(trend));
    if (summary.expense_count === 0) {
      body.replaceChildren(...parts);
      return;
    }

    const largest = summary.by_category[0].total_cents;
    body.replaceChildren(
      ...parts,
      donut(summary),
      h('h2', { class: 'section-title' }, 'Spese per categoria'),
      h('ul', { class: 'card bars' }, summary.by_category.map((category) => {
        const fill = h('span', { class: 'bar-fill' });
        // Bars are relative to the largest category, so the top one is full width.
        fill.style.width = `${Math.max(2, Math.round((category.total_cents / largest) * 100))}%`;
        const count = category.expense_count === 1 ? '1 spesa' : `${category.expense_count} spese`;
        const share = formatShare(category.total_cents, summary.total_cents);
        return h('li', {},
          h('a', {
            class: 'bar', href: categoryPath(category.category_id, month), dataset: { link: '' },
            'aria-label': `${category.category_name}: ${formatEuro(category.total_cents)}, ${share} del mese, ${count}. Vedi le spese`,
          },
          h('span', { class: 'bar-head' },
            h('span', { class: 'bar-name' }, category.category_name),
            h('span', { class: 'bar-amount' }, formatEuro(category.total_cents)),
            h('span', { class: 'bar-go', 'aria-hidden': 'true' }, '›')),
          h('span', { class: 'bar-track' }, fill),
          h('span', { class: 'bar-meta' }, `${share} del mese, ${count}`)));
      })));
  }

  ctx.onResume(({ longAway }) => { if (longAway) show(month, { quiet: true }); });
  await show(month);
}
