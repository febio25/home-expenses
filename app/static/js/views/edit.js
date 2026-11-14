// "Modifica spesa": same form as the entry screen, plus delete.

import { api } from '../api.js';
import { state, loadUsers, loadCategories, loadMerchants } from '../store.js';
import { createExpenseForm } from '../expense-form.js';
import {
  h, toast, confirmDialog, formatEuro, centsToInput, shortDate, loadingBlock, errorBlock,
} from '../ui.js';

export async function mount(root, ctx) {
  const expenseId = ctx.params[0];
  root.append(loadingBlock());

  let expense;
  let users;
  let categories;
  let merchants;
  try {
    [expense, users, categories, merchants] = await Promise.all([
      api.get(`/expenses/${expenseId}`), loadUsers(), loadCategories(), loadMerchants(),
    ]);
  } catch (error) {
    if (!ctx.isCurrent()) return;
    if (error.status === 404) {
      toast('Questa spesa non esiste più.', { kind: 'error' });
      ctx.navigate('/movimenti', { replace: true });
    } else {
      root.replaceChildren(errorBlock(error, () => ctx.navigate(location.pathname, { replace: true })));
    }
    return;
  }
  if (!ctx.isCurrent()) return;

  // Return to the month the expense was listed under.
  const backPath = `/movimenti?mese=${expense.expense_date.slice(0, 7)}`;
  const goBack = () => ctx.navigate(backPath, { replace: true });
  // created_at is UTC: show it as a local date.
  const createdOn = new Date(expense.created_at).toLocaleDateString('it-IT', {
    day: 'numeric', month: 'long', year: 'numeric',
  });

  const form = createExpenseForm({
    users,
    // Active categories, plus this expense's own one even if deactivated since.
    categories: categories.filter((c) => c.is_active || c.id === expense.category_id),
    merchants,
    me: state.me,
    values: {
      amount: centsToInput(expense.amount_cents),
      merchant: expense.merchant_name || '',
      categoryId: expense.category_id,
      date: expense.expense_date,
      paidBy: expense.paid_by_user_id,
      method: expense.payment_method,
      note: expense.note || '',
      categoryTouched: true, // never change the category behind the user's back here
    },
  });

  const errorBanner = h('div', { class: 'banner banner-error', role: 'alert', hidden: true });
  const saveButton = h('button', {
    class: 'btn btn-primary btn-grow', type: 'button',
    onpointerdown: (event) => event.preventDefault(),
    onclick: save,
  }, 'Salva modifiche');
  const deleteButton = h('button', { class: 'btn btn-danger-quiet', type: 'button', onclick: remove }, 'Elimina');

  async function save() {
    if (saveButton.disabled || !form.validate()) return;
    errorBanner.hidden = true;
    saveButton.disabled = true;
    try {
      const updated = await api.patch(`/expenses/${expenseId}`, form.toPayload());
      state.merchants = null; // names and counts may have changed
      toast('Modifiche salvate.', { kind: 'success' });
      expense = updated;
      goBack();
    } catch (error) {
      if (error.status === 422 && /mporto|decimali/.test(error.message)) {
        form.showAmountError(error.message);
      } else if (error.status !== 401) {
        errorBanner.replaceChildren(
          h('strong', {}, 'Modifiche non salvate.'),
          h('span', {}, error.network ? ' La connessione è caduta: riprova.' : ` ${error.message}`));
        errorBanner.hidden = false;
      }
      saveButton.disabled = false;
    }
  }

  async function remove() {
    const where = expense.merchant_name ? ` da ${expense.merchant_name}` : '';
    const confirmed = await confirmDialog({
      title: 'Eliminare questa spesa?',
      message: `${formatEuro(expense.amount_cents)}${where}, ${shortDate(expense.expense_date)}. L’eliminazione è definitiva.`,
      confirmLabel: 'Elimina',
      danger: true,
    });
    if (!confirmed) return;
    try {
      await api.del(`/expenses/${expenseId}`);
      state.merchants = null;
      toast('Spesa eliminata.');
      goBack();
    } catch (error) {
      if (error.status !== 401) toast(`Non eliminata: ${error.message}`, { kind: 'error' });
    }
  }

  root.replaceChildren(
    h('header', { class: 'page-head' },
      h('h1', { class: 'page-title' }, 'Modifica spesa'),
      h('a', { class: 'page-link', href: backPath, dataset: { link: '' } }, 'Annulla')),
    h('p', { class: 'page-meta' },
      `Inserita da ${expense.created_by_name} il ${createdOn}`),
    form.element,
    h('div', { class: 'footer-bar footer-bar-row' }, errorBanner, deleteButton, saveButton));
}
