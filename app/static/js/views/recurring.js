// "Spese ricorrenti": templates due for registration first, then the others.
// Nothing is recorded automatically: each occurrence is confirmed with a tap
// ("Registra"), changed first ("Modifica importo") or skipped ("Salta").

import { api } from '../api.js';
import { state } from '../store.js';
import { INTERVALS } from '../expense-form.js';
import {
  h, toast, vibrate, confirmDialog, formatEuro, shortDate, todayIso, newUuid,
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

function titleOf(template) {
  return template.merchant_name || template.category_name;
}

function metaOf(template) {
  return [
    template.merchant_name ? template.category_name : null,
    `paga ${template.paid_by_name}`,
    PAYMENT_LABELS[template.payment_method].toLowerCase(),
  ].filter(Boolean).join(', ');
}

export async function mount(root, ctx) {
  const body = h('div');
  root.append(
    h('header', { class: 'page-head' },
      h('a', { class: 'page-back', href: '/impostazioni', dataset: { link: '' }, 'aria-label': 'Torna alle impostazioni' }, '‹'),
      h('h1', { class: 'page-title' }, 'Spese ricorrenti')),
    body);

  async function load({ quiet = false } = {}) {
    if (!quiet) body.replaceChildren(loadingBlock());
    let templates;
    try {
      templates = await api.get('/recurring');
    } catch (error) {
      if (!quiet && ctx.isCurrent()) body.replaceChildren(errorBlock(error, () => load()));
      return;
    }
    if (!ctx.isCurrent()) return;
    render(templates);
  }

  function render(templates) {
    const today = todayIso();
    const due = templates.filter((t) => t.is_active && t.next_due <= today);
    const upcoming = templates.filter((t) => t.is_active && t.next_due > today);
    const paused = templates.filter((t) => !t.is_active);
    const addButton = h('a', { class: 'btn btn-primary btn-block', href: '/ricorrenti/nuova', dataset: { link: '' } },
      'Nuova spesa ricorrente');

    if (templates.length === 0) {
      body.replaceChildren(h('div', { class: 'empty' },
        h('p', { class: 'empty-title' }, 'Nessuna spesa ricorrente'),
        h('p', { class: 'empty-text' },
          'Aggiungi abbonamenti e bollette: alla scadenza li trovi qui, pronti da registrare con un tocco.'),
        addButton));
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
      h('div', { class: 'recurring-add' }, addButton),
    ].filter(Boolean));
  }

  function dueCard(template) {
    const late = template.next_due < todayIso();
    const registerButton = h('button', {
      class: 'btn btn-primary btn-grow', type: 'button',
      onclick: () => register(template, registerButton),
    }, `Registra ${formatEuro(template.amount_cents)}`);
    return h('section', { class: 'card due-card' },
      h('a', { class: 'due-head', href: `/ricorrenti/${template.id}`, dataset: { link: '' } },
        h('span', { class: 'row-main' },
          h('span', { class: 'row-title' }, titleOf(template)),
          h('span', { class: `row-meta${late ? ' is-late' : ''}` },
            `${late ? 'Scaduta il' : 'Scade oggi,'} ${shortDate(template.next_due)}`),
          h('span', { class: 'row-meta' }, metaOf(template)))),
      h('div', { class: 'due-actions' },
        registerButton,
        h('a', { class: 'btn btn-quiet', href: `/ricorrenti/${template.id}/registra`, dataset: { link: '' } },
          'Modifica'),
        h('button', { class: 'btn btn-quiet', type: 'button', onclick: () => skip(template) }, 'Salta')));
  }

  function templateRow(template) {
    const meta = template.is_active
      ? `${intervalText(template.interval_months)}, prossima ${compactDate(template.next_due)}`
      : `sospesa, ${intervalText(template.interval_months)}`;
    return h('a', { class: 'row', href: `/ricorrenti/${template.id}`, dataset: { link: '' } },
      h('span', { class: 'row-main' },
        h('span', { class: 'row-title' }, titleOf(template)),
        h('span', { class: 'row-meta' }, meta)),
      h('span', { class: 'row-amount' }, formatEuro(template.amount_cents)));
  }

  async function register(template, button) {
    if (button.disabled) return;
    button.disabled = true;
    try {
      const { expense } = await api.post(`/recurring/${template.id}/register`, {
        due_date: template.next_due, client_uuid: newUuid(),
      });
      vibrate();
      state.merchants = null; // a merchant may have been created
      toast(`Registrata: ${formatEuro(expense.amount_cents)} ${titleOf(template)}`, {
        kind: 'success',
        action: { label: 'Annulla', run: () => undo(template, expense) },
      });
      await load();
    } catch (error) {
      button.disabled = false;
      report(error, 'Non registrata');
      if (error.status === 409) await load();
    }
  }

  async function undo(template, expense) {
    // Delete the expense and put the due date back where it was.
    try {
      await api.del(`/expenses/${expense.id}`);
      await api.patch(`/recurring/${template.id}`, { next_due: template.next_due });
      toast('Registrazione annullata.');
      await load();
    } catch (error) {
      report(error, 'Non annullata');
    }
  }

  async function skip(template) {
    const ok = await confirmDialog({
      title: `Saltare ${titleOf(template)}?`,
      message: `Nessuna spesa verrà registrata per la scadenza del ${shortDate(template.next_due)}.`,
      confirmLabel: 'Salta',
    });
    if (!ok) return;
    try {
      await api.post(`/recurring/${template.id}/skip`, { due_date: template.next_due });
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
