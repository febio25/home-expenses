// "Movimenti → Entrate": the month's incomes (salaries, refunds, gifts...),
// newest first and grouped by day like the expenses. Same tab as the
// expense list: the switch at the top moves between the two, on the same
// month. "Nuova entrata" sits at the bottom, in reach of the thumb. The
// search box (0.9.0) looks through every month, as for the expenses.

import { api } from '../api.js';
import { viewCache, sameData } from '../cache.js';
import { state } from '../store.js';
import {
  h, icon, mainHead, formatEuro, euroParts, monthLabel, dayMonthShort, currentMonth, todayIso, loadingBlock, errorBlock,
} from '../ui.js';
import {
  monthSwitcher, monthFromQuery, movementsSwitch, incomesPath, vintedLine,
  searchFromQuery, withSearch, searchBox, searchResults, searchFirstPage, noResults, SEARCH_PAGE,
} from './movements.js';

const countIncomes = (number) => (number === 1 ? '1 entrata' : `${number} entrate`);

// From the list of a past month, a new income starts in that month.
export function newIncomePath(month) {
  return month === currentMonth() ? '/entrate/nuova' : `/entrate/nuova?mese=${month}`;
}

// The sale of a Vinted item opens the item (see vintedLine).
// showDate: in the search results, grouped by month.
export function incomeRow(income, { showDate = false } = {}) {
  const href = income.vinted_item_id ? `/vinted/articolo/${income.vinted_item_id}` : `/entrate/${income.id}`;
  const meta = showDate ? `${dayMonthShort(income.income_date)} · ${income.received_by_name}` : income.received_by_name;
  return h('a', { class: 'row', href, dataset: { link: '' } },
    h('span', { class: 'row-main' },
      h('span', { class: 'row-title' }, income.category_name),
      h('span', { class: 'row-meta' }, meta),
      income.vinted_item_id ? vintedLine(income.vinted_item_title) : null,
      income.note ? h('span', { class: 'row-note' }, income.note) : null),
    h('span', { class: 'row-amount' }, formatEuro(income.amount_cents)));
}

// Recurring incomes still expected in the month: active, with the next
// occurrence inside it. The same rule as the «Attese» of the Riepilogo
// (expected_incomes in app/routers/summary.py).
export function expectedIn(templates, month) {
  return templates.filter((t) => t.is_active && t.next_due.slice(0, 7) === month).length;
}

// "15/11"
function dayMonthDigits(iso) {
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
}

// 0.16.0, «busta paga»: the incomes of a month on a plain sheet, like a pay
// slip. A head with the period, the number of incomes and the ones still
// expected; a table Data | Voce | Importo, newest first; at the bottom the
// total in its own box (the «netto» of the slip), then the part in meal
// vouchers. expected: a number, or null to leave that box out.
// marked (0.18.0): a category whose rows are highlighted, as opened from
// the incomes side of the Riepilogo; onUnmark removes the highlight.
export function payslip(incomes, { month, expected = null, marked = null, onUnmark = null }) {
  const total = incomes.reduce((sum, income) => sum + income.amount_cents, 0);
  const vouchers = incomes.filter((income) => income.category === 'meal_voucher')
    .reduce((sum, income) => sum + income.amount_cents, 0);
  const box = (label, value) => h('div', { class: 'slip-box' },
    h('span', { class: 'slip-label' }, label), h('span', { class: 'slip-value' }, value));
  const rows = incomes.map((income) => {
    const href = income.vinted_item_id ? `/vinted/articolo/${income.vinted_item_id}` : `/entrate/${income.id}`;
    const meta = [income.received_by_name, income.note].filter(Boolean).join(' · ');
    const isMarked = marked !== null && income.category === marked;
    return h('a', { class: `slip-row${isMarked ? ' is-marked' : ''}`, href, dataset: { link: '' } },
      h('span', { class: 'slip-date' }, dayMonthDigits(income.income_date)),
      h('span', { class: 'row-main' },
        h('span', { class: 'row-title' }, income.category_name),
        meta ? h('span', { class: 'row-meta' }, meta) : null,
        income.vinted_item_id ? vintedLine(income.vinted_item_title) : null),
      h('span', { class: 'row-amount' }, formatEuro(income.amount_cents)));
  });
  const markedRows = marked === null ? [] : incomes.filter((income) => income.category === marked);
  const markLine = markedRows.length
    ? h('p', { class: 'slip-marked' },
      h('span', { class: 'slip-marked-text' },
        `Evidenziate: ${markedRows[0].category_name} · ${formatEuro(markedRows.reduce((sum, income) => sum + income.amount_cents, 0))}`),
      h('button', {
        class: 'slip-marked-clear', type: 'button', 'aria-label': 'Togli l’evidenza', onclick: onUnmark,
      }, icon('close')))
    : null;
  return h('div', { class: 'slip' },
    markLine,
    h('div', { class: 'slip-head' },
      box('Periodo', monthLabel(month)),
      box('Entrate', String(incomes.length)),
      expected === null ? null : box('Attese', String(expected))),
    h('div', { class: 'slip-cols', 'aria-hidden': 'true' },
      h('span', {}, 'Data'), h('span', {}, 'Voce'), h('span', {}, 'Importo')),
    h('div', { class: 'slip-rows' }, rows),
    h('p', { class: 'slip-total' },
      h('span', { class: 'slip-total-label' }, 'Totale entrate'),
      h('span', { class: 'slip-total-amount' }, ...euroParts(total))),
    vouchers ? h('p', { class: 'slip-note' },
      h('span', {}, 'di cui buoni pasto'), h('span', {}, formatEuro(vouchers))) : null);
}

export async function mount(root, ctx) {
  let month = monthFromQuery(ctx.query);
  let search = searchFromQuery(ctx.query);
  let marked = ctx.query.get('evidenzia') || null; // 0.18.0: a category, from the Riepilogo
  let request = 0; // the latest load wins
  const tabSlot = h('div');
  const searchSlot = searchBox({
    id: 'income-search', label: 'Cerca nelle entrate', initial: search,
    onChange: (text) => {
      if (text === search) return;
      search = text;
      show(month);
    },
  });
  const switcherSlot = h('div');
  const body = h('div');
  const addLink = h('a', { class: 'btn btn-primary btn-block', dataset: { link: '' } }, 'Nuova entrata');
  // Recurring incomes due today or earlier (a salary): the same yellow
  // reminder as on "Nuova spesa", loaded in the background.
  const dueBanner = h('a', { class: 'due-banner', href: '/ricorrenti', dataset: { link: '' }, hidden: true });
  let templates = null; // for «Attese» in the sheet, once loaded
  let drawn = null; // the incomes on screen, drawn again when templates arrive
  function loadDueBanner() {
    api.get('/recurring-incomes').then((loaded) => {
      if (!ctx.isCurrent()) return;
      templates = loaded;
      if (drawn && drawn.month === month && !search) draw(drawn.incomes);
      const due = templates.filter((t) => t.is_active && t.next_due <= todayIso()).length;
      dueBanner.hidden = !due;
      if (!due) return;
      dueBanner.replaceChildren(
        h('span', {}, due === 1 ? '1 ricorrente da registrare' : `${due} ricorrenti da registrare`),
        h('span', { class: 'due-banner-go', 'aria-hidden': 'true' }, 'Vedi ›'));
    }).catch(() => {});
  }
  root.append(
    mainHead('Movimenti', state.me.display_name),
    tabSlot, searchSlot, dueBanner, switcherSlot, body,
    h('div', { class: 'footer-bar' }, addLink));

  function addressOf() {
    const path = withSearch(incomesPath(month), search);
    if (!marked || search) return path;
    return `${path}${path.includes('?') ? '&' : '?'}evidenzia=${encodeURIComponent(marked)}`;
  }

  // quiet, and the month drawn from memory: see show() in movements.js.
  async function show(nextMonth, { quiet = false } = {}) {
    month = nextMonth;
    const mine = ++request;
    history.replaceState(history.state, '', addressOf());
    tabSlot.replaceChildren(movementsSwitch('incomes', month, ctx.navigate));
    switcherSlot.replaceChildren(monthSwitcher(month, show));
    switcherSlot.hidden = Boolean(search); // a search looks at every month
    addLink.href = newIncomePath(month);
    const text = search;
    const current = () => ctx.isCurrent() && mine === request; // a newer request takes over

    if (text) {
      if (!quiet) body.replaceChildren(loadingBlock());
      let found;
      try {
        found = await searchFirstPage('incomes', text);
      } catch (error) {
        if (!quiet && current()) body.replaceChildren(errorBlock(error, () => show(month)));
        return;
      }
      if (!current()) return;
      body.replaceChildren(...(found.totals.count
        ? searchResults(found, {
          dateOf: (income) => income.income_date,
          row: (income) => incomeRow(income, { showDate: true }),
          count: countIncomes,
          sheet: true,
          loadMore: async (offset) => {
            const page = await api.get(
              `/incomes?q=${encodeURIComponent(text)}&limit=${SEARCH_PAGE}&offset=${offset}`);
            return current() ? page : null;
          },
        })
        : [noResults(`Nessuna entrata trovata per «${text}»`,
          'La ricerca guarda categoria, nota e importo (per esempio 1850), in tutti i mesi.')]));
      return;
    }

    const key = `incomes:${month}`;
    const cached = viewCache.get(key);
    if (cached) draw(cached);
    else if (!quiet) body.replaceChildren(loadingBlock());
    let incomes;
    try {
      incomes = await api.get(`/incomes?month=${month}`);
    } catch (error) {
      if (!quiet && !cached && current()) body.replaceChildren(errorBlock(error, () => show(month)));
      return;
    }
    if (!current()) return;
    if (cached && sameData(cached, incomes)) return;
    viewCache.set(key, incomes);
    draw(incomes);
  }

  function draw(incomes) {
    drawn = { month, incomes };
    if (incomes.length === 0) {
      body.replaceChildren(h('div', { class: 'empty' },
        h('p', { class: 'empty-title' }, `Nessuna entrata a ${monthLabel(month)}`),
        h('p', { class: 'empty-text' },
          'Stipendi, rimborsi, regali, vendite: registrali qui e nel Riepilogo vedrai quanto resta ogni mese.'),
        h('p', { class: 'empty-text' },
          'Per lo stipendio di ogni mese puoi creare un’entrata ricorrente: alla scadenza la registri con un tocco.'),
        h('a', { class: 'btn btn-quiet', href: '/ricorrenti/entrate/nuova', dataset: { link: '' } },
          'Nuova entrata ricorrente')));
      return;
    }
    body.replaceChildren(payslip(incomes, {
      month,
      expected: templates ? expectedIn(templates, month) : null,
      marked,
      onUnmark: () => {
        marked = null;
        history.replaceState(history.state, '', addressOf());
        draw(incomes);
      },
    }));
  }

  ctx.onResume(({ longAway }) => {
    if (!longAway) return;
    loadDueBanner();
    show(month, { quiet: true });
  });
  loadDueBanner();
  await show(month);
}
