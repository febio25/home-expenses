// Session-wide state: who is logged in, plus the reference lists every
// screen needs (users, categories, merchants). Kept in memory only.

import { api } from './api.js';

export const state = {
  me: null,          // { id, display_name }
  users: null,       // [{ id, display_name }]
  categories: null,  // active and inactive
  merchants: null,   // most used first
  incomeCategories: null, // fixed list [{ code, name }], changes only with a new version
};

export async function loadMe() {
  state.me = await api.get('/auth/me');
  return state.me;
}

export async function loadUsers({ force = false } = {}) {
  if (!state.users || force) state.users = await api.get('/users');
  return state.users;
}

export async function loadCategories({ force = false } = {}) {
  if (!state.categories || force) {
    state.categories = await api.get('/categories?include_inactive=true');
  }
  return state.categories;
}

export async function loadMerchants({ force = false } = {}) {
  if (!state.merchants || force) state.merchants = await api.get('/merchants');
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
