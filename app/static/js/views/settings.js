// "Impostazioni": categories, merchants, CSV export, backup, account.

import { api } from '../api.js';
import { state, loadUsers, loadCategories, loadMerchants, clearState } from '../store.js';
import {
  h, toast, confirmDialog, promptDialog, currentMonth, todayIso, loadingBlock, errorBlock,
  passwordField, passwordProblem, newPasswordDialog,
} from '../ui.js';

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

  async function refresh() {
    const categories = await loadCategories({ force: true });
    list.replaceChildren(...categories.map((category) => h('li', { class: 'manage-item' },
      h('span', { class: 'manage-name' },
        category.name,
        category.is_active ? null : h('span', { class: 'tag' }, 'disattivata')),
      h('span', { class: 'manage-actions' },
        h('button', { class: 'btn-text', type: 'button', onclick: () => rename(category) }, 'Rinomina'),
        h('button', {
          class: 'btn-text', type: 'button', onclick: () => toggle(category),
        }, category.is_active ? 'Disattiva' : 'Riattiva')))));
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

  return { element: h('div', {}, list, form), refresh };
}

// --- merchants --------------------------------------------------------------

function merchantsSection() {
  const list = h('ul', { class: 'manage-list' });

  async function refresh() {
    const merchants = await loadMerchants({ force: true });
    if (merchants.length === 0) {
      list.replaceChildren(h('li', { class: 'manage-empty' },
        'Gli esercenti compaiono qui dopo la prima spesa.'));
      return;
    }
    const sorted = [...merchants].sort((a, b) => a.name.localeCompare(b.name, 'it'));
    list.replaceChildren(...sorted.map((merchant) => h('li', { class: 'manage-item' },
      h('span', { class: 'manage-name' },
        merchant.name,
        h('span', { class: 'manage-count' },
          merchant.expense_count === 1 ? '1 spesa' : `${merchant.expense_count} spese`)),
      h('span', { class: 'manage-actions' },
        h('button', { class: 'btn-text', type: 'button', onclick: () => rename(merchant) }, 'Rinomina'),
        merchants.length > 1
          ? h('button', { class: 'btn-text', type: 'button', onclick: () => merge(merchant, sorted) }, 'Unisci')
          : null))));
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

  async function merge(merchant, all) {
    const target = await promptDialog({
      title: `Unisci «${merchant.name}»`,
      label: 'Sposta tutte le sue spese su',
      confirmLabel: 'Unisci',
      options: all.filter((other) => other.id !== merchant.id)
        .map((other) => ({ value: other.id, label: other.name })),
    });
    if (target === null) return;
    const into = all.find((other) => String(other.id) === target);
    const confirmed = await confirmDialog({
      title: 'Confermi l’unione?',
      message: `Le spese di «${merchant.name}» passeranno a «${into.name}» e «${merchant.name}» sparirà. Non si può annullare.`,
      confirmLabel: 'Unisci',
    });
    if (!confirmed) return;
    try {
      await api.post(`/merchants/${merchant.id}/merge`, { into_id: into.id });
      await refresh();
      toast('Esercenti uniti.', { kind: 'success' });
    } catch (error) { report(error, 'Non uniti'); }
  }

  return { element: list, refresh };
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
  // Two separate files: the expense CSV keeps its usual columns.
  const EXPORTS = {
    expenses: { path: '/export.csv', fallbackName: 'spese.csv' },
    incomes: { path: '/export/incomes.csv', fallbackName: 'entrate.csv' },
  };
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

  const button = h('button', {
    class: 'btn btn-primary btn-block', type: 'button',
    onclick: async () => {
      const query = new URLSearchParams({ format });
      if (period === 'month') {
        if (!month.value) { toast('Scegli un mese.', { kind: 'error' }); return; }
        query.set('month', month.value);
      } else {
        if (!from.value || !to.value) { toast('Indica entrambe le date.', { kind: 'error' }); return; }
        if (from.value > to.value) { toast('La data iniziale viene dopo quella finale.', { kind: 'error' }); return; }
        query.set('from', from.value);
        query.set('to', to.value);
      }
      button.disabled = true;
      try {
        await api.download(`${EXPORTS[what].path}?${query}`, EXPORTS[what].fallbackName);
      } catch (error) { report(error, 'Export non riuscito'); }
      button.disabled = false;
    },
  }, 'Scarica CSV');

  return h('div', {},
    h('span', { class: 'label' }, 'Cosa esportare'),
    choice('export-what', [
      { value: 'expenses', label: 'Spese' },
      { value: 'incomes', label: 'Entrate', hint: 'Un file a parte: data, importo, categoria, nota, ricevuto da.' },
    ], (value) => { what = value; }),
    h('span', { class: 'label' }, 'Periodo'),
    choice('export-period', [
      { value: 'month', label: 'Un mese' },
      { value: 'range', label: 'Un intervallo di date' },
    ], (value) => {
      period = value;
      monthFields.hidden = value !== 'month';
      rangeFields.hidden = value !== 'range';
    }),
    monthFields, rangeFields,
    h('span', { class: 'label' }, 'Formato'),
    choice('export-format', [
      { value: 'standard', label: 'Standard', hint: 'Virgola come separatore, punto decimale. Per l’analisi con un assistente AI.' },
      { value: 'excel_it', label: 'Excel italiano', hint: 'Punto e virgola come separatore, virgola decimale. Si apre con un doppio clic.' },
    ], (value) => { format = value; }),
    button);
}

// --- backup and restore -------------------------------------------------------

function backupSection() {
  const downloadButton = h('button', {
    class: 'btn btn-primary btn-block', type: 'button',
    onclick: async () => {
      downloadButton.disabled = true;
      try {
        await api.download('/backup', 'spese-backup.db');
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
        clearState();
        toast('Ripristino completato.', { kind: 'success' });
        // Start over: users and sessions now come from the backup.
        setTimeout(() => location.assign('/'), 1200);
      } catch (error) { report(error, 'Ripristino non riuscito'); }
    },
  });

  return h('div', {},
    h('p', { class: 'settings-text' },
      'Il backup è un unico file con tutti i dati dell’app, compresi gli utenti e le loro password in forma protetta: conservalo in un posto sicuro.'),
    downloadButton,
    h('label', { class: 'btn btn-quiet btn-block', for: 'restore-file' }, 'Ripristina da file…'),
    fileInput);
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

export async function mount(root, ctx) {
  root.append(
    h('header', { class: 'page-head' }, h('h1', { class: 'page-title' }, 'Impostazioni')),
    loadingBlock());

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
    h('header', { class: 'page-head' },
      h('h1', { class: 'page-title' }, 'Impostazioni'),
      h('span', { class: 'page-who' }, state.me.display_name)),
    h('a', { class: 'card settings-link', href: '/ricorrenti', dataset: { link: '' } },
      h('span', {},
        h('span', { class: 'settings-title' }, 'Spese ricorrenti'),
        h('span', { class: 'settings-hint' }, 'Abbonamenti e bollette da registrare con un tocco')),
      h('span', { class: 'settings-go', 'aria-hidden': 'true' }, '›')),
    section('Categorie', 'Aggiungi, rinomina, disattiva', categories.element),
    section('Esercenti', 'Rinomina o unisci i doppioni', merchants.element),
    section('Esporta CSV', 'Spese o entrate, per mese o intervallo di date', exportSection()),
    section('Backup e ripristino', 'Scarica o ricarica tutti i dati', backupSection()),
    section('Account', 'Password, uscita', accountSection(users, ctx.navigate)),
    version);
}
