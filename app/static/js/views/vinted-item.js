// The screen of a Vinted item (0.8.0): photo, title and status; its purchase
// and its sale, each edited on the expense or income screen it really is;
// the note; withdraw and delete. "Segna come venduto" sits at the bottom.

import { api } from '../api.js';
import {
  h, icon, toast, confirmDialog, promptDialog, choiceDialog, formatEuro, PAYMENT_LABELS,
  loadingBlock, errorBlock,
} from '../ui.js';
import { thumbButton, choosePhotoFor } from '../photo.js';
import { itemPath, dayMonth, sinceLabel, daysBetween, gainSpan, captionOf } from './vinted.js';

function statusText(item) {
  if (item.status === 'sold') return `Venduto il ${dayMonth(item.sale.income_date)}`;
  if (item.status === 'withdrawn') return 'Ritirato dalla vendita';
  return `In vendita ${sinceLabel(daysBetween(item.listed_on))}`;
}

function report(error, prefix) {
  if (error.status === 401) return; // the app is already going to the login screen
  toast(`${prefix}: ${error.network ? 'connessione assente.' : error.message}`, { kind: 'error' });
}

export async function mount(root, ctx) {
  const itemId = Number(ctx.params[0]);
  root.append(loadingBlock());
  let item;
  try {
    item = await api.get(`/vinted/items/${itemId}`);
  } catch (error) {
    if (!ctx.isCurrent()) return;
    if (error.status === 404) {
      toast('Questo articolo non esiste più.', { kind: 'error' });
      ctx.back('/vinted');
    } else {
      root.replaceChildren(errorBlock(error, () => ctx.navigate(location.pathname, { replace: true })));
    }
    return;
  }
  if (!ctx.isCurrent()) return;

  const goBack = () => ctx.back('/vinted');
  const content = h('div');
  const footer = h('div', { class: 'footer-bar' });
  root.replaceChildren(
    h('header', { class: 'page-head' },
      h('a', {
        class: 'page-back', href: '/vinted', 'aria-label': 'Torna agli articoli',
        onclick: (event) => { event.preventDefault(); goBack(); },
      }, '‹'),
      h('h1', { class: 'page-title' }, 'Articolo')),
    content,
    footer);

  async function reload() {
    try {
      item = await api.get(`/vinted/items/${itemId}`);
    } catch (error) {
      if (error.status === 404) goBack();
      return;
    }
    if (ctx.isCurrent()) draw();
  }

  async function run(action, prefix, done = null) {
    try {
      await action();
      if (done) toast(done, { kind: 'success' });
      await reload();
    } catch (error) { report(error, prefix); }
  }

  // --- photo, title, status -------------------------------------------------------
  async function changePhoto() {
    try {
      const updated = await choosePhotoFor(item);
      if (!updated) return;
      item = updated;
      draw();
      toast('Foto salvata.', { kind: 'success' });
    } catch (error) { report(error, 'Foto non salvata'); }
  }

  async function removePhoto() {
    const confirmed = await confirmDialog({
      title: 'Togliere la foto?', message: 'L’articolo resta, senza foto.', confirmLabel: 'Togli', danger: true,
    });
    if (confirmed) run(() => api.del(`/vinted/items/${itemId}/photo`), 'Foto non tolta');
  }

  async function rename() {
    const title = await promptDialog({ title: 'Rinomina articolo', label: 'Titolo', value: item.title });
    if (title === null || title === item.title) return;
    run(() => api.patch(`/vinted/items/${itemId}`, { title }), 'Non rinominato');
  }

  function hero() {
    const photo = item.photo
      ? thumbButton(item, { large: true, caption: captionOf(item) })
      : h('button', { class: 'thumb thumb-large is-empty', type: 'button', 'aria-label': 'Aggiungi foto', onclick: changePhoto },
        icon('camera'), h('span', { class: 'thumb-add' }, 'Aggiungi foto'));
    return h('div', { class: 'art-hero' },
      photo,
      h('div', { class: 'art-hero-main' },
        h('h2', { class: 'art-hero-title' }, item.title),
        h('span', { class: `status${item.status === 'listed' ? '' : ` is-${item.status}`}` }, statusText(item)),
        h('div', { class: 'art-hero-actions' },
          h('button', { class: 'btn-text', type: 'button', onclick: rename }, 'Rinomina'),
          item.photo ? h('button', { class: 'btn-text', type: 'button', onclick: changePhoto }, 'Cambia foto') : null,
          item.photo ? h('button', { class: 'btn-text', type: 'button', onclick: removePhoto }, 'Togli foto') : null)));
  }

  // --- purchase ------------------------------------------------------------------------
  async function linkPurchase() {
    let waiting;
    try {
      waiting = await api.get('/vinted/unlinked-expenses');
    } catch (error) { report(error, 'Elenco non disponibile'); return; }
    const id = await choiceDialog({
      title: 'Collega una spesa',
      text: 'Spese della categoria Vinted non ancora collegate a un articolo.',
      empty: 'Nessuna spesa Vinted da collegare: registrala da Nuova spesa, nella categoria Vinted.',
      options: waiting.map((expense) => ({
        value: expense.id,
        label: expense.merchant_name || 'Senza esercente',
        meta: [dayMonth(expense.expense_date), expense.paid_by_name, expense.note].filter(Boolean).join(' · '),
        amount: formatEuro(expense.amount_cents),
      })),
    });
    if (id !== null) run(() => api.post(`/vinted/items/${itemId}/purchase`, { expense_id: id }), 'Non collegata', 'Acquisto collegato.');
  }

  function purchaseCard() {
    if (!item.purchase) {
      return h('div', { class: 'card info' },
        h('span', { class: 'info-main' },
          h('span', { class: 'info-text' }, 'Era già nostro'),
          h('span', { class: 'info-meta' }, 'Nessun acquisto: tutto il prezzo di vendita è guadagno.')),
        h('button', { class: 'btn-text', type: 'button', onclick: linkPurchase }, 'Collega una spesa'));
    }
    const purchase = item.purchase;
    const where = purchase.merchant_name ? ` · ${purchase.merchant_name}` : '';
    return h('div', { class: 'card info' },
      h('span', { class: 'info-main' },
        h('span', { class: 'info-figure' }, formatEuro(purchase.amount_cents)),
        h('span', { class: 'info-meta' },
          `${dayMonth(purchase.expense_date)} · pagato da ${purchase.paid_by_name} con ${PAYMENT_LABELS[purchase.payment_method]}${where}`)),
      h('a', { class: 'btn-text', href: `/spesa/${purchase.expense_id}`, dataset: { link: '' } }, 'Modifica'));
  }

  // --- sale ------------------------------------------------------------------------------
  async function cancelSale() {
    const confirmed = await confirmDialog({
      title: 'Annullare la vendita?',
      message: `L’entrata di ${formatEuro(item.sale.amount_cents)} del ${dayMonth(item.sale.income_date)} viene eliminata e l’articolo torna in vendita. Utile per un reso.`,
      confirmLabel: 'Annulla vendita',
      danger: true,
    });
    if (confirmed) run(() => api.del(`/vinted/items/${itemId}/sale`), 'Vendita non annullata', 'Vendita annullata.');
  }

  function saleCard() {
    if (!item.sale) {
      return h('div', { class: 'card info' },
        h('span', { class: 'info-main' },
          h('span', { class: 'info-text' }, 'Non ancora venduto'),
          h('span', { class: 'info-meta' }, 'Quando si vende, tocca «Segna come venduto»: il guadagno si calcola da solo.')));
    }
    const sale = item.sale;
    return h('div', { class: 'card' },
      h('div', { class: 'info' },
        h('span', { class: 'info-main' },
          h('span', { class: 'info-figure' }, formatEuro(sale.amount_cents)),
          h('span', { class: 'info-meta' }, `${dayMonth(sale.income_date)} · incassa ${sale.received_by_name}`)),
        h('a', { class: 'btn-text', href: `/entrate/${sale.income_id}`, dataset: { link: '' } }, 'Modifica')),
      h('div', { class: 'info info-split' },
        h('span', { class: 'info-main' },
          h('span', { class: 'info-text' }, 'Guadagno'),
          h('span', { class: 'info-meta' }, item.purchase
            ? `Venduto a ${formatEuro(sale.amount_cents)}, pagato ${formatEuro(item.purchase.amount_cents)}`
            : 'Era già nostro: tutto il prezzo')),
        h('span', { class: 'info-gain' }, gainSpan(item.gain_cents))),
      h('div', { class: 'info info-split' },
        h('button', { class: 'btn-text btn-text-danger', type: 'button', onclick: cancelSale }, 'Annulla vendita')));
  }

  // --- note, withdraw, delete ---------------------------------------------------------------
  async function editNote() {
    const note = await promptDialog({ title: 'Nota', label: 'Nota', value: item.note || '', minLength: 0 });
    if (note === null || note === (item.note || '')) return;
    run(() => api.patch(`/vinted/items/${itemId}`, { note: note || null }), 'Nota non salvata');
  }

  async function remove() {
    const parts = [`l’articolo «${item.title}»`];
    if (item.purchase) parts.push(`la spesa di ${formatEuro(item.purchase.amount_cents)} del ${dayMonth(item.purchase.expense_date)}`);
    if (item.sale) parts.push(`l’entrata di ${formatEuro(item.sale.amount_cents)} del ${dayMonth(item.sale.income_date)}`);
    const list = parts.length > 1 ? `${parts.slice(0, -1).join(', ')} e ${parts[parts.length - 1]}` : parts[0];
    const confirmed = await confirmDialog({
      title: 'Eliminare l’articolo?',
      message: `Vengono eliminati ${list}. L’eliminazione è definitiva.`,
      confirmLabel: 'Elimina',
      danger: true,
    });
    if (!confirmed) return;
    try {
      await api.del(`/vinted/items/${itemId}`);
      toast('Articolo eliminato.');
      goBack();
    } catch (error) { report(error, 'Non eliminato'); }
  }

  function draw() {
    const withdraw = item.status === 'sold' ? null : h('button', {
      class: 'btn btn-quiet', type: 'button',
      onclick: () => run(() => api.patch(`/vinted/items/${itemId}`, { is_withdrawn: item.status !== 'withdrawn' }),
        'Non modificato'),
    }, item.status === 'withdrawn' ? 'Rimetti in vendita' : 'Ritira dalla vendita');
    content.replaceChildren(
      hero(),
      h('h2', { class: 'section-title' }, 'Acquisto'), purchaseCard(),
      h('h2', { class: 'section-title' }, 'Vendita'), saleCard(),
      h('h2', { class: 'section-title' }, 'Nota'),
      h('div', { class: 'card info' },
        h('span', { class: 'info-main' }, item.note
          ? h('span', { class: 'info-note' }, item.note)
          : h('span', { class: 'info-meta' }, 'Nessuna nota')),
        h('button', { class: 'btn-text', type: 'button', onclick: editNote }, item.note ? 'Modifica' : 'Aggiungi')),
      h('div', { class: 'actions-row' },
        withdraw,
        h('button', { class: 'btn btn-danger-quiet', type: 'button', onclick: remove }, 'Elimina')));
    footer.hidden = item.status === 'sold';
    footer.replaceChildren(h('a', {
      class: 'btn btn-primary btn-block btn-save', href: `${itemPath(itemId)}/venduto`, dataset: { link: '' },
    }, 'Segna come venduto'));
  }

  ctx.onResume(({ longAway }) => { if (longAway) reload(); });
  draw();
}
