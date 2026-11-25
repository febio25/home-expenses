// Session-wide state: who is logged in, plus the reference lists every
// screen needs (users, categories, merchants).
//
// 0.14.0: the four are also kept in localStorage, so the app opens at once
// with the lists of the last time (hydrate) and checks them in the
// background (refreshLists). Without a network, or with a slow one, the
// entry form is there anyway and the amount can be typed: saving still
// needs the server, as before.

import { api } from './api.js';
import { viewCache } from './cache.js';

export const state = {
  me: null,          // { id, display_name }
  users: null,       // [{ id, display_name }]
  categories: null,  // active and inactive
  merchants: null,   // most used first
  incomeCategories: null, // fixed list [{ code, name }], changes only with a new version
};

const LISTS_KEY = 'lists';

// Write the lists known now to localStorage (only for a signed-in user).
function persist() {
  if (!state.me) return;
  local.set(LISTS_KEY, {
    me: state.me, users: state.users, categories: state.categories, merchants: state.merchants,
  });
}

// The lists of the last session, if any: true when the app can open
// straight away. Each list may be null (never loaded): then it is fetched.
export function hydrate() {
  const saved = local.get(LISTS_KEY);
  if (!saved || !saved.me || typeof saved.me.id !== 'number') return false;
  state.me = saved.me;
  state.users = saved.users || null;
  state.categories = saved.categories || null;
  state.merchants = saved.merchants || null;
  return true;
}

// Fetch the three lists again, then tell the open screen (event
// "spese:lists"), which can update its suggestions and buttons.
export async function refreshLists() {
  const [users, categories, merchants] = await Promise.all([
    api.get('/users'), api.get('/categories?include_inactive=true'), api.get('/merchants'),
  ]);
  Object.assign(state, { users, categories, merchants });
  persist();
  window.dispatchEvent(new CustomEvent('spese:lists'));
}

export async function loadMe() {
  state.me = await api.get('/auth/me');
  persist();
  return state.me;
}

export async function loadUsers({ force = false } = {}) {
  if (!state.users || force) {
    state.users = await api.get('/users');
    persist();
  }
  return state.users;
}

export async function loadCategories({ force = false } = {}) {
  if (!state.categories || force) {
    state.categories = await api.get('/categories?include_inactive=true');
    persist();
  }
  return state.categories;
}

// A list saved elsewhere (the new order of the categories, 0.14.0).
export function rememberCategories(list) {
  state.categories = list;
  persist();
}

export async function loadMerchants({ force = false } = {}) {
  if (!state.merchants || force) {
    state.merchants = await api.get('/merchants');
    persist();
  }
  return state.merchants;
}

export async function loadIncomeCategories() {
  if (!state.incomeCategories) state.incomeCategories = await api.get('/incomes/categories');
  return state.incomeCategories;
}

// Forget the cached lists; the next load* call fetches them again.
export function invalidateLists() {
  state.users = null;
  state.categories = null;
  state.merchants = null;
}

export function clearState() {
  state.me = null;
  state.users = null;
  state.categories = null;
  state.merchants = null;
  state.incomeCategories = null;
  local.remove(LISTS_KEY);
  viewCache.clear();
}

// Per-device preferences and the unsent draft live in localStorage. Access
// is wrapped: storage can be unavailable or full, and that must never break
// entering an expense.
export const local = {
  get(key, fallback = null) {
    try {
      const raw = localStorage.getItem(`spese.${key}`);
      return raw === null ? fallback : JSON.parse(raw);
    } catch (error) {
      return fallback;
    }
  },
  set(key, value) {
    try { localStorage.setItem(`spese.${key}`, JSON.stringify(value)); } catch (error) { /* ignore */ }
  },
  remove(key) {
    try { localStorage.removeItem(`spese.${key}`); } catch (error) { /* ignore */ }
  },
};
