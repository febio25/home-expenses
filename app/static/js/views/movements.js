// "Movimenti": the month's expenses. 0.18.0 (F15): it opens on a calendar
// of the month with the total of each day; the day picked opens below as a
// receipt. The lens beside the total shows the whole month as one receipt,
// with «Cerca nelle spese» and the filters (F6) that look through every
// month. The switch at the top leads to the month's incomes (incomes.js),
// in the same tab.

import { api } from '../api.js';
import { viewCache, sameData } from '../cache.js';
import { state, loadUsers, loadCategories } from '../store.js';
import {
  h, icon, mainHead, formatEuro, euroParts, monthLabel, dayLabel, dayMonthShort, currentMonth, shiftMonth, isPlanned,
  latestPlannedMonth, latestPlannedIso, todayIso, PAYMENT_LABELS, loadingBlock, errorBlock, toast, choiceDialog,
} from '../ui.js';
import { tagsIn, noteWithoutTags } from '../tags.js';

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

// Shared with the summary screen: "‹  novembre 2026  ›". Forward stops at
// the current month, or at `max`: the expense screens pass the last month an
// expense can be planned in (0.12.0).
export function monthSwitcher(month, onChange, { max = currentMonth() } = {}) {
  const isLast = month >= max;
  return h('div', { class: 'month-switch' },
    h('button', {
      class: 'month-step', type: 'button', 'aria-label': 'Mese precedente',
      onclick: () => onChange(shiftMonth(month, -1)),
    }, icon('left')),
    h('span', { class: 'month-name', 'aria-live': 'polite' }, monthLabel(month)),
    h('button', {
      class: 'month-step', type: 'button', 'aria-label': 'Mese successivo', disabled: isLast,
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
// repeat the same name on every row. showDate: in the search results, which
// are grouped by month: the day leads the line, the payment method makes
// room for it.
// 0.18.0 (F2): the tags of the note are pills under the row; a tap shows
// every expense with that tag, with the total. They are links of their own,
// next to the row's link (a link inside a link is not allowed), laid over
// its bottom edge.
export function tagPath(tag) {
  return `/movimenti?vista=lista&etichetta=${encodeURIComponent(tag)}`;
}

function expenseRow(expense, { showCategory = true, showDate = false } = {}) {
  const title = expense.merchant_name || (showCategory ? expense.category_name : 'Senza esercente');
  const who = [
    showCategory && expense.merchant_name ? expense.category_name : null,
    expense.paid_by_name,
    showDate ? null : PAYMENT_LABELS[expense.payment_method].toLowerCase(),
  ].filter(Boolean).join(', ');
  const meta = showDate ? `${dayMonthShort(expense.expense_date)} · ${who}` : who;
  const href = expense.vinted_item_id ? `/vinted/articolo/${expense.vinted_item_id}` : `/spesa/${expense.id}`;
  const tags = tagsIn(expense.note);
  const note = tags.length ? noteWithoutTags(expense.note) : expense.note;
  const row = h('a', { class: `row${tags.length ? ' has-tags' : ''}`, href, dataset: { link: '' } },
    h('span', { class: 'row-main' },
      h('span', { class: 'row-title' }, title),
      h('span', { class: 'row-meta' }, meta),
      expense.vinted_item_id ? vintedLine(expense.vinted_item_title) : null,
      note ? h('span', { class: 'row-note' }, note) : null,
      isPlanned(expense.expense_date) ? h('span', { class: 'tag tag-planned' }, 'Prevista') : null),
    h('span', { class: 'row-amount' }, formatEuro(expense.amount_cents)));
  if (!tags.length) return row;
  return h('div', { class: 'row-wrap' }, row,
    h('div', { class: 'row-tags' }, tags.map((tag) => h('a', {
      class: 'tag-pill', href: tagPath(tag), dataset: { link: '' },
      'aria-label': `Tutte le spese con l’etichetta ${tag}`,
    }, `#${tag}`))));
}

// Total of a list above its receipt: "897,57 €" with the € small, and the
// count ("29 spese").
export function listTotal(cents, countText) {
  return h('p', { class: 'month-total' },
    h('span', { class: 'month-total-amount' }, ...euroParts(cents)),
    h('span', { class: 'month-total-count' }, countText));
}

// 0.16.0, «scontrino vero»: the whole list is one strip of receipt paper,
// torn at the top and at the bottom. Each section (a day, or a month in the
// search results) opens with its name in capitals between two dashed lines,
// like a department on a till receipt, and closes with its «Subtotale», even
// with a single row: the same place every time. No line between the rows of
// a section. sections: [{ title, items, note }], rows drawn by row.
// 0.18.1: in the lens and the search, a section of a single row (single:
// true) closes with nothing: no «Subtotale» repeating its amount, no dotted
// line. The day picked on the calendar keeps its «Subtotale» even then.
function receipt(sections, row) {
  const sum = (list) => list.reduce((total, item) => total + item.amount_cents, 0);
  return h('div', { class: 'roll' }, sections.map(({ title, items, cents = null, note = null, single = null }) => {
    const rows = h('div', { class: 'rows' }, items.map(row));
    const section = h('section', { class: 'day' },
      h('h2', { class: 'day-head' }, h('span', {}, title)),
      rows,
      single
        ? null
        : h('p', { class: 'day-sub' },
          h('span', {}, note ? `Subtotale · ${note}` : 'Subtotale'),
          h('span', { class: 'day-total' }, formatEuro(cents ?? sum(items)))));
    section.rows = rows; // the search adds the rows of a later page here
    return section;
  }));
}

// Total of the list, then one section per day (newest first), on the
// receipt. items must be newest first; dateOf gives an item's date, row
// draws it and count words the number ("3 spese"). Shared by the expenses
// and the search results; the incomes have a sheet of their own (0.16.0,
// payslip() in incomes.js).
// showTotal: false where the screen already shows the total above.
// lone: true (the lens, 0.18.1) closes a day of one row with nothing; the
// day picked on the calendar keeps its «Subtotale», like a receipt.
export function dayList(items, { dateOf, row, count, showTotal = true, lone = false }) {
  const groups = new Map(); // date -> items, insertion order = newest day first
  for (const item of items) {
    const date = dateOf(item);
    if (!groups.has(date)) groups.set(date, []);
    groups.get(date).push(item);
  }
  const total = items.reduce((sum, item) => sum + item.amount_cents, 0);
  return [
    ...(showTotal ? [listTotal(total, count(items.length))] : []), // spread into replaceChildren: no nulls
    receipt(Array.from(groups, ([date, dayItems]) => ({ title: dayLabel(date), items: dayItems, single: lone && dayItems.length === 1 })), row),
  ];
}

// --- search (0.9.0) -------------------------------------------------------------

const SEARCH_MAX = 80; // as the API

// The text searched, from the address (?cerca=…): Back from an opened
// movement finds the same results.
export function searchFromQuery(query) {
  return (query.get('cerca') || '').trim().replace(/\s+/g, ' ').slice(0, SEARCH_MAX);
}

// A list address with the text searched, if any.
export function withSearch(path, text) {
  if (!text) return path;
  return `${path}${path.includes('?') ? '&' : '?'}cerca=${encodeURIComponent(text)}`;
}

// The search box of the two lists. onChange gets the tidied text a moment
// after the typing stops (at once on Enter or on the clear button).
export function searchBox({ id, label, initial, onChange }) {
  const input = h('input', {
    class: 'input', id, type: 'text', inputmode: 'search', enterkeyhint: 'search',
    autocomplete: 'off', maxLength: SEARCH_MAX, placeholder: label, value: initial,
  });
  input.setAttribute('autocorrect', 'off');
  input.setAttribute('spellcheck', 'false');
  const clear = h('button', {
    class: 'search-clear', type: 'button', 'aria-label': 'Cancella la ricerca', hidden: !initial,
  }, icon('close'));
  const box = h('div', { class: `search search-movements${initial ? ' has-text' : ''}`, role: 'search' },
    icon('search'), h('label', { class: 'visually-hidden', for: id }, label), input, clear);
  let timer = null;
  function changed(now) {
    const hasText = input.value !== '';
    box.classList.toggle('has-text', hasText);
    clear.hidden = !hasText;
    clearTimeout(timer);
    const send = () => onChange(input.value.trim().replace(/\s+/g, ' '));
    if (now) send(); else timer = setTimeout(send, 300);
  }
  input.addEventListener('input', () => changed(false));
  input.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    input.blur(); // closes the keyboard: the results are below it
    changed(true);
  });
  clear.addEventListener('click', () => {
    input.value = '';
    changed(true);
    input.focus();
  });
  return box;
}

// Rows read per page of a search (0.14.0).
export const SEARCH_PAGE = 100;

// The first page of a search and the totals of every match: `what` is
// "expenses" or "incomes". The totals come from the server, so they count
// every result, not only the rows on screen.
export async function searchFirstPage(what, text) {
  const q = encodeURIComponent(text);
  const [items, totals] = await Promise.all([
    api.get(`/${what}?q=${q}&limit=${SEARCH_PAGE}`),
    api.get(`/summary/search/${what}?q=${q}`),
  ]);
  return { items, totals };
}

// Search results (0.14.0: a page at a time): total and count of every
// match, then one section per month (newest first) with its own total, and
// «Mostra altre» while rows are left. loadMore(offset) returns the next
// page, or null when the screen moved on meanwhile. Same dateOf, row and
// count as dayList.
// sheet: the incomes, on the plain sheet of their list (no torn edges).
// scope (0.18.0): the line under the total, "In tutti i mesi, dalle più recenti".
export function searchResults({ items, totals }, {
  dateOf, row, count, loadMore, sheet = false, scope = 'In tutti i mesi, dalle più recenti',
}) {
  const monthTotals = new Map(totals.months.map((item) => [item.month, item]));
  const sections = new Map(); // 'YYYY-MM' -> the rows of that month
  const list = h('div', { class: sheet ? 'roll is-sheet' : 'roll' });
  let shown = 0;
  const more = h('button', { class: 'btn btn-quiet btn-block search-more', type: 'button', onclick: next });

  // The same receipt as the month's list, one section per month: its
  // subtotal and count are of every match in that month (from the server).
  function add(page) {
    for (const item of page) {
      const month = dateOf(item).slice(0, 7);
      if (!sections.has(month)) {
        const info = monthTotals.get(month) || { count: 0, total_cents: 0 };
        const [section] = receipt([{
          title: monthLabel(month), items: [], cents: info.total_cents, note: count(info.count), single: info.count === 1,
        }], row).children;
        list.append(section);
        sections.set(month, section.rows);
      }
      sections.get(month).append(row(item));
    }
    shown += page.length;
    const left = totals.count - shown;
    more.hidden = left <= 0 || page.length === 0;
    more.disabled = false;
    more.textContent = `Mostra altre ${Math.min(left, SEARCH_PAGE)} (${shown} di ${totals.count})`;
  }

  async function next() {
    more.disabled = true;
    more.textContent = 'Caricamento…';
    try {
      const page = await loadMore(shown);
      if (page) add(page);
    } catch (error) {
      more.disabled = false;
      more.textContent = 'Riprova a caricare le altre';
      toast(`Non caricate: ${error.message}`, { kind: 'error' });
    }
  }

  add(items);
  return [
    listTotal(totals.total_cents, count(totals.count)),
    h('p', { class: 'search-scope' }, scope),
    list,
    more,
  ];
}

// Nothing found: what the search looks at.
export function noResults(title, text) {
  return h('div', { class: 'empty' }, h('p', { class: 'empty-title' }, title), h('p', { class: 'empty-text' }, text));
}

const countExpenses = (number) => (number === 1 ? '1 spesa' : `${number} spese`);

// Shared with the summary of a single category.
export function expenseList(expenses, rowOptions) {
  return dayList(expenses, {
    dateOf: (expense) => expense.expense_date,
    row: (expense) => expenseRow(expense, rowOptions),
    count: countExpenses,
  });
}


// --- the calendar of the month (0.18.0, F15) -------------------------------------

const WEEKDAYS = ['lun', 'mar', 'mer', 'gio', 'ven', 'sab', 'dom'];
const wholeEuros = new Intl.NumberFormat('it-IT', { maximumFractionDigits: 0, useGrouping: 'always' });
const DAY_SHAPE = /^\d{4}-\d{2}-\d{2}$/;

function daysIn(month) {
  const [year, number] = month.split('-').map(Number);
  return new Date(year, number, 0).getDate();
}

const isoOf = (month, day) => `${month}-${String(day).padStart(2, '0')}`;

// The day picked when a month opens: today in the current month, always.
// In another month the last day with expenses (the newest, as the lists
// go), or its first day when it has none.
export function startDay(month, expenses) {
  const today = todayIso();
  if (month === today.slice(0, 7)) return today;
  return expenses.length ? expenses[0].expense_date : isoOf(month, 1);
}

// «127 €», «1,2k €», «12k €»: the total under a day, in whole euros, short
// enough for a cell of a 320 px screen (0.18.1). The exact amount is in the
// receipt below and in what a screen reader says.
export function dayAmount(cents) {
  const euros = Math.round(cents / 100);
  if (euros < 1000) return `${wholeEuros.format(euros)} €`;
  if (euros < 10000) return `${(Math.round(euros / 100) / 10).toLocaleString('it-IT')}k €`;
  if (euros < 1000000) return `${Math.round(euros / 1000)}k €`;
  return `${(Math.round(euros / 100000) / 10).toLocaleString('it-IT')}M €`;
}

// Monday-first grid; each day shows its total (planned days after today in
// grey), today is underlined, the day picked is filled. 0.18.1: the days
// of the months around fill the first and last week, in light grey and
// without totals: a tap goes to that month. The more a day cost compared
// with the others of the month, the deeper its green, so the heavy days
// stand out.
function calendar(month, totals, selected, onPick, onOtherMonth) {
  const today = todayIso();
  const [year, number] = month.split('-').map(Number);
  const lead = (new Date(year, number - 1, 1).getDay() + 6) % 7; // days of the month before
  const length = daysIn(month);
  const trail = (7 - ((lead + length) % 7)) % 7; // days of the month after
  const largest = Math.max(0, ...[...totals].filter(([iso]) => iso <= today).map(([, info]) => info.cents));
  const cells = [];
  const other = (iso) => {
    const reachable = iso >= '2000-01-01' && iso.slice(0, 7) <= latestPlannedMonth();
    return h('button', {
      class: 'cal-day is-other', type: 'button', disabled: !reachable, tabindex: '-1',
      'aria-label': `${dayLabel(iso)}: vai a ${monthLabel(iso.slice(0, 7))}`,
      onclick: () => onOtherMonth(iso),
    }, h('span', { class: 'cal-num' }, String(Number(iso.slice(8, 10)))), h('span', { class: 'cal-sum' }, ''));
  };
  const before = shiftMonth(month, -1);
  for (let index = lead; index > 0; index -= 1) cells.push(other(isoOf(before, daysIn(before) - index + 1)));
  for (let day = 1; day <= length; day += 1) {
    const iso = isoOf(month, day);
    const info = totals.get(iso);
    const classes = ['cal-day'];
    if (iso === selected) classes.push('is-selected');
    if (iso === today) classes.push('is-today');
    if (iso > today) classes.push('is-future');
    if (info && iso <= today && largest > 0) {
      const share = info.cents / largest;
      classes.push(share > 0.66 ? 'heat-3' : share > 0.33 ? 'heat-2' : 'heat-1');
    }
    const words = info
      ? `${formatEuro(info.cents)}, ${countExpenses(info.count)}${iso > today ? ' previste' : ''}`
      : 'nessuna spesa';
    cells.push(h('button', {
      class: classes.join(' '), type: 'button', 'aria-pressed': String(iso === selected),
      'aria-label': `${dayLabel(iso)}: ${words}`,
      onclick: () => onPick(iso),
    },
    h('span', { class: 'cal-num' }, String(day)),
    h('span', { class: 'cal-sum' }, info ? dayAmount(info.cents) : '')));
  }
  const after = shiftMonth(month, 1);
  for (let day = 1; day <= trail; day += 1) cells.push(other(isoOf(after, day)));
  return h('div', { class: 'cal', role: 'group', 'aria-label': `Calendario di ${monthLabel(month)}` },
    h('div', { class: 'cal-head', 'aria-hidden': 'true' }, WEEKDAYS.map((name) => h('span', {}, name))),
    h('div', { class: 'cal-grid' }, cells));
}

// The day picked, as a receipt torn at the top and at the bottom, or the
// way to add an expense on that day.
function dayReceipt(day, items) {
  if (items.length) {
    return h('div', { class: 'cal-receipt' },
      ...dayList(items, {
        dateOf: (expense) => expense.expense_date,
        row: (expense) => expenseRow(expense),
        count: countExpenses,
        showTotal: false,
      }));
  }
  const planned = day > todayIso();
  const canAdd = day <= latestPlannedIso();
  const label = dayLabel(day);
  return h('div', { class: 'empty cal-empty' },
    h('p', { class: 'empty-text' }, `${planned ? 'Nessuna spesa prevista' : 'Nessuna spesa'} ${label === 'Oggi' ? 'oggi' : label}`),
    canAdd
      ? h('a', { class: 'btn btn-quiet', href: `/?data=${day}`, dataset: { link: '' } }, 'Aggiungi una spesa in questo giorno')
      : null);
}

// --- filters of the search (0.18.0, F6) ---------------------------------------------

const PERIODS = [
  { value: 'mese', label: 'Questo mese' },
  { value: '3mesi', label: 'Ultimi 3 mesi' },
  { value: 'anno', label: 'Quest’anno' },
  { value: 'annoscorso', label: 'Anno scorso' },
];

// First and last day of a period, from today; the end reaches the planned
// expenses of the month or year.
function periodRange(value) {
  const month = currentMonth();
  const year = Number(month.slice(0, 4));
  const lastOf = (m) => isoOf(m, daysIn(m));
  switch (value) {
    case 'mese': return { from: `${month}-01`, to: lastOf(month) };
    case '3mesi': return { from: `${shiftMonth(month, -2)}-01`, to: lastOf(month) };
    case 'anno': return { from: `${year}-01-01`, to: `${year}-12-31` };
    case 'annoscorso': return { from: `${year - 1}-01-01`, to: `${year - 1}-12-31` };
    default: return null;
  }
}

// The filters in the address: ?categoria=3&chi=2&metodo=cash&periodo=anno&etichetta=vacanze
const FILTER_KEYS = ['categoria', 'chi', 'metodo', 'periodo', 'etichetta'];

function filtersFromQuery(query) {
  const filters = {};
  const number = (text) => (/^\d+$/.test(text || '') ? text : null);
  if (number(query.get('categoria'))) filters.categoria = query.get('categoria');
  if (number(query.get('chi'))) filters.chi = query.get('chi');
  if (PAYMENT_LABELS[query.get('metodo')]) filters.metodo = query.get('metodo');
  if (PERIODS.some((item) => item.value === query.get('periodo'))) filters.periodo = query.get('periodo');
  const tag = (query.get('etichetta') || '').replace(/^#/, '').trim();
  if (tag) filters.etichetta = tag.slice(0, 40);
  return filters;
}

// The API parameters of a search: text and filters.
function searchParams(text, filters) {
  const params = new URLSearchParams();
  if (text) params.set('q', text);
  if (filters.categoria) params.set('category_id', filters.categoria);
  if (filters.chi) params.set('paid_by_user_id', filters.chi);
  if (filters.metodo) params.set('payment_method', filters.metodo);
  if (filters.etichetta) params.set('tag', filters.etichetta);
  const range = periodRange(filters.periodo);
  if (range) {
    params.set('from', range.from);
    params.set('to', range.to);
  }
  return params;
}

// --- the screen ------------------------------------------------------------------------

export function calendarPath(month) {
  return movementsPath(month);
}

export async function mount(root, ctx) {
  let month = monthFromQuery(ctx.query);
  // The lens: the whole month, the search and the filters. Old addresses
  // with only ?cerca= (0.9.0) open it too.
  const lens = ctx.query.get('vista') === 'lista' || ctx.query.has('cerca') || ctx.query.has('etichetta');
  let search = searchFromQuery(ctx.query);
  let filters = lens ? filtersFromQuery(ctx.query) : {};
  const askedDay = ctx.query.get('giorno');
  let day = askedDay && DAY_SHAPE.test(askedDay) && askedDay.slice(0, 7) === month ? askedDay : null;
  let request = 0; // the latest load wins
  let monthItems = null; // the expenses of the month on screen
  let landingDay = null; // 0.18.1: the day tapped in the month before or after
  let lookups = null; // users, categories and tags, for the filters

  const head = mainHead('Movimenti', state.me.display_name);
  const tabSlot = h('div');
  const switcherSlot = h('div');
  const totalSlot = h('div', { class: 'cal-total' });
  const toolSlot = h('div');
  const body = h('div');
  root.append(head, tabSlot, switcherSlot, totalSlot, toolSlot, body);

  const searching = () => Boolean(search) || Object.keys(filters).length > 0;

  function addressOf() {
    if (!lens) {
      const base = movementsPath(month);
      if (!day || day === startDay(month, monthItems || [])) return base;
      return `${base}${base.includes('?') ? '&' : '?'}giorno=${day}`;
    }
    const params = new URLSearchParams();
    params.set('vista', 'lista');
    if (month !== currentMonth()) params.set('mese', month);
    if (search) params.set('cerca', search);
    for (const key of FILTER_KEYS) if (filters[key]) params.set(key, filters[key]);
    return `/movimenti?${params.toString()}`;
  }

  // Calendar and lens, beside the total. The lens is a screen of its own
  // in the history: Back from it returns to the calendar.
  function modeButtons() {
    const button = (name, label, active, onclick) => h('button', {
      class: `mode-btn${active ? ' is-active' : ''}`, type: 'button', 'aria-label': label,
      'aria-pressed': String(active), onclick,
    }, icon(name));
    return h('div', { class: 'mode-btns' },
      button('calendar', 'Calendario del mese', !lens, () => { if (lens) ctx.back(calendarPath(month)); }),
      button('search', 'Lista del mese e ricerca', lens, () => {
        if (!lens) ctx.navigate(`/movimenti?vista=lista${month === currentMonth() ? '' : `&mese=${month}`}`);
      }));
  }

  function drawTotal(cents, count) {
    totalSlot.replaceChildren(
      h('p', { class: 'month-total', 'aria-label': `${monthLabel(month)}: ${formatEuro(cents)}, ${countExpenses(count)}` },
        h('span', { class: 'month-total-amount' }, ...euroParts(cents))),
      modeButtons());
  }

  // --- filter pills ---
  async function loadLookups() {
    if (lookups) return lookups;
    const [users, categories, tags] = await Promise.all([
      loadUsers(), loadCategories(), api.get('/tags').catch(() => []),
    ]);
    lookups = { users, categories, tags };
    return lookups;
  }

  function filterValueLabel(key) {
    const value = filters[key];
    if (!value) return null;
    if (key === 'metodo') return PAYMENT_LABELS[value];
    if (key === 'periodo') return PERIODS.find((item) => item.value === value).label;
    if (key === 'etichetta') return `#${value}`;
    if (!lookups) return '…';
    if (key === 'chi') return (lookups.users.find((u) => String(u.id) === value) || {}).display_name || '?';
    return (lookups.categories.find((c) => String(c.id) === value) || {}).name || '?';
  }

  async function chooseFilter(key) {
    const data = await loadLookups().catch(() => null);
    if (!data || !ctx.isCurrent()) return;
    let options;
    let title;
    if (key === 'categoria') {
      title = 'Categoria';
      options = data.categories.map((c) => ({ value: String(c.id), label: c.name }));
    } else if (key === 'chi') {
      title = 'Pagato da';
      options = data.users.map((u) => ({ value: String(u.id), label: u.display_name }));
    } else if (key === 'metodo') {
      title = 'Metodo di pagamento';
      options = Object.entries(PAYMENT_LABELS).map(([value, label]) => ({ value, label }));
    } else if (key === 'periodo') {
      title = 'Periodo';
      options = PERIODS;
    } else {
      title = 'Etichetta';
      options = data.tags.map((t) => ({
        value: t.tag, label: `#${t.tag}`, meta: countExpenses(t.count), amount: formatEuro(t.total_cents),
      }));
    }
    const picked = await choiceDialog({
      title, options, sheet: true,
      empty: key === 'etichetta' ? 'Nessuna etichetta: scrivi #parola nella nota di una spesa.' : 'Niente da scegliere.',
    });
    if (picked === null || !ctx.isCurrent()) return;
    filters = { ...filters, [key]: picked };
    show(month);
  }

  function pills() {
    const names = { categoria: 'Categoria', chi: 'Chi', metodo: 'Metodo', periodo: 'Periodo', etichetta: 'Etichetta' };
    return h('div', { class: 'filters', role: 'group', 'aria-label': 'Filtri' }, FILTER_KEYS.map((key) => {
      const value = filterValueLabel(key);
      if (!value) {
        return h('button', { class: 'fpill', type: 'button', onclick: () => chooseFilter(key) },
          names[key], h('span', { class: 'fpill-caret', 'aria-hidden': 'true' }, '▾'));
      }
      return h('span', { class: 'fpill is-active' },
        h('button', {
          class: 'fpill-main', type: 'button', 'aria-label': `${names[key]}: ${value}. Cambia`,
          onclick: () => chooseFilter(key),
        }, value),
        h('button', {
          class: 'fpill-clear', type: 'button', 'aria-label': `Togli il filtro ${names[key]}`,
          onclick: () => {
            const next = { ...filters };
            delete next[key];
            filters = next;
            show(month);
          },
        }, icon('close')));
    }));
  }

  const searchInput = lens ? searchBox({
    id: 'expense-search', label: 'Cerca nelle spese', initial: search,
    onChange: (text) => {
      if (text === search) return;
      search = text;
      show(month);
    },
  }) : null;

  // --- drawing ---
  async function show(nextMonth, { quiet = false } = {}) {
    if (nextMonth !== month) day = null;
    month = nextMonth;
    const mine = ++request;
    const current = () => ctx.isCurrent() && mine === request; // a newer request takes over
    tabSlot.replaceChildren(movementsSwitch('expenses', month, ctx.navigate));
    switcherSlot.replaceChildren(monthSwitcher(month, show, { max: latestPlannedMonth() }));
    switcherSlot.hidden = lens && searching(); // a search looks at every month
    if (lens) {
      toolSlot.replaceChildren(searchInput, pills());
      if (Object.keys(filters).length && !lookups) {
        loadLookups().then(() => { if (current()) toolSlot.replaceChildren(searchInput, pills()); }).catch(() => {});
      }
    }

    if (lens && searching()) {
      history.replaceState(history.state, '', addressOf());
      totalSlot.replaceChildren(h('span'), modeButtons());
      if (!quiet) body.replaceChildren(loadingBlock());
      const params = searchParams(search, filters);
      let found;
      try {
        const page = new URLSearchParams(params);
        page.set('limit', String(SEARCH_PAGE));
        const [items, totals] = await Promise.all([
          api.get(`/expenses?${page}`),
          api.get(`/summary/search/expenses?${params}`),
        ]);
        found = { items, totals };
      } catch (error) {
        if (!quiet && current()) body.replaceChildren(errorBlock(error, () => show(month)));
        return;
      }
      if (!current()) return;
      const period = PERIODS.find((item) => item.value === filters.periodo);
      body.replaceChildren(...(found.totals.count
        ? searchResults(found, {
          dateOf: (expense) => expense.expense_date,
          row: (expense) => expenseRow(expense, { showDate: true }),
          count: countExpenses,
          scope: period ? `${period.label}, dalle più recenti` : 'In tutti i mesi, dalle più recenti',
          loadMore: async (offset) => {
            const more = new URLSearchParams(params);
            more.set('limit', String(SEARCH_PAGE));
            more.set('offset', String(offset));
            const rows = await api.get(`/expenses?${more}`);
            return current() ? rows : null;
          },
        })
        : [noResults(search ? `Nessuna spesa trovata per «${search}»` : 'Nessuna spesa con questi filtri',
          'La ricerca guarda esercente, nota, categoria e importo (per esempio 12,50); i filtri si combinano con il testo.')]));
      return;
    }

    const key = `expenses:${month}`;
    const cached = viewCache.get(key);
    if (cached) draw(cached);
    else if (!quiet) {
      history.replaceState(history.state, '', addressOf());
      totalSlot.replaceChildren();
      body.replaceChildren(loadingBlock());
    }
    let expenses;
    try {
      expenses = await api.get(`/expenses?month=${month}`);
    } catch (error) {
      if (!quiet && !cached && current()) body.replaceChildren(errorBlock(error, () => show(month)));
      return;
    }
    if (!current()) return;
    if (cached && sameData(cached, expenses)) return;
    viewCache.set(key, expenses);
    draw(expenses);
  }

  function draw(expenses) {
    monthItems = expenses;
    const total = expenses.reduce((sum, expense) => sum + expense.amount_cents, 0);
    drawTotal(total, expenses.length);
    if (lens) {
      history.replaceState(history.state, '', addressOf());
      body.replaceChildren(...(expenses.length
        ? dayList(expenses, {
          dateOf: (expense) => expense.expense_date,
          row: (expense) => expenseRow(expense),
          count: countExpenses,
          showTotal: false,
          lone: true,
        })
        : [h('div', { class: 'empty' }, h('p', { class: 'empty-title' }, `Nessuna spesa a ${monthLabel(month)}`))]));
      return;
    }
    if (!day) day = landingDay && landingDay.slice(0, 7) === month ? landingDay : startDay(month, expenses);
    landingDay = null;
    history.replaceState(history.state, '', addressOf());
    const totals = new Map();
    for (const expense of expenses) {
      const info = totals.get(expense.expense_date) || { cents: 0, count: 0 };
      info.cents += expense.amount_cents;
      info.count += 1;
      totals.set(expense.expense_date, info);
    }
    const receiptSlot = h('div');
    const pick = (iso) => {
      day = iso;
      history.replaceState(history.state, '', addressOf());
      grid.querySelectorAll('.cal-day:not(.is-other)').forEach((cell, index) => {
        const selected = isoOf(month, index + 1) === iso;
        cell.classList.toggle('is-selected', selected);
        cell.setAttribute('aria-pressed', String(selected));
      });
      receiptSlot.replaceChildren(dayReceipt(iso, expenses.filter((expense) => expense.expense_date === iso)));
    };
    const grid = calendar(month, totals, day, pick, (iso) => {
      landingDay = iso;
      show(iso.slice(0, 7));
    });
    receiptSlot.replaceChildren(dayReceipt(day, expenses.filter((expense) => expense.expense_date === day)));
    body.replaceChildren(grid, receiptSlot);
  }

  ctx.onResume(({ longAway }) => { if (longAway) show(month, { quiet: true }); });
  await show(month);
}
