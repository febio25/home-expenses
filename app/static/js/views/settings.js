// "Impostazioni": categories, merchants, CSV export, backup, account.

import { api } from '../api.js';
import {
  state, loadUsers, loadCategories, loadMerchants, clearState, rememberCategories,
} from '../store.js';
import {
  h, icon, toast, confirmDialog, promptDialog, choiceDialog, openDialog, currentMonth, todayIso, loadingBlock, errorBlock,
  passwordField, passwordProblem, newPasswordDialog, dayMonthShort,
} from '../ui.js';
import { copyText, canShareFiles, shareFilesWithText } from '../vinted-listing.js';
import { categoryIcon, DEFAULT_ICON, ICON_LABELS } from '../category-icons.js';

function section(title, hint, content, { open = false } = {}) {
  return h('details', { class: 'card settings-section', open },
    h('summary', { class: 'settings-summary' },
      h('span', { class: 'settings-title' }, title),
      h('span', { class: 'settings-hint' }, hint)),
    h('div', { class: 'settings-body' }, content));
}

function report(error, prefix) {
  if (error.status === 401) return; // the app is already going to the login screen
  toast(`${prefix}: ${error.network ? 'connessione assente.' : error.message}`, { kind: 'error' });
}

// --- categories -------------------------------------------------------------

// The icons a category can have (GET /categories/icons), fetched once.
let iconChoices = null;
async function loadIconChoices() {
  if (!iconChoices) iconChoices = (await api.get('/categories/icons')).icons;
  return iconChoices;
}

// 0.15.0: name and icon of a category in one window, for «Aggiungi» and
// «Modifica»; with `toggleLabel`, also «Disattiva» / «Riattiva» (out of the
// row, where the name now shares the width with the icon). Resolves to
// { name, icon }, { toggle: true } or null.
function categoryDialog({ title, name = '', icon: chosen = null, icons, confirmLabel = 'Salva', toggleLabel = null }) {
  return openDialog((finish) => {
    let current = chosen;
    const field = h('input', {
      class: 'input', id: 'category-name', type: 'text', value: name, maxLength: 40, required: true,
      autocomplete: 'off', autocapitalize: 'sentences',
    });
    const error = h('p', { class: 'field-error', hidden: true });
    const grid = h('div', { class: 'icon-picker', role: 'group', 'aria-labelledby': 'category-icon-label' });
    function draw() {
      grid.replaceChildren(...icons.map((key) => h('button', {
        class: `icon-choice${key === current ? ' is-selected' : ''}`,
        type: 'button',
        'aria-label': ICON_LABELS[key] || key,
        'aria-pressed': String(key === current),
        dataset: { icon: key },
        onclick: () => { current = key; error.hidden = true; draw(); },
      }, categoryIcon(key))));
    }
    draw();
    const form = h('form', {
      class: 'dialog-body',
      onsubmit: (event) => {
        event.preventDefault();
        const text = field.value.trim().replace(/\s+/g, ' ');
        if (!text) return;
        if (!current) {
          error.textContent = 'Scegli un’icona: è quella dei pulsanti in «Nuova spesa».';
          error.hidden = false;
          return;
        }
        finish({ name: text, icon: current });
      },
    },
    // The title takes the focus, not the name: on a phone the keyboard would
    // cover the icons, which are what is usually changed here.
    h('h2', { class: 'dialog-title', tabIndex: -1, autofocus: true }, title),
    h('label', { class: 'label', for: 'category-name' }, 'Nome'),
    field,
    h('span', { class: 'label', id: 'category-icon-label' }, 'Icona'),
    grid, error,
    toggleLabel ? h('button', {
      class: 'btn btn-quiet btn-block category-toggle', type: 'button', onclick: () => finish({ toggle: true }),
    }, toggleLabel) : null,
    h('div', { class: 'dialog-actions' },
      h('button', { class: 'btn btn-quiet', type: 'button', onclick: () => finish(null) }, 'Annulla'),
      h('button', { class: 'btn btn-primary', type: 'submit' }, confirmLabel)));
    return form;
  });
}

function categoriesSection() {
  const list = h('ul', { class: 'manage-list' });
  const nameInput = h('input', {
    class: 'input', type: 'text', maxLength: 40, required: true, autocomplete: 'off',
    placeholder: 'Nuova categoria', 'aria-label': 'Nome della nuova categoria',
  });
  // 0.14.0: "Cambia l'ordine" turns the list into one with arrows; the order
  // is the one of the buttons in "Nuova spesa".
  let categories = [];
  let reordering = false;
  const orderButton = h('button', {
    class: 'btn btn-quiet btn-block', type: 'button',
    onclick: () => { reordering = !reordering; draw(); },
  });
  const orderHint = h('p', { class: 'settings-text', hidden: true },
    'Lo stesso ordine dei pulsanti in «Nuova spesa»: in alto le categorie che usate di più.');

  async function refresh() {
    categories = await loadCategories({ force: true });
    draw();
  }

  function draw() {
    orderButton.textContent = reordering ? 'Fatto' : 'Cambia l’ordine';
    orderButton.classList.toggle('btn-primary', reordering);
    orderButton.classList.toggle('btn-quiet', !reordering);
    orderHint.hidden = !reordering;
    if (reordering) {
      list.replaceChildren(...categories.map((category, index) => h('li', { class: 'manage-item' },
        categoryIcon(category.icon || DEFAULT_ICON),
        h('span', { class: 'manage-name' },
          category.name,
          category.is_active ? null : h('span', { class: 'tag' }, 'disattivata')),
        h('span', { class: 'manage-actions order-actions' },
          h('button', {
            class: 'order-step', type: 'button', disabled: index === 0,
            'aria-label': `Sposta su «${category.name}»`, onclick: () => move(index, -1),
          }, icon('up')),
          h('button', {
            class: 'order-step', type: 'button', disabled: index === categories.length - 1,
            'aria-label': `Sposta giù «${category.name}»`, onclick: () => move(index, 1),
          }, icon('down'))))));
      return;
    }
    // 0.15.0: one action, «Modifica» (name, icon, and «Disattiva» inside).
    list.replaceChildren(...categories.map((category) => h('li', { class: 'manage-item' },
      categoryIcon(category.icon || DEFAULT_ICON),
      h('span', { class: 'manage-name' },
        category.name,
        category.is_active ? null : h('span', { class: 'tag' }, 'disattivata'),
        category.system_key === 'vinted' ? h('span', { class: 'tag' }, 'usata dalla sezione Vinted') : null),
      h('span', { class: 'manage-actions' },
        h('button', { class: 'btn-text', type: 'button', onclick: () => edit(category) }, 'Modifica')))));
  }

  // One request with the whole new order (PUT /categories/order): two
  // phones reordering at once cannot leave it half done.
  async function move(index, step) {
    const ids = categories.map((category) => category.id);
    [ids[index], ids[index + step]] = [ids[index + step], ids[index]];
    try {
      const saved = await api.put('/categories/order', { ids });
      categories = saved;
      rememberCategories(saved);
      draw();
      const moved = list.querySelectorAll('.manage-item')[index + step];
      const button = moved && moved.querySelector(`.order-step:nth-child(${step < 0 ? 1 : 2})`);
      if (button && !button.disabled) button.focus({ preventScroll: true });
    } catch (error) {
      report(error, 'Ordine non salvato');
      if (error.status === 409) refresh().catch(() => {});
    }
  }

  // 0.15.0: name and icon («Rinomina» until 0.14.0).
  async function edit(category) {
    let icons;
    try { icons = await loadIconChoices(); } catch (error) { report(error, 'Icone non caricate'); return; }
    const answer = await categoryDialog({
      title: 'Modifica categoria', name: category.name, icon: category.icon || DEFAULT_ICON, icons,
      // The Vinted category (0.8.0) is never deactivated: its section relies on it.
      toggleLabel: category.system_key ? null : category.is_active ? 'Disattiva categoria' : 'Riattiva categoria',
    });
    if (!answer) return;
    if (answer.toggle) { await toggle(category); return; }
    const changes = {};
    if (answer.name !== category.name) changes.name = answer.name;
    if (answer.icon !== category.icon) changes.icon = answer.icon;
    if (!Object.keys(changes).length) return;
    try {
      await api.patch(`/categories/${category.id}`, changes);
      await refresh();
      toast('Categoria modificata.', { kind: 'success' });
    } catch (error) { report(error, 'Non modificata'); }
  }

  async function toggle(category) {
    if (category.is_active) {
      const confirmed = await confirmDialog({
        title: `Disattivare «${category.name}»?`,
        message: 'Non comparirà più tra le scelte per le nuove spese. Le spese già registrate restano com’erano e puoi riattivarla quando vuoi.',
        confirmLabel: 'Disattiva',
      });
      if (!confirmed) return;
    }
    try {
      await api.patch(`/categories/${category.id}`, { is_active: !category.is_active });
      await refresh();
    } catch (error) { report(error, 'Non modificata'); }
  }

  const form = h('form', {
    class: 'inline-form',
    onsubmit: async (event) => {
      event.preventDefault();
      const typed = nameInput.value.trim();
      if (!typed) return;
      // 0.15.0: then the icon, in the same window as «Modifica».
      let icons;
      try { icons = await loadIconChoices(); } catch (error) { report(error, 'Icone non caricate'); return; }
      const answer = await categoryDialog({ title: 'Nuova categoria', name: typed, icons, confirmLabel: 'Aggiungi' });
      if (!answer) return;
      try {
        await api.post('/categories', answer);
        nameInput.value = '';
        await refresh();
        toast('Categoria aggiunta.', { kind: 'success' });
      } catch (error) { report(error, 'Non aggiunta'); }
    },
  }, nameInput, h('button', { class: 'btn btn-primary', type: 'submit' }, 'Aggiungi'));

  return { element: h('div', {}, list, orderHint, orderButton, form), refresh };
}

// --- merchants --------------------------------------------------------------

// Search without case and accents: "caffe" finds "Caffè".
function fold(text) {
  return text.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('it-IT').replace(/\s+/g, ' ').trim();
}

const countLabel = (count) => (count === 1 ? '1 spesa' : `${count} spese`);

// 0.11.0: a search box, and the possible duplicates (names that look alike,
// found by the server) with «Unisci» and «Non sono doppioni».
function merchantsSection() {
  const list = h('ul', { class: 'manage-list' });
  const duplicatesBox = h('div');
  const allTitle = h('p', { class: 'all-title', hidden: true }, 'Tutti gli esercenti');
  const search = h('input', {
    class: 'input', type: 'search', autocomplete: 'off', enterkeyhint: 'search',
    placeholder: 'Cerca un esercente', 'aria-label': 'Cerca un esercente',
    oninput: () => draw(),
  });
  search.setAttribute('autocorrect', 'off');
  search.setAttribute('spellcheck', 'false');
  const searchBox = h('div', { class: 'search merchant-search', hidden: true }, icon('search'), search);
  let merchants = [];
  let pairs = [];

  async function refresh() {
    [merchants, pairs] = await Promise.all([
      loadMerchants({ force: true }),
      api.get('/merchants/duplicates'),
    ]);
    draw();
  }

  function draw() {
    searchBox.hidden = merchants.length < 2;
    const query = fold(search.value);
    // The duplicates stay out of the way while searching.
    duplicatesBox.replaceChildren(...(query || pairs.length === 0 ? [] : [
      h('p', { class: 'dup-title' }, pairs.length === 1 ? '1 possibile doppione' : `${pairs.length} possibili doppioni`),
      h('p', { class: 'dup-hint' }, 'Nomi che si assomigliano. Se sono lo stesso negozio, uniscili; se no, segnali come diversi e non compariranno più.'),
      ...pairs.map(pairItem),
    ]));
    allTitle.hidden = Boolean(query) || pairs.length === 0;
    if (merchants.length === 0) {
      list.replaceChildren(h('li', { class: 'manage-empty' },
        'Gli esercenti compaiono qui dopo la prima spesa.'));
      return;
    }
    const sorted = [...merchants].sort((a, b) => a.name.localeCompare(b.name, 'it'));
    const shown = query ? sorted.filter((merchant) => fold(merchant.name).includes(query)) : sorted;
    if (shown.length === 0) {
      list.replaceChildren(h('li', { class: 'manage-empty' }, `Nessun esercente con «${search.value.trim()}».`));
      return;
    }
    list.replaceChildren(...shown.map((merchant) => h('li', { class: 'manage-item' },
      h('span', { class: 'manage-name' },
        merchant.name,
        h('span', { class: 'manage-count' }, countLabel(merchant.expense_count))),
      h('span', { class: 'manage-actions' },
        h('button', { class: 'btn-text', type: 'button', onclick: () => rename(merchant) }, 'Rinomina'),
        merchants.length > 1
          ? h('button', { class: 'btn-text', type: 'button', onclick: () => merge(merchant, sorted) }, 'Unisci')
          : null))));
  }

  function pairItem(pair) {
    const [first, second] = pair.merchants;
    return h('div', { class: 'dup-item' },
      h('div', { class: 'dup-names' },
        ...pair.merchants.map((merchant) => h('span', { class: 'dup-name' },
          merchant.name, h('span', { class: 'manage-count' }, countLabel(merchant.expense_count))))),
      h('p', { class: 'dup-reason' }, pair.reason_name),
      h('div', { class: 'dup-actions' },
        h('button', { class: 'btn-text', type: 'button', onclick: () => notDuplicates(first, second) }, 'Non sono doppioni'),
        h('button', { class: 'btn-text', type: 'button', onclick: () => mergePair(first, second) }, 'Unisci')));
  }

  async function rename(merchant) {
    const name = await promptDialog({ title: 'Rinomina esercente', label: 'Nome', value: merchant.name });
    if (name === null || name === merchant.name) return;
    try {
      await api.patch(`/merchants/${merchant.id}`, { name });
      await refresh();
      toast('Esercente rinominato.', { kind: 'success' });
    } catch (error) { report(error, 'Non rinominato'); }
  }

  async function confirmAndMerge(source, into) {
    const confirmed = await confirmDialog({
      title: 'Confermi l’unione?',
      message: `Le spese di «${source.name}» passeranno a «${into.name}» e «${source.name}» sparirà. Non si può annullare.`,
      confirmLabel: 'Unisci',
    });
    if (!confirmed) return;
    try {
      await api.post(`/merchants/${source.id}/merge`, { into_id: into.id });
      await refresh();
      toast('Esercenti uniti.', { kind: 'success' });
    } catch (error) { report(error, 'Non uniti'); }
  }

  async function merge(merchant, all) {
    const target = await promptDialog({
      title: `Unisci «${merchant.name}»`,
      label: 'Sposta tutte le sue spese su',
      confirmLabel: 'Unisci',
      options: all.filter((other) => other.id !== merchant.id)
        .map((other) => ({ value: other.id, label: other.name })),
    });
    if (target === null) return;
    await confirmAndMerge(merchant, all.find((other) => String(other.id) === target));
  }

  // «Unisci» on a pair: first which name to keep.
  async function mergePair(first, second) {
    const keep = await choiceDialog({
      title: 'Quale nome tenere?',
      text: 'Le spese dell’altro passano al nome che scegli.',
      options: [first, second].map((merchant) => ({
        value: merchant.id, label: merchant.name, meta: countLabel(merchant.expense_count),
      })),
    });
    if (keep === null) return;
    const [into, source] = keep === first.id ? [first, second] : [second, first];
    await confirmAndMerge(source, into);
  }

  async function notDuplicates(first, second) {
    try {
      await api.post(`/merchants/${first.id}/distinct`, { other_id: second.id });
      await refresh();
    } catch (error) { report(error, 'Non salvato'); return; }
    toast(`«${first.name}» e «${second.name}»: non compariranno più come doppioni.`, {
      kind: 'success',
      action: {
        label: 'Annulla',
        run: async () => {
          try {
            await api.del(`/merchants/${first.id}/distinct/${second.id}`);
            await refresh();
          } catch (error) { report(error, 'Non annullato'); }
        },
      },
    });
  }

  return { element: h('div', {}, searchBox, duplicatesBox, allTitle, list), refresh };
}

// --- CSV export -------------------------------------------------------------

// 0.15.0: every export can be downloaded or shared. «Condividi» copies the
// text that goes with the files (GET /export/brief: what they hold, the
// totals to check them against, the rules of the app) and opens the share
// sheet with the files; «Scarica» saves them, and its confirmation offers
// to copy the same text. «Tutto» (until 0.14.0 «Per Claude») is spese,
// entrate and articoli Vinted together.
const EXPORT_KINDS = {
  expenses: { empty: 'Nel periodo non ci sono spese.' },
  incomes: { empty: 'Nel periodo non ci sono entrate.' },
  vinted: { empty: 'Non ci sono articoli Vinted.', allItems: true },
  all: { empty: 'Nel periodo non ci sono spese né entrate, e non ci sono articoli Vinted.' },
};

// Whether the "Condividi" button makes sense here: Chrome on Android in
// HTTPS (the Tailscale address) shares CSV files; plain HTTP does not.
function shareAvailable() {
  return canShareFiles([new File(['data'], 'prova.csv', { type: 'text/csv' })]);
}

function exportSection() {
  const month = h('input', {
    class: 'input', id: 'export-month', type: 'month', value: currentMonth(), max: currentMonth(),
  });
  const from = h('input', { class: 'input', id: 'export-from', type: 'date', value: `${currentMonth()}-01` });
  const to = h('input', { class: 'input', id: 'export-to', type: 'date', value: todayIso() });
  const monthFields = h('div', {}, h('label', { class: 'label', for: 'export-month' }, 'Mese'), month);
  const rangeFields = h('div', { class: 'two-cols', hidden: true },
    h('div', {}, h('label', { class: 'label', for: 'export-from' }, 'Dal'), from),
    h('div', {}, h('label', { class: 'label', for: 'export-to' }, 'Al'), to));

  let what = 'expenses';
  let period = 'month';
  let format = 'standard';
  const periodBlock = h('div', {});
  function choice(name, options, onPick) {
    return h('div', { class: 'radio-list' }, options.map((option, index) => h('label', { class: 'radio' },
      h('input', {
        type: 'radio', name, value: option.value, checked: index === 0,
        onchange: () => onPick(option.value),
      }),
      h('span', { class: 'radio-text' },
        h('span', {}, option.label),
        option.hint ? h('span', { class: 'radio-hint' }, option.hint) : null))));
  }

  periodBlock.append(
    h('span', { class: 'label' }, 'Periodo'),
    choice('export-period', [
      { value: 'month', label: 'Un mese' },
      { value: 'range', label: 'Un intervallo di date' },
    ], (value) => {
      period = value;
      monthFields.hidden = value !== 'month';
      rangeFields.hidden = value !== 'range';
    }),
    monthFields, rangeFields);

  // The query of GET /export/brief, or null after telling what is missing.
  function briefQuery() {
    const query = new URLSearchParams({ what, format });
    if (EXPORT_KINDS[what].allItems) return query;
    if (period === 'month') {
      if (!month.value) { toast('Scegli un mese.', { kind: 'error' }); return null; }
      query.set('month', month.value);
    } else {
      if (!from.value || !to.value) { toast('Indica entrambe le date.', { kind: 'error' }); return null; }
      if (from.value > to.value) { toast('La data iniziale viene dopo quella finale.', { kind: 'error' }); return null; }
      query.set('from', from.value);
      query.set('to', to.value);
    }
    return query;
  }

  async function withBrief(button, run) {
    const query = briefQuery();
    if (!query) return;
    buttons.forEach((each) => { each.disabled = true; });
    try {
      const brief = await api.get(`/export/brief?${query}`);
      if (!brief.files.length) toast(EXPORT_KINDS[what].empty, { kind: 'error' });
      else await run(brief);
    } catch (error) { report(error, 'Export non riuscito'); }
    buttons.forEach((each) => { each.disabled = false; });
  }

  const apiPath = (url) => url.replace(/^\/api\/v1/, '');

  const downloadButton = h('button', {
    class: 'btn btn-primary btn-grow', type: 'button',
    onclick: () => withBrief(downloadButton, async (brief) => {
      for (const file of brief.files) await api.download(apiPath(file.url), file.name);
      const many = brief.files.length > 1;
      toast(many ? `${brief.files.length} file scaricati.` : 'File scaricato.', {
        kind: 'success',
        duration: 8000,
        action: { label: 'Copia testo', run: () => copyText(brief.text, 'Testo copiato: incollalo con i file.') },
      });
    }),
  }, icon('download'), h('span', {}, 'Scarica'));

  const shareButton = h('button', {
    class: 'btn btn-quiet btn-grow', type: 'button', hidden: !shareAvailable(),
    onclick: () => withBrief(shareButton, async (brief) => {
      const files = [];
      for (const file of brief.files) {
        const blob = await api.blob(apiPath(file.url));
        files.push(new File([blob], file.name, { type: 'text/csv' }));
      }
      await shareFilesWithText(files, brief.text);
    }),
  }, icon('share'), h('span', {}, 'Condividi'));
  const buttons = [downloadButton, shareButton];

  const shareHint = h('p', { class: 'settings-text export-share-hint' },
    shareAvailable()
      ? '«Condividi» copia il testo che accompagna i file e apre il menu di Android: scegli Claude, Drive o un’altra app, allega i file e incolla il testo.'
      : '«Condividi» c’è sul telefono, dall’indirizzo di Tailscale. Qui i file si scaricano; dalla conferma puoi copiare il testo che li accompagna.');

  const formatBlock = h('div', {},
    h('span', { class: 'label' }, 'Formato'),
    choice('export-format', [
      { value: 'standard', label: 'Standard', hint: 'Virgola come separatore, punto decimale. Per l’analisi con un assistente AI.' },
      { value: 'excel_it', label: 'Excel italiano', hint: 'Punto e virgola come separatore, virgola decimale. Si apre con un doppio clic.' },
    ], (value) => { format = value; }));

  return h('div', {},
    h('span', { class: 'label' }, 'Cosa esportare'),
    choice('export-what', [
      { value: 'expenses', label: 'Spese' },
      { value: 'incomes', label: 'Entrate', hint: 'Un file a parte: data, importo, categoria, nota, ricevuto da.' },
      {
        value: 'vinted',
        label: 'Articoli Vinted',
        hint: 'Tutti gli articoli: acquisto, vendita, guadagno, giorni in vendita, prezzi dell’annuncio.',
      },
      {
        value: 'all',
        label: 'Tutto',
        hint: 'Spese ed entrate del periodo e tutti gli articoli Vinted, in file separati, con un testo che riassume i totali.',
      },
    ], (value) => {
      what = value;
      periodBlock.hidden = Boolean(EXPORT_KINDS[value].allItems);
    }),
    periodBlock,
    formatBlock,
    h('div', { class: 'export-actions' }, downloadButton, shareButton),
    shareHint);
}

// --- backup and restore -------------------------------------------------------

const KIND_LABELS = {
  daily: 'Copia del giorno',
  pre_update: 'Prima di un aggiornamento',
  pre_restore: 'Prima di un ripristino',
};

// "25 nov 2026, 18:02" in the phone's time (the server writes UTC).
function localStamp(iso) {
  return new Date(iso).toLocaleString('it-IT', {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

function sizeLabel(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace('.', ',')} MB`;
}

// After a restore, users and sessions come from the restored data: start over.
function restarted() {
  clearState();
  toast('Ripristino completato.', { kind: 'success' });
  setTimeout(() => location.assign('/'), 1200);
}

function backupSection() {
  // 0.14.0: when the last backup was downloaded, and by whom (shared by the
  // two phones), and the copies the server keeps by itself.
  const lastLine = h('p', { class: 'settings-text backup-last' });
  const copiesList = h('ul', { class: 'manage-list' });
  const copiesBlock = h('div', { hidden: true },
    h('h3', { class: 'settings-subtitle' }, 'Copie automatiche sull’Umbrel'),
    h('p', { class: 'settings-text' },
      'Una al giorno (le ultime 7), più una prima di ogni aggiornamento che cambia il database e una prima di ogni ripristino. Proteggono dagli errori, non da un guasto del disco: per quello scarica il backup ogni tanto, o attiva i Backup di umbrelOS (Settings → Backups).'),
    copiesList);

  async function refresh() {
    let info;
    try {
      info = await api.get('/backups');
    } catch (error) {
      lastLine.textContent = '';
      return;
    }
    const last = info.last_download;
    const days = last ? Math.floor((Date.now() - new Date(last.at).getTime()) / 86400000) : null;
    lastLine.classList.toggle('is-old', !last || days > 30);
    lastLine.textContent = last
      ? `Ultimo backup scaricato: ${localStamp(last.at)} (${last.user_name})${days > 30 ? `, ${days} giorni fa` : ''}.`
      : 'Nessun backup scaricato finora.';
    copiesBlock.hidden = !info.copies.length;
    copiesList.replaceChildren(...info.copies.map((copy) => h('li', { class: 'manage-item' },
      h('span', { class: 'manage-name' },
        localStamp(copy.created_at),
        h('span', { class: 'manage-count' }, `${KIND_LABELS[copy.kind]} · ${sizeLabel(copy.size_bytes)}`)),
      h('span', { class: 'manage-actions' },
        h('button', { class: 'btn-text', type: 'button', onclick: () => restoreCopy(copy) }, 'Ripristina')))));
  }

  async function restoreCopy(copy) {
    const confirmed = await confirmDialog({
      title: 'Ripristinare questa copia?',
      message: `Tutti i dati attuali (spese, entrate, categorie, esercenti, utenti e password) saranno sostituiti con quelli della copia del ${localStamp(copy.created_at)}. I dati attuali restano a loro volta in una copia.`,
      confirmLabel: 'Ripristina',
      danger: true,
    });
    if (!confirmed) return;
    try {
      await api.post(`/backups/${encodeURIComponent(copy.name)}/restore`);
      restarted();
    } catch (error) { report(error, 'Ripristino non riuscito'); }
  }

  const downloadButton = h('button', {
    class: 'btn btn-primary btn-block', type: 'button',
    onclick: async () => {
      downloadButton.disabled = true;
      // The file is named with the phone's own time (the server runs on UTC).
      const now = new Date();
      const pad = (number) => String(number).padStart(2, '0');
      const name = `spese-backup-${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}.db`;
      try {
        await api.download('/backup', name, { name });
        refresh();
      } catch (error) { report(error, 'Backup non riuscito'); }
      downloadButton.disabled = false;
    },
  }, 'Scarica backup');

  const fileInput = h('input', {
    class: 'visually-hidden', type: 'file', accept: '.db,application/octet-stream', id: 'restore-file',
    onchange: async () => {
      const file = fileInput.files[0];
      fileInput.value = '';
      if (!file) return;
      const confirmed = await confirmDialog({
        title: 'Ripristinare questo backup?',
        message: `Tutti i dati attuali (spese, entrate, categorie, esercenti, utenti e password) saranno sostituiti con quelli di «${file.name}». Una copia dei dati attuali resta sul server.`,
        confirmLabel: 'Ripristina',
        danger: true,
      });
      if (!confirmed) return;
      try {
        await api.restore(file);
        restarted();
      } catch (error) { report(error, 'Ripristino non riuscito'); }
    },
  });

  refresh();
  return h('div', {},
    h('p', { class: 'settings-text' },
      'Il backup è un unico file con tutti i dati dell’app, compresi gli utenti e le loro password in forma protetta: conservalo in un posto sicuro, fuori dall’Umbrel.'),
    lastLine,
    downloadButton,
    h('label', { class: 'btn btn-quiet btn-block', for: 'restore-file' }, 'Ripristina da file…'),
    fileInput,
    copiesBlock);
}

// --- account ------------------------------------------------------------------

function accountSection(users, navigate) {
  const current = passwordField({ id: 'pw-current', autocomplete: 'current-password' });
  const next = passwordField({ id: 'pw-new', autocomplete: 'new-password', minLength: 8 });
  const repeat = passwordField({ id: 'pw-repeat', autocomplete: 'new-password', minLength: 8 });
  const error = h('p', { class: 'form-error', role: 'alert', hidden: true });
  const form = h('form', {
    onsubmit: async (event) => {
      event.preventDefault();
      const problem = passwordProblem(next.input.value, repeat.input.value);
      error.textContent = problem || '';
      error.hidden = !problem;
      if (problem) return;
      try {
        await api.put(`/users/${state.me.id}/password`, {
          current_password: current.input.value, new_password: next.input.value,
        });
        for (const field of [current, next, repeat]) field.input.value = '';
        toast('Password cambiata.', { kind: 'success' });
      } catch (failure) { report(failure, 'Password non cambiata'); }
    },
  },
    h('label', { class: 'label', for: 'pw-current' }, 'Password attuale'), current.element,
    h('label', { class: 'label', for: 'pw-new' }, 'Nuova password (almeno 8 caratteri)'), next.element,
    h('label', { class: 'label', for: 'pw-repeat' }, 'Ripeti la nuova password'), repeat.element,
    error,
    h('button', { class: 'btn btn-primary btn-block', type: 'submit' }, 'Cambia password'));

  const others = users.filter((user) => user.id !== state.me.id).map((user) => h('button', {
    class: 'btn btn-quiet btn-block', type: 'button',
    onclick: async () => {
      const password = await newPasswordDialog({ title: `Nuova password per ${user.display_name}` });
      if (password === null) return;
      try {
        await api.put(`/users/${user.id}/password`, { new_password: password });
        toast(`Password di ${user.display_name} reimpostata.`, { kind: 'success' });
      } catch (error) { report(error, 'Password non reimpostata'); }
    },
  }, `${user.display_name} ha dimenticato la password`));

  const logout = h('button', {
    class: 'btn btn-danger-quiet btn-block', type: 'button',
    onclick: async () => {
      try { await api.post('/auth/logout'); } catch (error) { /* log out locally anyway */ }
      clearState();
      navigate('/login', { replace: true });
    },
  }, 'Esci');

  return h('div', {}, form, others, logout);
}

// --- view -----------------------------------------------------------------------

// Settings open from the icon at the top of the main screens (0.8.0): the
// arrow goes back to where they were opened from.
function head(ctx) {
  return h('header', { class: 'page-head' },
    h('a', {
      class: 'page-back', href: '/', 'aria-label': 'Indietro',
      onclick: (event) => { event.preventDefault(); ctx.back('/'); },
    }, '‹'),
    h('h1', { class: 'page-title' }, 'Impostazioni'));
}

export async function mount(root, ctx) {
  root.append(head(ctx), loadingBlock());

  const categories = categoriesSection();
  const merchants = merchantsSection();
  let users;
  try {
    [users] = await Promise.all([loadUsers(), categories.refresh(), merchants.refresh()]);
  } catch (error) {
    if (ctx.isCurrent()) {
      root.replaceChildren(errorBlock(error, () => ctx.navigate('/impostazioni', { replace: true })));
    }
    return;
  }
  if (!ctx.isCurrent()) return;

  const version = h('p', { class: 'settings-version' });
  fetch('/healthz').then((response) => response.json())
    .then((info) => { version.textContent = `Spese di Casa, versione ${info.version}`; })
    .catch(() => {});

  root.replaceChildren(
    head(ctx),
    h('a', { class: 'card settings-link', href: '/ricorrenti', dataset: { link: '' } },
      h('span', {},
        h('span', { class: 'settings-title' }, 'Ricorrenti'),
        h('span', { class: 'settings-hint' }, 'Abbonamenti, bollette e stipendi da registrare con un tocco')),
      h('span', { class: 'settings-go', 'aria-hidden': 'true' }, '›')),
    section('Categorie', 'Aggiungi, rinomina, riordina, disattiva', categories.element),
    section('Esercenti', 'Cerca, rinomina, unisci i doppioni', merchants.element),
    section('Esporta CSV', 'Spese, entrate, articoli Vinted o tutto: da scaricare o condividere', exportSection()),
    section('Backup e ripristino', 'Scarica, ricarica, copie automatiche', backupSection()),
    section('Account', 'Password, uscita', accountSection(users, ctx.navigate)),
    version);
}
