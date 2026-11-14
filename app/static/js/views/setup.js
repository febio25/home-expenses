// First-run setup: create the two household users. Shown only while the
// database has no users.

import { api } from '../api.js';
import { h, passwordField, passwordProblem } from '../ui.js';

const MIN_PASSWORD = 8;

function personFields(index, defaultName) {
  const name = h('input', {
    class: 'input', id: `setup-name-${index}`, type: 'text', required: true, maxLength: 40,
    value: defaultName, autocomplete: 'off', autocapitalize: 'words',
  });
  const password = passwordField({
    id: `setup-password-${index}`, autocomplete: 'new-password', minLength: MIN_PASSWORD,
  });
  const repeat = passwordField({
    id: `setup-repeat-${index}`, autocomplete: 'new-password', minLength: MIN_PASSWORD,
  });
  const block = h('fieldset', { class: 'card setup-person' },
    h('legend', { class: 'setup-legend' }, index === 0 ? 'Prima persona' : 'Seconda persona'),
    h('label', { class: 'label', for: name.id }, 'Nome'),
    name,
    h('label', { class: 'label', for: password.input.id }, `Password (almeno ${MIN_PASSWORD} caratteri)`),
    password.element,
    h('label', { class: 'label', for: repeat.input.id }, 'Ripeti la password'),
    repeat.element);
  return { block, name, password: password.input, repeat: repeat.input };
}

export async function mount(root, { navigate }) {
  const people = [personFields(0, 'Fabio'), personFields(1, 'Nastia')];
  const error = h('p', { class: 'form-error', role: 'alert', hidden: true });
  const submit = h('button', { class: 'btn btn-primary btn-block', type: 'submit' }, 'Crea gli utenti');

  const form = h('form', {
    class: 'auth-form',
    onsubmit: async (event) => {
      event.preventDefault();
      error.hidden = true;
      const names = people.map((person) => person.name.value.trim());
      if (names[0].toLowerCase() === names[1].toLowerCase()) {
        error.textContent = 'I due nomi devono essere diversi.';
        error.hidden = false;
        return;
      }
      for (const [index, person] of people.entries()) {
        const problem = passwordProblem(person.password.value, person.repeat.value, MIN_PASSWORD);
        if (problem) {
          error.textContent = `${names[index] || 'Persona ' + (index + 1)}: ${problem.toLowerCase()}`;
          error.hidden = false;
          person.repeat.focus();
          return;
        }
      }
      submit.disabled = true;
      try {
        await api.post('/setup', {
          users: people.map((person, index) => ({ name: names[index], password: person.password.value })),
        });
        navigate('/login', { replace: true });
      } catch (failure) {
        error.textContent = failure.status === 409
          ? 'Gli utenti esistono già: vai alla schermata di accesso.'
          : failure.message;
        error.hidden = false;
        submit.disabled = false;
      }
    },
  }, people.map((person) => person.block), error, submit);

  root.classList.add('view-auth');
  root.append(
    h('h1', { class: 'auth-title' }, 'Spese di Casa'),
    h('p', { class: 'auth-lead' },
      'Prima configurazione: scegli nome e password per le due persone che useranno l’app. Ognuno accederà con le proprie.'),
    form);
}
