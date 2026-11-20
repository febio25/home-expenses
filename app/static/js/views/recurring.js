// "Ricorrenti": expense templates (subscriptions, bills) and, from 0.6.0,
// income templates (salaries), in one list: the ones due for registration
// first, then the others. Nothing is recorded automatically: each
// occurrence is confirmed with a tap ("Registra"), changed first
// ("Modifica") or skipped ("Salta").

import { api } from '../api.js';
import { state } from '../store.js';
import { INTERVALS } from '../expense-form.js';
import {
  h, toast, vibrate, confirmDialog, formatEuro, formatSignedEuro, shortDate, todayIso, newUuid,
  PAYMENT_LABELS, loadingBlock, errorBlock,
} from '../ui.js';

function intervalText(months) {
  return INTERVALS.find((item) => item.value === months)?.long || `ogni ${months} mesi`;
}

// "5 dic", or "5 dic 2027" outside the current year: fits on one row.
function compactDate(iso) {
  const sameYear = iso.slice(0, 4) === todayIso().slice(0, 4);
  return new Date(`${iso}T12:00:00`).toLocaleDateString('it-IT', sameYear
    ? { day: 'numeric', month: 'short' }
    : { day: 'numeric', month: 'short', year: 'numeric' });
}

// What differs between the two kinds of template: endpoints, screens,
// wording. Everything else (sections, cards, actions) is shared. Incomes
// carry the receiver in the title ("Stipendio · Nastia": two salaries
// would read the same otherwise) and a "+" before the amount in the rows.
const KINDS = {
  expense: {
    api: '/recurring',
    screen: (template) => `/ricorrenti/${template.id}`,
    title: (template) => template.merchant_name || template.category_name,
    meta: (template) => [
      template.merchant_name ? template.category_name : null,
      `paga ${template.paid_by_name}`,
      PAYMENT_LABELS[template.payment_method].toLowerCase(),
    ].filter(Boolean).join(', '),
    amount: (template) => formatEuro(template.amount_cents),
    created: (result) => result.expense,
    createdPath: (item) => `/expenses/${item.id}`,
    skipped: 'Nessuna spesa verrà registrata',
  },
  income: {
    api: '/recurring-incomes',
    screen: (template) => `/ricorrenti/entrate/${template.id}`,
    title: (template) => `${template.category_name} · ${template.received_by_name}`,
    meta: () => 'Entrata',
    amount: (template) => formatSignedEuro(template.amount_cents),
    created: (result) => result.income,
    createdPath: (item) => `/incomes/${item.id}`,
    skipped: 'Nessuna entrata verrà registrata',
  },
};

export async function mount(root, ctx) {
  const body = h('div');
  root.append(
    h('header', { class: 'page-head' },
      h('a', { class: 'page-back', href: '/impostazioni', dataset: { link: '' }, 'aria-label': 'Torna alle impostazioni' }, '‹'),
      h('h1', { class: 'page-title' }, 'Ricorrenti')),
    body);

  async function load({ quiet = false } = {}) {
    if (!quiet) body.replaceChildren(loadingBlock());
    let expenses;
    let incomes;
    try {
      [expenses, incomes] = await Promise.all([api.get('/recurring'), api.get('/recurring-incomes')]);
    } catch (error) {
      if (!quiet && ctx.isCurrent()) body.replaceChildren(errorBlock(error, () => load()));
      return;
    }
    if (!ctx.isCurrent()) return;
    render([
      ...expenses.map((template) => ({ kind: 'expense', template })),
      ...incomes.map((template) => ({ kind: 'income', template })),
    ]);
  }

  function render(items) {
    const today = todayIso();
    const byDue = (a, b) => (a.template.next_due < b.template.next_due ? -1
      : a.template.next_due > b.template.next_due ? 1 : 0);
    const active = items.filter((item) => item.template.is_active).sort(byDue);
    const due = active.filter((item) => item.template.next_due <= today);
    const upcoming = active.filter((item) => item.template.next_due > today);
    const paused = items.filter((item) => !item.template.is_active).sort(byDue);
    const addButtons = [
      h('a', { class: 'btn btn-primary btn-block', href: '/ricorrenti/nuova', dataset: { link: '' } },
        'Nuova spesa ricorrente'),
      h('a', { class: 'btn btn-quiet btn-block', href: '/ricorrenti/entrate/nuova', dataset: { link: '' } },
        'Nuova entrata ricorrente'),
    ];

    if (items.length === 0) {
      body.replaceChildren(h('div', { class: 'empty' },
        h('p', { class: 'empty-title' }, 'Nessuna ricorrente'),
        h('p', { class: 'empty-text' },
          'Abbonamenti, bollette, stipendi: alla scadenza li trovi qui, pronti da registrare con un tocco.'),
        ...addButtons));
      return;
    }

    // replaceChildren() would print null as text: drop the empty sections.
    body.replaceChildren(...[
      due.length ? h('h2', { class: 'section-title' }, 'Da registrare') : null,
      ...due.map(dueCard),
      upcoming.length ? h('h2', { class: 'section-title' }, 'Prossime') : null,
      upcoming.length ? h('div', { class: 'card rows' }, upcoming.map(templateRow)) : null,
      paused.length ? h('h2', { class: 'section-title' }, 'Sospese') : null,
      paused.length ? h('div', { class: 'card rows' }, paused.map(templateRow)) : null,
      h('div', { class: 'recurring-add' }, ...addButtons),
    ].filter(Boolean));
  }

  function dueCard(item) {
    const { template } = item;
    const kind = KINDS[item.kind];
    const late = template.next_due < todayIso();
    const registerButton = h('button', {
      class: 'btn btn-primary btn-grow', type: 'button',
      onclick: () => register(item, registerButton),
    }, `Registra ${formatEuro(template.amount_cents)}`);
    return h('section', { class: 'card due-card' },
      h('a', { class: 'due-head', href: kind.screen(template), dataset: { link: '' } },
        h('span', { class: 'row-main' },
          h('span', { class: 'row-title' }, kind.title(template)),
          h('span', { class: `row-meta${late ? ' is-late' : ''}` },
            `${late ? 'Scaduta il' : 'Scade oggi,'} ${shortDate(template.next_due)}`),
          h('span', { class: 'row-meta' }, kind.meta(template)))),
      h('div', { class: 'due-actions' },
        registerButton,
        h('a', { class: 'btn btn-quiet', href: `${kind.screen(template)}/registra`, dataset: { link: '' } },
          'Modifica'),
        h('button', { class: 'btn btn-quiet', type: 'button', onclick: () => skip(item) }, 'Salta')));
  }

  function templateRow(item) {
    const { template } = item;
    const kind = KINDS[item.kind];
    const meta = template.is_active
      ? `${intervalText(template.interval_months)}, prossima ${compactDate(template.next_due)}`
      : `sospesa, ${intervalText(template.interval_months)}`;
    return h('a', { class: 'row', href: kind.screen(template), dataset: { link: '' } },
      h('span', { class: 'row-main' },
        h('span', { class: 'row-title' }, kind.title(template)),
        h('span', { class: 'row-meta' }, meta)),
      h('span', { class: 'row-amount' }, kind.amount(template)));
  }

  async function register(item, button) {
    if (button.disabled) return;
    const { template } = item;
    const kind = KINDS[item.kind];
    button.disabled = true;
    try {
      const result = await api.post(`${kind.api}/${template.id}/register`, {
        due_date: template.next_due, client_uuid: newUuid(),
      });
      const created = kind.created(result);
      vibrate();
      if (item.kind === 'expense') state.merchants = null; // a merchant may have been created
      toast(`Registrata: ${formatEuro(created.amount_cents)} ${kind.title(template)}`, {
        kind: 'success',
        action: { label: 'Annulla', run: () => undo(item, created) },
      });
      await load();
    } catch (error) {
      button.disabled = false;
      report(error, 'Non registrata');
      if (error.status === 409) await load();
    }
  }

  async function undo(item, created) {
    // Delete what was registered and put the due date back where it was.
    const kind = KINDS[item.kind];
    try {
      await api.del(kind.createdPath(created));
      await api.patch(`${kind.api}/${item.template.id}`, { next_due: item.template.next_due });
      toast('Registrazione annullata.');
      await load();
    } catch (error) {
      report(error, 'Non annullata');
    }
  }

  async function skip(item) {
    const { template } = item;
    const kind = KINDS[item.kind];
    const ok = await confirmDialog({
      title: `Saltare ${kind.title(template)}?`,
      message: `${kind.skipped} per la scadenza del ${shortDate(template.next_due)}.`,
      confirmLabel: 'Salta',
    });
    if (!ok) return;
    try {
      await api.post(`${kind.api}/${template.id}/skip`, { due_date: template.next_due });
      toast('Scadenza saltata.');
    } catch (error) {
      report(error, 'Non saltata');
    }
    await load();
  }

  function report(error, prefix) {
    if (error.status === 401) return;
    toast(`${prefix}: ${error.network ? 'connessione assente.' : error.message}`, { kind: 'error' });
  }

  ctx.onResume(({ longAway }) => { if (longAway) load({ quiet: true }); });
  await load();
}
