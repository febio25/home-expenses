// Recurring templates, three screens on the same form:
//   /ricorrenti/nuova          create a template
//   /ricorrenti/{id}           edit, suspend, delete a template
//   /ricorrenti/{id}/registra  register the due occurrence, changing amount
//                              or other fields first (variable bills)

import { api } from '../api.js';
import { state, loadUsers, loadCategories, loadMerchants } from '../store.js';
import { createExpenseForm } from '../expense-form.js';
import {
  h, toast, vibrate, confirmDialog, formatEuro, centsToInput, shortDate, newUuid,
  loadingBlock, errorBlock,
} from '../ui.js';

function valuesFrom(template) {
  return {
    amount: centsToInput(template.amount_cents),
    merchant: template.merchant_name || '',
    categoryId: template.category_id,
    date: template.next_due,
    paidBy: template.paid_by_user_id,
    method: template.payment_method,
    note: template.note || '',
    interval: template.interval_months,
    variable: template.is_variable,
    categoryTouched: true, // the template's category is a deliberate choice
  };
}

export async function mount(root, ctx) {
  const [idParam, action] = ctx.params;
  const creating = idParam === 'nuova';
  const registering = !creating && action === 'registra';
  const goBack = () => ctx.navigate('/ricorrenti', { replace: true });
  root.append(loadingBlock());

  let template = null;
  let users;
  let categories;
  let merchants;
  try {
    [template, users, categories, merchants] = await Promise.all([
      creating ? null : api.get(`/recurring/${idParam}`), loadUsers(), loadCategories(), loadMerchants(),
    ]);
  } catch (error) {
    if (!ctx.isCurrent()) return;
    if (error.status === 404) {
      toast('Questa spesa ricorrente non esiste più.', { kind: 'error' });
      goBack();
    } else {
      root.replaceChildren(errorBlock(error, () => ctx.navigate(location.pathname, { replace: true })));
    }
    return;
  }
  if (!ctx.isCurrent()) return;

  // When registering, a deactivated category must be replaced: show only
  // active ones. When editing, keep the template's own category visible.
  const shown = categories.filter((c) => c.is_active
    || (!registering && template && c.id === template.category_id));
  const values = template ? valuesFrom(template) : { categoryTouched: false };
  if (registering && !shown.some((c) => c.id === values.categoryId)) values.categoryId = null;

  const form = createExpenseForm({
    users,
    categories: shown,
    merchants,
    me: state.me,
    values,
    variant: registering ? 'expense' : 'recurring',
  });

  const errorBanner = h('div', { class: 'banner banner-error', role: 'alert', hidden: true });
  function showError(error) {
    if (error.status === 401) return;
    if (error.status === 422 && /mporto|decimali/.test(error.message)) {
      form.showAmountError(error.message);
      return;
    }
    errorBanner.textContent = error.network
      ? 'Connessione assente: i dati sono ancora qui, riprova.'
      : error.message;
    errorBanner.hidden = false;
  }

  // Same key for every retry of this screen: a dropped connection never
  // registers the occurrence twice.
  const registerUuid = newUuid();
  const saveLabel = registering ? 'Registra spesa' : creating ? 'Crea spesa ricorrente' : 'Salva modifiche';
  const saveButton = h('button', {
    class: 'btn btn-primary btn-block btn-save', type: 'button',
    onpointerdown: (event) => event.preventDefault(),
    onclick: save,
  }, saveLabel);

  async function save() {
    if (saveButton.disabled || !form.validate()) return;
    errorBanner.hidden = true;
    saveButton.disabled = true;
    try {
      if (registering) {
        const { expense } = await api.post(`/recurring/${template.id}/register`, {
          ...form.toPayload(), due_date: template.next_due, client_uuid: registerUuid,
        });
        vibrate();
        toast(`Registrata: ${formatEuro(expense.amount_cents)}`, { kind: 'success' });
      } else if (creating) {
        await api.post('/recurring', form.toRecurringPayload());
        toast('Spesa ricorrente creata.', { kind: 'success' });
      } else {
        await api.patch(`/recurring/${template.id}`, form.toRecurringPayload());
        toast('Modifiche salvate.', { kind: 'success' });
      }
      state.merchants = null;
      goBack();
    } catch (error) {
      showError(error);
      if (error.status === 409 && registering) {
        toast(error.message, { kind: 'error' });
        goBack();
      }
    } finally {
      saveButton.disabled = false;
    }
  }

  async function toggleActive() {
    try {
      await api.patch(`/recurring/${template.id}`, { is_active: !template.is_active });
      toast(template.is_active ? 'Spesa ricorrente sospesa.' : 'Spesa ricorrente riattivata.');
      goBack();
    } catch (error) { showError(error); }
  }

  async function remove() {
    const ok = await confirmDialog({
      title: 'Eliminare questa spesa ricorrente?',
      message: 'Le spese già registrate restano nei movimenti.',
      confirmLabel: 'Elimina',
      danger: true,
    });
    if (!ok) return;
    try {
      await api.del(`/recurring/${template.id}`);
      toast('Spesa ricorrente eliminata.');
      goBack();
    } catch (error) { showError(error); }
  }

  const title = registering
    ? `Registra ${template.merchant_name || template.category_name}`
    : creating ? 'Nuova ricorrente' : 'Spesa ricorrente';
  const intro = registering
    ? `Scadenza del ${shortDate(template.next_due)}. Cambia l’importo se questa volta è diverso.`
    : 'L’importo è una proposta: alla scadenza puoi confermarlo o cambiarlo. Nulla viene registrato da solo.';

  const extra = !creating && !registering ? h('div', { class: 'recurring-manage' },
    h('button', { class: 'btn btn-quiet btn-grow', type: 'button', onclick: toggleActive },
      template.is_active ? 'Sospendi' : 'Riattiva'),
    h('button', { class: 'btn btn-danger-quiet', type: 'button', onclick: remove }, 'Elimina')) : null;

  root.replaceChildren(...[
    h('header', { class: 'page-head' },
      h('a', { class: 'page-back', href: '/ricorrenti', dataset: { link: '' }, 'aria-label': 'Torna alle spese ricorrenti' }, '‹'),
      h('h1', { class: 'page-title' }, title)),
    h('p', { class: 'page-intro' }, intro),
    form.element,
    extra,
    h('div', { class: 'footer-bar' }, errorBanner, saveButton),
  ].filter(Boolean));
  if (creating || registering) form.focusAmount();
}
