// "Riepilogo": expenses of the month, incomes and the difference, a small
// chart of the last six months, then the expenses per category.
// Deliberately simple: the real analysis happens on the exported CSV. Each
// category opens the list of its expenses (summary-category.js); the
// "Entrate" row opens the incomes of the month (summary-incomes.js).

import { api } from '../api.js';
import { state } from '../store.js';
import {
  h, mainHead, formatEuro, formatSignedEuro, formatShare, monthLabel, currentMonth, loadingBlock, errorBlock,
} from '../ui.js';
import { monthSwitcher, monthFromQuery } from './movements.js';

const TREND_MONTHS = 6;

// Donut of the month, shared by the expenses (here) and the incomes
// (summary-incomes.js): both summaries carry total_cents and by_category,
// largest first. The legend next to the ring names every slice with its
// share, so color is never the only cue. Palettes checked with the dataviz
// validator on the white card.
//
// Expenses: the five largest categories plus "Altre". The categories are the
// user's own, so colors go by rank within the month: neighbouring slices are
// always neighbouring palette slots, the adjacent pairs the validator checked.
export const EXPENSE_SLICES = { ranked: ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4'] };
// Incomes (0.7.0), a scale of their own: the meal vouchers always take the
// light green of the chart above (.trend-bar.is-voucher), the other
// categories blue, pink and yellow by rank, the fourth and beyond fold into
// grey "Altre". Blue, pink and yellow are the palette hues that stay apart
// from that green for colour-blind readers too (orange, red, aqua and the
// darker green do not); the four were validated on every pair, since the
// vouchers can sit anywhere in the ring. Yellow next to the green is in the
// CVD 6-8 band, legal with the gap between slices and the named legend. The
// grey slice comes last, so it only ever touches yellow, green or blue.
export const INCOME_SLICES = { ranked: ['#2a78d6', '#e87ba4', '#eda100'], fixed: { meal_voucher: '#0ca30c' } };
const OTHER_COLOR = '#8a9690';
const SVG = 'http://www.w3.org/2000/svg';

function svg(tag, attrs = {}) {
  const node = document.createElementNS(SVG, tag);
  for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, String(value));
  return node;
}

// fixed: colors by category code (incomes only); the others take the ranked
// colors in order of size, and what is left folds into one grey slice.
function slicesOf(summary, { ranked, fixed = {} }) {
  const slices = [];
  const rest = [];
  let rank = 0;
  for (const category of summary.by_category) {
    const color = fixed[category.category] ?? (rank < ranked.length ? ranked[rank++] : null);
    if (color) slices.push({ name: category.category_name, cents: category.total_cents, color });
    else rest.push(category);
  }
  if (rest.length) {
    slices.push({
      name: rest.length === 1 ? rest[0].category_name : `Altre (${rest.length})`,
      cents: rest.reduce((sum, category) => sum + category.total_cents, 0),
      color: OTHER_COLOR,
    });
  }
  return slices;
}

// title starts the description read by a screen reader; palette is
// EXPENSE_SLICES or INCOME_SLICES.
export function donut(summary, title, palette) {
  const slices = slicesOf(summary, palette);
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
  return h('figure', { class: 'card donut', 'aria-label': `${title}: ${label}` },
    h('div', { class: 'donut-ring' }, ring),
    legend);
}

// --- incomes and difference -------------------------------------------------

function signClass(cents) {
  if (cents > 0) return 'is-positive';
  return cents < 0 ? 'is-negative' : 'is-zero';
}

// Incomes of the month (a link to their summary) and, when there are any,
// incomes minus expenses. A month with no income recorded shows no
// difference: minus the expenses would read as a deficit that is not there.
// Meal vouchers are an income like the others (category "Buoni pasto"):
// their part is named under the total, and the difference includes them,
// because what they paid for is among the expenses, in full.
function balanceCard(summary, month) {
  const hasIncome = summary.income_count > 0;
  const count = summary.income_count === 1 ? '1 entrata' : `${summary.income_count} entrate`;
  // "4 entrate, di cui 160,00 € in buoni pasto"; a no-break space keeps
  // "buoni pasto" on one line when the text wraps.
  const meta = summary.voucher_cents > 0
    ? `${count}, di cui ${formatEuro(summary.voucher_cents)} in buoni pasto`
    : count;
  const rows = [h('a', {
    class: 'balance-row balance-link', href: incomeSummaryPath(month), dataset: { link: '' },
    'aria-label': hasIncome
      ? `Entrate: ${formatEuro(summary.income_cents)}, ${meta}. Vedi le entrate per categoria`
      : 'Nessuna entrata registrata. Vedi o aggiungi le entrate',
  },
  h('span', { class: 'balance-main' },
    h('span', { class: 'balance-name' }, 'Entrate'),
    h('span', { class: 'balance-meta' }, hasIncome ? meta : 'Stipendi, rimborsi, regali: aggiungili qui')),
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
// The meal vouchers of a month sit on top of its income column, in a lighter
// green, so the part at the baseline is the money received.

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

function describeIncomes(item, { none }) {
  if (!item.income_count) return none;
  const vouchers = item.voucher_cents ? `, di cui buoni pasto ${formatEuro(item.voucher_cents)}` : '';
  return `${formatEuro(item.income_cents)}${vouchers}`;
}

// The words of the chart. The household one: incomes and expenses, and a
// month without incomes shows no difference ("–"): minus the expenses would
// look like a deficit that is not there. The Vinted section (0.8.0) passes
// its own: sales and Vinted expenses, and a month with only purchases does
// have a negative difference.
export const HOUSEHOLD_TREND = {
  title: 'Entrate e spese',
  income: 'Entrate',
  expense: 'Spese',
  noIncome: 'Nessuna entrata',
  incomeWord: 'entrate',
  noIncomeAria: 'nessuna registrata',
  note: 'Sotto ogni mese: entrate meno spese.',
  hasDifference: (item) => item.income_count > 0,
};

function describeMonth(item, words) {
  const incomes = describeIncomes(item, { none: words.noIncomeAria });
  const difference = words.hasDifference(item) ? `, differenza ${formatSignedEuro(item.balance_cents)}` : '';
  return `${monthLabel(item.month)}: ${words.incomeWord} ${incomes}, spese ${formatEuro(item.expense_cents)}${difference}`;
}

export function trendChart(trend, words = HOUSEHOLD_TREND) {
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

  // Incomes: meal vouchers on top, the rest at the baseline, 2 px of card
  // between the two. The parts share the column by flex-grow, so the gap
  // never makes it taller than the scale says.
  function incomeColumn(item) {
    if (!item.voucher_cents) return bar('income', item.income_cents);
    const stack = h('span', { class: 'trend-stack' });
    stack.style.height = `max(5px, ${(item.income_cents / largest) * 100}%)`;
    const part = (kind, cents) => {
      const node = h('span', { class: `trend-bar is-${kind}` });
      node.style.flex = `${cents} 1 0`;
      return node;
    };
    stack.append(part('voucher', item.voucher_cents));
    const money = item.income_cents - item.voucher_cents;
    if (money > 0) stack.append(part('income', money));
    return stack;
  }

  const columns = trend.map((item) => {
    const difference = words.hasDifference(item)
      ? h('span', { class: `trend-diff ${signClass(item.balance_cents)}` }, shortDifference(item.balance_cents))
      : h('span', { class: 'trend-diff is-none' }, '–');
    return h('button', {
      class: 'trend-col', type: 'button', 'aria-pressed': 'false', 'aria-label': describeMonth(item, words),
      onclick: () => select(item),
      onfocus: () => select(item),
    },
    h('span', { class: 'trend-bars' }, incomeColumn(item), bar('expense', item.expense_cents)),
    h('span', { class: 'trend-month' }, shortMonth(item.month)),
    difference);
  });

  function select(item) {
    trend.forEach((other, index) => {
      columns[index].classList.toggle('is-selected', other === item);
      columns[index].setAttribute('aria-pressed', String(other === item));
    });
    readoutMonth.textContent = monthLabel(item.month);
    readoutValues.textContent = (item.income_count ? `${words.income} ${describeIncomes(item, {})}` : words.noIncome)
      + ` · ${words.expense} ${formatEuro(item.expense_cents)}`;
  }
  select(trend[trend.length - 1]); // the month on screen

  // The voucher key only when the six months have any.
  const voucherKey = trend.some((item) => item.voucher_cents)
    ? h('span', { class: 'trend-key' }, h('span', { class: 'trend-swatch is-voucher' }), 'di cui buoni')
    : null;
  return h('figure', { class: 'card trend', 'aria-label': `${words.title} degli ultimi ${trend.length} mesi` },
    h('figcaption', { class: 'trend-head' },
      h('span', { class: 'trend-title' }, `Ultimi ${trend.length} mesi`),
      h('span', { class: 'trend-legend' },
        h('span', { class: 'trend-key' }, h('span', { class: 'trend-swatch is-income' }), words.income),
        voucherKey,
        h('span', { class: 'trend-key' }, h('span', { class: 'trend-swatch is-expense' }), words.expense))),
    h('div', { class: 'trend-plot' }, columns),
    h('p', { class: 'trend-note' }, words.note),
    readout);
}

// Addresses of the summary screens; the month is left out when current.
export function summaryPath(month) {
  return month === currentMonth() ? '/riepilogo' : `/riepilogo?mese=${month}`;
}

// "/riepilogo/categoria/3?mese=2026-10"
export function categoryPath(categoryId, month) {
  const base = `/riepilogo/categoria/${categoryId}`;
  return month === currentMonth() ? base : `${base}?mese=${month}`;
}

// "/riepilogo/entrate?mese=2026-10"
export function incomeSummaryPath(month) {
  return month === currentMonth() ? '/riepilogo/entrate' : `/riepilogo/entrate?mese=${month}`;
}

export async function mount(root, ctx) {
  // The month is kept in the address, so coming back from a category
  // shows the same month again.
  let month = monthFromQuery(ctx.query);
  const switcherSlot = h('div');
  const body = h('div');
  root.append(
    mainHead('Riepilogo', state.me.display_name),
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
      donut(summary, 'Spese del mese per categoria', EXPENSE_SLICES),
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
