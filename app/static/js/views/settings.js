// "Impostazioni": categories, merchants, CSV export, backup, account.

import { api } from '../api.js';
import {
  state, loadUsers, loadCategories, loadMerchants, clearState, rememberCategories,
} from '../store.js';
import {
  h, icon, toast, confirmDialog, promptDialog, choiceDialog, currentMonth, todayIso, loadingBlock, errorBlock,
  passwordField, passwordProblem, newPasswordDialog, dayMonthShort,
} from '../ui.js';
import { copyText } from '../vinted-listing.js';

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
    // The Vinted category (0.8.0) can be renamed, never deactivated: the
    // section of the same name relies on it.
    list.replaceChildren(...categories.map((category) => h('li', { class: 'manage-item' },
      h('span', { class: 'manage-name' },
        category.name,
        category.is_active ? null : h('span', { class: 'tag' }, 'disattivata'),
        category.system_key === 'vinted' ? h('span', { class: 'tag' }, 'usata dalla sezione Vinted') : null),
      h('span', { class: 'manage-actions' },
        h('button', { class: 'btn-text', type: 'button', onclick: () => rename(category) }, 'Rinomina'),
        category.system_key ? null : h('button', {
          class: 'btn-text', type: 'button', onclick: () => toggle(category),
        }, category.is_active ? 'Disattiva' : 'Riattiva')))));
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

  async function rename(category) {
    const name = await promptDialog({ title: 'Rinomina categoria', label: 'Nome', value: category.name });
    if (name === null || name === category.name) return;
    try {
      await api.patch(`/categories/${category.id}`, { name });
      await refresh();
      toast('Categoria rinominata.', { kind: 'success' });
    } catch (error) { report(error, 'Non rinominata'); }
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
      const name = nameInput.value.trim();
      if (!name) return;
      try {
        await api.post('/categories', { name });
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
  // Separate files: the expense CSV keeps its usual columns. The Vinted
  // items are all exported, with no period: they live for months.
  // "Per Claude" (0.14.0): the expense and income files of the period, in
  // the standard format, plus a text to paste with them (claudePackage).
  const EXPORTS = {
    expenses: { path: '/export.csv', fallbackName: 'spese.csv' },
    incomes: { path: '/export/incomes.csv', fallbackName: 'entrate.csv' },
    vinted: { path: '/export/vinted.csv', fallbackName: 'vinted_articoli.csv', allItems: true },
    claude: { path: '/export/brief', package: true },
  };
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

  const button = h('button', {
    class: 'btn btn-primary btn-block', type: 'button',
    onclick: async () => {
      const query = new URLSearchParams({ format });
      if (!EXPORTS[what].allItems && period === 'month') {
        if (!month.value) { toast('Scegli un mese.', { kind: 'error' }); return; }
        query.set('month', month.value);
      } else if (!EXPORTS[what].allItems) {
        if (!from.value || !to.value) { toast('Indica entrambe le date.', { kind: 'error' }); return; }
        if (from.value > to.value) { toast('La data iniziale viene dopo quella finale.', { kind: 'error' }); return; }
        query.set('from', from.value);
        query.set('to', to.value);
      }
      button.disabled = true;
      try {
        if (EXPORTS[what].package) {
          query.delete('format');
          await claudePackage(query);
        } else {
          await api.download(`${EXPORTS[what].path}?${query}`, EXPORTS[what].fallbackName);
        }
      } catch (error) { report(error, 'Export non riuscito'); }
      button.disabled = false;
    },
  }, 'Scarica CSV');
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
        value: 'claude',
        label: 'Per Claude',
        hint: 'Spese ed entrate del periodo in formato standard, più un testo da incollare con i totali per il controllo e le regole dell’app.',
      },
    ], (value) => {
      what = value;
      periodBlock.hidden = Boolean(EXPORTS[value].allItems);
      formatBlock.hidden = Boolean(EXPORTS[value].package);
      button.textContent = EXPORTS[value].package ? 'Scarica i file e copia il testo' : 'Scarica CSV';
    }),
    periodBlock,
    formatBlock,
    button);
}

// "Per Claude" (0.14.0): the files of the period and the text that goes with
// them. The app sends nothing anywhere: it downloads the files and copies
// the text; in Claude, a new chat of the project, the files attached and
// the text pasted.
async function claudePackage(query) {
  const brief = await api.get(`/export/brief?${query}`);
  if (!brief.files.length) {
    toast('Nel periodo non ci sono spese né entrate.', { kind: 'error' });
    return;
  }
  for (const file of brief.files) {
    await api.download(file.url.replace(/^\/api\/v1/, ''), file.name);
  }
  const files = brief.files.length === 1 ? 'il file' : `i ${brief.files.length} file`;
  await copyText(brief.text, `File scaricati e testo copiato: in Claude allega ${files} e incolla il testo.`);
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
    section('Esporta CSV', 'Spese, entrate, articoli Vinted o per Claude', exportSection()),
    section('Backup e ripristino', 'Scarica, ricarica, copie automatiche', backupSection()),
    section('Account', 'Password, uscita', accountSection(users, ctx.navigate)),
    version);
}
