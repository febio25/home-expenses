// Vinted listings written with Claude (0.10.0), by hand: the app prepares
// the request (GET /vinted/items/{id}/listing-request), the user gives it
// to the Claude app, then pastes Claude's answer back (POST
// /vinted/listing/parse). The app never talks to Claude itself.
//
// 0.11.0: the Claude app for Android, given text and a photo together,
// keeps only the photo. So "Condividi con Claude" copies the request to the
// clipboard and shares the photo alone (in Claude: hold in the chat,
// «Incolla»); an item without a photo shares the text. Request and photo
// are fetched when the item's screen opens: a share needs the user's tap,
// and Chrome allows it only for a few seconds after it.
//
// Clipboard and sharing need HTTPS: they work from the Tailscale address.
// From plain HTTP (umbrel.local) the text is shown to copy by hand.

import { api } from './api.js';
import { h, toast, openDialog, centsToInput, todayIso } from './ui.js';

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

// --- details: what step 1 of the ad asks for --------------------------------------

// Complete when the kind, the condition and the brand are there (the author
// for a book; for "Altro" the condition is enough).
const REQUIRED = {
  clothing: ['brand', 'condition'], bag: ['brand', 'condition'], book: ['book_author', 'condition'], other: ['condition'],
};
const MISSING_NAMES = { brand: 'marca', book_author: 'autore', condition: 'stato' };

// { state: 'empty' | 'partial' | 'complete', missing: ['tipo', 'stato', …] }
export function detailsProgress(details) {
  const missing = [];
  if (!details.kind) missing.push('tipo');
  const required = details.kind ? REQUIRED[details.kind] || [] : ['condition'];
  for (const field of required) if (!details[field]) missing.push(MISSING_NAMES[field]);
  const any = Boolean(details.kind || details.similar_prices) || DETAIL_FIELDS.some((field) => details[field]);
  return { state: missing.length === 0 ? 'complete' : any ? 'partial' : 'empty', missing };
}

// The details in evidence once they are complete: kind, brand or author,
// size, condition, colour and material.
export function detailChips(details) {
  return [
    details.kind_name, details.brand, details.book_author,
    details.size ? `Taglia ${details.size}` : null, details.condition_name, details.color_material,
  ].filter(Boolean);
}

// Every detail filled in, as [label, value], in reading order (0.13.0):
// what the "Dettagli dell'articolo" box of the ad shows. `names` are the
// field names from the API (loadListingOptions); unused fields are null.
export function detailsRows(details, names = {}) {
  const value = { ...details, kind: details.kind_name, condition: details.condition_name };
  const order = [
    ['kind', 'Che cos’è'], ['brand'], ['book_author'], ['book_publisher_year'], ['size'], ['condition'],
    ['color_material'], ['measurements'], ['defects'], ['similar_prices', 'Prezzi simili su Vinted'],
  ];
  return order
    .filter(([field]) => value[field])
    .map(([field, label]) => [label || names[field] || field, value[field]]);
}

// "Con misure e difetti · prezzi simili: 20, 25, 18": the rest, in one line.
export function detailsExtra(details) {
  const noted = [
    ['measurements', 'misure'], ['defects', 'difetti'], ['book_publisher_year', 'editore e anno'],
  ].filter(([field]) => details[field]).map(([, name]) => name);
  const parts = [];
  if (noted.length) {
    parts.push(`Con ${noted.length > 1 ? `${noted.slice(0, -1).join(', ')} e ${noted[noted.length - 1]}` : noted[0]}`);
  }
  if (details.similar_prices) parts.push(`prezzi simili: ${details.similar_prices}`);
  return parts.join(' · ');
}

// --- copy, share, paste ------------------------------------------------------------

// The text in a box to copy by hand: when the clipboard is not available
// (plain HTTP) or refuses. With `file`, a button shares the photo after
// (a new tap: the first one went to the clipboard that failed).
function manualCopyDialog(title, text, file = null) {
  return openDialog((finish) => {
    const area = h('textarea', { class: 'input textarea', readOnly: true, rows: 8 }, text);
    setTimeout(() => { area.focus(); area.select(); }, 50);
    return h('div', { class: 'dialog-body' },
      h('h2', { class: 'dialog-title' }, title),
      h('p', { class: 'dialog-text' }, file
        ? 'Tieni premuto sul testo, «Seleziona tutto», poi «Copia». Poi condividi la foto e in Claude incolla il testo.'
        : 'Tieni premuto sul testo, «Seleziona tutto», poi «Copia».'),
      area,
      h('div', { class: 'dialog-actions' },
        file ? h('button', { class: 'btn btn-quiet', type: 'button', onclick: () => finish(null) }, 'Chiudi') : null,
        file
          ? h('button', { class: 'btn btn-primary', type: 'button', onclick: () => { finish(null); sharePhoto(file); } },
            'Condividi la foto')
          : h('button', { class: 'btn btn-primary', type: 'button', onclick: () => finish(null) }, 'Fatto')));
  });
}

// One more tap, when the first one is no longer valid for a share: Chrome
// allows a share only a few seconds after the tap (slow connection), and
// sharing it consumes the tap.
function shareAgainDialog({ title, text, label, run }) {
  return openDialog((finish) => h('div', { class: 'dialog-body' },
    h('h2', { class: 'dialog-title' }, title),
    h('p', { class: 'dialog-text' }, text),
    h('div', { class: 'dialog-actions' },
      h('button', { class: 'btn btn-quiet', type: 'button', onclick: () => finish(null) }, 'Chiudi'),
      h('button', { class: 'btn btn-primary', type: 'button', onclick: () => { finish(null); run(); } }, label))));
}

async function writeClipboard(text) {
  if (!navigator.clipboard || !window.isSecureContext) throw new Error('no clipboard');
  await navigator.clipboard.writeText(text);
}

export async function copyText(text, done = 'Copiato.') {
  try {
    await writeClipboard(text);
    toast(done, { kind: 'success' });
  } catch (error) {
    await manualCopyDialog('Copia il testo', text);
  }
}

function report(error, prefix) {
  if (error.status === 401) return;
  toast(`${prefix}: ${error.network ? 'connessione assente.' : error.message}`, { kind: 'error' });
}

function fileName(item) {
  const base = item.title.normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^A-Za-z0-9]+/g, '-').replace(/^-|-$/g, '').toLowerCase().slice(0, 40);
  return `${base || 'articolo'}.jpg`;
}

// The request and the photo of an item, fetched once: the item's screen
// calls this when it opens and after every change, the buttons wait for it.
let prepared = null; // { key, promise }

function requestKey(item) {
  return [item.id, item.updated_at, item.photo || '', todayIso()].join('|');
}

export function prepareRequest(item) {
  const key = requestKey(item);
  if (prepared && prepared.key === key) return prepared.promise;
  const promise = (async () => {
    const request = await api.get(`/vinted/items/${item.id}/listing-request`);
    let file = null;
    if (item.photo) {
      try {
        const blob = await api.blob(`/vinted/items/${item.id}/photo?v=${encodeURIComponent(item.photo)}`);
        file = new File([blob], fileName(item), { type: 'image/jpeg' });
      } catch (error) { file = null; } // the text alone, then
    }
    return { text: request.text, file };
  })();
  prepared = { key, promise };
  promise.catch(() => { if (prepared && prepared.key === key) prepared = null; });
  return promise;
}

// Forget what was prepared: the purchase may have changed on another screen.
export function forgetRequest() { prepared = null; }

function canShareFile(file) {
  try {
    return Boolean(navigator.share && navigator.canShare && navigator.canShare({ files: [file] }));
  } catch (error) { return false; }
}

async function sharePhoto(file) {
  try {
    await navigator.share({ files: [file] });
  } catch (error) {
    if (error.name === 'AbortError') return; // share sheet closed
    await shareAgainDialog({
      title: 'Condividi la foto',
      text: 'La richiesta è negli appunti. Tocca qui sotto per condividere la foto con Claude.',
      label: 'Condividi la foto',
      run: () => sharePhoto(file),
    });
  }
}

async function shareText(text) {
  if (!navigator.share) {
    await manualCopyDialog('Richiesta per Claude', text);
    return;
  }
  try {
    await navigator.share({ text });
  } catch (error) {
    if (error.name === 'AbortError') return;
    await shareAgainDialog({
      title: 'Richiesta pronta',
      text: 'Tocca qui sotto per condividerla con Claude.',
      label: 'Condividi',
      run: () => shareText(text),
    });
  }
}

// "Condividi con Claude": with a photo, the request goes to the clipboard
// and the photo to the share sheet; without one, the request is shared.
export async function shareWithClaude(item) {
  let ready;
  try {
    ready = await prepareRequest(item);
  } catch (error) { report(error, 'Richiesta non pronta'); return; }
  if (!ready.file) {
    await shareText(ready.text);
    return;
  }
  let copied = true;
  try { await writeClipboard(ready.text); } catch (error) { copied = false; }
  if (!canShareFile(ready.file)) {
    // A browser that cannot share photos (a computer): the photo is
    // attached in Claude by hand.
    if (copied) toast('Richiesta copiata: incollala in Claude e allega la foto.', { kind: 'success', duration: 7000 });
    else await manualCopyDialog('Richiesta per Claude', ready.text);
    return;
  }
  if (!copied) {
    await manualCopyDialog('Richiesta per Claude', ready.text, ready.file);
    return;
  }
  // At the top: the share sheet that opens now covers the bottom of the screen.
  toast('Richiesta copiata: in Claude tieni premuto nella chat e scegli «Incolla».', {
    kind: 'success', duration: 10000, top: true,
  });
  await sharePhoto(ready.file);
}

export async function copyRequest(item) {
  let ready;
  try {
    ready = await prepareRequest(item);
  } catch (error) { report(error, 'Richiesta non pronta'); return; }
  await copyText(ready.text, item.photo
    ? 'Richiesta copiata: incollala in Claude e allega la foto.'
    : 'Richiesta copiata: incollala in Claude.');
}

// Claude's answer: from the clipboard when the phone allows it, otherwise
// pasted in a box. Resolves to the text, or null.
function pasteDialog(note = null) {
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
      note ? h('p', { class: 'dialog-text' }, note) : null,
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
  // Still the request (copied by «Condividi con Claude»), not the answer.
  if (isRequest(text)) {
    text = await pasteDialog('Negli appunti c’è ancora la richiesta. In Claude copia la risposta (il pulsante copia sotto il messaggio) e incollala qui.');
  } else if (!/TITOLO|DESCRIZIONE/i.test(text)) {
    // Only an answer that looks like Claude's: otherwise ask to paste it.
    text = await pasteDialog();
  }
  if (!text) return null;
  try {
    return await api.post('/vinted/listing/parse', { text });
  } catch (error) {
    report(error, 'Risposta non letta');
    return null;
  }
}

// The request itself, as the server builds it (0.10.0 or 0.11.0).
function isRequest(text) {
  return /Rispondi solo in questo formato/.test(text) && /annuncio Vinted \(Italia\)/.test(text);
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
