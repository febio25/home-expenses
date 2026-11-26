// "Ricorrenti": expense templates (subscriptions, bills) and, from 0.6.0,
// income templates (salaries), in one list: the ones due for registration
// first, then the others. Nothing is recorded automatically: each
// occurrence is confirmed with a tap ("Registra"), changed first
// ("Modifica") or skipped ("Salta").

import { api } from '../api.js';
import { state } from '../store.js';
import { INTERVALS } from '../expense-form.js';
import {
  h, toast, vibrate, confirmDialog, formatEuro, formatSignedEuro, formatEuroWhole, relativeDay, shortDate,
  todayIso, newUuid, PAYMENT_LABELS, loadingBlock, errorBlock,
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

// 0.17.0: the due date in words near today ("domani", "tra 5 giorni",
// "3 giorni fa"), otherwise "il 14 mar".
function whenText(iso) {
  return relativeDay(iso) || `il ${compactDate(iso)}`;
}

// "circa 140,00 €" for a variable amount (0.17.0): «circa» small, in grey.
function amountParts(template, text) {
  return template.is_variable ? [h('span', { class: 'circa' }, 'circa '), text] : [text];
}

// 0.17.0, «Quanto costano»: the active items as a monthly and a yearly
// amount, in whole euros (the server does the sums). An item every 2
// months counts half a month, a yearly one a twelfth; «~» when some
// amounts are estimates.
function costsCard(costs) {
  const figure = (side, cents, sign) => {
    const text = `${sign}${formatEuroWhole(cents)}`;
    return side.has_variable ? [h('span', { class: 'costs-tilde' }, '~'), text] : [text];
  };
  const line = (label, side, sign, kind) => h('div', { class: `costs-row is-${kind}` },
    h('span', { class: 'costs-name' }, label, h('span', { class: 'costs-count' }, ` (${side.count})`)),
    h('span', { class: 'costs-month' }, ...figure(side, side.month_cents, sign)),
    h('span', { class: 'costs-year' }, ...figure(side, side.year_cents, sign)));
  const anyVariable = costs.expenses.has_variable || costs.incomes.has_variable;
  return h('section', { class: 'card costs', 'aria-label': 'Quanto costano le ricorrenti' },
    h('h2', { class: 'costs-title' }, 'Quanto costano'),
    h('div', { class: 'costs-row costs-head' },
      h('span', { class: 'costs-name' }, 'Attive'),
      h('span', { class: 'costs-month' }, 'al mese'),
      h('span', { class: 'costs-year' }, 'all’anno')),
    costs.expenses.count ? line('Spese', costs.expenses, '−', 'expense') : null,
    costs.incomes.count ? line('Entrate', costs.incomes, '+', 'income') : null,
    h('p', { class: 'costs-note' },
      'Una spesa ogni 2 mesi conta metà al mese, una annuale un dodicesimo.',
      anyVariable ? ' «~»: ci sono importi variabili.' : null));
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
    // what it is, in the row of the list (0.17.0): its category, or «Entrata»
    what: (template) => (template.merchant_name ? template.category_name : 'Spesa'),
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
    what: () => 'Entrata',
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
    let costs;
    try {
      [expenses, incomes, costs] = await Promise.all([
        api.get('/recurring'), api.get('/recurring-incomes'), api.get('/summary/recurring'),
      ]);
    } catch (error) {
      if (!quiet && ctx.isCurrent()) body.replaceChildren(errorBlock(error, () => load()));
      return;
    }
    if (!ctx.isCurrent()) return;
    render([
      ...expenses.map((template) => ({ kind: 'expense', template })),
      ...incomes.map((template) => ({ kind: 'income', template })),
    ], costs);
  }

  function render(items, costs) {
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
      costs.expenses.count || costs.incomes.count ? costsCard(costs) : null,
      due.length ? h('h2', { class: 'section-title' }, 'Da registrare') : null,
      ...due.map(dueCard),
      upcoming.length ? h('h2', { class: 'section-title' }, 'Prossime') : null,
      upcoming.length ? h('div', { class: 'card rows' }, upcoming.map(templateRow)) : null,
      paused.length ? h('h2', { class: 'section-title' }, 'Sospese') : null,
      paused.length ? h('div', { class: 'card rows' }, paused.map(templateRow)) : null,
      h('div', { class: 'recurring-add' }, ...addButtons),
    ].filter(Boolean));
  }

  // 0.17.0: on light yellow, like every reminder; the amount on the right
  // («circa» when variable), the due date in words.
  function dueCard(item) {
    const { template } = item;
    const kind = KINDS[item.kind];
    const late = template.next_due < todayIso();
    const when = relativeDay(template.next_due);
    const dueText = late
      ? `Scaduta ${when || `il ${shortDate(template.next_due)}`}`
      : 'Scade oggi';
    const registerButton = h('button', {
      class: 'btn btn-primary btn-grow', type: 'button',
      onclick: () => register(item, registerButton),
    }, `Registra ${formatEuro(template.amount_cents)}`);
    return h('section', { class: 'card due-card' },
      h('a', { class: 'due-head', href: kind.screen(template), dataset: { link: '' } },
        h('span', { class: 'row-main' },
          h('span', { class: 'row-title' }, kind.title(template)),
          h('span', { class: 'row-meta' }, kind.meta(template)),
          h('span', { class: `row-meta${late ? ' is-late' : ''}` }, dueText)),
        h('span', { class: `row-amount${item.kind === 'income' ? ' is-income' : ''}` },
          ...amountParts(template, kind.amount(template)))),
      h('div', { class: 'due-actions' },
        registerButton,
        h('a', { class: 'btn btn-quiet', href: `${kind.screen(template)}/registra`, dataset: { link: '' } },
          'Modifica'),
        h('button', { class: 'btn btn-quiet', type: 'button', onclick: () => skip(item) }, 'Salta')));
  }

  // «Abbonamenti · ogni mese · domani»; suspended: «sospesa · ogni mese».
  function templateRow(item) {
    const { template } = item;
    const kind = KINDS[item.kind];
    const interval = intervalText(template.interval_months);
    const meta = template.is_active
      ? [`${kind.what(template)} · ${interval} · `, h('strong', {}, whenText(template.next_due))]
      : [`sospesa · ${kind.what(template)} · ${interval}`];
    return h('a', { class: 'row', href: kind.screen(template), dataset: { link: '' } },
      h('span', { class: 'row-main' },
        h('span', { class: 'row-title' }, kind.title(template)),
        h('span', { class: 'row-meta recurring-meta' }, ...meta)),
      h('span', { class: `row-amount${item.kind === 'income' ? ' is-income' : ''}` },
        ...amountParts(template, kind.amount(template))));
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
