// "Movimenti": the month's expenses, newest first, grouped by day. The
// switch at the top leads to the month's incomes (incomes.js), in the same tab.
// The search box under it (0.9.0) looks through every month instead.

import { api } from '../api.js';
import { viewCache, sameData } from '../cache.js';
import { state } from '../store.js';
import {
  h, icon, mainHead, formatEuro, monthLabel, dayLabel, dayMonthShort, currentMonth, shiftMonth, isPlanned, latestPlannedMonth,
  PAYMENT_LABELS, loadingBlock, errorBlock, toast,
} from '../ui.js';

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
function expenseRow(expense, { showCategory = true, showDate = false } = {}) {
  const title = expense.merchant_name || (showCategory ? expense.category_name : 'Senza esercente');
  const who = [
    showCategory && expense.merchant_name ? expense.category_name : null,
    expense.paid_by_name,
    showDate ? null : PAYMENT_LABELS[expense.payment_method].toLowerCase(),
  ].filter(Boolean).join(', ');
  const meta = showDate ? `${dayMonthShort(expense.expense_date)} · ${who}` : who;
  const href = expense.vinted_item_id ? `/vinted/articolo/${expense.vinted_item_id}` : `/spesa/${expense.id}`;
  return h('a', { class: 'row', href, dataset: { link: '' } },
    h('span', { class: 'row-main' },
      h('span', { class: 'row-title' }, title),
      h('span', { class: 'row-meta' }, meta),
      expense.vinted_item_id ? vintedLine(expense.vinted_item_title) : null,
      expense.note ? h('span', { class: 'row-note' }, expense.note) : null,
      isPlanned(expense.expense_date) ? h('span', { class: 'tag tag-planned' }, 'Prevista') : null),
    h('span', { class: 'row-amount' }, formatEuro(expense.amount_cents)));
}

// Total of the list, then one section per day (newest first) with its total.
// items must be newest first; dateOf gives an item's date, row draws it and
// count words the number ("3 spese"). Shared by expenses and incomes.
// showTotal: false where the screen already shows the total above.
export function dayList(items, { dateOf, row, count, showTotal = true }) {
  const sum = (list) => list.reduce((total, item) => total + item.amount_cents, 0);
  const groups = new Map(); // date -> items, insertion order = newest day first
  for (const item of items) {
    const date = dateOf(item);
    if (!groups.has(date)) groups.set(date, []);
    groups.get(date).push(item);
  }
  const total = h('p', { class: 'month-total' },
    h('span', { class: 'month-total-amount' }, formatEuro(sum(items))),
    h('span', { class: 'month-total-count' }, count(items.length)));
  return [
    ...(showTotal ? [total] : []), // the callers spread this into replaceChildren: no nulls
    ...Array.from(groups, ([date, dayItems]) => h('section', { class: 'day' },
      h('h2', { class: 'day-head' },
        h('span', {}, dayLabel(date)),
        h('span', { class: 'day-total' }, formatEuro(sum(dayItems)))),
      h('div', { class: 'card rows' }, dayItems.map(row)))),
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
export function searchResults({ items, totals }, { dateOf, row, count, loadMore }) {
  const monthTotals = new Map(totals.months.map((item) => [item.month, item]));
  const sections = new Map(); // 'YYYY-MM' -> the rows of that month
  const list = h('div');
  let shown = 0;
  const more = h('button', { class: 'btn btn-quiet btn-block search-more', type: 'button', onclick: next });

  function add(page) {
    for (const item of page) {
      const month = dateOf(item).slice(0, 7);
      if (!sections.has(month)) {
        const info = monthTotals.get(month) || { count: 0, total_cents: 0 };
        const rows = h('div', { class: 'card rows' });
        list.append(h('section', {},
          h('div', { class: 'list-head' },
            h('h2', { class: 'day-head' },
              h('span', {}, monthLabel(month)),
              h('span', { class: 'day-total' }, formatEuro(info.total_cents))),
            h('span', { class: 'list-head-note' }, count(info.count))),
          rows));
        sections.set(month, rows);
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
    h('p', { class: 'month-total' },
      h('span', { class: 'month-total-amount' }, formatEuro(totals.total_cents)),
      h('span', { class: 'month-total-count' }, count(totals.count))),
    h('p', { class: 'search-scope' }, 'In tutti i mesi, dalle più recenti'),
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

export async function mount(root, ctx) {
  let month = monthFromQuery(ctx.query);
  let search = searchFromQuery(ctx.query);
  let request = 0; // the latest load wins
  const head = mainHead('Movimenti', state.me.display_name);
  const tabSlot = h('div');
  const searchSlot = searchBox({
    id: 'expense-search', label: 'Cerca nelle spese', initial: search,
    onChange: (text) => {
      if (text === search) return;
      search = text;
      show(month);
    },
  });
  const switcherSlot = h('div');
  const body = h('div');
  root.append(head, tabSlot, searchSlot, switcherSlot, body);

  // quiet: refresh in place (back from the background), keeping what is on
  // screen until the new data arrives, and keeping it if the refresh fails.
  // A month seen before in this session is drawn at once from memory
  // (cache.js, 0.14.0), then refreshed the same quiet way.
  async function show(nextMonth, { quiet = false } = {}) {
    month = nextMonth;
    const mine = ++request;
    history.replaceState(history.state, '', withSearch(movementsPath(month), search));
    tabSlot.replaceChildren(movementsSwitch('expenses', month, ctx.navigate));
    switcherSlot.replaceChildren(monthSwitcher(month, show, { max: latestPlannedMonth() }));
    switcherSlot.hidden = Boolean(search); // a search looks at every month
    const text = search;
    const current = () => ctx.isCurrent() && mine === request; // a newer request takes over

    if (text) {
      if (!quiet) body.replaceChildren(loadingBlock());
      let found;
      try {
        found = await searchFirstPage('expenses', text);
      } catch (error) {
        if (!quiet && current()) body.replaceChildren(errorBlock(error, () => show(month)));
        return;
      }
      if (!current()) return;
      body.replaceChildren(...(found.totals.count
        ? searchResults(found, {
          dateOf: (expense) => expense.expense_date,
          row: (expense) => expenseRow(expense, { showDate: true }),
          count: countExpenses,
          loadMore: async (offset) => {
            const page = await api.get(
              `/expenses?q=${encodeURIComponent(text)}&limit=${SEARCH_PAGE}&offset=${offset}`);
            return current() ? page : null;
          },
        })
        : [noResults(`Nessuna spesa trovata per «${text}»`,
          'La ricerca guarda esercente, nota, categoria e importo (per esempio 12,50), in tutti i mesi.')]));
      return;
    }

    const key = `expenses:${month}`;
    const cached = viewCache.get(key);
    if (cached) draw(cached);
    else if (!quiet) body.replaceChildren(loadingBlock());
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
    if (expenses.length === 0) {
      body.replaceChildren(h('div', { class: 'empty' },
        h('p', { class: 'empty-title' }, `Nessuna spesa a ${monthLabel(month)}`),
        month === currentMonth()
          ? h('a', { class: 'btn btn-primary', href: '/', dataset: { link: '' } }, 'Aggiungi una spesa')
          : null));
      return;
    }
    body.replaceChildren(...expenseList(expenses));
  }

  ctx.onResume(({ longAway }) => { if (longAway) show(month, { quiet: true }); });
  await show(month);
}
