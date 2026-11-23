// "Nuovo articolo" (0.8.0): title, an optional photo, and whether it was
// bought to resell (then its purchase: a new expense in the Vinted category,
// or one already recorded from "Nuova spesa") or was already at home.
// 0.10.0: whether it is on Vinted already (usually not: it waits among the
// items "Da pubblicare" until it is published), and, if wanted, the details
// Claude will write its ad from (vinted-listing.js).

import { api } from '../api.js';
import { state, loadUsers } from '../store.js';
import {
  h, icon, toast, vibrate, formatEuro, newUuid, todayIso, choiceDialog, loadingBlock, errorBlock,
} from '../ui.js';
import { pickImage, preparePhoto } from '../photo.js';
import { purchaseFields } from '../vinted-forms.js';
import { dayMonth, showFilterNext } from './vinted.js';
import { loadListingOptions, detailsFields } from '../vinted-listing.js';

function expenseOption(expense) {
  return {
    value: expense.id,
    label: expense.merchant_name || 'Senza esercente',
    meta: [dayMonth(expense.expense_date), expense.paid_by_name, expense.note].filter(Boolean).join(' · '),
    amount: formatEuro(expense.amount_cents),
  };
}

export async function mount(root, ctx) {
  root.append(loadingBlock());
  let users;
  let waiting;
  let options;
  try {
    [users, waiting, options] = await Promise.all([
      loadUsers(), api.get('/vinted/unlinked-expenses'), loadListingOptions()]);
  } catch (error) {
    if (ctx.isCurrent()) root.replaceChildren(errorBlock(error, () => ctx.navigate('/vinted/nuovo', { replace: true })));
    return;
  }
  if (!ctx.isCurrent()) return;

  const goBack = () => ctx.back('/vinted');
  // Same key for every retry of this screen: a dropped connection never
  // stores the item (or its purchase) twice.
  const clientUuid = newUuid();
  let bought = true;
  let linked = null; // an expense already recorded, picked from the list
  let photo = null;  // { image, thumb, preview }, uploaded once the item exists

  const errorBanner = h('div', { class: 'banner banner-error', role: 'alert', hidden: true });
  const hideError = () => { errorBanner.hidden = true; };

  // --- title ------------------------------------------------------------------
  const titleError = h('p', { class: 'field-error', hidden: true });
  const titleInput = h('input', {
    class: 'input', id: 'item-title', type: 'text', maxLength: 120, autocomplete: 'off',
    autocapitalize: 'sentences', enterkeyhint: 'next', placeholder: 'Es. Giacca di lana blu, 8 anni',
    oninput: () => { titleError.hidden = true; hideError(); },
    onkeydown: (event) => {
      if (event.key === 'Enter') { event.preventDefault(); titleInput.blur(); }
    },
  });

  // --- photo ------------------------------------------------------------------
  const photoSlot = h('div');
  function drawPhoto() {
    if (!photo) {
      photoSlot.replaceChildren(h('button', { class: 'photo-pick', type: 'button', onclick: choosePhoto },
        h('span', { class: 'photo-tile', 'aria-hidden': 'true' }, icon('camera')),
        h('span', { class: 'photo-pick-text' },
          h('span', { class: 'photo-pick-title' }, 'Aggiungi foto'),
          h('span', { class: 'photo-pick-hint' }, 'Scatta o scegli dalla galleria'))));
      return;
    }
    photoSlot.replaceChildren(h('div', { class: 'photo-pick' },
      h('img', { class: 'photo-preview', src: photo.preview, alt: 'Foto scelta' }),
      h('span', { class: 'photo-pick-text' },
        h('button', { class: 'btn-text', type: 'button', onclick: choosePhoto }, 'Cambia foto'),
        h('button', { class: 'btn-text', type: 'button', onclick: () => { photo = null; drawPhoto(); } }, 'Togli'))));
  }
  async function choosePhoto() {
    const file = await pickImage();
    if (!file) return;
    try {
      photo = await preparePhoto(file);
      drawPhoto();
    } catch (error) {
      toast(error.message, { kind: 'error' });
    }
  }

  // --- bought or already at home --------------------------------------------------
  const purchase = purchaseFields({ users, me: state.me });
  const linkedSlot = h('div', { hidden: true });
  const pickButton = h('button', {
    class: 'btn btn-quiet btn-block', type: 'button', onclick: pickExpense, hidden: waiting.length === 0,
  }, 'Scegli una spesa già registrata');
  const pickHint = h('p', { class: 'form-hint', hidden: waiting.length === 0 },
    'L’hai già registrato da Nuova spesa, nella categoria Vinted?');
  const purchaseBlock = h('div', {}, purchase.element);
  const boughtBlock = h('div', {}, purchaseBlock, linkedSlot, pickHint, pickButton);

  function drawLinked() {
    purchaseBlock.hidden = Boolean(linked);
    linkedSlot.hidden = !linked;
    pickHint.hidden = Boolean(linked) || waiting.length === 0;
    pickButton.hidden = Boolean(linked) || waiting.length === 0;
    if (!linked) return;
    const option = expenseOption(linked);
    linkedSlot.replaceChildren(
      h('span', { class: 'label' }, 'Acquisto'),
      h('div', { class: 'card info' },
        h('span', { class: 'info-main' },
          h('span', { class: 'info-figure' }, option.amount),
          h('span', { class: 'info-meta' }, `${option.label} · ${option.meta}`)),
        h('button', { class: 'btn-text', type: 'button', onclick: pickExpense }, 'Cambia')),
      h('button', {
        class: 'btn-text', type: 'button', onclick: () => { linked = null; drawLinked(); },
      }, 'Inserisci il prezzo a mano'));
  }

  async function pickExpense() {
    const id = await choiceDialog({
      title: 'Scegli la spesa',
      text: 'Spese della categoria Vinted non ancora collegate a un articolo.',
      options: waiting.map(expenseOption),
    });
    if (id === null) return;
    linked = waiting.find((expense) => expense.id === id) || null;
    hideError();
    drawLinked();
  }

  const origin = h('div', { class: 'seg seg-compact', role: 'group', 'aria-labelledby': 'item-origin' });
  function drawOrigin() {
    const option = (value, label) => h('button', {
      class: `seg-item${bought === value ? ' is-selected' : ''}`,
      type: 'button',
      'aria-pressed': String(bought === value),
      onclick: () => { bought = value; drawOrigin(); hideError(); },
    }, label);
    origin.replaceChildren(option(true, 'Sì'), option(false, 'No, era già nostro'));
    boughtBlock.hidden = !bought;
  }

  // --- on Vinted already? ---------------------------------------------------------
  let published = false;
  const listedError = h('p', { class: 'field-error', hidden: true });
  const listedInput = h('input', {
    class: 'input', id: 'item-listed', type: 'date', value: todayIso(), min: '2000-01-01', max: todayIso(),
    required: true, onchange: () => { listedError.hidden = true; hideError(); },
  });
  const listedBlock = h('div', { hidden: true },
    h('label', { class: 'label', for: 'item-listed' }, 'Pubblicato il'), listedInput, listedError);
  const onVinted = h('div', { class: 'seg seg-compact', role: 'group', 'aria-labelledby': 'item-on-vinted' });
  function drawOnVinted() {
    const option = (value, label) => h('button', {
      class: `seg-item${published === value ? ' is-selected' : ''}`,
      type: 'button',
      'aria-pressed': String(published === value),
      onclick: () => { published = value; drawOnVinted(); hideError(); },
    }, label);
    onVinted.replaceChildren(option(false, 'Non ancora'), option(true, 'Già pubblicato'));
    listedBlock.hidden = !published;
  }

  // The day it went on Vinted: not before it was bought.
  function listedDayProblem() {
    const day = listedInput.value;
    if (!day) return 'Scegli il giorno della pubblicazione.';
    if (day > todayIso()) return 'La data non può essere nel futuro.';
    const boughtOn = !bought ? null : linked ? linked.expense_date : purchase.toPayload().expense_date;
    if (boughtOn && day < boughtOn) return `Non prima dell’acquisto (${dayMonth(boughtOn)}).`;
    return null;
  }

  // --- details for the ad (optional, folded) -------------------------------------------
  const details = detailsFields({ options, idPrefix: 'item' });
  const detailsBlock = h('div', { hidden: true },
    h('h2', { class: 'section-title' }, 'Dettagli per l’annuncio'), details.element);
  const detailsToggle = h('button', {
    class: 'btn btn-quiet btn-block details-toggle', type: 'button',
    onclick: () => { detailsBlock.hidden = false; detailsToggle.hidden = true; },
  }, 'Aggiungi dettagli per l’annuncio');

  // --- note, save -------------------------------------------------------------------
  const noteInput = h('input', {
    class: 'input', id: 'item-note', type: 'text', maxLength: 300, autocomplete: 'off',
    enterkeyhint: 'done', placeholder: 'Facoltativa, es. taglia, difetti',
    onkeydown: (event) => {
      if (event.key === 'Enter') { event.preventDefault(); noteInput.blur(); }
    },
  });

  const saveButton = h('button', {
    class: 'btn btn-primary btn-block btn-save', type: 'button',
    onpointerdown: (event) => event.preventDefault(), // keep the keyboard while tapping
    onclick: save,
  }, 'Salva articolo');

  async function save() {
    if (saveButton.disabled) return;
    if (!titleInput.value.trim()) {
      titleError.textContent = 'Scrivi il titolo dell’articolo.';
      titleError.hidden = false;
      titleInput.focus();
      return;
    }
    if (bought && !linked && !purchase.validate()) return;
    const listedProblem = published ? listedDayProblem() : null;
    if (listedProblem) {
      listedError.textContent = listedProblem;
      listedError.hidden = false;
      listedInput.focus();
      return;
    }
    hideError();
    saveButton.disabled = true;
    const payload = {
      title: titleInput.value.trim(),
      note: noteInput.value.trim() || null,
      client_uuid: clientUuid,
    };
    if (published) payload.listed_on = listedInput.value;
    if (!detailsBlock.hidden) Object.assign(payload, details.toPayload());
    if (bought) payload.purchase = linked ? { expense_id: linked.id } : purchase.toPayload();
    try {
      const item = await api.post('/vinted/items', payload);
      let photoFailed = false;
      if (photo) {
        try { await api.uploadPhoto(item.id, photo); } catch (error) { photoFailed = true; }
      }
      vibrate();
      if (photoFailed) {
        toast('Articolo salvato, ma la foto non è arrivata: aggiungila dalla scheda dell’articolo.', { kind: 'error', duration: 8000 });
      } else {
        toast(`Articolo salvato: ${item.title}`, { kind: 'success' });
      }
      showFilterNext(item.status); // the list opens where the new item is
      goBack();
    } catch (error) {
      saveButton.disabled = false;
      if (error.status === 401) return; // the app is already going to the login screen
      if (error.status === 422 && /mporto|decimali|prezzo/i.test(error.message)) {
        purchase.setAmountError(error.message);
        return;
      }
      errorBanner.replaceChildren(
        h('strong', {}, 'Articolo non salvato.'),
        h('span', {}, error.network
          ? ' La connessione è caduta: i dati sono ancora qui. Controlla Tailscale e riprova.'
          : ` ${error.message}`));
      errorBanner.hidden = false;
    }
  }

  drawPhoto();
  drawOrigin();
  drawLinked();
  drawOnVinted();
  root.replaceChildren(
    h('header', { class: 'page-head' },
      h('a', {
        class: 'page-back', href: '/vinted', 'aria-label': 'Torna agli articoli',
        onclick: (event) => { event.preventDefault(); goBack(); },
      }, '‹'),
      h('h1', { class: 'page-title' }, 'Nuovo articolo')),
    h('div', { class: 'vinted-form' },
      h('label', { class: 'label', for: 'item-title' }, 'Titolo'), titleInput, titleError,
      h('span', { class: 'label' }, 'Foto ', h('span', { class: 'label-soft' }, '(facoltativa)')), photoSlot,
      h('span', { class: 'label', id: 'item-origin' }, 'L’hai comprato per rivenderlo?'), origin,
      boughtBlock,
      h('span', { class: 'label', id: 'item-on-vinted' }, 'Su Vinted'), onVinted, listedBlock,
      h('label', { class: 'label', for: 'item-note' }, 'Nota'), noteInput,
      detailsToggle, detailsBlock),
    h('div', { class: 'footer-bar' }, errorBanner, saveButton));
  titleInput.focus({ preventScroll: true });
}
