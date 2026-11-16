// "Nuova spesa": the start screen. Goal: amount, merchant, category, Save
// in under ten seconds.

import { api } from '../api.js';
import { state, loadUsers, loadCategories, loadMerchants, local } from '../store.js';
import { createExpenseForm } from '../expense-form.js';
import {
  h, toast, dismissToasts, vibrate, formatEuro, loadingBlock, errorBlock, newUuid, todayIso,
} from '../ui.js';

const DRAFT_KEY = 'draft';
const DRAFT_MAX_AGE_MS = 12 * 60 * 60 * 1000;

export async function mount(root, ctx) {
  root.append(loadingBlock());
  let users;
  let categories;
  let merchants;
  try {
    [users, categories, merchants] = await Promise.all([
      loadUsers(), loadCategories(), loadMerchants(),
    ]);
  } catch (error) {
    if (ctx.isCurrent()) root.replaceChildren(errorBlock(error, () => ctx.navigate('/', { replace: true })));
    return;
  }
  if (!ctx.isCurrent()) return;

  const activeCategories = categories.filter((category) => category.is_active);

  // A draft survives a dropped connection, a closed app, a dead battery.
  // Its client_uuid makes the retry safe: the server never stores it twice.
  // After DRAFT_MAX_AGE_MS it is considered abandoned and dropped.
  const saved = local.get(DRAFT_KEY);
  const fresh = saved && saved.uuid && Date.now() - (saved.at || 0) < DRAFT_MAX_AGE_MS;
  let draft = fresh ? saved : { uuid: newUuid(), values: {} };
  const draftValues = { ...draft.values };
  delete draftValues.date; // a draft from yesterday is still entered as "today" unless changed
  delete draftValues.dateTouched;
  if (draftValues.categoryId && !activeCategories.some((c) => c.id === draftValues.categoryId)) {
    draftValues.categoryId = null;
  }
  if (draftValues.paidBy && !users.some((u) => u.id === draftValues.paidBy)) delete draftValues.paidBy;

  const form = createExpenseForm({
    users,
    categories: activeCategories,
    merchants,
    me: state.me,
    values: draftValues,
    onChange: (values) => {
      draft.values = values;
      draft.at = Date.now();
      local.set(DRAFT_KEY, draft);
      hideError();
    },
  });
  // Starting the next expense (a tap or a keystroke anywhere in the form)
  // closes the confirmation of the previous one: nothing to wait for.
  form.element.addEventListener('pointerdown', dismissToasts, { capture: true });
  form.element.addEventListener('input', dismissToasts, { capture: true });

  const errorBanner = h('div', { class: 'banner banner-error', role: 'alert', hidden: true });
  function showError(title, text) {
    errorBanner.replaceChildren(h('strong', {}, title), h('span', {}, text));
    errorBanner.hidden = false;
  }
  function hideError() { errorBanner.hidden = true; }

  const saveButton = h('button', {
    class: 'btn btn-primary btn-block btn-save', type: 'button',
    // Keep the keyboard open while tapping Save: if the field lost focus the
    // keyboard would close and the button would move away under the thumb.
    // It is closed on purpose once the expense is saved (see save()).
    onpointerdown: (event) => event.preventDefault(),
    onclick: save,
  }, 'Salva spesa');

  async function save() {
    form.syncToday(); // the app may have been open since yesterday
    if (saveButton.disabled || !form.validate()) return;
    hideError();
    saveButton.disabled = true;
    saveButton.textContent = 'Salvataggio…';
    const payload = { ...form.toPayload(), client_uuid: draft.uuid };
    try {
      const { expense } = await api.createExpense(payload);
      vibrate();
      local.remove(DRAFT_KEY);
      draft = { uuid: newUuid(), values: {} };
      form.reset(); // back to the defaults: today, me, card
      flashSaved();
      // Close the keyboard: the whole empty form is in view again, and the
      // confirmation (with "Annulla") appears above the Save button, in reach
      // of the thumb, instead of over the amount. A tap on the amount starts
      // the next expense and closes the confirmation.
      if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
      // Back to the top: the next expense starts from the amount, in view.
      document.getElementById('view').scrollTop = 0;
      toast(`Salvata: ${formatEuro(expense.amount_cents)}${expense.merchant_name ? ` da ${expense.merchant_name}` : ''}`, {
        kind: 'success',
        action: { label: 'Annulla', run: () => undo(expense) },
      });
      // Refresh the autocomplete in the background (new merchant, new counts).
      loadMerchants({ force: true }).then((list) => form.setMerchants(list)).catch(() => {});
    } catch (error) {
      if (error.network) {
        vibrate([60, 60, 60]);
        showError('Spesa non salvata.', ' La connessione è caduta: i dati sono ancora qui. Controlla Tailscale e tocca di nuovo «Salva spesa».');
      } else if (error.status === 422 && /mporto|decimali/.test(error.message)) {
        form.showAmountError(error.message);
      } else if (error.status !== 401) {
        showError('Spesa non salvata.', ` ${error.message}`);
      }
    } finally {
      saveButton.disabled = false;
      saveButton.textContent = 'Salva spesa';
    }
  }

  async function undo(expense) {
    try {
      await api.del(`/expenses/${expense.id}`);
      toast('Spesa annullata.');
      loadMerchants({ force: true }).then((list) => form.setMerchants(list)).catch(() => {});
    } catch (error) {
      toast(`Non annullata: ${error.message}`, { kind: 'error' });
    }
  }

  function flashSaved() {
    saveButton.classList.remove('is-saved');
    void saveButton.offsetWidth; // restart the animation
    saveButton.classList.add('is-saved');
  }

  // Recurring expenses due today or earlier: a one-line reminder, loaded in
  // the background so it never delays the amount field.
  const dueBanner = h('a', { class: 'due-banner', href: '/ricorrenti', dataset: { link: '' }, hidden: true });
  function loadDueBanner() {
    api.get('/recurring').then((templates) => {
      if (!ctx.isCurrent()) return;
      const due = templates.filter((t) => t.is_active && t.next_due <= todayIso()).length;
      dueBanner.hidden = !due;
      if (!due) return;
      dueBanner.replaceChildren(
        h('span', {}, due === 1 ? '1 ricorrente da registrare' : `${due} ricorrenti da registrare`),
        h('span', { class: 'due-banner-go', 'aria-hidden': 'true' }, 'Vedi ›'));
    }).catch(() => {});
  }
  loadDueBanner();

  // Back from the background: today's date first (instant), then, after a
  // longer absence, what the other person may have changed meanwhile.
  let shownDay = todayIso();
  ctx.onResume(({ longAway }) => {
    form.syncToday();
    const newDay = todayIso() !== shownDay;
    shownDay = todayIso();
    if (!longAway && !newDay) return;
    loadDueBanner();
    loadMerchants({ force: true }).then((list) => form.setMerchants(list)).catch(() => {});
    loadCategories({ force: true })
      .then((list) => form.setCategories(list.filter((category) => category.is_active)))
      .catch(() => {});
  });

  root.classList.add('view-new');
  root.replaceChildren(
    h('header', { class: 'page-head' },
      h('h1', { class: 'page-title' }, 'Nuova spesa'),
      h('span', { class: 'page-who' }, state.me.display_name)),
    dueBanner,
    form.element,
    h('div', { class: 'footer-bar' }, errorBanner, saveButton));
  form.focusAmount();

  // A restored draft is announced: typing into an old amount without
  // noticing would add digits to it.
  const restored = draftValues.amount || draftValues.merchant || draftValues.note;
  if (fresh && restored) {
    const what = [draftValues.amount ? `${draftValues.amount} €` : null, draftValues.merchant]
      .filter(Boolean).join(' da ');
    toast(`Bozza non salvata recuperata${what ? `: ${what}` : ''}.`, {
      duration: 8000,
      action: {
        label: 'Svuota',
        run: () => {
          local.remove(DRAFT_KEY);
          draft = { uuid: newUuid(), values: {} };
          form.reset();
          form.focusAmount();
        },
      },
    });
  }
}
