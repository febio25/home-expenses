// Small DOM helpers, formatters, toasts and dialogs shared by all views.

// --- DOM ------------------------------------------------------------------

// h('button', { class: 'btn', onclick: fn, disabled: true }, 'Salva')
export function h(tag, attrs = {}, ...children) {
  const element = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (name.startsWith('on') && typeof value === 'function') {
      element.addEventListener(name.slice(2), value);
    } else if (name === 'class') {
      element.className = value;
    } else if (name === 'dataset') {
      Object.assign(element.dataset, value);
    } else if (name in element && name !== 'list' && name !== 'form') {
      element[name] = value;
    } else {
      element.setAttribute(name, value === true ? '' : value);
    }
  }
  element.append(...children.flat().filter((child) => child !== null && child !== undefined && child !== false));
  return element;
}

// Static, trusted SVG markup only (never user data).
const ICONS = {
  plus: '<path d="M12 5v14M5 12h14"/>',
  list: '<path d="M8 6h12M8 12h12M8 18h12"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/>',
  chart: '<path d="M5 20V10M12 20V4M19 20v-7"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3h.1a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9v.1a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  left: '<path d="M15 5l-7 7 7 7"/>',
  right: '<path d="M9 5l7 7-7 7"/>',
  // 0.14.0: move a category up or down in Impostazioni.
  up: '<path d="M5 15l7-7 7 7"/>',
  down: '<path d="M5 9l7 7 7-7"/>',
  // 0.8.0, Vinted section: price tag (tab), search, camera, photo, close,
  // sold check (0.16.0: the enlarge mark gave way to a pencil).
  // 0.16.0: Tabler `tag` (MIT, see below), the same drawing as the «Vinted»
  // income category, so the tab and the category look alike.
  tag: '<path d="M6.5 7.5a1 1 0 1 0 2 0a1 1 0 1 0 -2 0"/><path d="M3 6v5.172a2 2 0 0 0 .586 1.414l7.71 7.71a2.41 2.41 0 0 0 3.408 0l5.592 -5.592a2.41 2.41 0 0 0 0 -3.408l-7.71 -7.71a2 2 0 0 0 -1.414 -.586h-5.172a3 3 0 0 0 -3 3"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.6-3.6"/>',
  camera: '<path d="M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z"/><circle cx="12" cy="13.5" r="3.5"/>',
  image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M21 16l-5-5-9 9"/>',
  close: '<path d="M6 6l12 12M18 6L6 18"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  // 0.10.0, the filters of the Vinted list: not on Vinted yet, on sale,
  // sold, all. From Tabler Icons 3.52.0 (building-store, coin-euro,
  // stack-2), MIT License, Copyright (c) 2020-2026 Pawel Kuna: see
  // THIRD-PARTY-NOTICES.md. 0.16.0: «Da pubblicare» is an hourglass
  // (Tabler `hourglass`, 3.53.0), in place of the cloud with the arrow.
  hourglass: '<path d="M6.5 7h11"/><path d="M6.5 17h11"/><path d="M6 20v-2a6 6 0 1 1 12 0v2a1 1 0 0 1 -1 1h-10a1 1 0 0 1 -1 -1"/><path d="M6 4v2a6 6 0 1 0 12 0v-2a1 1 0 0 0 -1 -1h-10a1 1 0 0 0 -1 1"/>',
  store: '<path d="M3 21l18 0"/><path d="M3 7v1a3 3 0 0 0 6 0v-1m0 1a3 3 0 0 0 6 0v-1m0 1a3 3 0 0 0 6 0v-1h-18l2 -4h14l2 4"/><path d="M5 21l0 -10.15"/><path d="M19 21l0 -10.15"/><path d="M9 21v-4a2 2 0 0 1 2 -2h2a2 2 0 0 1 2 2v4"/>',
  'coin-euro': '<path d="M3 12a9 9 0 1 0 18 0a9 9 0 1 0 -18 0"/><path d="M14.401 8c-.669 -.628 -1.5 -1 -2.401 -1c-2.21 0 -4 2.239 -4 5s1.79 5 4 5c.9 0 1.731 -.372 2.4 -1"/><path d="M7 10.5h4"/><path d="M7 13.5h4"/>',
  stack: '<path d="M12 4l-8 4l8 4l8 -4l-8 -4"/><path d="M4 12l8 4l8 -4"/><path d="M4 16l8 4l8 -4"/>',
  // 0.11.0, the steps of the "Annuncio" card: share, pencil, clipboard-text,
  // also from Tabler Icons 3.52.0 (same license).
  share: '<path d="M3 12a3 3 0 1 0 6 0a3 3 0 1 0 -6 0"/><path d="M15 6a3 3 0 1 0 6 0a3 3 0 1 0 -6 0"/><path d="M15 18a3 3 0 1 0 6 0a3 3 0 1 0 -6 0"/><path d="M8.7 10.7l6.6 -3.4"/><path d="M8.7 13.3l6.6 3.4"/>',
  pencil: '<path d="M4 20h4l10.5 -10.5a2.828 2.828 0 1 0 -4 -4l-10.5 10.5v4"/><path d="M13.5 6.5l4 4"/>',
  clipboard: '<path d="M9 5h-2a2 2 0 0 0 -2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2 -2v-12a2 2 0 0 0 -2 -2h-2"/><path d="M9 5a2 2 0 0 1 2 -2h2a2 2 0 0 1 2 2a2 2 0 0 1 -2 2h-2a2 2 0 0 1 -2 -2"/><path d="M9 12h6"/><path d="M9 16h6"/>',
  // 0.15.0, Tabler `download`: «Scarica» in Impostazioni → Esporta.
  download: '<path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2 -2v-2"/><path d="M7 11l5 5l5 -5"/><path d="M12 4l0 12"/>',
};

export function icon(name) {
  const wrapper = document.createElement('span');
  wrapper.className = 'icon';
  wrapper.setAttribute('aria-hidden', 'true');
  wrapper.innerHTML =
    `<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" ` +
    `stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name]}</svg>`;
  return wrapper;
}

// Head of the four main screens (0.8.0): title on the left; on the right
// who is signed in and the settings, which left the bottom bar to make room
// for Vinted. An icon without text, but a full-size tap target and a name
// for screen readers.
export function mainHead(title, name) {
  return h('header', { class: 'page-head has-tools' },
    h('h1', { class: 'page-title' }, title),
    h('div', { class: 'page-tools' },
      name ? h('span', { class: 'page-who' }, name) : null,
      h('a', {
        class: 'page-gear', href: '/impostazioni', 'aria-label': 'Impostazioni', dataset: { link: '' },
      }, icon('gear'))));
}

// --- formatting -----------------------------------------------------------

// Italian style groups thousands only from 10.000 up ("1864,93 €" but
// "25.329,82 €"); always grouping keeps amounts in a list comparable.
const euro = new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', useGrouping: 'always' });

export function formatEuro(cents) {
  return euro.format(cents / 100);
}

// 0.16.0: a big total with a smaller, lighter «€» (styled by .eur in
// app.css), as in the amount field of Nuova spesa. The text read is the
// same as formatEuro's: "897,57 €" with its no-break space.
// signed: "+1.250,00 €" / "−80,00 €", as formatSignedEuro.
export function euroParts(cents, { signed = false } = {}) {
  const text = signed ? formatSignedEuro(cents) : formatEuro(cents);
  const cut = text.lastIndexOf('\u00a0');
  if (cut < 0) return [text];
  return [h('span', { class: 'eur-num' }, text.slice(0, cut)), h('span', { class: 'eur' }, text.slice(cut))];
}

// 0.17.0: whole euros, for estimates ("252 €", "3.029 €").
const euroWhole = new Intl.NumberFormat('it-IT', {
  style: 'currency', currency: 'EUR', useGrouping: 'always', maximumFractionDigits: 0, minimumFractionDigits: 0,
});

export function formatEuroWhole(cents) {
  return euroWhole.format(Math.round(cents / 100));
}

// 0.17.0: a date near today in words, for the due dates of the recurring
// items: "oggi", "domani", "dopodomani", "tra 5 giorni", "ieri", "3 giorni
// fa", up to two weeks; further away null (the caller writes the date).
export function relativeDay(iso) {
  const [y1, m1, d1] = todayIso().split('-').map(Number);
  const [y2, m2, d2] = iso.split('-').map(Number);
  const days = Math.round((Date.UTC(y2, m2 - 1, d2) - Date.UTC(y1, m1 - 1, d1)) / 86400000);
  if (Math.abs(days) > 14) return null;
  if (days === 0) return 'oggi';
  if (days === 1) return 'domani';
  if (days === 2) return 'dopodomani';
  if (days === -1) return 'ieri';
  return days > 0 ? `tra ${days} giorni` : `${-days} giorni fa`;
}

// A difference: "+1.250,00 €", "−80,00 €" (true minus sign), "0,00 €".
export function formatSignedEuro(cents) {
  if (!cents) return euro.format(0);
  return `${cents > 0 ? '+' : '−'}${euro.format(Math.abs(cents) / 100)}`;
}

// Share of a total as "23%"; a share that rounds to zero reads "<1%", not "0%".
export function formatShare(part, total) {
  if (!total || !part) return '0%';
  const percent = Math.round((part / total) * 100);
  return percent === 0 ? '<1%' : `${percent}%`;
}

// 1250 -> "12,50" (for prefilling the amount field)
export function centsToInput(cents) {
  return `${Math.floor(cents / 100)},${String(cents % 100).padStart(2, '0')}`;
}

function pad(number) {
  return String(number).padStart(2, '0');
}

// Local calendar date, not UTC: at 00:30 in Italy "today" is still today.
// Idempotency key for writes that may be retried after a network error.
export function newUuid() {
  if (crypto.randomUUID) return crypto.randomUUID();
  // randomUUID needs a secure context; plain-HTTP LAN tests fall back here.
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
}

export function todayIso() {
  const now = new Date();
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

export function currentMonth() {
  return todayIso().slice(0, 7);
}

export function shiftMonth(month, delta) {
  const [year, number] = month.split('-').map(Number);
  const date = new Date(year, number - 1 + delta, 1);
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}`;
}

// An expense may be dated ahead of time (0.12.0), as far as this many months
// from today: the same window as the server (app/dates.py).
export const PLANNED_MONTHS_AHEAD = 12;

// Last day an expense may be dated. Day clamped to the length of the month,
// like the server: 31 Aug + 6 months = 28 Feb.
export function latestPlannedIso() {
  const [year, month, day] = todayIso().split('-').map(Number);
  const index = year * 12 + (month - 1) + PLANNED_MONTHS_AHEAD;
  const targetYear = Math.floor(index / 12);
  const targetMonth = index % 12; // 0-based
  const lastDay = new Date(targetYear, targetMonth + 1, 0).getDate();
  return `${targetYear}-${pad(targetMonth + 1)}-${pad(Math.min(day, lastDay))}`;
}

export function latestPlannedMonth() {
  return latestPlannedIso().slice(0, 7);
}

// A date still to come: its expense is "Prevista" until the day arrives.
export function isPlanned(iso) {
  return iso > todayIso();
}

function parseIso(iso) {
  const [year, month, day] = iso.split('-').map(Number);
  return new Date(year, month - 1, day || 1);
}

export function monthLabel(month) {
  return parseIso(`${month}-01`).toLocaleDateString('it-IT', { month: 'long', year: 'numeric' });
}

export function dayLabel(iso) {
  if (iso === todayIso()) return 'Oggi';
  return parseIso(iso).toLocaleDateString('it-IT', { weekday: 'long', day: 'numeric', month: 'long' });
}

export function shortDate(iso) {
  return parseIso(iso).toLocaleDateString('it-IT', { day: 'numeric', month: 'long', year: 'numeric' });
}

// "10 nov": the day of a row in the search results, under a month heading.
export function dayMonthShort(iso) {
  return parseIso(iso).toLocaleDateString('it-IT', { day: 'numeric', month: 'short' });
}

export const PAYMENT_LABELS = { card: 'Carta', cash: 'Contanti', other: 'Altro' };

// --- toasts ---------------------------------------------------------------

// Toasts sit at the bottom, where the thumb is, just above whatever is pinned
// there: the Save bar of the entry and edit screens, otherwise the bottom
// navigation, otherwise the edge of the screen. Called again whenever that
// can change (keyboard opening or closing, another screen).
export function placeToasts() {
  const host = document.getElementById('toasts');
  if (!host || !host.firstChild) return;
  if (host.classList.contains('toasts-top')) { // see toast({ top: true })
    host.style.bottom = '';
    return;
  }
  const visible = (node) => Boolean(node && node.getClientRects().length);
  const footer = document.querySelector('#view .footer-bar');
  const nav = document.getElementById('nav');
  const anchor = visible(footer) ? footer : visible(nav) ? nav : null;
  if (anchor) {
    const gap = window.innerHeight - anchor.getBoundingClientRect().top;
    host.style.bottom = `${Math.max(0, Math.round(gap)) + 8}px`;
  } else {
    host.style.bottom = 'calc(12px + env(safe-area-inset-bottom))';
  }
}

// toast('Spesa salvata', { action: { label: 'Annulla', run: fn }, kind: 'error' })
// Tapping the message closes it at once: a toast never has to be waited out.
// top: true (0.13.0) puts it at the top of the screen, for a message shown
// while the phone's share sheet covers the bottom half.
// Returns a function that closes this toast.
export function toast(message, { action = null, kind = 'info', duration = 5000, top = false } = {}) {
  const host = document.getElementById('toasts');
  host.classList.toggle('toasts-top', top);
  const element = h('div', { class: `toast toast-${kind}`, role: kind === 'error' || kind === 'warning' ? 'alert' : 'status' },
    h('span', { class: 'toast-text' }, message));
  const close = () => element.remove();
  element.addEventListener('click', close);
  if (action) {
    element.append(h('button', {
      class: 'toast-action',
      type: 'button',
      onclick: (event) => { event.stopPropagation(); close(); action.run(); },
    }, action.label));
  }
  host.replaceChildren(element); // one toast at a time: the newest wins
  placeToasts();
  setTimeout(close, action ? Math.max(duration, 7000) : duration);
  return close;
}

// Close the visible toast, unless it reports an error. Used when the user
// starts the next action: the confirmation of the previous one has done its job.
// A warning (0.14.0: "sembra un doppione") stays too: it must be read.
export function dismissToasts() {
  document.querySelectorAll('#toasts .toast:not(.toast-error):not(.toast-warning)').forEach((node) => node.remove());
}

export function vibrate(pattern = 35) {
  if (navigator.vibrate) navigator.vibrate(pattern);
}

// --- dialogs --------------------------------------------------------------

export function openDialog(build) {
  return new Promise((resolve) => {
    const dialog = h('dialog', { class: 'dialog' });
    let result = null;
    const finish = (value) => { result = value; dialog.close(); };
    dialog.addEventListener('close', () => { dialog.remove(); resolve(result); });
    // Tap on the dimmed backdrop cancels.
    dialog.addEventListener('click', (event) => { if (event.target === dialog) finish(null); });
    dialog.append(build(finish));
    document.body.append(dialog);
    dialog.showModal();
  });
}

// Resolves to true when confirmed.
export async function confirmDialog({ title, message, confirmLabel, danger = false }) {
  const answer = await openDialog((finish) => h('div', { class: 'dialog-body' },
    h('h2', { class: 'dialog-title' }, title),
    message ? h('p', { class: 'dialog-text' }, message) : null,
    h('div', { class: 'dialog-actions' },
      h('button', { class: 'btn btn-quiet', type: 'button', onclick: () => finish(null) }, 'Annulla'),
      h('button', {
        class: `btn ${danger ? 'btn-danger' : 'btn-primary'}`,
        type: 'button',
        onclick: () => finish(true),
      }, confirmLabel))));
  return answer === true;
}

// Password input with a "Mostra / Nascondi" toggle, so a password typed on
// a phone keyboard can be checked before sending. Returns { element, input }.
export function passwordField({ id, autocomplete, minLength = null }) {
  const input = h('input', {
    class: 'input pw-input', id, type: 'password', required: true, minLength,
    autocomplete, autocapitalize: 'none',
  });
  // Attributes, not properties: where `autocorrect` is a boolean property,
  // assigning the string 'off' would turn it on.
  input.setAttribute('autocorrect', 'off');
  input.setAttribute('spellcheck', 'false');
  const toggle = h('button', {
    class: 'pw-toggle', type: 'button', 'aria-controls': id, 'aria-pressed': 'false',
    onclick: () => {
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      toggle.textContent = show ? 'Nascondi' : 'Mostra';
      toggle.setAttribute('aria-pressed', String(show));
    },
  }, 'Mostra');
  return { element: h('div', { class: 'pw-field' }, input, toggle), input };
}

// Asks for a new password twice. Resolves to the password, or null.
export function newPasswordDialog({ title, confirmLabel = 'Imposta', minLength = 8 }) {
  return openDialog((finish) => {
    const first = passwordField({ id: 'dialog-pw', autocomplete: 'new-password', minLength });
    const again = passwordField({ id: 'dialog-pw-again', autocomplete: 'new-password', minLength });
    const error = h('p', { class: 'form-error', role: 'alert', hidden: true });
    const form = h('form', {
      class: 'dialog-body',
      onsubmit: (event) => {
        event.preventDefault();
        const problem = passwordProblem(first.input.value, again.input.value, minLength);
        if (problem) {
          error.textContent = problem;
          error.hidden = false;
          return;
        }
        finish(first.input.value);
      },
    },
      h('h2', { class: 'dialog-title' }, title),
      h('label', { class: 'label', for: 'dialog-pw' }, `Nuova password (almeno ${minLength} caratteri)`),
      first.element,
      h('label', { class: 'label', for: 'dialog-pw-again' }, 'Ripeti la password'),
      again.element,
      error,
      h('div', { class: 'dialog-actions' },
        h('button', { class: 'btn btn-quiet', type: 'button', onclick: () => finish(null) }, 'Annulla'),
        h('button', { class: 'btn btn-primary', type: 'submit' }, confirmLabel)));
    setTimeout(() => first.input.focus(), 50);
    return form;
  });
}

// Message for a new password and its confirmation, or null when fine.
export function passwordProblem(password, repeated, minLength = 8) {
  if (password.length < minLength) return `La password deve avere almeno ${minLength} caratteri.`;
  if (password !== repeated) return 'Le due password non coincidono.';
  return null;
}

// Resolves to the entered text, or null when cancelled.
// `options`: when given, shows a select instead of a text input.
export function promptDialog({ title, label, value = '', confirmLabel = 'Salva', type = 'text', options = null, minLength = 1 }) {
  return openDialog((finish) => {
    const field = options
      ? h('select', { class: 'input', id: 'dialog-field' },
        options.map((option) => h('option', { value: String(option.value) }, option.label)))
      : h('input', {
        class: 'input', id: 'dialog-field', type, value, required: true,
        minLength, autocomplete: type === 'password' ? 'new-password' : 'off',
      });
    const form = h('form', {
      class: 'dialog-body',
      onsubmit: (event) => {
        event.preventDefault();
        // Passwords are taken exactly as typed: spaces are characters too.
        const text = options || type === 'password' ? field.value : field.value.trim();
        if (text.length >= minLength) finish(text);
      },
    },
      h('h2', { class: 'dialog-title' }, title),
      h('label', { class: 'label', for: 'dialog-field' }, label),
      field,
      h('div', { class: 'dialog-actions' },
        h('button', { class: 'btn btn-quiet', type: 'button', onclick: () => finish(null) }, 'Annulla'),
        h('button', { class: 'btn btn-primary', type: 'submit' }, confirmLabel)));
    setTimeout(() => { field.focus(); if (field.select) field.select(); }, 50);
    return form;
  });
}

// One choice from a short list (an expense or income to link to a Vinted
// item). options: [{ value, label, meta, amount }]. Resolves to the value
// of the option picked, or null.
export function choiceDialog({ title, text = null, options, empty = 'Niente da scegliere.' }) {
  return openDialog((finish) => h('div', { class: 'dialog-body' },
    h('h2', { class: 'dialog-title' }, title),
    text ? h('p', { class: 'dialog-text' }, text) : null,
    options.length
      ? h('div', { class: 'dialog-list' }, options.map((option) => h('button', {
        class: 'dialog-option', type: 'button', onclick: () => finish(option.value),
      },
      h('span', { class: 'dialog-option-main' },
        h('span', { class: 'dialog-option-title' }, option.label),
        option.meta ? h('span', { class: 'dialog-option-meta' }, option.meta) : null),
      option.amount ? h('span', { class: 'dialog-option-amount' }, option.amount) : null)))
      : h('p', { class: 'dialog-text' }, empty),
    h('div', { class: 'dialog-actions' },
      h('button', { class: 'btn btn-quiet', type: 'button', onclick: () => finish(null) }, 'Annulla'))));
}

// Loading / error placeholders used while a view fetches its data.
export function loadingBlock() {
  return h('p', { class: 'boot' }, 'Caricamento…');
}

export function errorBlock(error, retry) {
  return h('div', { class: 'empty' },
    h('p', { class: 'empty-title' }, error.network ? 'Server non raggiungibile' : 'Qualcosa non ha funzionato'),
    h('p', { class: 'empty-text' }, error.network
      ? 'Controlla che Tailscale sia attivo sul telefono, poi riprova.'
      : error.message),
    h('button', { class: 'btn btn-primary', type: 'button', onclick: retry }, 'Riprova'));
}
