// "Esplora" (0.9.0): the totals of a period, for the household and for the
// Vinted section. A month, a year, the last six months (a window that moves
// one month at a time, as the chart of the Riepilogo) or two dates of one's
// choice. Opened from the link under the six-month chart. Only totals and
// the dates they cover: the movements stay in "Movimenti", the deeper
// analysis on the CSV.

import { api } from '../api.js';
import {
  h, icon, formatEuro, formatSignedEuro, monthLabel, currentMonth, shiftMonth, todayIso,
  latestPlannedMonth, latestPlannedIso, loadingBlock, errorBlock,
} from '../ui.js';

const VIEWS = [
  { id: 'mese', label: 'Mese' },
  { id: 'anno', label: 'Anno' },
  { id: '6mesi', label: '6 mesi' },
  { id: 'date', label: 'Date' },
];
const WINDOW_MONTHS = 6;
const EARLIEST_DAY = '2000-01-01'; // as the dates of the movements
const EARLIEST_MONTH = '2000-01';
const MONTH_SHAPE = /^\d{4}-(0[1-9]|1[0-2])$/;
const DAY_SHAPE = /^\d{4}-\d{2}-\d{2}$/;

const SECTIONS = {
  house: {
    title: 'Esplora', base: '/riepilogo/esplora', back: '/riepilogo',
    backLabel: 'Torna al riepilogo', api: '/summary/period',
    // 0.18.0 (F10): the household periods reach the planned expenses, as
    // the Riepilogo and its chart do; the Vinted ones stop at today.
    planned: true,
  },
  vinted: {
    title: 'Esplora Vinted', base: '/vinted/riepilogo/esplora', back: '/vinted/riepilogo',
    backLabel: 'Torna al riepilogo Vinted', api: '/vinted/summary/period',
  },
};

const plural = (count, one, many) => (count === 1 ? `1 ${one}` : `${count} ${many}`);

// --- dates --------------------------------------------------------------------

function lastDayOf(month) {
  const [year, number] = month.split('-').map(Number);
  return `${month}-${String(new Date(year, number, 0).getDate()).padStart(2, '0')}`;
}

const earlier = (a, b) => (a < b ? a : b);

function validDay(text) {
  if (!text || !DAY_SHAPE.test(text)) return false;
  const [year, month, day] = text.split('-').map(Number);
  const date = new Date(year, month - 1, day);
  return date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day;
}

function monthName(month, style = 'long') {
  const [year, number] = month.split('-').map(Number);
  return new Date(year, number - 1, 1).toLocaleDateString('it-IT', { month: style });
}

// "dal"/"al" + day, with the elision Italian wants: "dall'8", "all'11".
function onDay(preposition, day) {
  const elided = day === 8 || day === 11;
  return elided ? `${preposition}l’${day}` : `${preposition} ${day}`;
}

// "Dal 1 gennaio al 22 novembre 2026 (oggi)", "Dal 1 al 30 giugno 2026",
// "Dal 15 dicembre 2025 al 31 marzo 2026".
export function rangeLabel(start, end) {
  const [y1, m1, d1] = start.split('-').map(Number);
  const [y2, m2, d2] = end.split('-').map(Number);
  const from = onDay('Dal', d1);
  const to = onDay('al', d2);
  const endMonth = `${monthName(end.slice(0, 7))} ${y2}`;
  let text;
  if (y1 === y2 && m1 === m2) text = `${from} ${to} ${endMonth}`;
  else if (y1 === y2) text = `${from} ${monthName(start.slice(0, 7))} ${to} ${endMonth}`;
  else text = `${from} ${monthName(start.slice(0, 7))} ${y1} ${to} ${endMonth}`;
  return end === todayIso() ? `${text} (oggi)` : text;
}

// --- the period on screen ---------------------------------------------------------

// What the address asks for, made safe: "?vista=anno&anno=2026",
// "?vista=mese&mese=2026-11", "?vista=6mesi&mese=2026-11",
// "?vista=date&dal=2026-03-15&al=2026-08-03".
function periodFromQuery(query, limits) {
  const now = limits.month; // the furthest month the arrows reach
  const view = VIEWS.some((item) => item.id === query.get('vista')) ? query.get('vista') : 'anno';
  let month = query.get('mese');
  month = month && MONTH_SHAPE.test(month) ? month : currentMonth();
  if (month > now) month = now;
  if (month < EARLIEST_MONTH) month = EARLIEST_MONTH;
  let year = Number(query.get('anno'));
  const thisYear = Number(now.slice(0, 4));
  if (!Number.isInteger(year) || year < 2000 || year > thisYear) year = Number(month.slice(0, 4));
  let from = query.get('dal');
  let to = query.get('al');
  if (!validDay(from) || !validDay(to) || from > to || to > limits.day) {
    from = `${currentMonth().slice(0, 4)}-01-01`;
    to = todayIso();
  }
  return { view, month, year, from, to };
}

function pathOf(section, period) {
  const base = SECTIONS[section].base;
  switch (period.view) {
    case 'mese': return `${base}?vista=mese&mese=${period.month}`;
    case '6mesi': return `${base}?vista=6mesi&mese=${period.month}`;
    case 'date': return `${base}?vista=date&dal=${period.from}&al=${period.to}`;
    default: return `${base}?vista=anno&anno=${period.year}`;
  }
}

// The address the Riepilogo links to: the year of the month it shows.
export function explorePath(section, month) {
  return pathOf(section, { view: 'anno', year: Number(month.slice(0, 4)) });
}

// How far forward a section looks: the last month and day an expense can
// be planned in for the household (0.18.0), today for Vinted.
function limitsOf(config) {
  return config.planned
    ? { month: latestPlannedMonth(), day: latestPlannedIso() }
    : { month: currentMonth(), day: todayIso() };
}

// First and last day (never after limits.day), the label between the
// arrows and whether the arrows can move.
function bounds(period, limits) {
  const today = limits.day;
  const now = limits.month;
  if (period.view === 'mese') {
    return {
      start: `${period.month}-01`, end: earlier(lastDayOf(period.month), today),
      label: monthLabel(period.month), canBack: period.month > EARLIEST_MONTH, canForward: period.month < now,
      backLabel: 'Mese precedente', forwardLabel: 'Mese successivo',
    };
  }
  if (period.view === '6mesi') {
    const first = shiftMonth(period.month, -(WINDOW_MONTHS - 1));
    const sameYear = first.slice(0, 4) === period.month.slice(0, 4);
    const label = sameYear
      ? `${monthName(first, 'short')} – ${monthName(period.month, 'short')} ${period.month.slice(0, 4)}`
      : `${monthName(first, 'short')} ${first.slice(0, 4)} – ${monthName(period.month, 'short')} ${period.month.slice(0, 4)}`;
    const firstDay = `${first}-01`;
    return {
      start: firstDay < EARLIEST_DAY ? EARLIEST_DAY : firstDay,
      end: earlier(lastDayOf(period.month), today),
      label, canBack: first > EARLIEST_MONTH, canForward: period.month < now,
      backLabel: 'Indietro di un mese', forwardLabel: 'Avanti di un mese',
    };
  }
  if (period.view === 'date') return { start: period.from, end: period.to };
  const year = period.year;
  return {
    start: `${year}-01-01`, end: earlier(`${year}-12-31`, today),
    label: String(year), canBack: year > 2000, canForward: year < Number(now.slice(0, 4)),
    backLabel: 'Anno precedente', forwardLabel: 'Anno successivo',
  };
}

// Moving to another view keeps the time being looked at: the month or the
// year where the current period ends, or its dates.
function switchTo(period, view, limits) {
  const { start, end } = bounds(period, limits);
  const endMonth = end.slice(0, 7);
  return {
    ...period, view, month: endMonth, year: Number(end.slice(0, 4)),
    from: view === 'date' ? start : period.from, to: view === 'date' ? end : period.to,
  };
}

function step(period, delta) {
  if (period.view === 'anno') return { ...period, year: period.year + delta };
  return { ...period, month: shiftMonth(period.month, delta) };
}

// --- the figures ---------------------------------------------------------------------

function signClass(cents) {
  if (cents > 0) return 'is-positive';
  return cents < 0 ? 'is-negative' : '';
}

// One bar of the chart: name and total, the bar on the shared scale, what
// it counts. parts: [{ kind, cents }], the first one fills what the others
// leave (incomes, then the meal vouchers at its end).
function cumulRow(name, cents, meta, parts, largest) {
  const fill = h('span', { class: 'cumul-fill' }, parts.map((part, index) => {
    const node = h('span', { class: `cumul-part is-${part.kind}` });
    if (index > 0) node.style.width = `${(part.cents / cents) * 100}%`;
    return node;
  }));
  fill.style.width = cents > 0 ? `max(4px, ${(cents / largest) * 100}%)` : '0';
  return h('div', { class: 'cumul-row' },
    h('div', { class: 'cumul-head' },
      h('span', { class: 'cumul-name' }, name),
      h('span', { class: 'cumul-amount' }, formatEuro(cents))),
    h('span', { class: 'cumul-track' }, fill),
    h('span', { class: 'cumul-meta' }, meta));
}

function balanceRow(name, meta, amount, amountClass = '') {
  return h('div', { class: 'balance-row' },
    h('span', { class: 'balance-main' },
      h('span', { class: 'balance-name' }, name),
      h('span', { class: 'balance-meta' }, meta)),
    h('span', { class: `balance-amount ${amountClass}`.trim() }, amount));
}

// "29 spese, di cui previste dopo oggi: 120,00 €" (0.18.0, F10): known
// debits and bills dated after today count in their period, as in the
// Riepilogo, and are named so they are not taken for money already spent.
function expenseMeta(totals) {
  if (!totals.expense_count) return 'Nessuna spesa';
  const count = plural(totals.expense_count, 'spesa', 'spese');
  return totals.planned_count ? `${count}, di cui previste dopo oggi: ${formatEuro(totals.planned_cents)}` : count;
}

function houseFigures(totals) {
  const largest = Math.max(totals.income_cents, totals.expense_cents, 1);
  let incomeMeta = 'Nessuna entrata';
  if (totals.income_count) {
    incomeMeta = plural(totals.income_count, 'entrata', 'entrate');
    if (totals.voucher_cents) incomeMeta += `, di cui ${formatEuro(totals.voucher_cents)} in buoni pasto`;
  }
  const incomeParts = [{ kind: 'income', cents: totals.income_cents - totals.voucher_cents }];
  if (totals.voucher_cents) incomeParts.push({ kind: 'voucher', cents: totals.voucher_cents });
  const parts = [
    h('figure', { class: 'card cumul', 'aria-label': 'Entrate e spese del periodo' },
      cumulRow('Entrate', totals.income_cents, incomeMeta, incomeParts, largest),
      cumulRow('Spese', totals.expense_cents, expenseMeta(totals),
        [{ kind: 'expense', cents: totals.expense_cents }], largest)),
  ];
  // As in the Riepilogo: without incomes, minus the expenses would look
  // like a deficit that is not there.
  if (totals.income_count) {
    parts.push(h('div', { class: 'card balance' }, balanceRow('Differenza', 'Entrate meno spese',
      formatSignedEuro(totals.balance_cents), `balance-diff ${signClass(totals.balance_cents)}`)));
  }
  return parts;
}

function vintedFigures(totals) {
  const largest = Math.max(totals.sales_cents, totals.expense_cents, 1);
  const spent = [];
  if (totals.purchase_count) spent.push(plural(totals.purchase_count, 'articolo comprato', 'articoli comprati'));
  if (totals.extra_count) spent.push(plural(totals.extra_count, 'costo extra', 'costi extra'));
  const parts = [
    h('figure', { class: 'card cumul', 'aria-label': 'Vendite e spese Vinted del periodo' },
      cumulRow('Vendite', totals.sales_cents,
        totals.sales_count ? plural(totals.sales_count, 'vendita', 'vendite') : 'Nessuna vendita',
        [{ kind: 'income', cents: totals.sales_cents }], largest),
      cumulRow('Spese Vinted', totals.expense_cents, spent.length ? spent.join(' e ') : 'Nessuna spesa Vinted',
        [{ kind: 'expense', cents: totals.expense_cents }], largest)),
  ];
  // As in Vinted → Riepilogo: purchases alone make a real, negative difference.
  if (totals.sales_count || totals.expense_count) {
    parts.push(h('div', { class: 'card balance' }, balanceRow('Differenza', 'Vendite meno spese del periodo',
      formatSignedEuro(totals.balance_cents), `balance-diff ${signClass(totals.balance_cents)}`)));
  }
  parts.push(h('h2', { class: 'section-title' }, 'Articoli venduti'));
  parts.push(h('div', { class: 'card balance balance-flush' }, totals.sold_count
    ? balanceRow('Guadagno',
      `${plural(totals.sold_count, 'articolo', 'articoli')}: incassati ${formatEuro(totals.sold_cents)}, pagati ${formatEuro(totals.sold_cost_cents)} per comprarli; le cose già vostre costano zero`,
      formatSignedEuro(totals.gain_cents), `balance-diff ${signClass(totals.gain_cents)}`)
    : balanceRow('Guadagno', 'Nessun articolo venduto nel periodo', '–')));
  return parts;
}

// --- the screen ----------------------------------------------------------------------

export function mountFor(section) {
  return (root, ctx) => mount(root, ctx, section);
}

async function mount(root, ctx, section) {
  const config = SECTIONS[section];
  const limits = limitsOf(config);
  let period = periodFromQuery(ctx.query, limits);
  let request = 0; // the latest load wins
  const backLink = h('a', {
    class: 'page-back', href: config.back, 'aria-label': config.backLabel,
    onclick: (event) => { event.preventDefault(); ctx.back(config.back); },
  }, '‹');
  const tabs = h('nav', { class: 'seg seg-links', 'aria-label': 'Periodo' });
  const pickerSlot = h('div');
  const datesLine = h('p', { class: 'period-dates', 'aria-live': 'polite' });
  const body = h('div');
  root.append(
    h('header', { class: 'page-head' }, backLink, h('h1', { class: 'page-title' }, config.title)),
    tabs, pickerSlot, datesLine, body);

  function drawTabs() {
    tabs.replaceChildren(...VIEWS.map((item) => h('a', {
      class: `seg-item${item.id === period.view ? ' is-selected' : ''}`,
      href: pathOf(section, switchTo(period, item.id, limits)),
      'aria-current': item.id === period.view ? 'page' : null,
      onclick: (event) => {
        event.preventDefault();
        if (item.id !== period.view) show(switchTo(period, item.id, limits), { redrawPicker: true });
      },
    }, item.label)));
  }

  // "Date": two date fields; the totals follow as soon as both make sense.
  function datePicker() {
    const error = h('p', { class: 'field-error', hidden: true });
    const field = (id, label, value) => h('div', {},
      h('label', { class: 'label', for: id }, label),
      h('input', {
        class: 'input', id, type: 'date', min: EARLIEST_DAY, max: limits.day, value, required: true,
        onchange: changed,
      }));
    const fields = h('div', { class: 'period-range' },
      field('explore-from', 'Dal', period.from), field('explore-to', 'Al', period.to));
    function changed() {
      const from = fields.querySelector('#explore-from').value;
      const to = fields.querySelector('#explore-to').value;
      if (!validDay(from) || !validDay(to)) return;
      if (from > to) {
        error.textContent = 'La data iniziale deve precedere quella finale.';
        error.hidden = false;
        return;
      }
      error.hidden = true;
      show({ ...period, from, to });
    }
    return h('div', {}, fields, error);
  }

  function stepper(range) {
    return h('div', { class: 'month-switch' },
      h('button', {
        class: 'month-step', type: 'button', 'aria-label': range.backLabel, disabled: !range.canBack,
        onclick: () => show(step(period, -1), { redrawPicker: true }),
      }, icon('left')),
      h('span', { class: 'month-name', 'aria-live': 'polite' }, range.label),
      h('button', {
        class: 'month-step', type: 'button', 'aria-label': range.forwardLabel, disabled: !range.canForward,
        onclick: () => show(step(period, 1), { redrawPicker: true }),
      }, icon('right')));
  }

  // redrawPicker: false while the date fields are being edited, so the
  // field the person is typing in is not replaced under the thumb.
  async function show(next, { quiet = false, redrawPicker = false } = {}) {
    period = next;
    const mine = ++request;
    history.replaceState(history.state, '', pathOf(section, period));
    const range = bounds(period, limits);
    drawTabs();
    if (redrawPicker || !pickerSlot.firstChild) {
      pickerSlot.replaceChildren(period.view === 'date' ? datePicker() : stepper(range));
    }
    datesLine.textContent = rangeLabel(range.start, range.end);
    if (!quiet) body.replaceChildren(loadingBlock());
    let totals;
    try {
      totals = await api.get(`${config.api}?from=${range.start}&to=${range.end}`);
    } catch (error) {
      if (!quiet && ctx.isCurrent() && mine === request) body.replaceChildren(errorBlock(error, () => show(period)));
      return;
    }
    if (!ctx.isCurrent() || mine !== request) return; // a newer request took over
    body.replaceChildren(...(section === 'vinted' ? vintedFigures(totals) : houseFigures(totals)));
  }

  ctx.onResume(({ longAway }) => { if (longAway) show(period, { quiet: true }); });
  await show(period, { redrawPicker: true });
}
