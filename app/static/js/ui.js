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

// --- formatting -----------------------------------------------------------

// Italian style groups thousands only from 10.000 up ("1864,93 €" but
// "25.329,82 €"); always grouping keeps amounts in a list comparable.
const euro = new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR', useGrouping: 'always' });

export function formatEuro(cents) {
  return euro.format(cents / 100);
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

export const PAYMENT_LABELS = { card: 'Carta', cash: 'Contanti', other: 'Altro' };

// --- toasts ---------------------------------------------------------------

// Toasts sit at the bottom, where the thumb is, just above whatever is pinned
// there: the Save bar of the entry and edit screens, otherwise the bottom
// navigation, otherwise the edge of the screen. Called again whenever that
// can change (keyboard opening or closing, another screen).
export function placeToasts() {
  const host = document.getElementById('toasts');
  if (!host || !host.firstChild) return;
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
// Returns a function that closes this toast.
export function toast(message, { action = null, kind = 'info', duration = 5000 } = {}) {
  const host = document.getElementById('toasts');
  const element = h('div', { class: `toast toast-${kind}`, role: kind === 'error' ? 'alert' : 'status' },
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
export function dismissToasts() {
  document.querySelectorAll('#toasts .toast:not(.toast-error)').forEach((node) => node.remove());
}

export function vibrate(pattern = 35) {
  if (navigator.vibrate) navigator.vibrate(pattern);
}

// --- dialogs --------------------------------------------------------------

function openDialog(build) {
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
