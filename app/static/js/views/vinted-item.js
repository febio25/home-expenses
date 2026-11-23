// The screen of a Vinted item (0.8.0): photo, title and status; its purchase
// and its sale, each edited on the expense or income screen it really is;
// the note; withdraw and delete. "Segna come venduto" sits at the bottom.
//
// 0.10.0: the day it went on Vinted ("Su Vinted"). An item not on Vinted yet
// has "Segna come pubblicato" at the bottom instead (one tap: today), and
// "Segna come venduto" in its sale card. The "Annuncio" card holds the ad
// written with Claude: share the request, paste the answer, copy the text
// for Vinted, change the asking price (vinted-listing.js).
//
// 0.11.0: the "Annuncio" card follows the item's life. Before Claude, three
// numbered steps (details, ask Claude, paste the answer); with the ad
// written (a description saved), the text to copy to Vinted and a reminder
// to mark it published; on sale, the price on Vinted first; sold or
// withdrawn, only what was written, and nothing when there is nothing.

import { api } from '../api.js';
import {
  h, icon, toast, vibrate, confirmDialog, promptDialog, choiceDialog, openDialog, formatEuro, PAYMENT_LABELS,
  todayIso, loadingBlock, errorBlock,
} from '../ui.js';
import { thumbButton, choosePhotoFor } from '../photo.js';
import { itemPath, dayMonth, sinceLabel, daysBetween, gainSpan, captionOf, waitingSince } from './vinted.js';
import {
  shareWithClaude, copyRequest, prepareRequest, forgetRequest, readAnswer, keepAnswer, copyText, detailsSummary,
  detailsProgress, detailChips, detailsExtra, detailsRows, loadListingOptions, priceInput,
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
    asking = false;
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

  // "Chiedi di nuovo" / "Chiedi a Claude un prezzo nuovo": the steps again,
  // over an ad already written, until the answer is pasted or "Annulla".
  let asking = false;
  const listingPath = `${itemPath(itemId)}/annuncio`;
  const detailsPath = `${itemPath(itemId)}/dettagli`;
  const textButton = (label, onclick) => h('button', { class: 'btn-text', type: 'button', onclick }, label);
  const link = (label, href, extra = '') => h('a', { class: `btn-text${extra}`, href, dataset: { link: '' } }, label);
  const stepButton = (label, iconName, primary, onclick) => h('button', {
    class: `btn btn-block step-btn ${primary ? 'btn-primary' : 'btn-quiet'}`, type: 'button', onclick,
  }, icon(iconName), label);

  function priceMeta(listing) {
    const meta = [];
    const changes = listing.price_changes.length - 1;
    if (listing.price_changes.length) {
      meta.push(`partito da ${formatEuro(listing.start_price_cents)} il ${dayMonth(listing.price_changes[0].changed_on)}`);
    }
    if (changes > 0) meta.push(changes === 1 ? '1 cambio di prezzo' : `${changes} cambi di prezzo`);
    if (listing.min_price_cents) meta.push(`minimo ${formatEuro(listing.min_price_cents)}`);
    return meta.join(' · ');
  }

  // A text of the ad with its "Copia"; a long description is cut at three
  // lines, with "Mostra tutto".
  function textRow(label, text, copyLabel, { clamp = false, copy = true } = {}) {
    const value = h('span', { class: clamp ? 'listing-desc is-clamped' : 'listing-value' }, text);
    let more = null;
    if (clamp && (text.length > 140 || text.split('\n').length > 3)) {
      more = h('button', {
        class: 'btn-text btn-text-start', type: 'button',
        onclick: () => {
          const open = value.classList.toggle('is-clamped') === false;
          more.textContent = open ? 'Mostra meno' : 'Mostra tutto';
        },
      }, 'Mostra tutto');
    }
    return h('div', { class: 'info' },
      h('span', { class: 'info-main' },
        h('span', { class: 'info-label' }, label), value, more),
      copy ? textButton('Copia', () => copyText(text, copyLabel)) : null);
  }

  function step(number, done, title, ...body) {
    return h('div', { class: 'info step' },
      h('span', { class: `step-num${done ? ' is-done' : ''}`, 'aria-hidden': 'true' }, done ? icon('check') : String(number)),
      h('div', { class: 'step-main' },
        h('span', { class: 'sr-only' }, done ? 'Fatto: ' : `Passo ${number}: `),
        ...(Array.isArray(title) ? title : [h('span', { class: 'step-title' }, title)]),
        ...body));
  }

  function stepsCard() {
    const listing = item.listing;
    const details = item.details;
    const progress = detailsProgress(details);
    const ready = progress.state === 'complete';
    const rows = [];
    if (item.status === 'listed') {
      rows.push(h('div', { class: 'info' },
        h('span', { class: 'info-main' },
          h('span', { class: 'info-text' }, 'È già in vendita'),
          h('span', { class: 'info-meta' }, 'Claude proporrà anche un prezzo aggiornato.'))));
    }
    if (ready) {
      const extra = detailsExtra(details);
      rows.push(step(1, true,
        [h('span', { class: 'step-head' },
          h('span', { class: 'step-title' }, 'Dettagli compilati'), link('Modifica', detailsPath))],
        h('span', { class: 'detail-chips' }, detailChips(details).map((text) => h('span', { class: 'detail-chip' }, text))),
        extra ? h('span', { class: 'step-text' }, extra) : null));
    } else if (progress.state === 'partial') {
      rows.push(step(1, false, 'Completa i dettagli',
        h('span', { class: 'step-text' }, detailsSummary(details) || 'Prezzi simili indicati'),
        h('span', { class: 'step-text step-missing' }, `Mancano: ${progress.missing.join(', ')}.`),
        stepButton('Completa i dettagli', 'pencil', true, () => ctx.navigate(detailsPath))));
    } else {
      rows.push(step(1, false, 'Compila i dettagli',
        h('span', { class: 'step-text' }, 'Tipo, marca, taglia, stato, misure, difetti: più ne scrivi, meno Claude deve indovinare.'),
        stepButton('Aggiungi dettagli', 'pencil', true, () => ctx.navigate(detailsPath))));
    }
    rows.push(step(2, false, 'Chiedi a Claude',
      h('span', { class: 'step-text' }, item.photo
        ? 'Copia la richiesta e condivide la foto: in Claude tieni premuto nella chat e scegli «Incolla».'
        : 'Condivide la richiesta: scegli l’app Claude e invia.'),
      stepButton('Condividi con Claude', 'share', ready, () => shareWithClaude(item)),
      h('span', { class: 'step-text step-alt' },
        item.photo ? 'Senza foto? ' : 'Oppure ', textButton(item.photo ? 'Copia solo la richiesta' : 'copia la richiesta', () => copyRequest(item)))));
    rows.push(step(3, false, 'Incolla la risposta',
      h('span', { class: 'step-text' }, 'Copia la risposta di Claude e torna qui.'),
      stepButton('Incolla risposta di Claude', 'clipboard', false, pasteAnswer)));
    rows.push(h('div', { class: 'info info-center' }, asking
      ? textButton('Annulla', () => { asking = false; draw(); })
      : link(listing.description || listing.price_cents ? 'Modifica annuncio' : 'Oppure scrivi l’annuncio tu', listingPath)));
    return h('div', { class: 'card listing-card' }, ...rows);
  }

  // "Dettagli dell'articolo" (0.13.0): once the ad is written the steps are
  // gone, and with them the details. Closed it is one line; open, every
  // detail filled in, with "Modifica dettagli". Stays open across redraws.
  let detailsOpen = false;
  let fieldNames = null; // from the API, loaded at the first opening
  function detailsBox({ edit = true } = {}) {
    const rows = detailsRows(item.details, fieldNames || {});
    if (!rows.length && !edit) return null;
    const summary = detailsSummary(item.details);
    const toggle = h('button', {
      class: 'details-toggle', type: 'button', 'aria-expanded': String(detailsOpen),
      onclick: async () => {
        detailsOpen = !detailsOpen;
        if (detailsOpen && !fieldNames) {
          try {
            const options = await loadListingOptions();
            fieldNames = Object.fromEntries(options.fields.map((field) => [field.field, field.name]));
          } catch (error) { fieldNames = {}; } // the labels fall back to the field codes
        }
        draw();
      },
    },
    h('span', { class: 'info-main' },
      h('span', { class: 'info-label' }, 'Dettagli dell’articolo'),
      h('span', { class: 'info-meta' }, rows.length ? summary || `${rows.length} indicati` : 'Nessun dettaglio indicato')),
    h('span', { class: 'details-toggle-action', 'aria-hidden': 'true' }, detailsOpen ? 'Chiudi ▴' : 'Mostra ▾'));
    const box = h('div', { class: 'details-box' }, toggle);
    if (detailsOpen) {
      if (rows.length) {
        box.append(h('dl', { class: 'details-list' },
          rows.flatMap(([label, value]) => [h('dt', {}, label), h('dd', {}, value)])));
      }
      if (edit) {
        box.append(h('div', { class: 'details-edit' },
          link(rows.length ? 'Modifica dettagli' : 'Aggiungi dettagli', detailsPath, ' btn-text-start')));
      }
    }
    return box;
  }

  function priceRow(listing, { change = false } = {}) {
    if (!listing.price_cents) {
      return h('div', { class: 'info' },
        h('span', { class: 'info-main' },
          h('span', { class: 'info-label' }, 'Prezzo su Vinted'),
          h('span', { class: 'info-meta' }, 'Non indicato')),
        change ? textButton('Imposta', changePrice) : null);
    }
    const meta = priceMeta(listing);
    return h('div', { class: 'info' },
      h('span', { class: 'info-main' },
        h('span', { class: 'info-label' }, change ? 'Prezzo su Vinted' : 'Prezzo'),
        h('span', { class: 'info-figure' }, formatEuro(listing.price_cents)),
        meta ? h('span', { class: 'info-meta' }, meta) : null),
      change ? textButton('Cambia', changePrice) : null);
  }

  // Written, not on Vinted yet: the text to copy, then "Segna come pubblicato".
  function readyCard() {
    const listing = item.listing;
    return h('div', { class: 'card listing-card' },
      h('div', { class: 'info' },
        h('p', { class: 'listing-reminder' },
          'Su Vinted: crea l’annuncio, incolla titolo e descrizione, metti il prezzo. Poi qui sotto «Segna come pubblicato».')),
      textRow('Titolo', listing.effective_title, 'Titolo copiato.'),
      textRow('Descrizione', listing.description, 'Descrizione copiata.', { clamp: true }),
      listing.price_cents ? priceRow(listing) : null,
      detailsBox(),
      h('div', { class: 'info info-center listing-links' },
        link('Modifica annuncio', listingPath),
        textButton('Chiedi di nuovo', () => { asking = true; draw(); })));
  }

  // On Vinted: the price first, to change it when it changes on Vinted.
  function onSaleCard() {
    const listing = item.listing;
    return h('div', { class: 'card listing-card' },
      priceRow(listing, { change: true }),
      textRow('Titolo', listing.effective_title, 'Titolo copiato.'),
      textRow('Descrizione', listing.description, 'Descrizione copiata.', { clamp: true }),
      detailsBox(),
      h('div', { class: 'info info-center' },
        h('span', { class: 'step-text' }, 'Non si vende? ',
          textButton('Chiedi a Claude un prezzo nuovo', () => { asking = true; draw(); }))),
      h('div', { class: 'info info-center' }, link('Modifica annuncio', listingPath)));
  }

  // Sold or withdrawn: what was written, nothing to ask.
  function closedCard() {
    const listing = item.listing;
    return h('div', { class: 'card listing-card' },
      textRow('Titolo', listing.effective_title, 'Titolo copiato.', { copy: false }),
      listing.description ? textRow('Descrizione', listing.description, '', { clamp: true, copy: false }) : null,
      listing.price_cents ? priceRow(listing) : null,
      detailsBox({ edit: false }),
      h('div', { class: 'info info-center' }, link('Modifica annuncio', listingPath)));
  }

  // The card, or null when there is nothing to show (sold or withdrawn
  // without an ad).
  function listingCard() {
    const listing = item.listing;
    const active = item.status === 'unlisted' || item.status === 'listed';
    if (!active) {
      return listing.title || listing.description || listing.price_cents ? closedCard() : null;
    }
    if (!listing.description || asking) return stepsCard();
    return item.status === 'unlisted' ? readyCard() : onSaleCard();
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
    const active = item.status === 'unlisted' || item.status === 'listed';
    if (active) prepareRequest(item).catch(() => {}); // ready for "Condividi con Claude"
    const listing = listingCard();
    const withdraw = item.status === 'sold' ? null : h('button', {
      class: 'btn btn-quiet', type: 'button',
      onclick: () => run(() => api.patch(`/vinted/items/${itemId}`, { is_withdrawn: item.status !== 'withdrawn' }),
        'Non modificato'),
    }, item.status === 'withdrawn' ? 'Annulla il ritiro' : 'Ritira dalla vendita');
    content.replaceChildren(
      hero(),
      h('h2', { class: 'section-title' }, 'Su Vinted'), vintedCard(),
      listing ? h('h2', { class: 'section-title' }, 'Annuncio') : null, listing,
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

  ctx.onResume(({ longAway }) => { if (longAway) { forgetRequest(); reload(); } });
  forgetRequest(); // the purchase or the photo may have changed elsewhere
  draw();
}
