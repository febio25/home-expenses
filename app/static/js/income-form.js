// The income form, shared by "Nuova entrata", "Modifica entrata" and the
// recurring income templates. A short form, all in view: amount, category
// from the fixed list, date, who receives it, note. Incomes are entered a
// few times a month, so there is no draft and no folded details panel as
// on the expense screen.

import { h, todayIso } from './ui.js';
import { AMOUNT_SHAPE, INTERVALS, variableCheck } from './expense-form.js';
import { createCategoryPicker } from './category-picker.js';

// options: { users, categories, me, values, onChange, onCategoryName, variant }
// `categories` is the fixed list [{ code, name, icon }]. onCategoryName:
// as in the expense form (0.15.0).
// variant 'recurring': the form of a recurring template. The date becomes
// the next due date (no upper limit) and "Si ripete ogni" is added.
export function createIncomeForm({
  users, categories, me, values, onChange = () => {}, onCategoryName = () => {}, variant = 'income',
}) {
  const recurring = variant === 'recurring';
  const state = {
    amount: '', category: null, date: todayIso(), receivedBy: me.id, note: '', interval: 1, variable: false,
    ...values,
  };

  function setError(node, message) {
    node.textContent = message || '';
    node.hidden = !message;
  }

  // --- amount -------------------------------------------------------------
  const amountInput = h('input', {
    class: 'receipt-input', id: 'income-amount', type: 'text', inputmode: 'decimal',
    autocomplete: 'off', enterkeyhint: 'done', placeholder: '0,00', value: state.amount,
    'aria-describedby': 'income-amount-error',
    oninput: () => { state.amount = amountInput.value; setError(amountError, null); onChange(); },
    onkeydown: (event) => {
      if (event.key === 'Enter') { event.preventDefault(); amountInput.blur(); }
    },
  });
  const amountError = h('p', { class: 'field-error', id: 'income-amount-error', hidden: true });
  const amountBlock = h('div', { class: 'receipt' },
    h('label', { class: 'receipt-label', for: 'income-amount' }, recurring ? 'Importo previsto' : 'Importo'),
    h('div', { class: 'receipt-line' }, amountInput,
      h('span', { class: 'receipt-currency', 'aria-hidden': 'true' }, '€')));
  const variableBox = recurring ? variableCheck('income-variable', state.variable,
    'Stipendio con straordinari o bonus: l’importo è una stima, scritta con «circa». Alla scadenza lo correggi.',
    (checked) => { state.variable = checked; onChange(); }) : null;

  // --- category (fixed list, icons from 0.15.0) -------------------------------
  const categoryError = h('p', { class: 'field-error', hidden: true });
  const picker = createCategoryPicker({
    items: categories.map((category) => ({ key: category.code, name: category.name, icon: category.icon })),
    selected: state.category,
    labelId: 'income-category-label',
    onName: onCategoryName,
    onPick: (code) => {
      state.category = code;
      setError(categoryError, null);
      onChange();
    },
  });
  const categoryGrid = picker.grid;

  // --- date, frequency, received by, note -------------------------------------
  // Same window as the server: from 2000 to today. A template's next due
  // date is naturally in the future, so it has no upper limit.
  const dateInput = h('input', {
    class: 'input', id: 'income-date', type: 'date', value: state.date, required: true,
    min: '2000-01-01', max: recurring ? null : todayIso(),
    onchange: () => {
      state.date = dateInput.value || todayIso();
      dateInput.value = state.date;
      onChange();
    },
  });

  function segmented(options, current, labelId, onPick) {
    const group = h('div', { class: 'seg', role: 'group', 'aria-labelledby': labelId });
    const draw = (selected) => group.replaceChildren(...options.map((option) => h('button', {
      class: `seg-item${option.value === selected ? ' is-selected' : ''}`,
      type: 'button',
      'aria-pressed': String(option.value === selected),
      onclick: () => { draw(option.value); onPick(option.value); onChange(); },
    }, option.label)));
    draw(current);
    return group;
  }

  const intervalGroup = recurring
    ? segmented(INTERVALS, state.interval, 'income-interval-label', (value) => { state.interval = value; })
    : null;
  if (intervalGroup) intervalGroup.classList.add('seg-compact', 'seg-grid3');
  const receivedGroup = segmented(
    users.map((user) => ({ value: user.id, label: user.display_name })),
    state.receivedBy, 'income-received-label', (value) => { state.receivedBy = value; });

  const noteInput = h('input', {
    class: 'input', id: 'income-note', type: 'text', autocomplete: 'off', maxLength: 300,
    placeholder: 'Facoltativa, es. tredicesima, 730', value: state.note, enterkeyhint: 'done',
    oninput: () => { state.note = noteInput.value; onChange(); },
    onkeydown: (event) => {
      if (event.key === 'Enter') { event.preventDefault(); noteInput.blur(); }
    },
  });

  const element = h('div', { class: 'income-form' },
    amountBlock, amountError,
    variableBox ? variableBox.element : null,
    picker.label,
    categoryGrid, categoryError,
    h('label', { class: 'label', for: 'income-date' }, recurring ? 'Prossima scadenza' : 'Data'), dateInput,
    ...(recurring ? [h('span', { class: 'label', id: 'income-interval-label' }, 'Si ripete ogni'), intervalGroup] : []),
    h('span', { class: 'label', id: 'income-received-label' }, recurring ? 'Riceve' : 'Ricevuta da'),
    receivedGroup,
    h('label', { class: 'label', for: 'income-note' }, 'Nota'), noteInput);

  function validate() {
    let firstInvalid = null;
    if (!state.amount.trim()) {
      setError(amountError, 'Inserisci l’importo.');
      firstInvalid = amountInput;
    } else if (!AMOUNT_SHAPE.test(state.amount)) {
      setError(amountError, 'Importo non valido: usa un formato come 1850,00.');
      firstInvalid = amountInput;
    }
    if (!state.category) {
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

  // Body for POST /incomes, PATCH /incomes/{id} and the register endpoint.
  function toPayload() {
    return {
      amount: state.amount.trim(),
      category: state.category,
      income_date: state.date,
      received_by_user_id: state.receivedBy,
      note: state.note.trim() || null,
    };
  }

  // Body for POST /recurring-incomes and PATCH /recurring-incomes/{id}.
  function toRecurringPayload() {
    const { income_date: nextDue, ...rest } = toPayload();
    return { ...rest, next_due: nextDue, interval_months: state.interval, is_variable: state.variable };
  }

  function showAmountError(message) {
    setError(amountError, message);
    amountInput.scrollIntoView({ block: 'center' });
  }

  return {
    element, validate, toPayload, toRecurringPayload, showAmountError, categoryName: () => picker.name(),
    focusAmount: () => amountInput.focus({ preventScroll: true }),
  };
}
