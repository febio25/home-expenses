// Markdowns of the Vinted items on sale (0.19.0, F7): the section «Ribasso»
// of an item, the sheet to choose its plan, and the plan read in Claude's
// answer. The server says where an item stands (item.markdown, see
// app/vinted_markdown.py); nothing changes the price by itself: the user
// changes it on Vinted, then confirms it here.

import { h, openDialog, choiceDialog, formatEuro, centsToInput } from './ui.js';
import { dayMonth, daysBetween } from './views/vinted.js';

// As BASE_* in app/vinted_markdown.py: only for the sheet, when the item
// has a plan of its own and the base is one of the choices.
const BASE_PLAN_TEXT = '−10% ogni 14 giorni';

const SOURCE_WORDS = { base: 'Piano base', claude: 'Proposto da Claude', manual: 'Scelto da te' };

function daysWord(days) {
  return days === 1 ? '1 giorno' : `${days} giorni`;
}

// The body of PATCH /vinted/items/{id} for a plan ({ kind, amount, days }).
export function planPayload(plan, source) {
  if (plan.kind === 'none') return { plan: 'none', source };
  const amount = plan.kind === 'pct' ? String(plan.amount) : centsToInput(plan.amount);
  return { plan: plan.kind, amount, days: plan.days, source };
}

// "Scrivo io": how much (a percentage or euro) and every how many days.
// Resolves to the payload, or null.
function ownPlanDialog(plan) {
  return openDialog((finish) => {
    let unit = plan.kind === 'eur' ? 'eur' : 'pct';
    const amount = h('input', {
      class: 'input', id: 'markdown-amount', type: 'text', inputmode: 'decimal', autocomplete: 'off',
      value: plan.kind === 'none' ? '' : (unit === 'pct' ? String(plan.amount) : centsToInput(plan.amount)),
      placeholder: 'Es. 10',
    });
    const days = h('input', {
      class: 'input', id: 'markdown-days', type: 'number', inputmode: 'numeric', min: 1, max: 90,
      value: plan.days || 14,
    });
    const unitButton = (id, label) => h('button', {
      class: `seg-item${unit === id ? ' is-selected' : ''}`, type: 'button', 'aria-pressed': String(unit === id),
      onclick: (event) => {
        unit = id;
        for (const button of event.currentTarget.parentNode.children) {
          const on = button === event.currentTarget;
          button.classList.toggle('is-selected', on);
          button.setAttribute('aria-pressed', String(on));
        }
        amount.placeholder = id === 'pct' ? 'Es. 10' : 'Es. 2';
        amount.focus();
      },
    }, label);
    setTimeout(() => { amount.focus(); amount.select(); }, 50);
    return h('form', {
      class: 'dialog-body',
      onsubmit: (event) => {
        event.preventDefault();
        const value = amount.value.trim();
        const every = Number(days.value);
        if (!value || !every) return;
        finish({ plan: unit, amount: value, days: every, source: 'manual' });
      },
    },
      h('h2', { class: 'dialog-title' }, 'Il tuo ribasso'),
      h('div', { class: 'seg md-unit', role: 'group', 'aria-label': 'In percentuale o in euro' },
        unitButton('pct', 'In %'), unitButton('eur', 'In euro')),
      h('div', { class: 'price-pair' },
        h('div', {}, h('label', { class: 'label', for: 'markdown-amount' }, 'Di quanto'), amount),
        h('div', {}, h('label', { class: 'label', for: 'markdown-days' }, 'Ogni quanti giorni'), days)),
      h('p', { class: 'form-hint' }, 'Il prezzo nuovo si arrotonda al mezzo euro e non scende sotto il minimo.'),
      h('div', { class: 'dialog-actions' },
        h('button', { class: 'btn btn-quiet', type: 'button', onclick: () => finish(null) }, 'Annulla'),
        h('button', { class: 'btn btn-primary', type: 'submit' }, 'Salva')));
  });
}

// «Cambia»: the plans to choose from, in a sheet. Resolves to the payload
// for PATCH, or null.
export async function planDialog(item) {
  const plan = item.markdown.plan;
  const options = [{ value: 'base', label: 'Piano base', meta: plan.source === 'base' ? plan.text : BASE_PLAN_TEXT }];
  if (plan.source !== 'base' && plan.kind !== 'none') {
    options.push({ value: 'own', label: SOURCE_WORDS[plan.source], meta: plan.text });
  }
  options.push({ value: 'write', label: 'Scrivo io', meta: 'una % o un importo, ogni quanti giorni' });
  options.push({ value: 'none', label: 'Niente ribasso', meta: 'il prezzo resta questo' });
  const choice = await choiceDialog({ title: 'Ribasso di questo articolo', options, sheet: true });
  if (choice === null || choice === 'own') return null;
  if (choice === 'base') return plan.source === 'base' ? null : { plan: 'base' };
  if (choice === 'none') return plan.kind === 'none' ? null : { plan: 'none', source: 'manual' };
  return ownPlanDialog(plan);
}

// The plan line of the section: what it is, who chose it, and «Cambia».
function planRow(item, onChange) {
  const { plan } = item.markdown;
  const meta = [SOURCE_WORDS[plan.source]];
  if (plan.kind !== 'none' && item.listing.min_price_cents) meta.push(`minimo ${formatEuro(item.listing.min_price_cents)}`);
  return h('div', { class: 'info' },
    h('span', { class: 'info-main' },
      h('span', { class: 'info-text' }, plan.text),
      h('span', { class: 'info-meta' }, meta.join(' · '))),
    h('button', { class: 'btn-text', type: 'button', onclick: onChange }, 'Cambia'));
}

const metaRow = (text) => h('div', { class: 'info' }, h('span', { class: 'info-main' }, h('span', { class: 'info-meta' }, text)));

function stepsText(steps) {
  return steps.map((cents, index) => (index === steps.length - 1
    ? `${formatEuro(cents)} (minimo)` : formatEuro(cents))).join(' · ');
}

// The yellow box of a decision: what is due, why, and the buttons.
function dueBox(title, text, primary, secondary) {
  return h('div', { class: 'info md-due', role: 'status' },
    h('span', { class: 'info-main' },
      h('span', { class: 'info-text' }, title),
      h('span', { class: 'info-meta' }, text)),
    primary,
    h('div', { class: 'md-actions' }, ...secondary));
}

const textButton = (label, onclick) => h('button', { class: 'btn-text', type: 'button', onclick }, label);

// The label beside «Ribasso», or null.
function badge(state) {
  const word = { due: 'Da ribassare', review: 'Al minimo', at_minimum: 'Al minimo', settled: 'Al minimo' }[state];
  if (!word) return null;
  return h('span', { class: `status${state === 'due' || state === 'review' ? ' is-due' : ''}` }, word);
}

// The section «Ribasso» of an item not sold nor withdrawn, or [] for the
// others. actions: { changePlan, lower, skip, otherPrice, review, withdraw,
// settle, setMinimum }.
export function markdownSection(item, actions) {
  if (item.status !== 'listed' && item.status !== 'unlisted') return [];
  const md = item.markdown;
  const rows = [planRow(item, actions.changePlan)];
  const price = item.listing.price_cents;
  switch (md.state) {
    case 'inactive':
      rows.push(metaRow(item.status === 'unlisted'
        ? 'Il conto parte dal giorno in cui lo segni come pubblicato.'
        : 'Serve un prezzo su Vinted per il ribasso.'));
      break;
    case 'off':
      break;
    case 'no_minimum':
      rows.push(h('div', { class: 'info' },
        h('span', { class: 'info-main' }, h('span', { class: 'info-meta' }, 'Serve un minimo: il ribasso non scende sotto quello.')),
        textButton('Imposta', actions.setMinimum)));
      break;
    case 'waiting':
      rows.push(metaRow(`Prossimo ribasso il ${dayMonth(md.due_on)}: ${formatEuro(md.next_price_cents)}.`));
      if (md.steps.length > 1) rows.push(metaRow(`Poi: ${stepsText(md.steps.slice(1))}`));
      break;
    case 'due': {
      const days = daysBetween(md.since);
      rows.push(dueBox(
        `È ora di ribassare: ${formatEuro(price)} → ${formatEuro(md.next_price_cents)}`,
        `Allo stesso prezzo da ${daysWord(days)}. Cambia prima il prezzo su Vinted, poi conferma qui.`,
        h('button', { class: 'btn btn-primary btn-block', type: 'button', onclick: () => actions.lower(md.next_price_cents) },
          `Ribassa a ${formatEuro(md.next_price_cents)}`),
        [textButton(`Salta ${daysWord(md.plan.days)}`, actions.skip), textButton('Altro prezzo', actions.otherPrice)]));
      if (md.steps.length > 1) rows.push(metaRow(`Poi: ${stepsText(md.steps.slice(1))}`));
      break;
    }
    case 'at_minimum':
      rows.push(metaRow(`Al minimo: se il ${dayMonth(md.due_on)} è ancora invenduto, ti chiedo come proseguire.`));
      break;
    case 'review': {
      const changes = item.listing.price_changes; // the steps already made, when there were some
      const history = changes.length > 1 ? changes.map((change) => formatEuro(change.price_cents)).join(' → ') : '';
      rows.push(dueBox(
        `Al minimo da ${daysWord(daysBetween(md.since))}, ancora invenduto`,
        `${history ? `${history}. ` : ''}Decidi tu come proseguire.`,
        h('button', { class: 'btn btn-primary btn-block', type: 'button', onclick: actions.review }, 'Rivaluta con Claude'),
        [textButton('Ritira dalla vendita', actions.withdraw), textButton('Lascia così', actions.settle)]));
      break;
    }
    case 'settled':
      rows.push(metaRow('Lasciato al minimo: nessun altro promemoria finché non cambi il prezzo.'));
      break;
    default:
      break;
  }
  return [
    h('div', { class: 'section-head' }, h('h2', { class: 'section-title' }, 'Ribasso'), badge(md.state)),
    h('div', { class: 'card md-card' }, rows),
  ];
}
