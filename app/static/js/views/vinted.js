// "Vinted" (0.8.0): the items bought to resell or sold from home. Two views
// under one tab, like "Spese | Entrate" in Movimenti: the items (here) and
// the month summary (vinted-summary.js). The money of an item is an expense
// and an income of the Vinted categories; see app/routers/vinted.py.
//
// Each row starts with the photo, as in Vinted's own lists: a tap on the
// photo opens it full size, a tap on the rest opens the item.

import { api } from '../api.js';
import { state } from '../store.js';
import {
  h, icon, mainHead, formatEuro, formatSignedEuro, monthLabel, todayIso, loadingBlock, errorBlock,
} from '../ui.js';
import { thumbButton, thumbPlaceholder } from '../photo.js';

const FILTERS = [
  { id: 'listed', query: null, label: 'In vendita' },
  { id: 'sold', query: 'venduti', label: 'Venduti' },
  { id: 'all', query: 'tutti', label: 'Tutti' },
];

export function itemPath(id) {
  return `/vinted/articolo/${id}`;
}

// Title, who is signed in, settings, and the switch between the two views.
export function vintedHead(active, navigate) {
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
    mainHead('Vinted', state.me.display_name),
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

// "da oggi", "da ieri", "da 12 giorni": how long an item has been listed.
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
    h('span', { class: 'art-meta' }, item.status === 'withdrawn'
      ? 'Ritirato dalla vendita'
      : `In vendita ${sinceLabel(daysBetween(item.listed_on))}`),
  ];
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
  return item.status === 'withdrawn'
    ? `${price} · ritirato dalla vendita`
    : `${price} · in vendita ${sinceLabel(daysBetween(item.listed_on))}`;
}

function normalize(text) {
  return text.trim().replace(/\s+/g, ' ').toLocaleLowerCase('it-IT');
}

// "In vendita": how many, what they cost, how long the oldest has waited.
function listedHead(items) {
  const paid = items.reduce((total, item) => total + (item.purchase ? item.purchase.amount_cents : 0), 0);
  const oldest = items.reduce((first, item) => (item.listed_on < first ? item.listed_on : first), todayIso());
  return h('div', { class: 'list-head' },
    h('p', { class: 'day-head' },
      h('span', {}, items.length === 1 ? '1 articolo in vendita' : `${items.length} articoli in vendita`),
      h('span', { class: 'day-total' }, `${formatEuro(paid)} pagati`)),
    h('span', { class: 'list-head-note' }, items.length === 1
      ? `In vendita ${sinceLabel(daysBetween(oldest))}`
      : `Il più vecchio è in vendita ${sinceLabel(daysBetween(oldest))}`));
}

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
  const pills = h('div', { class: 'pills', role: 'group', 'aria-label': 'Quali articoli' });
  const body = h('div');
  root.append(
    ...vintedHead('items', ctx.navigate),
    h('div', { class: 'search' }, icon('search'),
      h('label', { class: 'visually-hidden', for: 'vinted-search' }, 'Cerca un articolo'), searchInput),
    pills,
    body,
    h('div', { class: 'footer-bar' },
      h('a', { class: 'btn btn-primary btn-block btn-save', href: '/vinted/nuovo', dataset: { link: '' } },
        'Nuovo articolo')));

  function setFilter(id) {
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
    pills.replaceChildren(...FILTERS.map((item) => h('button', {
      class: `pill${item.id === filter ? ' is-selected' : ''}`,
      type: 'button',
      'aria-pressed': String(item.id === filter),
      onclick: () => setFilter(item.id),
    }, item.label, item.id === 'all' ? null : h('span', { class: 'pill-count' }, String(count(item.id))))));

    if (!items.length) {
      body.replaceChildren(emptyAll());
      return;
    }
    const visible = items.filter((item) => (filter === 'all' || item.status === filter)
      && (!search || normalize(item.title).includes(search)));
    if (!visible.length) {
      const title = search ? 'Nessun articolo trovato'
        : filter === 'sold' ? 'Ancora nessun articolo venduto' : 'Nessun articolo in vendita';
      body.replaceChildren(h('div', { class: 'empty' }, h('p', { class: 'empty-title' }, title)));
      return;
    }
    if (filter === 'listed') body.replaceChildren(listedHead(visible), h('div', { class: 'card rows' }, visible.map(itemRow)));
    else if (filter === 'sold') body.replaceChildren(...soldGroups(visible));
    else body.replaceChildren(h('div', { class: 'card rows list-card' }, visible.map(itemRow)));
  }

  async function load({ quiet = false } = {}) {
    if (!quiet) body.replaceChildren(loadingBlock());
    try {
      items = await api.get('/vinted/items');
    } catch (error) {
      if (!quiet && ctx.isCurrent()) body.replaceChildren(errorBlock(error, () => load()));
      return;
    }
    if (ctx.isCurrent()) draw();
  }

  ctx.onResume(({ longAway }) => { if (longAway) load({ quiet: true }); });
  await load();
}
