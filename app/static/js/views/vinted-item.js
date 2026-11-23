// The screen of a Vinted item (0.8.0): photo, title and status; its purchase
// and its sale, each edited on the expense or income screen it really is;
// the note; withdraw and delete. "Segna come venduto" sits at the bottom.
//
// 0.10.0: the day it went on Vinted ("Su Vinted"). An item not on Vinted yet
// has "Segna come pubblicato" at the bottom instead (one tap: today), and
// "Segna come venduto" in its sale card. The "Annuncio" card holds the ad
// written with Claude: share the request, paste the answer, copy the text
// for Vinted, change the asking price (vinted-listing.js).

import { api } from '../api.js';
import {
  h, icon, toast, vibrate, confirmDialog, promptDialog, choiceDialog, openDialog, formatEuro, PAYMENT_LABELS,
  todayIso, loadingBlock, errorBlock,
} from '../ui.js';
import { thumbButton, choosePhotoFor } from '../photo.js';
import { itemPath, dayMonth, sinceLabel, daysBetween, gainSpan, captionOf, waitingSince } from './vinted.js';
import {
  shareWithClaude, copyRequest, savePhoto, readAnswer, keepAnswer, copyText, detailsSummary, priceInput,
} from '../vinted-listing.js';

function statusText(item) {
  if (item.status === 'sold') return `Venduto il ${dayMonth(item.sale.income_date)}`;
  if (item.status === 'withdrawn') return 'Ritirato dalla vendita';
  if (item.status === 'unlisted') return 'Da pubblicare';
  return `In vendita ${sinceLabel(daysBetween(item.listed_on))}`;
}

function daysWord(days) {
  return days === 1 ? '1 giorno' : `${days} giorni`;
}

// A new asking price for an item on Vinted. Resolves to the text typed, or null.
function priceDialog(item) {
  return openDialog((finish) => {
    const field = priceInput('dialog-field', item.listing.price_cents);
    setTimeout(() => { field.focus(); field.select(); }, 50);
    return h('form', {
      class: 'dialog-body',
      onsubmit: (event) => { event.preventDefault(); if (field.value.trim()) finish(field.value.trim()); },
    },
      h('h2', { class: 'dialog-title' }, 'Nuovo prezzo su Vinted'),
      h('label', { class: 'label', for: 'dialog-field' }, 'Prezzo'),
      field,
      item.listing.min_price_cents
        ? h('p', { class: 'form-hint' }, `Il minimo è ${formatEuro(item.listing.min_price_cents)}.`)
        : null,
      h('div', { class: 'dialog-actions' },
        h('button', { class: 'btn btn-quiet', type: 'button', onclick: () => finish(null) }, 'Annulla'),
        h('button', { class: 'btn btn-primary', type: 'submit' }, 'Salva')));
  });
}

// The day an item went on Vinted: between its purchase (or 2000) and today
// (or its sale). Resolves to { day } with a date, { day: null } to take it
// back to "not published", or null when cancelled.
function listingDayDialog(item) {
  const min = item.purchase ? item.purchase.expense_date : '2000-01-01';
  const today = todayIso();
  const max = item.sale && item.sale.income_date < today ? item.sale.income_date : today;
  return openDialog((finish) => {
    const field = h('input', {
      class: 'input', id: 'dialog-field', type: 'date', required: true, min, max,
      value: item.listed_on || max,
    });
    const error = h('p', { class: 'field-error', hidden: true });
    const clearLabel = item.status === 'sold' ? 'Venduto senza pubblicarlo' : 'Non ancora pubblicato';
    return h('form', {
      class: 'dialog-body',
      onsubmit: (event) => {
        event.preventDefault();
        const day = field.value;
        if (!day) return;
        if (day < min || day > max) {
          error.textContent = day < min
            ? `Non prima dell’acquisto (${dayMonth(min)}).`
            : `Non dopo il ${dayMonth(max)}.`;
          error.hidden = false;
          return;
        }
        finish({ day });
      },
    },
      h('h2', { class: 'dialog-title' }, 'Pubblicato su Vinted'),
      h('label', { class: 'label', for: 'dialog-field' }, 'Il giorno'),
      field, error,
      item.listed_on ? h('button', {
        class: 'btn-text btn-text-start', type: 'button', onclick: () => finish({ day: null }),
      }, clearLabel) : null,
      h('div', { class: 'dialog-actions' },
        h('button', { class: 'btn btn-quiet', type: 'button', onclick: () => finish(null) }, 'Annulla'),
        h('button', { class: 'btn btn-primary', type: 'submit' }, 'Salva')));
  });
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

  // --- on Vinted ------------------------------------------------------------------------
  async function setListingDay(day, { undo = null } = {}) {
    try {
      item = await api.patch(`/vinted/items/${itemId}`, { listed_on: day });
    } catch (error) {
      report(error, 'Data non salvata');
      return false;
    }
    if (ctx.isCurrent()) draw();
    if (undo) toast(undo.message, { kind: 'success', action: { label: 'Annulla', run: undo.run } });
    return true;
  }

  let publishing = false; // a double tap records the day once
  async function publishToday() {
    if (publishing) return;
    publishing = true;
    const done = await setListingDay(todayIso(), {
      undo: { message: 'Pubblicato oggi.', run: () => setListingDay(null) },
    });
    publishing = false;
    if (done) vibrate();
  }

  async function editListingDay() {
    const answer = await listingDayDialog(item);
    if (answer === null || answer.day === item.listed_on) return;
    const was = item.listed_on;
    setListingDay(answer.day, answer.day === null
      ? { undo: { message: item.status === 'sold' ? 'Data di pubblicazione tolta.' : 'Di nuovo da pubblicare.', run: () => setListingDay(was) } }
      : {});
  }

  function vintedCard() {
    if (!item.listed_on) {
      const [text, meta] = {
        unlisted: ['Non ancora pubblicato', `Aspetta ${sinceLabel(daysBetween(waitingSince(item)))}. Quando è online, tocca «Segna come pubblicato».`],
        sold: ['Venduto senza pubblicarlo', 'Nessun giorno in vendita.'],
        withdrawn: ['Mai pubblicato', null],
      }[item.status];
      return h('div', { class: 'card info' },
        h('span', { class: 'info-main' },
          h('span', { class: 'info-text' }, text),
          meta ? h('span', { class: 'info-meta' }, meta) : null),
        item.status === 'unlisted' ? null
          : h('button', { class: 'btn-text', type: 'button', onclick: editListingDay }, 'Imposta data'));
    }
    let meta = null;
    if (item.status === 'listed') meta = `In vendita ${sinceLabel(daysBetween(item.listed_on))}`;
    else if (item.status === 'sold') meta = `Venduto dopo ${daysWord(daysBetween(item.listed_on, item.sale.income_date))}`;
    return h('div', { class: 'card info' },
      h('span', { class: 'info-main' },
        h('span', { class: 'info-text' }, `Dal ${dayMonth(item.listed_on)}`),
        meta ? h('span', { class: 'info-meta' }, meta) : null),
      h('button', { class: 'btn-text', type: 'button', onclick: editListingDay }, 'Modifica'));
  }

  // --- listing --------------------------------------------------------------------------
  async function pasteAnswer() {
    const answer = await readAnswer();
    if (!answer || !ctx.isCurrent()) return;
    keepAnswer(answer); // the listing screen opens filled in, to check and save
    ctx.navigate(`${itemPath(itemId)}/annuncio`);
  }

  async function changePrice() {
    const value = await priceDialog(item);
    if (value === null) return;
    try {
      item = await api.patch(`/vinted/items/${itemId}`, { price: value });
    } catch (error) { report(error, 'Prezzo non salvato'); return; }
    if (!ctx.isCurrent()) return;
    draw();
    toast(`Nuovo prezzo: ${formatEuro(item.listing.price_cents)}.`, { kind: 'success' });
  }

  function listingCard() {
    const listing = item.listing;
    const active = item.status === 'unlisted' || item.status === 'listed';
    const textButton = (label, onclick) => h('button', { class: 'btn-text', type: 'button', onclick }, label);
    const rows = [];
    if (listing.title || listing.description) {
      rows.push(h('div', { class: 'info' },
        h('span', { class: 'info-main' },
          h('span', { class: 'info-text' }, listing.title || 'Senza titolo'),
          listing.description ? h('span', { class: 'listing-desc' }, listing.description) : null)));
      rows.push(h('div', { class: 'info info-split listing-links' },
        listing.title ? textButton('Copia titolo', () => copyText(listing.title, 'Titolo copiato.')) : null,
        listing.description
          ? textButton('Copia descrizione', () => copyText(listing.description, 'Descrizione copiata.')) : null));
    } else {
      rows.push(h('div', { class: 'info' },
        h('span', { class: 'info-main' },
          h('span', { class: 'info-text' }, 'Ancora nessun annuncio'),
          h('span', { class: 'info-meta' }, active
            ? 'Condividi la richiesta con Claude, poi incolla qui la sua risposta.'
            : 'Nessun testo salvato.'))));
    }
    if (listing.price_cents) {
      const meta = [];
      if (listing.min_price_cents) meta.push(`minimo ${formatEuro(listing.min_price_cents)}`);
      const changes = listing.price_changes.length - 1;
      if (changes > 0) {
        meta.push(`partito da ${formatEuro(listing.start_price_cents)}, ${changes === 1 ? '1 cambio' : `${changes} cambi`}`);
      }
      rows.push(h('div', { class: 'info info-split' },
        h('span', { class: 'info-main' },
          h('span', { class: 'info-figure' }, formatEuro(listing.price_cents)),
          meta.length ? h('span', { class: 'info-meta' }, meta.join(' · ')) : null),
        item.status === 'listed' ? textButton('Cambia prezzo', changePrice) : null));
    }
    const summary = detailsSummary(item.details);
    rows.push(h('div', { class: 'info info-split' },
      h('span', { class: 'info-main' },
        h('span', { class: 'info-meta' }, summary || 'Nessun dettaglio: marca, taglia e stato aiutano Claude.'))));
    rows.push(h('div', { class: 'info info-split info-stack' },
      active ? h('button', {
        class: 'btn btn-quiet btn-block btn-claude', type: 'button', onclick: () => shareWithClaude(item),
      }, 'Condividi con Claude') : null,
      h('div', { class: 'listing-links' },
        active ? textButton('Copia richiesta', () => copyRequest(item)) : null,
        active && item.photo ? textButton('Salva foto', () => savePhoto(item)) : null,
        active ? textButton('Incolla risposta', pasteAnswer) : null,
        h('a', { class: 'btn-text', href: `${itemPath(itemId)}/annuncio`, dataset: { link: '' } }, 'Modifica'))));
    return h('div', { class: 'card' }, ...rows);
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
      message: `L’entrata di ${formatEuro(item.sale.amount_cents)} del ${dayMonth(item.sale.income_date)} viene eliminata e l’articolo torna ${item.listed_on ? 'in vendita' : 'tra quelli da pubblicare'}. Utile per un reso.`,
      confirmLabel: 'Annulla vendita',
      danger: true,
    });
    if (confirmed) run(() => api.del(`/vinted/items/${itemId}/sale`), 'Vendita non annullata', 'Vendita annullata.');
  }

  function saleCard() {
    if (!item.sale && item.status === 'unlisted') {
      // The big button is "Segna come pubblicato": selling first stays possible.
      return h('div', { class: 'card' },
        h('div', { class: 'info' },
          h('span', { class: 'info-main' },
            h('span', { class: 'info-text' }, 'Non ancora venduto'),
            h('span', { class: 'info-meta' }, 'Venduto senza pubblicarlo? Si può segnare lo stesso.'))),
        h('div', { class: 'info info-split' },
          h('a', { class: 'btn-text btn-text-start', href: `${itemPath(itemId)}/venduto`, dataset: { link: '' } },
            'Segna come venduto')));
    }
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
    }, item.status === 'withdrawn' ? 'Annulla il ritiro' : 'Ritira dalla vendita');
    content.replaceChildren(
      hero(),
      h('h2', { class: 'section-title' }, 'Su Vinted'), vintedCard(),
      h('h2', { class: 'section-title' }, 'Annuncio'), listingCard(),
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
    footer.replaceChildren(item.status === 'unlisted'
      ? h('button', {
        class: 'btn btn-primary btn-block btn-save', type: 'button', onclick: publishToday,
      }, 'Segna come pubblicato')
      : h('a', {
        class: 'btn btn-primary btn-block btn-save', href: `${itemPath(itemId)}/venduto`, dataset: { link: '' },
      }, 'Segna come venduto'));
  }

  ctx.onResume(({ longAway }) => { if (longAway) reload(); });
  draw();
}
