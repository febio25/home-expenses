// Vinted listings written with Claude (0.10.0), by hand: the app prepares
// the request (GET /vinted/items/{id}/listing-request), the user shares it
// with the Claude app (Android's share sheet, text and photo together) or
// copies it, then pastes Claude's answer back (POST /vinted/listing/parse).
// The app never talks to Claude itself.
//
// Clipboard and sharing need HTTPS: they work from the Tailscale address.
// From plain HTTP (umbrel.local) the text is shown to copy by hand.

import { api } from './api.js';
import { h, toast, openDialog, centsToInput } from './ui.js';

let optionsCache = null;

// Kinds of item, conditions and field names, from the API (fixed lists).
export async function loadListingOptions() {
  if (!optionsCache) optionsCache = await api.get('/vinted/listing/options');
  return optionsCache;
}

const PLACEHOLDERS = {
  brand: 'Es. Levi’s, Zara',
  size: 'Es. M, 42, 8 anni',
  color_material: 'Es. blu, cotone',
  measurements: 'Es. spalle 45 cm, lunghezza 62 cm',
  book_author: 'Es. Umberto Eco',
  book_publisher_year: 'Es. Bompiani, 1980',
  defects: 'Es. piccolo segno sul polsino',
};
const DETAIL_FIELDS = Object.keys(PLACEHOLDERS).concat('condition');
const ANY_KIND = 'clothing'; // without a kind, the fields of clothing (as the API)

// The details of an item: its kind (decides the fields), then those fields
// and the prices seen on Vinted. toPayload() sends null for the fields the
// kind does not use, so the request for Claude never carries stale ones.
export function detailsFields({ options, details = {}, idPrefix = 'det' }) {
  const state = { kind: details.kind || null };
  const inputs = {};
  const rows = {};
  const kindSeg = h('div', { class: 'seg seg-compact seg-wrap', role: 'group', 'aria-labelledby': `${idPrefix}-kind` });

  for (const field of Object.keys(PLACEHOLDERS)) {
    const id = `${idPrefix}-${field}`;
    inputs[field] = h('input', {
      class: 'input', id, type: 'text', autocomplete: 'off', value: details[field] || '',
      placeholder: PLACEHOLDERS[field], enterkeyhint: 'next',
      autocapitalize: field === 'brand' || field === 'book_author' ? 'words' : 'sentences',
    });
  }
  inputs.condition = h('select', { class: 'input', id: `${idPrefix}-condition` },
    h('option', { value: '' }, 'Non indicato'),
    options.conditions.map((condition) => h('option', {
      value: condition.code, selected: details.condition === condition.code,
    }, condition.name)));
  const names = Object.fromEntries(options.fields.map((item) => [item.field, item.name]));
  for (const field of DETAIL_FIELDS) {
    rows[field] = h('div', {},
      h('label', { class: 'label', for: `${idPrefix}-${field}` }, names[field] || field), inputs[field]);
  }
  const similar = h('input', {
    class: 'input', id: `${idPrefix}-similar`, type: 'text', autocomplete: 'off',
    value: details.similar_prices || '', placeholder: 'Es. 20, 25, 18', enterkeyhint: 'done',
  });
  const fieldsBox = h('div');

  function fieldsOf(kind) {
    const found = options.kinds.find((item) => item.code === (kind || ANY_KIND));
    return found ? found.fields : [];
  }

  function draw() {
    kindSeg.replaceChildren(...options.kinds.map((kind) => h('button', {
      class: `seg-item${state.kind === kind.code ? ' is-selected' : ''}`,
      type: 'button',
      'aria-pressed': String(state.kind === kind.code),
      onclick: () => { state.kind = state.kind === kind.code ? null : kind.code; draw(); },
    }, kind.name)));
    fieldsBox.replaceChildren(...fieldsOf(state.kind).map((field) => rows[field]));
  }
  draw();

  const element = h('div', {},
    h('span', { class: 'label', id: `${idPrefix}-kind` }, 'Che cos’è'), kindSeg,
    fieldsBox,
    h('label', { class: 'label', for: `${idPrefix}-similar` }, 'Prezzi simili visti su Vinted'),
    similar,
    h('p', { class: 'form-hint' }, 'Facoltativi: più dettagli scrivi, migliore viene l’annuncio.'));

  return {
    element,
    toPayload() {
      const used = new Set(fieldsOf(state.kind));
      const payload = { kind: state.kind, similar_prices: similar.value.trim() || null };
      for (const field of DETAIL_FIELDS) {
        payload[field] = used.has(field) ? (inputs[field].value.trim() || null) : null;
      }
      return payload;
    },
  };
}

// "Abbigliamento · Levi's · M · Ottime condizioni": the details in one line.
export function detailsSummary(details) {
  const parts = [details.kind_name, details.brand, details.size, details.book_author, details.condition_name];
  return parts.filter(Boolean).join(' · ');
}

// --- copy, share, paste ------------------------------------------------------------

// The text in a box to copy by hand: when the clipboard is not available
// (plain HTTP) or refuses.
function manualCopyDialog(title, text) {
  return openDialog((finish) => {
    const area = h('textarea', { class: 'input textarea', readOnly: true, rows: 8 }, text);
    setTimeout(() => { area.focus(); area.select(); }, 50);
    return h('div', { class: 'dialog-body' },
      h('h2', { class: 'dialog-title' }, title),
      h('p', { class: 'dialog-text' }, 'Tieni premuto sul testo, «Seleziona tutto», poi «Copia».'),
      area,
      h('div', { class: 'dialog-actions' },
        h('button', { class: 'btn btn-primary', type: 'button', onclick: () => finish(null) }, 'Fatto')));
  });
}

export async function copyText(text, done = 'Copiato.') {
  try {
    if (!navigator.clipboard || !window.isSecureContext) throw new Error('no clipboard');
    await navigator.clipboard.writeText(text);
    toast(done, { kind: 'success' });
  } catch (error) {
    await manualCopyDialog('Copia il testo', text);
  }
}

async function requestOf(item) {
  return api.get(`/vinted/items/${item.id}/listing-request`);
}

function report(error, prefix) {
  if (error.status === 401) return;
  toast(`${prefix}: ${error.network ? 'connessione assente.' : error.message}`, { kind: 'error' });
}

function fileName(item) {
  const base = item.title.normalize('NFKD').replace(/[̀-ͯ]/g, '')
    .replace(/[^A-Za-z0-9]+/g, '-').replace(/^-|-$/g, '').toLowerCase().slice(0, 40);
  return `${base || 'articolo'}.jpg`;
}

// Android's share sheet with the request and the photo: the user picks the
// Claude app. Without file sharing, the text alone; without sharing at all,
// the text to copy.
export async function shareWithClaude(item) {
  let request;
  try {
    request = await requestOf(item);
  } catch (error) { report(error, 'Richiesta non pronta'); return; }
  const data = { text: request.text };
  if (item.photo && navigator.canShare) {
    try {
      const blob = await api.blob(`/vinted/items/${item.id}/photo?v=${encodeURIComponent(item.photo)}`);
      const file = new File([blob], fileName(item), { type: 'image/jpeg' });
      if (navigator.canShare({ files: [file] })) data.files = [file];
    } catch (error) { /* share the text alone */ }
  }
  if (!navigator.share) {
    await manualCopyDialog('Richiesta per Claude', request.text);
    return;
  }
  try {
    await navigator.share(data);
  } catch (error) {
    if (error.name === 'AbortError') return; // share sheet closed
    await manualCopyDialog('Richiesta per Claude', request.text);
  }
}

export async function copyRequest(item) {
  let request;
  try {
    request = await requestOf(item);
  } catch (error) { report(error, 'Richiesta non pronta'); return; }
  await copyText(request.text, item.photo
    ? 'Richiesta copiata: incollala in Claude e allega la foto.'
    : 'Richiesta copiata: incollala in Claude.');
}

export async function savePhoto(item) {
  try {
    await api.download(`/vinted/items/${item.id}/photo?v=${encodeURIComponent(item.photo)}`, fileName(item));
  } catch (error) { report(error, 'Foto non salvata'); }
}

// Claude's answer: from the clipboard when the phone allows it, otherwise
// pasted in a box. Resolves to the text, or null.
function pasteDialog() {
  return openDialog((finish) => {
    const area = h('textarea', {
      class: 'input textarea', rows: 8, placeholder: 'Tieni premuto qui e scegli «Incolla».',
    });
    setTimeout(() => area.focus(), 50);
    return h('form', {
      class: 'dialog-body',
      onsubmit: (event) => { event.preventDefault(); if (area.value.trim()) finish(area.value); },
    },
      h('h2', { class: 'dialog-title' }, 'Incolla la risposta di Claude'),
      area,
      h('div', { class: 'dialog-actions' },
        h('button', { class: 'btn btn-quiet', type: 'button', onclick: () => finish(null) }, 'Annulla'),
        h('button', { class: 'btn btn-primary', type: 'submit' }, 'Usa questo testo')));
  });
}

export async function readAnswer() {
  let text = '';
  try {
    if (navigator.clipboard && window.isSecureContext && navigator.clipboard.readText) {
      text = await navigator.clipboard.readText();
    }
  } catch (error) { text = ''; }
  // Only an answer that looks like Claude's: otherwise ask to paste it.
  if (!/TITOLO|DESCRIZIONE/i.test(text)) text = await pasteDialog();
  if (!text) return null;
  try {
    return await api.post('/vinted/listing/parse', { text });
  } catch (error) {
    report(error, 'Risposta non letta');
    return null;
  }
}

// The answer read last, for the listing screen opened right after.
let pendingAnswer = null;
export function keepAnswer(answer) { pendingAnswer = answer; }
export function takeAnswer() {
  const answer = pendingAnswer;
  pendingAnswer = null;
  return answer;
}

export function priceInput(id, cents, placeholder = 'Es. 25') {
  return h('input', {
    class: 'input', id, type: 'text', inputmode: 'decimal', autocomplete: 'off', enterkeyhint: 'done',
    value: cents ? centsToInput(cents) : '', placeholder,
  });
}
