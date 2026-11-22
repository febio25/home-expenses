// The purchase and the sale of a Vinted item: the amount on its strip of
// receipt, then the details bar of "Nuova spesa" ("Oggi paga Nastia con
// Carta, su Vinted"), which opens a panel with the less common choices.
// Used by "Nuovo articolo" (vinted-new.js) and "Segna come venduto"
// (vinted-sell.js).

import { h, todayIso, formatSignedEuro, PAYMENT_LABELS } from './ui.js';
import { AMOUNT_SHAPE, summaryDate } from './expense-form.js';

function segmented(options, current, onPick) {
  const group = h('div', { class: 'seg', role: 'group' });
  const draw = (selected) => group.replaceChildren(...options.map((option) => h('button', {
    class: `seg-item${option.value === selected ? ' is-selected' : ''}`,
    type: 'button',
    'aria-pressed': String(option.value === selected),
    onclick: () => { draw(option.value); onPick(option.value); },
  }, option.label)));
  draw(current);
  return group;
}

function amountField({ id, label, onInput }) {
  const error = h('p', { class: 'field-error', id: `${id}-error`, hidden: true });
  const setError = (message) => { error.textContent = message || ''; error.hidden = !message; };
  const input = h('input', {
    class: 'receipt-input', id, type: 'text', inputmode: 'decimal', autocomplete: 'off',
    enterkeyhint: 'done', placeholder: '0,00', 'aria-describedby': `${id}-error`,
    oninput: () => { setError(null); onInput(input.value); },
    onkeydown: (event) => {
      if (event.key === 'Enter') { event.preventDefault(); input.blur(); }
    },
  });
  const receipt = h('div', { class: 'receipt' },
    h('label', { class: 'receipt-label', for: id }, label),
    h('div', { class: 'receipt-line' }, input,
      h('span', { class: 'receipt-currency', 'aria-hidden': 'true' }, '€')));
  function validate() {
    let message = null;
    if (!input.value.trim()) message = 'Inserisci l’importo.';
    else if (!AMOUNT_SHAPE.test(input.value)) message = 'Importo non valido: usa un formato come 12,50.';
    setError(message);
    if (message) {
      input.scrollIntoView({ block: 'center', behavior: 'smooth' });
      input.focus();
    }
    return !message;
  }
  return { element: h('div', {}, receipt, error), input, setError, validate };
}

function detailsBar({ id, describe, isChanged, children }) {
  const text = h('span', { class: 'more-text' });
  const action = h('span', { class: 'more-action', 'aria-hidden': 'true' });
  const bar = h('button', {
    class: 'more-bar', type: 'button', 'aria-controls': id, 'aria-expanded': 'false',
    onclick: () => setOpen(panel.hidden),
  }, text, action);
  const panel = h('div', { class: 'more-body', id, hidden: true },
    ...children,
    h('button', { class: 'btn btn-quiet btn-block more-close', type: 'button', onclick: () => setOpen(false) },
      'Chiudi dettagli'));
  function refresh() {
    text.replaceChildren(...describe());
    bar.classList.toggle('is-changed', isChanged());
    bar.setAttribute('aria-label',
      `Dettagli: ${text.textContent}. Tocca per ${panel.hidden ? 'cambiarli' : 'chiudere'}.`);
  }
  function setOpen(open) {
    panel.hidden = !open;
    bar.setAttribute('aria-expanded', String(open));
    bar.classList.toggle('is-open', open);
    action.textContent = open ? 'Chiudi' : 'Cambia';
    refresh();
  }
  setOpen(false);
  return { element: h('section', { class: 'more', 'aria-label': 'Dettagli' }, bar, panel), refresh };
}

function dateField(id, onPick) {
  const input = h('input', {
    class: 'input', id, type: 'date', value: todayIso(), min: '2000-01-01', max: todayIso(), required: true,
    onchange: () => onPick(input.value || todayIso()),
  });
  return input;
}

const bold = (text) => h('strong', {}, text);

// The expense of an item bought to resell. Merchant "Vinted" unless changed
// (a flea market, a shop): it sits in the panel, it rarely changes.
export function purchaseFields({ users, me }) {
  const state = { amount: '', date: todayIso(), paidBy: me.id, method: 'card', merchant: 'Vinted' };
  const amount = amountField({ id: 'purchase-amount', label: 'Prezzo pagato', onInput: (value) => { state.amount = value; } });
  const dateInput = dateField('purchase-date', (value) => { state.date = value; details.refresh(); });
  const merchantInput = h('input', {
    class: 'input', id: 'purchase-merchant', type: 'text', autocomplete: 'off', autocapitalize: 'words',
    maxLength: 80, value: state.merchant, enterkeyhint: 'done', placeholder: 'Vinted, un mercatino…',
    oninput: () => { state.merchant = merchantInput.value; details.refresh(); },
  });
  const details = detailsBar({
    id: 'purchase-details',
    describe: () => {
      const payer = users.find((user) => user.id === state.paidBy);
      const [lead, when] = summaryDate(state.date);
      const parts = [lead, bold(when), ' paga ', bold(payer ? payer.display_name : '?'),
        ' con ', bold(PAYMENT_LABELS[state.method])];
      const merchant = state.merchant.trim();
      if (merchant) parts.push(merchant.toLocaleLowerCase('it-IT') === 'vinted' ? ', su ' : ', da ', bold(merchant));
      return parts;
    },
    isChanged: () => state.date !== todayIso() || state.paidBy !== me.id || state.method !== 'card'
      || state.merchant.trim() !== 'Vinted',
    children: [
      h('label', { class: 'label', for: 'purchase-date' }, 'Data dell’acquisto'), dateInput,
      h('span', { class: 'label' }, 'Pagato da'),
      segmented(users.map((user) => ({ value: user.id, label: user.display_name })), state.paidBy,
        (value) => { state.paidBy = value; details.refresh(); }),
      h('span', { class: 'label' }, 'Metodo di pagamento'),
      segmented(Object.entries(PAYMENT_LABELS).map(([value, label]) => ({ value, label })), state.method,
        (value) => { state.method = value; details.refresh(); }),
      h('p', { class: 'form-hint' }, 'Pagato con il saldo Vinted? Scegli «Altro».'),
      h('label', { class: 'label', for: 'purchase-merchant' }, 'Dove l’hai comprato'), merchantInput,
    ],
  });
  return {
    element: h('div', {}, amount.element, details.element),
    validate: amount.validate,
    setAmountError: amount.setError,
    toPayload: () => ({
      amount: state.amount.trim(),
      expense_date: state.date,
      paid_by_user_id: state.paidBy,
      payment_method: state.method,
      merchant: state.merchant.trim() || null,
    }),
  };
}

// Cents of what is being typed, only for the live gain: the server does the
// real parsing ("1.250,00" simply shows no gain until saved).
function previewCents(text) {
  const match = /^(\d+)(?:[.,](\d{1,2}))?$/.exec(text.replace(/[€\s]/g, ''));
  if (!match) return null;
  return Number(match[1]) * 100 + Number((match[2] || '').padEnd(2, '0'));
}

// The income of a sale. `costCents`: what the item cost, null for things
// already at home; the gain is shown while the price is typed.
export function saleFields({ users, me, costCents = null }) {
  const state = { amount: '', date: todayIso(), receivedBy: me.id };
  const gain = h('p', { class: 'gain-preview', 'aria-live': 'polite', hidden: true });
  function showGain() {
    const cents = previewCents(state.amount);
    gain.hidden = cents === null;
    if (cents === null) return;
    const value = cents - (costCents || 0);
    gain.replaceChildren(
      h('span', {}, costCents === null ? 'Guadagno (era già vostro)' : 'Guadagno'),
      h('span', { class: value >= 0 ? 'gain' : 'loss' }, formatSignedEuro(value)));
  }
  const amount = amountField({
    id: 'sale-amount', label: 'Prezzo di vendita', onInput: (value) => { state.amount = value; showGain(); },
  });
  const dateInput = dateField('sale-date', (value) => { state.date = value; details.refresh(); });
  const details = detailsBar({
    id: 'sale-details',
    describe: () => {
      const receiver = users.find((user) => user.id === state.receivedBy);
      const [lead, when] = summaryDate(state.date);
      return [lead, bold(when), ' incassa ', bold(receiver ? receiver.display_name : '?')];
    },
    isChanged: () => state.date !== todayIso() || state.receivedBy !== me.id,
    children: [
      h('label', { class: 'label', for: 'sale-date' }, 'Data della vendita'), dateInput,
      h('span', { class: 'label' }, 'Incassa'),
      segmented(users.map((user) => ({ value: user.id, label: user.display_name })), state.receivedBy,
        (value) => { state.receivedBy = value; details.refresh(); }),
    ],
  });
  return {
    element: h('div', {}, amount.element, gain, details.element),
    validate: amount.validate,
    setAmountError: amount.setError,
    focusAmount: () => amount.input.focus({ preventScroll: true }),
    toPayload: () => ({
      amount: state.amount.trim(),
      income_date: state.date,
      received_by_user_id: state.receivedBy,
    }),
  };
}
