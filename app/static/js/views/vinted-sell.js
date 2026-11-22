// "Segna come venduto" (0.8.0): the price received, with the gain shown
// while it is typed; date and who received it in the details bar. Or the
// income already recorded from "Nuova entrata" (or, before 0.8.0, among the
// "Vendite"), picked from a list. Saving records an income in the category
// Vinted, linked to the item.

import { api } from '../api.js';
import { state, loadUsers } from '../store.js';
import {
  h, toast, vibrate, formatEuro, formatSignedEuro, newUuid, choiceDialog, loadingBlock, errorBlock,
} from '../ui.js';
import { saleFields } from '../vinted-forms.js';
import { itemPath, dayMonth } from './vinted.js';

function incomeOption(income) {
  return {
    value: income.id,
    label: income.category_name,
    meta: [dayMonth(income.income_date), income.received_by_name, income.note].filter(Boolean).join(' · '),
    amount: formatEuro(income.amount_cents),
  };
}

export async function mount(root, ctx) {
  const itemId = Number(ctx.params[0]);
  root.append(loadingBlock());
  let item;
  let users;
  let waiting;
  try {
    [item, users, waiting] = await Promise.all([
      api.get(`/vinted/items/${itemId}`), loadUsers(), api.get('/vinted/unlinked-incomes'),
    ]);
  } catch (error) {
    if (!ctx.isCurrent()) return;
    if (error.status === 404) {
      toast('Questo articolo non esiste più.', { kind: 'error' });
      ctx.back('/vinted');
    } else {
      root.replaceChildren(errorBlock(error, () => ctx.navigate(location.pathname, { replace: true })));
    }
    return;
  }
  if (!ctx.isCurrent()) return;

  const goBack = () => ctx.back(itemPath(itemId));
  if (item.status === 'sold') { // sold meanwhile, by the other person
    toast('Questo articolo risulta già venduto.', { kind: 'error' });
    goBack();
    return;
  }

  const costCents = item.purchase ? item.purchase.amount_cents : null;
  const fields = saleFields({ users, me: state.me, costCents });
  const clientUuid = newUuid(); // retries after a dropped connection never record the sale twice
  let linked = null;

  const errorBanner = h('div', { class: 'banner banner-error', role: 'alert', hidden: true });
  const fieldsBlock = h('div', {}, fields.element);
  const linkedSlot = h('div', { hidden: true });
  const pickHint = h('p', { class: 'form-hint' }, 'L’hai già registrata da Nuova entrata?');
  const pickButton = h('button', { class: 'btn btn-quiet btn-block', type: 'button', onclick: pickIncome },
    'Scegli un’entrata già registrata');

  function drawLinked() {
    fieldsBlock.hidden = Boolean(linked);
    linkedSlot.hidden = !linked;
    pickHint.hidden = Boolean(linked) || waiting.length === 0;
    pickButton.hidden = Boolean(linked) || waiting.length === 0;
    if (!linked) return;
    const option = incomeOption(linked);
    const gain = linked.amount_cents - (costCents || 0);
    linkedSlot.replaceChildren(
      h('span', { class: 'label' }, 'Vendita'),
      h('div', { class: 'card info' },
        h('span', { class: 'info-main' },
          h('span', { class: 'info-figure' }, option.amount),
          h('span', { class: 'info-meta' }, `${option.label} · ${option.meta}`)),
        h('button', { class: 'btn-text', type: 'button', onclick: pickIncome }, 'Cambia')),
      h('p', { class: 'gain-preview' }, h('span', {}, 'Guadagno'),
        h('span', { class: gain >= 0 ? 'gain' : 'loss' }, formatSignedEuro(gain))),
      h('button', { class: 'btn-text', type: 'button', onclick: () => { linked = null; drawLinked(); } },
        'Inserisci il prezzo a mano'));
  }

  async function pickIncome() {
    const id = await choiceDialog({
      title: 'Scegli l’entrata',
      text: 'Entrate Vinted o Vendite non ancora collegate a un articolo. Una «Vendite» diventa «Vinted».',
      options: waiting.map(incomeOption),
    });
    if (id === null) return;
    linked = waiting.find((income) => income.id === id) || null;
    errorBanner.hidden = true;
    drawLinked();
  }

  const saveButton = h('button', {
    class: 'btn btn-primary btn-block btn-save', type: 'button',
    onpointerdown: (event) => event.preventDefault(), // keep the keyboard while tapping
    onclick: save,
  }, 'Salva vendita');

  async function save() {
    if (saveButton.disabled) return;
    if (!linked && !fields.validate()) return;
    errorBanner.hidden = true;
    saveButton.disabled = true;
    const payload = linked ? { income_id: linked.id } : { ...fields.toPayload(), client_uuid: clientUuid };
    try {
      const sold = await api.post(`/vinted/items/${itemId}/sale`, payload);
      vibrate();
      toast(`Venduto a ${formatEuro(sold.sale.amount_cents)} · guadagno ${formatSignedEuro(sold.gain_cents)}`,
        { kind: 'success' });
      goBack();
    } catch (error) {
      saveButton.disabled = false;
      if (error.status === 401) return;
      if (error.status === 422 && /mporto|decimali|prezzo/i.test(error.message)) {
        fields.setAmountError(error.message);
        return;
      }
      errorBanner.replaceChildren(
        h('strong', {}, 'Vendita non salvata.'),
        h('span', {}, error.network
          ? ' La connessione è caduta: i dati sono ancora qui. Controlla Tailscale e riprova.'
          : ` ${error.message}`));
      errorBanner.hidden = false;
    }
  }

  const paid = item.purchase
    ? `Pagato ${formatEuro(item.purchase.amount_cents)} il ${dayMonth(item.purchase.expense_date)}`
    : 'Era già nostro';
  drawLinked();
  root.replaceChildren(
    h('header', { class: 'page-head' },
      h('a', {
        class: 'page-back', href: itemPath(itemId), 'aria-label': 'Torna all’articolo',
        onclick: (event) => { event.preventDefault(); goBack(); },
      }, '‹'),
      h('h1', { class: 'page-title' }, 'Segna come venduto')),
    h('div', { class: 'sale-item' },
      h('span', { class: 'art-main' },
        h('span', { class: 'art-title' }, item.title),
        h('span', { class: 'art-meta' }, paid))),
    h('div', { class: 'vinted-form' },
      fieldsBlock, linkedSlot, pickHint, pickButton,
      h('p', { class: 'form-hint form-hint-end' },
        'Salvando, l’app registra un’entrata «Vinted» collegata all’articolo.')),
    h('div', { class: 'footer-bar' }, errorBanner, saveButton));
  fields.focusAmount();
}
