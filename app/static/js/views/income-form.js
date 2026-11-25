// "Nuova entrata" (/entrate/nuova) and "Modifica entrata" (/entrate/{id}),
// on the shared income form (income-form.js).

import { api } from '../api.js';
import { state, loadUsers, loadIncomeCategories } from '../store.js';
import { createIncomeForm } from '../income-form.js';
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

// A code dropped from the fixed list in a later version stays selectable
// on the incomes (and templates) that already have it.
export function categoriesFor(categories, item) {
  if (!item || categories.some((category) => category.code === item.category)) return categories;
  return [...categories, { code: item.category, name: item.category_name }];
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

  const values = income ? {
    amount: centsToInput(income.amount_cents),
    category: income.category,
    date: income.income_date,
    receivedBy: income.received_by_user_id,
    note: income.note || '',
  } : { date: defaultDate(ctx.query) };
  // Back to the list it was opened from; opened directly, the list of its month.
  const backPath = incomesPath((income ? income.income_date : values.date).slice(0, 7));
  const goBack = () => ctx.back(backPath);

  const errorBanner = h('div', { class: 'banner banner-error', role: 'alert', hidden: true });
  // The sale of a Vinted item stays a Vinted income (the server refuses a
  // change): only that category is offered.
  const vintedTitle = income && income.vinted_item_id ? income.vinted_item_title : null;
  // 0.15.0: a new income's button says where it goes, «Salva in Stipendio».
  let saveButton = null;
  const labelFor = (name) => (name ? `Salva in ${name}` : 'Salva entrata');
  const form = createIncomeForm({
    users,
    categories: vintedTitle
      ? categories.filter((category) => category.code === income.category)
      : categoriesFor(categories, income),
    me: state.me,
    values,
    onChange: () => { errorBanner.hidden = true; },
    onCategoryName: (name) => { if (creating && saveButton) saveButton.textContent = labelFor(name); },
  });

  // Same key for every retry of this screen: a dropped connection never
  // stores the income twice.
  const clientUuid = newUuid();
  saveButton = h('button', {
    class: creating ? 'btn btn-primary btn-block btn-save btn-save-named' : 'btn btn-primary btn-grow',
    type: 'button',
    // Keep the keyboard open while tapping, as on the expense screens.
    onpointerdown: (event) => event.preventDefault(),
    onclick: save,
  }, creating ? labelFor(form.categoryName()) : 'Salva modifiche');

  async function save() {
    if (saveButton.disabled || !form.validate()) return;
    errorBanner.hidden = true;
    saveButton.disabled = true;
    try {
      if (creating) {
        const saved = await api.post('/incomes', { ...form.toPayload(), client_uuid: clientUuid });
        vibrate();
        toast(`Entrata salvata: ${formatEuro(saved.amount_cents)}`, { kind: 'success' });
      } else {
        await api.patch(`/incomes/${income.id}`, form.toPayload());
        toast('Modifiche salvate.', { kind: 'success' });
      }
      goBack();
    } catch (error) {
      saveButton.disabled = false;
      if (error.status === 401) return; // the app is already going to the login screen
      if (error.status === 422 && /mporto|decimali/.test(error.message)) {
        form.showAmountError(error.message);
        return;
      }
      errorBanner.replaceChildren(
        h('strong', {}, creating ? 'Entrata non salvata.' : 'Modifiche non salvate.'),
        h('span', {}, error.network
          ? ' La connessione è caduta: i dati sono ancora qui. Controlla Tailscale e riprova.'
          : ` ${error.message}`));
      errorBanner.hidden = false;
    }
  }

  async function remove() {
    const confirmed = await confirmDialog({
      title: 'Eliminare questa entrata?',
      message: `${formatEuro(income.amount_cents)} (${income.category_name}), ${shortDate(income.income_date)}. L’eliminazione è definitiva.${vintedTitle ? ` L’articolo «${vintedTitle}» tornerà in vendita.` : ''}`,
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
    vintedTitle
      ? h('p', { class: 'page-meta' }, `Vendita dell’articolo Vinted «${vintedTitle}»: la categoria resta Vinted.`)
      : null,
    form.element,
    creating
      ? h('div', { class: 'footer-bar' }, errorBanner, saveButton)
      : h('div', { class: 'footer-bar footer-bar-row' }, errorBanner,
        h('button', { class: 'btn btn-danger-quiet', type: 'button', onclick: remove }, 'Elimina'),
        saveButton),
  ].filter(Boolean));
  if (creating) form.focusAmount();
}
