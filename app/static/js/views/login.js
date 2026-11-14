// Login screen. The session lasts 90 days, so this is rarely seen.

import { api } from '../api.js';
import { loadMe } from '../store.js';
import { h, passwordField } from '../ui.js';

export async function mount(root, { navigate }) {
  const error = h('p', { class: 'form-error', role: 'alert', hidden: true });
  const username = h('input', {
    class: 'input', id: 'login-name', name: 'username', type: 'text', required: true,
    autocomplete: 'username', autocapitalize: 'words', placeholder: 'Fabio',
  });
  // Phone keyboards must not "correct" the name.
  username.setAttribute('autocorrect', 'off');
  username.setAttribute('spellcheck', 'false');
  const { element: passwordBox, input: password } = passwordField({
    id: 'login-password', autocomplete: 'current-password',
  });
  password.name = 'password';
  const submit = h('button', { class: 'btn btn-primary btn-block', type: 'submit' }, 'Accedi');

  const form = h('form', {
    class: 'auth-form',
    onsubmit: async (event) => {
      event.preventDefault();
      error.hidden = true;
      submit.disabled = true;
      submit.textContent = 'Accesso…';
      try {
        await api.post('/auth/login', { username: username.value, password: password.value });
        try {
          await loadMe();
        } catch (sessionError) {
          // The password was right but the browser did not keep the cookie:
          // it is marked Secure and the page was opened over plain HTTP.
          throw new Error(location.protocol === 'https:'
            ? 'Accesso riuscito, ma il browser non ha salvato la sessione. Riprova.'
            : 'Accesso riuscito, ma la sessione non si salva su una connessione non protetta. Apri l’app dal suo indirizzo https://');
        }
        navigate('/', { replace: true });
      } catch (failure) {
        error.textContent = failure.status === 401
          ? 'Nome o password non corretti. Tocca «Mostra» per controllare la password. Dopo 5 tentativi sbagliati l’accesso si blocca per 5 minuti.'
          : failure.message;
        error.hidden = false;
        submit.disabled = false;
        submit.textContent = 'Accedi';
      }
    },
  },
    h('label', { class: 'label', for: 'login-name' }, 'Nome'),
    username,
    h('label', { class: 'label', for: 'login-password' }, 'Password'),
    passwordBox,
    error,
    submit);

  root.classList.add('view-auth');
  root.append(
    h('h1', { class: 'auth-title' }, 'Spese di Casa'),
    h('p', { class: 'auth-lead' }, 'Accedi per registrare le spese.'),
    form);
  username.focus();
}
