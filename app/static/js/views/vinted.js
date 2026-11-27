// "Vinted" (0.8.0): the items bought to resell or sold from home. Two views
// under one tab, like "Spese | Entrate" in Movimenti: the items (here) and
// the month summary (vinted-summary.js). The money of an item is an expense
// and an income of the Vinted categories; see app/routers/vinted.py.
//
// Each row starts with the photo, as in Vinted's own lists: a tap on the
// photo opens it full size, a tap on the rest opens the item.
//
// 0.10.0: four filters drawn as icons with a count (as text they did not fit
// a 360 px phone): not on Vinted yet (where the tab opens), on sale, sold,
// all. The heading under them always says in words what is shown. A search
// looks through every item, whatever the filter.

import { api } from '../api.js';
import { viewCache, sameData } from '../cache.js';
import { state } from '../store.js';
import {
  h, icon, mainHead, formatEuro, formatSignedEuro, monthLabel, todayIso, loadingBlock, errorBlock,
} from '../ui.js';
import { thumbButton, thumbPlaceholder } from '../photo.js';

const FILTERS = [
  { id: 'unlisted', query: null, label: 'Da pubblicare', icon: 'hourglass' },
  { id: 'listed', query: 'in-vendita', label: 'In vendita', icon: 'store' },
  { id: 'sold', query: 'venduti', label: 'Venduti', icon: 'coin-euro' },
  { id: 'all', query: 'tutti', label: 'Tutti', icon: 'stack' },
];

// The filter to show the next time the list opens, once: after "Nuovo
// articolo" the list opens where the new item is.
let nextFilter = null;
export function showFilterNext(status) {
  nextFilter = FILTERS.some((item) => item.id === status) ? status : null;
}

export function itemPath(id) {
  return `/vinted/articolo/${id}`;
}

// Title, who is signed in, settings, and the switch between the two views.
export function vintedHead(active, navigate, tool = null) {
  const link = (id, label, path) => h('a', {
    class: `seg-item${id === active ? ' is-selected' : ''}`,
    href: path,
    'aria-current': id === active ? 'page' : null,
    onclick: (event) => {
      event.preventDefault();
      if (id !== active) navigate(path, { replace: true }); // like a tab: back does not bounce
    },
  }, label);
  return [
    mainHead('Vinted', state.me.display_name, tool),
    h('nav', { class: 'seg seg-links', 'aria-label': 'Articoli o riepilogo' },
      link('items', 'Articoli', '/vinted'),
      link('summary', 'Riepilogo', '/vinted/riepilogo')),
  ];
}

// Whole days between two local dates.
export function daysBetween(fromIso, toIso = todayIso()) {
  const [y1, m1, d1] = fromIso.split('-').map(Number);
  const [y2, m2, d2] = toIso.split('-').map(Number);
  return Math.max(0, Math.round((Date.UTC(y2, m2 - 1, d2) - Date.UTC(y1, m1 - 1, d1)) / 86400000));
}

// The day an item not on Vinted yet started waiting: its purchase, or the
// day it was added (created_at is UTC: read it as a local day).
export function waitingSince(item) {
  if (item.purchase) return item.purchase.expense_date;
  const added = new Date(item.created_at);
  const pad = (number) => String(number).padStart(2, '0');
  return `${added.getFullYear()}-${pad(added.getMonth() + 1)}-${pad(added.getDate())}`;
}

// "da oggi", "da ieri", "da 12 giorni": how long an item has been waiting.
export function sinceLabel(days) {
  if (days === 0) return 'da oggi';
  if (days === 1) return 'da ieri';
  return `da ${days} giorni`;
}

// "18 novembre", with the year when it is not this one.
export function dayMonth(iso) {
  const [year, month, day] = iso.split('-').map(Number);
  const sameYear = iso.slice(0, 4) === todayIso().slice(0, 4);
  return new Date(year, month - 1, day).toLocaleDateString('it-IT',
    sameYear ? { day: 'numeric', month: 'long' } : { day: 'numeric', month: 'long', year: 'numeric' });
}

export function gainSpan(cents) {
  return h('span', { class: cents >= 0 ? 'gain' : 'loss' }, formatSignedEuro(cents));
}

// The two lines under the title: price, then status or date.
export function itemLines(item) {
  if (item.status === 'sold') {
    const price = `Venduto a ${formatEuro(item.sale.amount_cents)}`;
    if (item.purchase) {
      return [
        h('span', { class: 'art-price' }, `${price} · `, gainSpan(item.gain_cents)),
        h('span', { class: 'art-meta' },
          `Pagato ${formatEuro(item.purchase.amount_cents)} · ${dayMonth(item.sale.income_date)}`),
      ];
    }
    return [
      h('span', { class: 'art-price' }, price),
      h('span', { class: 'art-meta' }, `Già nostro · ${dayMonth(item.sale.income_date)}`),
    ];
  }
  return [
    h('span', { class: 'art-price' }, item.purchase ? `Pagato ${formatEuro(item.purchase.amount_cents)}` : 'Già nostro'),
    h('span', { class: 'art-meta' }, waitingText(item)),
  ];
}

// Status of an item not sold: where it is and since when.
function waitingText(item) {
  if (item.status === 'withdrawn') return 'Ritirato dalla vendita';
  if (item.status === 'unlisted') return `Da pubblicare ${sinceLabel(daysBetween(waitingSince(item)))}`;
  return `In vendita ${sinceLabel(daysBetween(item.listed_on))}`;
}

export function itemRow(item) {
  const link = h('a', { class: 'art-link', href: itemPath(item.id), dataset: { link: '' } },
    item.photo ? null : thumbPlaceholder(item),
    h('span', { class: 'art-main' }, h('span', { class: 'art-title' }, item.title), ...itemLines(item)),
    h('span', { class: 'bar-go', 'aria-hidden': 'true' }, '›'));
  return h('div', { class: 'art-row' }, item.photo ? thumbButton(item, { caption: captionOf(item) }) : null, link);
}

// Under the full-size photo: what the item cost or made.
export function captionOf(item) {
  if (item.status === 'sold') return `Venduto a ${formatEuro(item.sale.amount_cents)} · ${dayMonth(item.sale.income_date)}`;
  const price = item.purchase ? `Pagato ${formatEuro(item.purchase.amount_cents)}` : 'Già nostro';
  return `${price} · ${waitingText(item).toLocaleLowerCase('it-IT')}`;
}

function normalize(text) {
  return text.trim().replace(/\s+/g, ' ').toLocaleLowerCase('it-IT');
}

// The heading of a list: what it is, in words, with a figure on the right
// and a line under it.
function listHead(title, figure, note) {
  return h('div', { class: 'list-head' },
    h('p', { class: 'day-head' }, h('span', {}, title), figure ? h('span', { class: 'day-total' }, figure) : null),
    note ? h('span', { class: 'list-head-note' }, note) : null);
}

function paidOf(items) {
  return items.reduce((total, item) => total + (item.purchase ? item.purchase.amount_cents : 0), 0);
}

// "Da pubblicare": how many, what they cost, how long the oldest has waited.
function unlistedHead(items) {
  const oldest = items.reduce((first, item) => {
    const since = waitingSince(item);
    return since < first ? since : first;
  }, todayIso());
  const waited = sinceLabel(daysBetween(oldest));
  return listHead(
    items.length === 1 ? '1 da pubblicare' : `${items.length} da pubblicare`,
    `${formatEuro(paidOf(items))} pagati`,
    items.length === 1 ? `Aspetta ${waited}` : `Il più vecchio aspetta ${waited}`);
}

// "In vendita": how many, what they cost, how long the oldest has waited.
function listedHead(items) {
  const oldest = items.reduce((first, item) => (item.listed_on < first ? item.listed_on : first), todayIso());
  return listHead(
    items.length === 1 ? '1 articolo in vendita' : `${items.length} articoli in vendita`,
    `${formatEuro(paidOf(items))} pagati`,
    items.length === 1
      ? `In vendita ${sinceLabel(daysBetween(oldest))}`
      : `Il più vecchio è in vendita ${sinceLabel(daysBetween(oldest))}`);
}

const countLabel = (count) => (count === 1 ? '1 articolo' : `${count} articoli`);

// "Venduti": by month of sale, newest first, with the gain of the month.
function soldGroups(items) {
  const groups = new Map();
  for (const item of items) {
    const month = item.sale.income_date.slice(0, 7);
    if (!groups.has(month)) groups.set(month, []);
    groups.get(month).push(item);
  }
  return Array.from(groups, ([month, monthItems]) => {
    const gain = monthItems.reduce((total, item) => total + item.gain_cents, 0);
    const cashed = monthItems.reduce((total, item) => total + item.sale.amount_cents, 0);
    const count = monthItems.length === 1 ? '1 venduto' : `${monthItems.length} venduti`;
    return h('section', {},
      h('div', { class: 'list-head' },
        h('h2', { class: 'day-head' },
          h('span', {}, monthLabel(month)),
          h('span', { class: 'day-total' }, 'guadagno ', gainSpan(gain))),
        h('span', { class: 'list-head-note' }, `${count} · incassati ${formatEuro(cashed)}`)),
      h('div', { class: 'card rows' }, monthItems.map(itemRow)));
  });
}

export async function mount(root, ctx) {
  let filter = (FILTERS.find((item) => item.query === ctx.query.get('filtro')) || FILTERS[0]).id;
  // 0.14.0: opening the tab, the list starts from the first filter with
  // items ("Da pubblicare", else "In vendita", else all of them). A filter
  // chosen with a tap, or in the address, stays.
  let chosen = ctx.query.has('filtro');
  if (nextFilter) {
    chosen = true;
    filter = nextFilter;
    nextFilter = null;
    const query = FILTERS.find((item) => item.id === filter).query;
    history.replaceState(history.state, '', query ? `/vinted?filtro=${query}` : '/vinted');
  }
  let search = '';
  let items = [];
  const searchInput = h('input', {
    class: 'input', id: 'vinted-search', type: 'text', inputmode: 'search', enterkeyhint: 'search',
    autocomplete: 'off', placeholder: 'Cerca un articolo',
    oninput: () => { search = normalize(searchInput.value); draw(); },
    onkeydown: (event) => {
      if (event.key === 'Enter') { event.preventDefault(); searchInput.blur(); }
    },
  });
  searchInput.setAttribute('autocorrect', 'off');
  const pills = h('div', { class: 'pills pills-icons', role: 'group', 'aria-label': 'Quali articoli' });
  // 0.18.1: the search box only when needed. The lens in the head of the
  // page, beside the name, opens it under the tabs with the cursor inside;
  // the lens again, or the ×, empties it and closes it. The filters keep
  // their row to themselves, even at 320 px.
  function closeSearch() {
    searchInput.value = '';
    search = '';
    searchBar.hidden = true;
    lens.classList.remove('is-open');
    lens.setAttribute('aria-expanded', 'false');
    draw();
  }
  const searchBar = h('div', { class: 'search search-movements has-text vinted-search', hidden: true }, icon('search'),
    h('label', { class: 'visually-hidden', for: 'vinted-search' }, 'Cerca un articolo'), searchInput,
    h('button', {
      class: 'search-clear', type: 'button', 'aria-label': 'Chiudi la ricerca',
      onclick: () => { closeSearch(); lens.focus(); },
    }, icon('close')));
  const lens = h('button', {
    class: 'page-gear vinted-lens', type: 'button', 'aria-label': 'Cerca un articolo',
    'aria-controls': 'vinted-search', 'aria-expanded': 'false',
    onclick: () => {
      if (!searchBar.hidden) { closeSearch(); return; }
      searchBar.hidden = false;
      lens.classList.add('is-open');
      lens.setAttribute('aria-expanded', 'true');
      searchInput.focus();
    },
  }, icon('search'));
  const body = h('div');
  root.append(
    ...vintedHead('items', ctx.navigate, lens),
    searchBar,
    pills,
    body,
    h('div', { class: 'footer-bar' },
      h('a', { class: 'btn btn-primary btn-block btn-save', href: '/vinted/nuovo', dataset: { link: '' } },
        'Nuovo articolo')));

  function setFilter(id) {
    chosen = true;
    filter = id;
    const query = FILTERS.find((item) => item.id === id).query;
    history.replaceState(history.state, '', query ? `/vinted?filtro=${query}` : '/vinted');
    draw();
  }

  function emptyAll() {
    const hint = h('p', { class: 'empty-text', hidden: true });
    // After the update, the purchases already recorded in the Vinted
    // category wait for their item: say how to link them.
    api.get('/vinted/unlinked-expenses').then((waiting) => {
      if (!waiting.length || !ctx.isCurrent()) return;
      const what = waiting.length === 1
        ? '1 spesa Vinted già registrata non ha ancora'
        : `${waiting.length} spese Vinted già registrate non hanno ancora`;
      hint.textContent = `${what} un articolo: in «Nuovo articolo» tocca «Scegli una spesa già registrata».`;
      hint.hidden = false;
    }).catch(() => {});
    return h('div', { class: 'empty' },
      h('p', { class: 'empty-title' }, 'Nessun articolo'),
      h('p', { class: 'empty-text' },
        'Aggiungi gli articoli che compri per rivenderli e le cose di casa che metti in vendita: qui vedrai quanto le hai pagate, a quanto le vendi e quanto ci guadagni.'),
      hint);
  }

  function draw() {
    const count = (status) => items.filter((item) => item.status === status).length;
    pills.replaceChildren(...FILTERS.map((item) => {
      const number = item.id === 'all' ? null : count(item.id);
      return h('button', {
        class: `pill${item.id === filter ? ' is-selected' : ''}`,
        type: 'button',
        title: item.label,
        'aria-label': number === null ? item.label : `${item.label}: ${number}`,
        'aria-pressed': String(item.id === filter),
        onclick: () => setFilter(item.id),
      }, icon(item.icon), number === null ? null : h('span', { class: 'pill-count' }, String(number)));
    }));

    if (!items.length) {
      body.replaceChildren(emptyAll());
      return;
    }
    // A search looks everywhere: a sold or withdrawn item is found too.
    if (search) {
      const found = items.filter((item) => normalize(item.title).includes(search));
      body.replaceChildren(found.length
        ? h('div', {},
          listHead(found.length === 1 ? '1 articolo trovato' : `${found.length} articoli trovati`, null,
            'In tutti gli articoli, venduti e ritirati compresi'),
          h('div', { class: 'card rows' }, found.map(itemRow)))
        : h('div', { class: 'empty' },
          h('p', { class: 'empty-title' }, 'Nessun articolo trovato'),
          h('p', { class: 'empty-text' }, 'La ricerca guarda il titolo di tutti gli articoli.')));
      return;
    }
    const visible = filter === 'all' ? items : items.filter((item) => item.status === filter);
    if (!visible.length) {
      body.replaceChildren(emptyFilter());
      return;
    }
    if (filter === 'unlisted') body.replaceChildren(unlistedHead(visible), h('div', { class: 'card rows' }, visible.map(itemRow)));
    else if (filter === 'listed') body.replaceChildren(listedHead(visible), h('div', { class: 'card rows' }, visible.map(itemRow)));
    else if (filter === 'sold') body.replaceChildren(...soldGroups(visible));
    else {
      body.replaceChildren(
        listHead('Tutti gli articoli', countLabel(visible.length), null),
        h('div', { class: 'card rows' }, visible.map(itemRow)));
    }
  }

  // An empty filter, with the items still elsewhere: say what goes here.
  function emptyFilter() {
    const [title, text] = {
      unlisted: ['Niente da pubblicare',
        'Gli articoli nuovi arrivano qui finché non li segni come pubblicati su Vinted.'],
      listed: ['Nessun articolo in vendita',
        'Quando pubblichi un articolo su Vinted, segnalo nella sua scheda: comparirà qui.'],
      sold: ['Ancora nessun articolo venduto', null],
    }[filter];
    return h('div', { class: 'empty' },
      h('p', { class: 'empty-title' }, title),
      text ? h('p', { class: 'empty-text' }, text) : null);
  }

  function startingFilter() {
    if (chosen) return;
    const has = (status) => items.some((item) => item.status === status);
    filter = has('unlisted') ? 'unlisted' : has('listed') ? 'listed' : 'all';
  }

  // The list seen before in this session is drawn at once from memory
  // (cache.js, 0.14.0), then refreshed quietly.
  async function load({ quiet = false } = {}) {
    const cached = viewCache.get('vinted:items');
    if (cached) {
      items = cached;
      startingFilter();
      draw();
    } else if (!quiet) body.replaceChildren(loadingBlock());
    let fresh;
    try {
      fresh = await api.get('/vinted/items');
    } catch (error) {
      if (!quiet && !cached && ctx.isCurrent()) body.replaceChildren(errorBlock(error, () => load()));
      return;
    }
    if (!ctx.isCurrent() || (cached && sameData(cached, fresh))) return;
    viewCache.set('vinted:items', fresh);
    items = fresh;
    startingFilter();
    draw();
  }

  ctx.onResume(({ longAway }) => { if (longAway) load({ quiet: true }); });
  await load();
}
