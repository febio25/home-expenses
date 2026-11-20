// "Nuova entrata" (/entrate/nuova) and "Modifica entrata" (/entrate/{id}).
// A short form, all in view: amount, category from the fixed list, date,
// who received it, note. Incomes are entered a few times a month, so there
// is no draft and no folded details panel as on the expense screen.

import { api } from '../api.js';
import { state, loadUsers, loadIncomeCategories } from '../store.js';
import { AMOUNT_SHAPE } from '../expense-form.js';
import {
  h, toast, vibrate, confirmDialog, formatEuro, centsToInput, shortDate, newUuid, todayIso,
  currentMonth, loadingBlock, errorBlock,
} from '../ui.js';
import { incomesPath } from './movements.js';

const MONTH_SHAPE = /^\d{4}-(0[1-9]|1[0-2])$/;

// Added from the list of a past month (?mese=2026-10), a new income starts
// on that month's last day, so backfilling last month's salary does not
// land in this month by mistake. Otherwise: today.
function defaultDate(query) {
  const month = query.get('mese');
  if (!month || !MONTH_SHAPE.test(month) || month >= currentMonth()) return todayIso();
  const [year, number] = month.split('-').map(Number);
  const lastDay = new Date(year, number, 0).getDate();
  return `${month}-${String(lastDay).padStart(2, '0')}`;
}

export async function mount(root, ctx) {
  const creating = ctx.params[0] === 'nuova';
  root.append(loadingBlock());

  let income = null;
  let users;
  let categories;
  try {
    [income, users, categories] = await Promise.all([
      creating ? null : api.get(`/incomes/${ctx.params[0]}`), loadUsers(), loadIncomeCategories(),
    ]);
  } catch (error) {
    if (!ctx.isCurrent()) return;
    if (error.status === 404) {
      toast('Questa entrata non esiste più.', { kind: 'error' });
      ctx.back('/entrate');
    } else {
      root.replaceChildren(errorBlock(error,
        () => ctx.navigate(location.pathname + location.search, { replace: true })));
    }
    return;
  }
  if (!ctx.isCurrent()) return;

  // A code dropped from the fixed list in a later version stays selectable
  // on the incomes that already have it.
  if (income && !categories.some((category) => category.code === income.category)) {
    categories = [...categories, { code: income.category, name: income.category_name }];
  }
  const values = income ? {
    amount: centsToInput(income.amount_cents),
    category: income.category,
    date: income.income_date,
    receivedBy: income.received_by_user_id,
    note: income.note || '',
  } : {
    amount: '', category: null, date: defaultDate(ctx.query), receivedBy: state.me.id, note: '',
  };
  // Back to the list it was opened from; opened directly, the list of its month.
  const backPath = incomesPath(values.date.slice(0, 7));
  const goBack = () => ctx.back(backPath);

  function setError(node, message) {
    node.textContent = message || '';
    node.hidden = !message;
  }

  // --- amount -------------------------------------------------------------
  const amountInput = h('input', {
    class: 'receipt-input', id: 'income-amount', type: 'text', inputmode: 'decimal',
    autocomplete: 'off', enterkeyhint: 'done', placeholder: '0,00', value: values.amount,
    'aria-describedby': 'income-amount-error',
    oninput: () => { values.amount = amountInput.value; setError(amountError, null); hideBanner(); },
    onkeydown: (event) => {
      if (event.key === 'Enter') { event.preventDefault(); amountInput.blur(); }
    },
  });
  const amountError = h('p', { class: 'field-error', id: 'income-amount-error', hidden: true });
  const amountBlock = h('div', { class: 'receipt' },
    h('label', { class: 'receipt-label', for: 'income-amount' }, 'Importo'),
    h('div', { class: 'receipt-line' }, amountInput,
      h('span', { class: 'receipt-currency', 'aria-hidden': 'true' }, '€')));

  // --- category (fixed list) ------------------------------------------------
  const categoryGrid = h('div', { class: 'cat-grid', role: 'group', 'aria-labelledby': 'income-category-label' });
  const categoryError = h('p', { class: 'field-error', hidden: true });
  function renderCategories() {
    categoryGrid.replaceChildren(...categories.map((category) => h('button', {
      class: `cat${category.code === values.category ? ' is-selected' : ''}`,
      type: 'button',
      'aria-pressed': String(category.code === values.category),
      onclick: () => {
        values.category = category.code;
        setError(categoryError, null);
        renderCategories();
      },
    }, category.name)));
  }

  // --- date, received by, note ----------------------------------------------
  const dateInput = h('input', {
    class: 'input', id: 'income-date', type: 'date', value: values.date, required: true,
    min: '2000-01-01', max: todayIso(),
    onchange: () => {
      values.date = dateInput.value || todayIso();
      dateInput.value = values.date;
    },
  });

  const receivedGroup = h('div', { class: 'seg', role: 'group', 'aria-labelledby': 'income-received-label' });
  function renderReceived() {
    receivedGroup.replaceChildren(...users.map((user) => h('button', {
      class: `seg-item${user.id === values.receivedBy ? ' is-selected' : ''}`,
      type: 'button',
      'aria-pressed': String(user.id === values.receivedBy),
      onclick: () => { values.receivedBy = user.id; renderReceived(); },
    }, user.display_name)));
  }

  const noteInput = h('input', {
    class: 'input', id: 'income-note', type: 'text', autocomplete: 'off', maxLength: 300,
    placeholder: 'Facoltativa, es. tredicesima, 730', value: values.note, enterkeyhint: 'done',
    oninput: () => { values.note = noteInput.value; },
    onkeydown: (event) => {
      if (event.key === 'Enter') { event.preventDefault(); noteInput.blur(); }
    },
  });

  // --- save, delete -----------------------------------------------------------
  const errorBanner = h('div', { class: 'banner banner-error', role: 'alert', hidden: true });
  function showBanner(text) {
    errorBanner.replaceChildren(
      h('strong', {}, creating ? 'Entrata non salvata.' : 'Modifiche non salvate.'),
      h('span', {}, text));
    errorBanner.hidden = false;
  }
  function hideBanner() { errorBanner.hidden = true; }

  function validate() {
    let firstInvalid = null;
    if (!values.amount.trim()) {
      setError(amountError, 'Inserisci l’importo.');
      firstInvalid = amountInput;
    } else if (!AMOUNT_SHAPE.test(values.amount)) {
      setError(amountError, 'Importo non valido: usa un formato come 1850,00.');
      firstInvalid = amountInput;
    }
    if (!values.category) {
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

  // Same key for every retry of this screen: a dropped connection never
  // stores the income twice.
  const clientUuid = newUuid();
  const saveButton = h('button', {
    class: creating ? 'btn btn-primary btn-block btn-save' : 'btn btn-primary btn-grow',
    type: 'button',
    // Keep the keyboard open while tapping, as on the expense screens.
    onpointerdown: (event) => event.preventDefault(),
    onclick: save,
  }, creating ? 'Salva entrata' : 'Salva modifiche');

  async function save() {
    if (saveButton.disabled || !validate()) return;
    hideBanner();
    saveButton.disabled = true;
    const payload = {
      amount: values.amount.trim(),
      category: values.category,
      income_date: values.date,
      received_by_user_id: values.receivedBy,
      note: values.note.trim() || null,
    };
    try {
      if (creating) {
        const saved = await api.post('/incomes', { ...payload, client_uuid: clientUuid });
        vibrate();
        toast(`Entrata salvata: ${formatEuro(saved.amount_cents)}`, { kind: 'success' });
      } else {
        await api.patch(`/incomes/${income.id}`, payload);
        toast('Modifiche salvate.', { kind: 'success' });
      }
      goBack();
    } catch (error) {
      saveButton.disabled = false;
      if (error.status === 401) return; // the app is already going to the login screen
      if (error.status === 422 && /mporto|decimali/.test(error.message)) {
        setError(amountError, error.message);
        amountInput.scrollIntoView({ block: 'center' });
        return;
      }
      showBanner(error.network
        ? ' La connessione è caduta: i dati sono ancora qui. Controlla Tailscale e riprova.'
        : ` ${error.message}`);
    }
  }

  async function remove() {
    const confirmed = await confirmDialog({
      title: 'Eliminare questa entrata?',
      message: `${formatEuro(income.amount_cents)} (${income.category_name}), ${shortDate(income.income_date)}. L’eliminazione è definitiva.`,
      confirmLabel: 'Elimina',
      danger: true,
    });
    if (!confirmed) return;
    try {
      await api.del(`/incomes/${income.id}`);
      toast('Entrata eliminata.');
      goBack();
    } catch (error) {
      if (error.status !== 401) toast(`Non eliminata: ${error.message}`, { kind: 'error' });
    }
  }

  renderCategories();
  renderReceived();

  // created_at is UTC: show it as a local date.
  const createdOn = income && new Date(income.created_at).toLocaleDateString('it-IT', {
    day: 'numeric', month: 'long', year: 'numeric',
  });
  root.replaceChildren(...[
    h('header', { class: 'page-head' },
      h('a', {
        class: 'page-back', href: backPath, 'aria-label': 'Torna alle entrate',
        onclick: (event) => { event.preventDefault(); goBack(); },
      }, '‹'),
      h('h1', { class: 'page-title' }, creating ? 'Nuova entrata' : 'Modifica entrata')),
    income ? h('p', { class: 'page-meta' }, `Inserita da ${income.created_by_name} il ${createdOn}`) : null,
    h('div', { class: 'income-form' },
      amountBlock, amountError,
      h('span', { class: 'label', id: 'income-category-label' }, 'Categoria'),
      categoryGrid, categoryError,
      h('label', { class: 'label', for: 'income-date' }, 'Data'), dateInput,
      h('span', { class: 'label', id: 'income-received-label' }, 'Ricevuta da'), receivedGroup,
      h('label', { class: 'label', for: 'income-note' }, 'Nota'), noteInput),
    creating
      ? h('div', { class: 'footer-bar' }, errorBanner, saveButton)
      : h('div', { class: 'footer-bar footer-bar-row' }, errorBanner,
        h('button', { class: 'btn btn-danger-quiet', type: 'button', onclick: remove }, 'Elimina'),
        saveButton),
  ].filter(Boolean));
  if (creating) amountInput.focus({ preventScroll: true });
}
