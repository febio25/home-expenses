// The expense form, shared by "Nuova spesa" and "Modifica spesa".
// Order follows the thumb: amount, merchant, category; the rest has defaults.

import { h, todayIso, latestPlannedIso, isPlanned, PAYMENT_LABELS } from './ui.js';
import { createCategoryPicker } from './category-picker.js';

const MAX_SUGGESTIONS = 6;
// Light check for instant feedback; the server does the real parsing.
// Also used by the income form.
export const AMOUNT_SHAPE = /^\s*€?\s*(\d[\d.,]*|[.,]\d{1,2})\s*€?\s*$/;

function normalize(text) {
  return text.trim().replace(/\s+/g, ' ').toLocaleLowerCase('it-IT');
}

// The merchants to suggest for what is typed: the most used ones when
// nothing is, otherwise those starting with it, then those containing it.
// The one already typed in full is left out. Also used by the purchase of
// a Vinted item (vinted-forms.js, 0.9.0).
export function merchantMatches(merchants, typed, max = MAX_SUGGESTIONS) {
  const query = normalize(typed);
  if (!query) return merchants.slice(0, max); // most used first
  const starts = [];
  const contains = [];
  for (const merchant of merchants) {
    const name = normalize(merchant.name);
    if (name === query) continue; // already typed in full
    if (name.startsWith(query)) starts.push(merchant);
    else if (name.includes(query)) contains.push(merchant);
  }
  return [...starts, ...contains].slice(0, max);
}

// The date part of a details summary as [lead-in, bold value]:
//   expense:   "Oggi", "Ieri", "Il 5 nov", "L'8 nov", "Il 5 nov 2025"
//   recurring: "Da oggi", "Dal 5 nov", "Dall'8 nov"
// Days 1, 8 and 11 start with a vowel sound in Italian, hence the elision.
// Shared with the Vinted purchase and sale forms (vinted-forms.js).
export function summaryDate(iso, recurring = false) {
  const today = todayIso();
  if (iso === today) return recurring ? ['Da ', 'oggi'] : ['', 'Oggi'];
  const yesterday = new Date(`${today}T12:00:00`);
  yesterday.setDate(yesterday.getDate() - 1);
  const yesterdayIso = `${yesterday.getFullYear()}-${String(yesterday.getMonth() + 1).padStart(2, '0')}-${String(yesterday.getDate()).padStart(2, '0')}`;
  if (!recurring && iso === yesterdayIso) return ['', 'Ieri'];
  const date = new Date(`${iso}T12:00:00`);
  const sameYear = iso.slice(0, 4) === today.slice(0, 4);
  const text = date.toLocaleDateString('it-IT', sameYear
    ? { day: 'numeric', month: 'short' }
    : { day: 'numeric', month: 'short', year: 'numeric' });
  const elided = [1, 8, 11].includes(date.getDate());
  if (recurring) return [elided ? 'Dall’' : 'Dal ', text];
  return [elided ? 'L’' : 'Il ', text];
}

export const INTERVALS = [
  { value: 1, label: 'Mese', long: 'ogni mese' },
  { value: 2, label: '2 mesi', long: 'ogni 2 mesi' },
  { value: 3, label: '3 mesi', long: 'ogni 3 mesi' },
  { value: 6, label: '6 mesi', long: 'ogni 6 mesi' },
  { value: 12, label: 'Anno', long: 'ogni anno' },
];

// options: { users, categories, merchants, me, values, onChange, onCategoryName, variant }
// onCategoryName(name|null): the chosen category changed (0.15.0, the Save
// button of Nuova spesa says where the expense goes).
// `categories` must already be the list to show (active ones, plus the
// expense's own category when editing an old expense).
// variant 'recurring': the form of a recurring template. The date becomes
// the next due date, a frequency control is added and the details panel
// starts open, because both matter for a template.
export function createExpenseForm({
  users, categories, merchants, me, values, onChange = () => {}, onCategoryName = () => {}, variant = 'expense',
}) {
  const recurring = variant === 'recurring';
  const state = {
    amount: '',
    merchant: '',
    categoryId: null,
    date: todayIso(),
    paidBy: me.id,
    method: 'card',
    note: '',
    interval: 1,
    // True once the user picks a category by hand: a merchant suggestion
    // must not override that choice.
    categoryTouched: false,
    // True once the user picks a date by hand. Until then the date follows
    // the calendar: an app left open overnight saves today, not yesterday.
    dateTouched: false,
    ...values,
  };
  const changed = () => onChange(getValues());

  // --- amount -------------------------------------------------------------
  const amountInput = h('input', {
    class: 'receipt-input', id: 'expense-amount', type: 'text', inputmode: 'decimal',
    autocomplete: 'off', enterkeyhint: 'next', placeholder: '0,00', value: state.amount,
    'aria-describedby': 'amount-error',
    oninput: () => { state.amount = amountInput.value; setError(amountError, null); changed(); },
    onkeydown: (event) => {
      if (event.key === 'Enter') { event.preventDefault(); merchantInput.focus(); }
    },
  });
  const amountError = h('p', { class: 'field-error', id: 'amount-error', hidden: true });
  const amountBlock = h('div', { class: 'receipt' },
    h('label', { class: 'receipt-label', for: 'expense-amount' }, 'Importo'),
    h('div', { class: 'receipt-line' }, amountInput, h('span', { class: 'receipt-currency', 'aria-hidden': 'true' }, '€')));

  // --- merchant -----------------------------------------------------------
  const merchantInput = h('input', {
    class: 'input', id: 'expense-merchant', type: 'text', autocomplete: 'off',
    autocapitalize: 'words', enterkeyhint: 'done', maxLength: 80,
    placeholder: 'Dove hai pagato?', value: state.merchant,
    oninput: () => {
      state.merchant = merchantInput.value;
      const exact = merchants.find((merchant) => normalize(merchant.name) === normalize(state.merchant));
      if (exact) applyMerchantCategory(exact);
      renderSuggestions();
      changed();
    },
    onkeydown: (event) => {
      if (event.key === 'Enter') { event.preventDefault(); merchantInput.blur(); }
    },
  });
  // One row that scrolls sideways: the categories stay close to the top.
  const suggestions = h('div', { class: 'chips chips-scroll', 'aria-label': 'Esercenti usati di recente' });

  function applyMerchantCategory(merchant) {
    if (state.categoryTouched || !merchant.last_category_id) return;
    if (!categories.some((category) => category.id === merchant.last_category_id)) return;
    state.categoryId = merchant.last_category_id;
    setError(categoryError, null);
    // The bubble shows what the merchant chose: an icon alone could go unnoticed.
    picker.set(state.categoryId, { bubble: true });
  }

  // 0.15.0: the merchant chosen (tapped, or typed in full) stays first in
  // the row, coloured like a chosen category; tapping it again clears it.
  function renderSuggestions() {
    const exact = state.merchant.trim()
      ? merchants.find((merchant) => normalize(merchant.name) === normalize(state.merchant))
      : null;
    const chips = merchantMatches(merchants, state.merchant).map((merchant) => h('button', {
      class: 'chip', type: 'button',
      onclick: () => {
        state.merchant = merchant.name;
        merchantInput.value = merchant.name;
        applyMerchantCategory(merchant);
        renderSuggestions();
        changed();
      },
    }, merchant.name));
    if (exact) {
      chips.unshift(h('button', {
        class: 'chip is-selected', type: 'button', 'aria-pressed': 'true',
        'aria-label': `${exact.name}, scelto: tocca per toglierlo`,
        onclick: () => {
          state.merchant = '';
          merchantInput.value = '';
          renderSuggestions();
          changed();
        },
      }, exact.name));
    }
    suggestions.replaceChildren(...chips);
    suggestions.hidden = suggestions.childElementCount === 0;
    if (exact) suggestions.scrollLeft = 0;
  }

  // --- category (icons, 0.15.0: category-picker.js) ----------------------
  const categoryError = h('p', { class: 'field-error', hidden: true });
  const asItems = (list) => list.map((category) => ({ key: category.id, name: category.name, icon: category.icon }));
  const picker = createCategoryPicker({
    items: asItems(categories),
    selected: state.categoryId,
    labelId: 'category-label',
    onName: onCategoryName,
    onPick: (id) => {
      state.categoryId = id;
      state.categoryTouched = true;
      setError(categoryError, null);
      changed();
    },
  });
  const categoryGrid = picker.grid;
  function renderCategories() { picker.set(state.categoryId); }

  // --- details (date, paid by, method, note) ------------------------------
  // Same window as the server: from 2000 to a year ahead (0.12.0: a direct
  // debit or a bill whose date is known can be entered now). A recurring
  // template's next due date is naturally in the future, so it has no upper
  // limit.
  const dateInput = h('input', {
    class: 'input', id: 'expense-date', type: 'date', value: state.date, required: true, min: '2000-01-01',
    onchange: () => {
      state.date = dateInput.value || todayIso();
      state.dateTouched = Boolean(dateInput.value);
      renderDetailsSummary();
      changed();
    },
  });
  function updateDateLimit() {
    if (!recurring) dateInput.max = latestPlannedIso();
  }
  // Shown under the date while it is still to come.
  const dateHint = h('p', { class: 'field-note', id: 'expense-date-hint', hidden: true },
    'Data futura: la spesa conta già nel suo mese e porta l’etichetta «Prevista» fino a quel giorno.');

  function segmented(name, options, current, onPick) {
    const group = h('div', { class: 'seg', role: 'group' });
    const draw = (selected) => group.replaceChildren(...options.map((option) => h('button', {
      class: `seg-item${option.value === selected ? ' is-selected' : ''}`,
      type: 'button',
      'aria-pressed': String(option.value === selected),
      onclick: () => { draw(option.value); onPick(option.value); },
    }, option.label)));
    draw(current);
    group.redraw = draw;
    return group;
  }

  const paidByGroup = segmented('paid-by',
    users.map((user) => ({ value: user.id, label: user.display_name })),
    state.paidBy,
    (value) => { state.paidBy = value; renderDetailsSummary(); changed(); });
  const methodGroup = segmented('method',
    Object.entries(PAYMENT_LABELS).map(([value, label]) => ({ value, label })),
    state.method,
    (value) => { state.method = value; renderDetailsSummary(); changed(); });
  const noteInput = h('input', {
    class: 'input', id: 'expense-note', type: 'text', autocomplete: 'off', maxLength: 300,
    placeholder: 'Facoltativa', value: state.note, enterkeyhint: 'done',
    oninput: () => { state.note = noteInput.value; renderDetailsSummary(); changed(); },
    onkeydown: (event) => {
      if (event.key === 'Enter') { event.preventDefault(); noteInput.blur(); }
    },
  });

  const intervalGroup = recurring ? segmented('interval', INTERVALS, state.interval,
    (value) => { state.interval = value; renderDetailsSummary(); changed(); }) : null;
  if (intervalGroup) intervalGroup.classList.add('seg-compact');

  // One full-width bar sums up the details ("Oggi, paga Nastia, carta") and
  // opens the panel with the controls. The bar is highlighted when something
  // differs from the default, so a changed date or payer is hard to miss.
  const summaryText = h('span', { class: 'more-text' });
  const summaryAction = h('span', { class: 'more-action', 'aria-hidden': 'true' });
  const bar = h('button', {
    class: 'more-bar', type: 'button', 'aria-controls': 'expense-details', 'aria-expanded': 'false',
    onclick: () => setOpen(panel.hidden),
  }, summaryText, summaryAction);
  const panel = h('div', { class: 'more-body', id: 'expense-details', hidden: true });

  function setOpen(open) {
    panel.hidden = !open;
    bar.setAttribute('aria-expanded', String(open));
    bar.classList.toggle('is-open', open);
    summaryAction.textContent = open ? 'Chiudi' : 'Cambia';
    renderDetailsSummary();
  }

  // "Oggi paga Fabio con Carta": values in bold, joining words in plain text.
  function renderDetailsSummary() {
    const payer = users.find((user) => user.id === state.paidBy);
    const [lead, when] = summaryDate(state.date, recurring);
    const bold = (text) => h('strong', {}, text);
    const parts = [lead, bold(when)];
    if (recurring) {
      const interval = INTERVALS.find((item) => item.value === state.interval)?.long || '';
      parts.push(', ', bold(interval), ',');
    }
    parts.push(' paga ', bold(payer ? payer.display_name : '?'), ' con ', bold(PAYMENT_LABELS[state.method]));
    if (state.note.trim()) parts.push(', ', bold('con nota'));
    const planned = !recurring && isPlanned(state.date);
    if (planned) parts.push(', ', bold('spesa prevista'));
    dateHint.hidden = !planned;
    summaryText.replaceChildren(...parts);
    const changedFromDefault = !recurring && (state.date !== todayIso()
      || state.paidBy !== me.id || state.method !== 'card' || Boolean(state.note.trim()));
    bar.classList.toggle('is-changed', changedFromDefault);
    bar.setAttribute('aria-label', `Dettagli: ${summaryText.textContent}. Tocca per ${panel.hidden ? 'cambiarli' : 'chiudere'}.`);
  }

  panel.append(
    h('label', { class: 'label', for: 'expense-date' }, recurring ? 'Prossima scadenza' : 'Data'), dateInput,
    ...(recurring ? [] : [dateHint]),
    ...(recurring ? [h('span', { class: 'label' }, 'Si ripete ogni'), intervalGroup] : []),
    h('span', { class: 'label' }, recurring ? 'Paga' : 'Pagato da'), paidByGroup,
    h('span', { class: 'label' }, 'Metodo di pagamento'), methodGroup,
    h('label', { class: 'label', for: 'expense-note' }, 'Nota'), noteInput,
    h('button', { class: 'btn btn-quiet btn-block more-close', type: 'button', onclick: () => setOpen(false) },
      'Chiudi dettagli'));

  const details = h('section', { class: 'more', 'aria-label': 'Dettagli della spesa' }, bar, panel);

  // --- assembly -----------------------------------------------------------
  const element = h('div', { class: 'expense-form' },
    amountBlock, amountError,
    h('label', { class: 'label', for: 'expense-merchant' }, 'Esercente'),
    merchantInput, suggestions,
    picker.label,
    categoryGrid, categoryError,
    details);

  function setError(node, message) {
    node.textContent = message || '';
    node.hidden = !message;
  }

  function getValues() {
    return { ...state };
  }

  // Body for POST /expenses and PATCH /expenses/{id}.
  function toPayload() {
    return {
      amount: state.amount.trim(),
      category_id: state.categoryId,
      merchant: state.merchant.trim() || null,
      note: state.note.trim() || null,
      expense_date: state.date,
      paid_by_user_id: state.paidBy,
      payment_method: state.method,
    };
  }

  // Body for POST /recurring and PATCH /recurring/{id}.
  function toRecurringPayload() {
    const { expense_date: nextDue, ...rest } = toPayload();
    return { ...rest, next_due: nextDue, interval_months: state.interval };
  }

  function validate() {
    let firstInvalid = null;
    if (!state.amount.trim()) {
      setError(amountError, 'Inserisci l’importo.');
      firstInvalid = amountInput;
    } else if (!AMOUNT_SHAPE.test(state.amount)) {
      setError(amountError, 'Importo non valido: usa un formato come 12,50.');
      firstInvalid = amountInput;
    }
    if (!state.categoryId) {
      setError(categoryError, 'Scegli una categoria.');
      firstInvalid = firstInvalid || categoryGrid;
    }
    if (firstInvalid) {
      firstInvalid.scrollIntoView({ block: 'center', behavior: 'smooth' });
      if (firstInvalid === amountInput) amountInput.focus();
      return false;
    }
    return true;
  }

  function showAmountError(message) {
    setError(amountError, message);
    amountInput.scrollIntoView({ block: 'center' });
  }

  function reset(next) {
    Object.assign(state, {
      amount: '', merchant: '', categoryId: null, date: todayIso(), paidBy: me.id,
      method: 'card', note: '', interval: 1, categoryTouched: false, dateTouched: false, ...next,
    });
    updateDateLimit();
    amountInput.value = state.amount;
    merchantInput.value = state.merchant;
    dateInput.value = state.date;
    noteInput.value = state.note;
    paidByGroup.redraw(state.paidBy);
    methodGroup.redraw(state.method);
    if (intervalGroup) intervalGroup.redraw(state.interval);
    setOpen(recurring);
    setError(amountError, null);
    setError(categoryError, null);
    renderSuggestions();
    renderCategories();
    renderDetailsSummary();
  }

  function setMerchants(list) {
    merchants = list;
    // The name typed may only now be a known merchant (the fresh list
    // arrived after the typing): its category, as if typed now.
    const exact = state.merchant.trim()
      ? merchants.find((merchant) => normalize(merchant.name) === normalize(state.merchant))
      : null;
    if (exact && state.categoryId === null) {
      applyMerchantCategory(exact);
      if (state.categoryId !== null) changed();
    }
    renderSuggestions();
  }

  // Categories changed elsewhere (added, renamed, deactivated by the other
  // person). A choice that disappeared is cleared, never silently replaced.
  function setCategories(list) {
    categories = list;
    if (state.categoryId && !categories.some((category) => category.id === state.categoryId)) {
      state.categoryId = null;
      state.categoryTouched = false;
      changed();
    }
    picker.set(state.categoryId);
    picker.setItems(asItems(categories));
  }

  // The calendar moved on (app reopened the next day). Labels like "Oggi"
  // and "Ieri" are recomputed; an untouched date becomes today.
  function syncToday() {
    if (!recurring && !state.dateTouched && state.date !== todayIso()) {
      state.date = todayIso();
      dateInput.value = state.date;
    }
    updateDateLimit();
    renderDetailsSummary();
  }

  updateDateLimit();
  renderSuggestions();
  renderCategories();
  setOpen(recurring);
  renderDetailsSummary();

  return {
    element, getValues, toPayload, toRecurringPayload, validate, reset, setMerchants, setCategories,
    syncToday, showAmountError, categoryName: () => picker.name(),
    focusAmount: () => amountInput.focus({ preventScroll: true }),
  };
}
