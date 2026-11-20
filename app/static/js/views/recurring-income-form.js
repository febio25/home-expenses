// Recurring income templates (a salary, a fixed transfer), three screens on
// the shared income form, like recurring-form.js for expenses:
//   /ricorrenti/entrate/nuova          create a template
//   /ricorrenti/entrate/{id}           edit, suspend, delete a template
//   /ricorrenti/entrate/{id}/registra  register the due occurrence, changing
//                                      the amount or other fields first

import { api } from '../api.js';
import { state, loadUsers, loadIncomeCategories } from '../store.js';
import { createIncomeForm } from '../income-form.js';
import {
  h, toast, vibrate, confirmDialog, formatEuro, centsToInput, shortDate, newUuid,
  loadingBlock, errorBlock,
} from '../ui.js';
import { categoriesFor } from './income-form.js';

function valuesFrom(template) {
  return {
    amount: centsToInput(template.amount_cents),
    category: template.category,
    date: template.next_due,
    receivedBy: template.received_by_user_id,
    note: template.note || '',
    interval: template.interval_months,
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
  try {
    [template, users, categories] = await Promise.all([
      creating ? null : api.get(`/recurring-incomes/${idParam}`), loadUsers(), loadIncomeCategories(),
    ]);
  } catch (error) {
    if (!ctx.isCurrent()) return;
    if (error.status === 404) {
      toast('Questa entrata ricorrente non esiste più.', { kind: 'error' });
      goBack();
    } else {
      root.replaceChildren(errorBlock(error, () => ctx.navigate(location.pathname, { replace: true })));
    }
    return;
  }
  if (!ctx.isCurrent()) return;

  const errorBanner = h('div', { class: 'banner banner-error', role: 'alert', hidden: true });
  const form = createIncomeForm({
    users,
    // Registering needs a category of the current list; editing keeps the
    // template's own one visible.
    categories: registering ? categories : categoriesFor(categories, template),
    me: state.me,
    values: template ? valuesFrom(template) : {},
    variant: registering ? 'income' : 'recurring',
    onChange: () => { errorBanner.hidden = true; },
  });

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
  const saveLabel = registering ? 'Registra entrata' : creating ? 'Crea entrata ricorrente' : 'Salva modifiche';
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
        const { income } = await api.post(`/recurring-incomes/${template.id}/register`, {
          ...form.toPayload(), due_date: template.next_due, client_uuid: registerUuid,
        });
        vibrate();
        toast(`Registrata: ${formatEuro(income.amount_cents)}`, { kind: 'success' });
      } else if (creating) {
        await api.post('/recurring-incomes', form.toRecurringPayload());
        toast('Entrata ricorrente creata.', { kind: 'success' });
      } else {
        await api.patch(`/recurring-incomes/${template.id}`, form.toRecurringPayload());
        toast('Modifiche salvate.', { kind: 'success' });
      }
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
      await api.patch(`/recurring-incomes/${template.id}`, { is_active: !template.is_active });
      toast(template.is_active ? 'Entrata ricorrente sospesa.' : 'Entrata ricorrente riattivata.');
      goBack();
    } catch (error) { showError(error); }
  }

  async function remove() {
    const ok = await confirmDialog({
      title: 'Eliminare questa entrata ricorrente?',
      message: 'Le entrate già registrate restano nei movimenti.',
      confirmLabel: 'Elimina',
      danger: true,
    });
    if (!ok) return;
    try {
      await api.del(`/recurring-incomes/${template.id}`);
      toast('Entrata ricorrente eliminata.');
      goBack();
    } catch (error) { showError(error); }
  }

  const title = registering
    ? `Registra ${template.category_name}`
    : creating ? 'Nuova entrata ricorrente' : 'Entrata ricorrente';
  const intro = registering
    ? `Entrata di ${template.received_by_name}, scadenza del ${shortDate(template.next_due)}. Cambia l’importo se questa volta è diverso.`
    : 'L’importo è una proposta: alla scadenza puoi confermarlo o cambiarlo. Nulla viene registrato da solo.';

  const extra = !creating && !registering ? h('div', { class: 'recurring-manage' },
    h('button', { class: 'btn btn-quiet btn-grow', type: 'button', onclick: toggleActive },
      template.is_active ? 'Sospendi' : 'Riattiva'),
    h('button', { class: 'btn btn-danger-quiet', type: 'button', onclick: remove }, 'Elimina')) : null;

  root.replaceChildren(...[
    h('header', { class: 'page-head' },
      h('a', { class: 'page-back', href: '/ricorrenti', dataset: { link: '' }, 'aria-label': 'Torna alle ricorrenti' }, '‹'),
      h('h1', { class: 'page-title' }, title)),
    h('p', { class: 'page-intro' }, intro),
    form.element,
    extra,
    h('div', { class: 'footer-bar' }, errorBanner, saveButton),
  ].filter(Boolean));
  if (creating || registering) form.focusAmount();
}
