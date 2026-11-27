// "Riepilogo" (rebuilt in 0.18.0, R1): the balance of the month as a ledger,
// the bars of six months (a tap shows that month), then the categories of
// the expenses or of the incomes. Deliberately simple: the real analysis
// happens on the exported CSV. An expense category opens the list of its
// expenses (summary-category.js); an income category, the month's pay slip
// in Movimenti with its rows highlighted.

import { api } from '../api.js';
import { viewCache, sameData } from '../cache.js';
import { state } from '../store.js';
import {
  h, mainHead, formatEuro, formatSignedEuro, formatShare, monthLabel, currentMonth, shiftMonth, latestPlannedMonth,
  dayMonthShort, loadingBlock, errorBlock,
} from '../ui.js';
import { monthSwitcher, monthFromQuery, movementsPath, incomesPath } from './movements.js';
import { explorePath } from './explore.js';

const TREND_MONTHS = 6;

// Donut of the month, for the expenses and for the incomes: both summaries carry total_cents and by_category,
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
  return h('figure', { class: 'donut', 'aria-label': `${title}: ${label}` },
    h('div', { class: 'donut-ring' }, ring),
    legend);
}

// --- the balance of the month (0.18.0, R1) ---------------------------------------
//
// «Da ragioniere»: one card, read top to bottom like a ledger. Entrate (with
// the meal vouchers indented under them), Spese with the minus sign, a rule,
// «Differenza finora»; then, while the month is not over, the recurring
// incomes still expected, another rule and «A fine mese», double underlined.
// A month that is over ends with its «Differenza». Entrate and Spese open
// the month's lists in Movimenti. A month with no income and none expected
// shows no difference: minus the expenses would read as a deficit that is
// not there.

function signClass(cents) {
  if (cents > 0) return 'is-positive';
  return cents < 0 ? 'is-negative' : 'is-zero';
}

const plural = (count, one, many) => (count === 1 ? `1 ${one}` : `${count} ${many}`);

function ledgerLine({ name, meta = null, amount, href = null, label = null, kind = '' }) {
  const main = h('span', { class: 'ledger-main' },
    h('span', { class: 'ledger-name' }, name),
    meta ? h('span', { class: 'ledger-meta' }, meta) : null);
  const figure = h('span', { class: 'ledger-amount' }, amount);
  const className = `ledger-line ${kind}`.trim();
  return href
    ? h('a', { class: `${className} ledger-link`, href, dataset: { link: '' }, 'aria-label': label }, main, figure)
    : h('div', { class: className }, main, figure);
}

function ledgerCard(summary, month) {
  const now = currentMonth();
  const hasIncome = summary.income_count > 0;
  // Only while the month is not over: a past month's unregistered salary
  // is a reminder of Ricorrenti, not part of its result.
  const expected = month >= now ? (summary.expected_incomes || []) : [];
  const lines = [];

  lines.push(ledgerLine({
    name: 'Entrate',
    meta: hasIncome ? plural(summary.income_count, 'entrata', 'entrate') : 'Nessuna entrata registrata',
    amount: formatEuro(summary.income_cents),
    href: incomesPath(month),
    label: `Entrate: ${formatEuro(summary.income_cents)}. Vedi le entrate del mese`,
  }));
  if (summary.voucher_cents > 0) {
    lines.push(ledgerLine({
      name: 'di cui buoni pasto', amount: formatEuro(summary.voucher_cents), kind: 'is-detail',
    }));
  }
  lines.push(ledgerLine({
    name: 'Spese',
    meta: summary.expense_count ? plural(summary.expense_count, 'spesa', 'spese') : 'Nessuna spesa',
    amount: summary.total_cents ? `− ${formatEuro(summary.total_cents)}` : formatEuro(0),
    href: movementsPath(month),
    label: `Spese: ${formatEuro(summary.total_cents)}. Vedi le spese del mese`,
  }));

  if (hasIncome || expected.length) {
    const diffName = month === now ? 'Differenza finora' : 'Differenza';
    const signed = (cents) => formatSignedEuro(cents).replace(/^([+−])/, '$1 ');
    if (expected.length) {
      lines.push(ledgerLine({
        name: diffName, amount: signed(summary.balance_cents),
        kind: `is-sum ledger-diff ${signClass(summary.balance_cents)}`,
      }));
      const listed = expected.slice(0, 2)
        // No-break spaces: "27 nov" and the name stay together when it wraps.
        .map((item) => `${item.category_name} ${item.received_by_name}, ${dayMonthShort(item.due_date).replace(' ', ' ')}`);
      if (expected.length > 2) listed.push(`altre ${expected.length - 2}`);
      lines.push(ledgerLine({
        name: 'Entrate attese', meta: listed.join(' · '),
        amount: `+ ${formatEuro(summary.expected_income_cents)}`,
        href: '/ricorrenti', kind: 'is-expected',
        label: `Entrate attese: ${formatEuro(summary.expected_income_cents)}, ${listed.join(', ')}. Vedi le ricorrenti`,
      }));
      const projected = summary.balance_cents + summary.expected_income_cents;
      lines.push(ledgerLine({
        name: 'A fine mese', amount: signed(projected),
        kind: `is-sum is-final ledger-diff ${signClass(projected)}`,
      }));
    } else {
      lines.push(ledgerLine({
        name: diffName, amount: signed(summary.balance_cents),
        kind: `is-sum is-final ledger-diff ${signClass(summary.balance_cents)}`,
      }));
    }
  }
  return h('div', { class: 'card ledger', 'aria-label': `Bilancio di ${monthLabel(month)}` }, lines);
}

// --- the bars of six months (0.18.0, R1) --------------------------------------------
//
// Two thin columns per month, incomes and expenses, on one shared scale,
// with only the month's name under them: the figures are in the ledger
// above. A tap on a month shows that month on the whole page. The columns
// stay where they are while the month shown is among them: the window of
// six months moves only when the arrows go past its oldest or newest month.
// Always drawn, even when the six months are empty.

function monthBars(trend, month, onPick, explore) {
  const largest = Math.max(1, ...trend.map((item) => Math.max(item.income_cents, item.expense_cents)));
  function bar(kind, cents) {
    const node = h('span', { class: `trend-bar is-${kind}` });
    if (cents > 0) node.style.height = `max(2px, ${(cents / largest) * 100}%)`;
    else node.classList.add('is-empty');
    return node;
  }
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
    const selected = item.month === month;
    const incomes = item.income_count ? formatEuro(item.income_cents) : 'nessuna';
    return h('button', {
      class: `trend-col${selected ? ' is-selected' : ''}`, type: 'button', 'aria-pressed': String(selected),
      'aria-label': `${monthLabel(item.month)}: entrate ${incomes}, spese ${formatEuro(item.expense_cents)}. Mostra il mese`,
      onclick: () => { if (!selected) onPick(item.month); },
    },
    h('span', { class: 'trend-bars' }, incomeColumn(item), bar('expense', item.expense_cents)),
    h('span', { class: 'trend-month' }, shortMonth(item.month)));
  });
  const voucherKey = trend.some((item) => item.voucher_cents)
    ? h('span', { class: 'trend-key' }, h('span', { class: 'trend-swatch is-voucher' }), 'di cui buoni')
    : null;
  return h('figure', { class: 'card trend trend-months', 'aria-label': `Entrate e spese di ${trend.length} mesi` },
    h('figcaption', { class: 'trend-legend' },
      h('span', { class: 'trend-key' }, h('span', { class: 'trend-swatch is-income' }), 'Entrate'),
      voucherKey,
      h('span', { class: 'trend-key' }, h('span', { class: 'trend-swatch is-expense' }), 'Spese')),
    h('div', { class: 'trend-plot' }, columns),
    h('a', { class: 'trend-more', href: explore, dataset: { link: '' } }, 'Esplora ›'));
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

// explore: the address of "Esplora" (0.9.0), linked at the bottom of the card.
export function trendChart(trend, words = HOUSEHOLD_TREND, { explore = null } = {}) {
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
    readout,
    explore ? exploreLink(explore) : null);
}

// "Esplora ›" (0.9.0): the totals of a month, a year, six months or two
// dates. At the bottom of the chart card, or in a card of its own when the
// chart is left out (six empty months).
export function exploreLink(href) {
  return h('a', { class: 'trend-explore', href, dataset: { link: '' } },
    h('span', { class: 'trend-explore-main' },
      h('span', { class: 'trend-explore-name' }, 'Esplora'),
      h('span', { class: 'trend-explore-meta' }, 'Totali di un mese, un anno, 6 mesi o delle date che scegli')),
    h('span', { class: 'bar-go', 'aria-hidden': 'true' }, '›'));
}

// Addresses of the summary screen; the month is left out when current.
// side 'incomes' (0.18.0): the categories of the incomes under the chart.
export function summaryPath(month, side = 'expenses') {
  const query = [];
  if (month !== currentMonth()) query.push(`mese=${month}`);
  if (side === 'incomes') query.push('vista=entrate');
  return query.length ? `/riepilogo?${query.join('&')}` : '/riepilogo';
}

// "/riepilogo/categoria/3?mese=2026-10"
export function categoryPath(categoryId, month) {
  const base = `/riepilogo/categoria/${categoryId}`;
  return month === currentMonth() ? base : `${base}?mese=${month}`;
}

// 0.18.0: the old «Riepilogo → Entrate» became the incomes side of the
// Riepilogo; its address (bookmarks, history) leads there.
export const incomesRedirect = {
  mount(root, ctx) {
    ctx.navigate(summaryPath(monthFromQuery(ctx.query), 'incomes'), { replace: true });
  },
};

// The categories of one side, as ring and bars in one card. Expenses open
// the list of their category; incomes open the month's pay slip in
// Movimenti with that category's rows highlighted (0.18.0).
function categoryCard(summary, side, month) {
  const incomes = side === 'incomes';
  const total = summary.total_cents;
  const largest = summary.by_category[0].total_cents;
  return h('div', { class: 'card cat-card' },
    donut(summary, incomes ? 'Entrate del mese per categoria' : 'Spese del mese per categoria',
      incomes ? INCOME_SLICES : EXPENSE_SLICES),
    h('ul', { class: 'bars' }, summary.by_category.map((category) => {
      const fill = h('span', { class: 'bar-fill' });
      // Bars are relative to the largest category, so the top one is full width.
      fill.style.width = `${Math.max(2, Math.round((category.total_cents / largest) * 100))}%`;
      const count = incomes
        ? plural(category.income_count, 'entrata', 'entrate')
        : plural(category.expense_count, 'spesa', 'spese');
      const share = formatShare(category.total_cents, total);
      const href = incomes
        ? `${incomesPath(month)}${month === currentMonth() ? '?' : '&'}evidenzia=${encodeURIComponent(category.category)}`
        : categoryPath(category.category_id, month);
      return h('li', {},
        h('a', {
          class: 'bar', href, dataset: { link: '' },
          'aria-label': `${category.category_name}: ${formatEuro(category.total_cents)}, ${share} del mese, ${count}. Vedi ${incomes ? 'le entrate' : 'le spese'}`,
        },
        h('span', { class: 'bar-head' },
          h('span', { class: 'bar-name' }, category.category_name),
          h('span', { class: 'bar-amount' }, formatEuro(category.total_cents)),
          h('span', { class: 'bar-go', 'aria-hidden': 'true' }, '›')),
        h('span', { class: 'bar-track' }, fill),
        h('span', { class: 'bar-meta' }, `${share} del mese, ${count}`)));
    })));
}

export async function mount(root, ctx) {
  // The month and the side are kept in the address, so coming back from a
  // category shows the same again.
  let month = monthFromQuery(ctx.query);
  let side = ctx.query.get('vista') === 'entrate' ? 'incomes' : 'expenses';
  let windowEnd = month; // the newest month of the six columns
  let request = 0; // the latest load wins
  const switcherSlot = h('div');
  const body = h('div');
  root.append(mainHead('Riepilogo', state.me.display_name), switcherSlot, body);

  // The window moves only when the month leaves it (see monthBars).
  function placeWindow(next) {
    if (next > windowEnd) windowEnd = next;
    else if (next < shiftMonth(windowEnd, -(TREND_MONTHS - 1))) windowEnd = shiftMonth(next, TREND_MONTHS - 1);
  }

  // quiet: see the same option in movements.js. A month seen before in this
  // session is drawn at once from memory (cache.js), then refreshed.
  async function show(nextMonth, { quiet = false } = {}) {
    placeWindow(nextMonth);
    month = nextMonth;
    const mine = ++request;
    history.replaceState(history.state, '', summaryPath(month, side));
    switcherSlot.replaceChildren(monthSwitcher(month, show, { max: latestPlannedMonth() }));
    const key = `summary:${month}:${windowEnd}`;
    const cached = viewCache.get(key);
    if (cached) draw(cached);
    else if (!quiet) body.replaceChildren(loadingBlock());
    let data;
    try {
      const [summary, incomes, trend] = await Promise.all([
        api.get(`/summary?month=${month}`),
        api.get(`/summary/incomes?month=${month}`),
        api.get(`/summary/trend?month=${windowEnd}&months=${TREND_MONTHS}`),
      ]);
      data = { summary, incomes, trend };
    } catch (error) {
      if (!quiet && !cached && ctx.isCurrent() && mine === request) {
        body.replaceChildren(errorBlock(error, () => show(month)));
      }
      return;
    }
    if (!ctx.isCurrent() || mine !== request) return;
    if (cached && sameData(cached, data)) return;
    viewCache.set(key, data);
    draw(data);
  }

  function sideSwitch(data) {
    const item = (id, label) => h('button', {
      class: `seg-item${id === side ? ' is-selected' : ''}`, type: 'button', 'aria-pressed': String(id === side),
      onclick: () => {
        if (id === side) return;
        side = id;
        history.replaceState(history.state, '', summaryPath(month, side));
        draw(data);
      },
    }, label);
    return h('div', { class: 'seg seg-side', role: 'group', 'aria-label': 'Categorie di spese o di entrate' },
      item('expenses', 'Spese'), item('incomes', 'Entrate'));
  }

  function draw(data) {
    const { summary, incomes, trend } = data;
    const shown = side === 'incomes' ? incomes : summary;
    const empty = side === 'incomes' ? !incomes.income_count : !summary.expense_count;
    body.replaceChildren(
      ledgerCard(summary, month),
      monthBars(trend, month, (picked) => show(picked), explorePath('house', month)),
      sideSwitch(data),
      empty
        ? h('div', { class: 'card cat-empty' }, h('p', { class: 'empty-text' },
          side === 'incomes' ? `Nessuna entrata a ${monthLabel(month)}.` : `Nessuna spesa a ${monthLabel(month)}.`))
        : categoryCard(shown, side, month));
  }

  ctx.onResume(({ longAway }) => { if (longAway) show(month, { quiet: true }); });
  await show(month);
}
