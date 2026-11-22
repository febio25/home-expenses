// "Movimenti → Entrate": the month's incomes (salaries, refunds, gifts...),
// newest first and grouped by day like the expenses. Same tab as the
// expense list: the switch at the top moves between the two, on the same
// month. "Nuova entrata" sits at the bottom, in reach of the thumb. The
// search box (0.9.0) looks through every month, as for the expenses.

import { api } from '../api.js';
import { state } from '../store.js';
import {
  h, mainHead, formatEuro, monthLabel, dayMonthShort, currentMonth, todayIso, loadingBlock, errorBlock,
} from '../ui.js';
import {
  monthSwitcher, monthFromQuery, movementsSwitch, incomesPath, dayList, vintedLine,
  searchFromQuery, withSearch, searchBox, searchResults, noResults,
} from './movements.js';

const countIncomes = (number) => (number === 1 ? '1 entrata' : `${number} entrate`);

// From the list of a past month, a new income starts in that month.
export function newIncomePath(month) {
  return month === currentMonth() ? '/entrate/nuova' : `/entrate/nuova?mese=${month}`;
}

// Shared with the incomes summary (summary-incomes.js).
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

export async function mount(root, ctx) {
  let month = monthFromQuery(ctx.query);
  let search = searchFromQuery(ctx.query);
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
  function loadDueBanner() {
    api.get('/recurring-incomes').then((templates) => {
      if (!ctx.isCurrent()) return;
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

  // quiet: see the same option in movements.js.
  async function show(nextMonth, { quiet = false } = {}) {
    month = nextMonth;
    const mine = ++request;
    history.replaceState(history.state, '', withSearch(incomesPath(month), search));
    tabSlot.replaceChildren(movementsSwitch('incomes', month, ctx.navigate));
    switcherSlot.replaceChildren(monthSwitcher(month, show));
    switcherSlot.hidden = Boolean(search); // a search looks at every month
    addLink.href = newIncomePath(month);
    if (!quiet) body.replaceChildren(loadingBlock());
    const text = search;
    let incomes;
    try {
      incomes = await api.get(text ? `/incomes?q=${encodeURIComponent(text)}` : `/incomes?month=${month}`);
    } catch (error) {
      if (!quiet && ctx.isCurrent() && mine === request) body.replaceChildren(errorBlock(error, () => show(month)));
      return;
    }
    if (!ctx.isCurrent() || mine !== request) return; // a newer request took over

    if (text) {
      body.replaceChildren(...(incomes.length
        ? searchResults(incomes, {
          dateOf: (income) => income.income_date,
          row: (income) => incomeRow(income, { showDate: true }),
          count: countIncomes,
        })
        : [noResults(`Nessuna entrata trovata per «${text}»`,
          'La ricerca guarda categoria, nota e importo (per esempio 1850), in tutti i mesi.')]));
      return;
    }

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
    body.replaceChildren(...dayList(incomes, {
      dateOf: (income) => income.income_date,
      row: (income) => incomeRow(income),
      count: countIncomes,
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
