// App shell: boot, routing, bottom navigation, service worker registration.

import { api } from './api.js';
import {
  state, loadMe, clearState, invalidateLists, hydrate, refreshLists,
} from './store.js';
import { h, icon, errorBlock, placeToasts } from './ui.js';
import { handleOverlayPop } from './overlay.js';
import * as loginView from './views/login.js';
import * as setupView from './views/setup.js';
import * as newView from './views/new.js';
import * as editView from './views/edit.js';
import * as movementsView from './views/movements.js';
import * as incomesView from './views/incomes.js';
import * as incomeFormView from './views/income-form.js';
import * as summaryView from './views/summary.js';
import { incomesRedirect } from './views/summary.js';
import * as summaryCategoryView from './views/summary-category.js';
import * as settingsView from './views/settings.js';
import * as recurringView from './views/recurring.js';
import * as recurringFormView from './views/recurring-form.js';
import * as recurringIncomeFormView from './views/recurring-income-form.js';
import * as vintedView from './views/vinted.js';
import * as vintedSummaryView from './views/vinted-summary.js';
import * as vintedNewView from './views/vinted-new.js';
import * as vintedItemView from './views/vinted-item.js';
import * as vintedSellView from './views/vinted-sell.js';
import * as vintedListingView from './views/vinted-listing-edit.js';
import * as vintedDetailsView from './views/vinted-details.js';
import { mountFor as exploreFor } from './views/explore.js';

const ROUTES = [
  { pattern: /^\/$/, view: newView, tab: 'new' },
  { pattern: /^\/movimenti$/, view: movementsView, tab: 'movements' },
  { pattern: /^\/spesa\/(\d+)$/, view: editView, tab: 'movements' },
  { pattern: /^\/entrate$/, view: incomesView, tab: 'movements' },
  { pattern: /^\/entrate\/(nuova|\d+)$/, view: incomeFormView, tab: 'movements' },
  { pattern: /^\/riepilogo$/, view: summaryView, tab: 'summary' },
  { pattern: /^\/riepilogo\/categoria\/(\d+)$/, view: summaryCategoryView, tab: 'summary' },
  { pattern: /^\/riepilogo\/entrate$/, view: incomesRedirect, tab: 'summary' },
  { pattern: /^\/riepilogo\/esplora$/, view: { mount: exploreFor('house') }, tab: 'summary' },
  { pattern: /^\/vinted$/, view: vintedView, tab: 'vinted' },
  { pattern: /^\/vinted\/riepilogo$/, view: vintedSummaryView, tab: 'vinted' },
  { pattern: /^\/vinted\/riepilogo\/esplora$/, view: { mount: exploreFor('vinted') }, tab: 'vinted' },
  { pattern: /^\/vinted\/nuovo$/, view: vintedNewView, tab: 'vinted' },
  { pattern: /^\/vinted\/articolo\/(\d+)$/, view: vintedItemView, tab: 'vinted' },
  { pattern: /^\/vinted\/articolo\/(\d+)\/venduto$/, view: vintedSellView, tab: 'vinted' },
  { pattern: /^\/vinted\/articolo\/(\d+)\/annuncio$/, view: vintedListingView, tab: 'vinted' },
  { pattern: /^\/vinted\/articolo\/(\d+)\/dettagli$/, view: vintedDetailsView, tab: 'vinted' },
  // Settings open from the icon at the top of the main screens (0.8.0): the
  // bottom bar stays, with no tab lit.
  { pattern: /^\/impostazioni$/, view: settingsView, tab: 'none' },
  { pattern: /^\/ricorrenti$/, view: recurringView, tab: 'none' },
  { pattern: /^\/ricorrenti\/(nuova|\d+)(?:\/(registra))?$/, view: recurringFormView, tab: 'none' },
  { pattern: /^\/ricorrenti\/entrate\/(nuova|\d+)(?:\/(registra))?$/, view: recurringIncomeFormView, tab: 'none' },
  { pattern: /^\/login$/, view: loginView, public: true },
  { pattern: /^\/setup$/, view: setupView, public: true },
];

const TABS = [
  { id: 'new', path: '/', label: 'Nuova', icon: 'plus' },
  { id: 'movements', path: '/movimenti', label: 'Movimenti', icon: 'list' },
  { id: 'summary', path: '/riepilogo', label: 'Riepilogo', icon: 'chart' },
  { id: 'vinted', path: '/vinted', label: 'Vinted', icon: 'tag' },
];

const viewRoot = document.getElementById('view');
const nav = document.getElementById('nav');
let cleanup = null;
let renderToken = 0;
// Set by the current view through ctx.onResume(fn); see "back to the app".
let resumeHandler = null;

// Entries pushed from inside the app are marked, so a screen can tell
// whether "back" leads to another screen of the app (see goBack).
export function navigate(path, { replace = false } = {}) {
  if (replace) history.replaceState(history.state, '', path);
  else history.pushState({ inApp: true }, '', path);
  return render();
}

// Back to the screen the user came from (the summary of a category, the
// month list...), like Android's back button. When the screen was opened
// directly (app shortcut, address bar) there is nothing behind it in the
// app: go to `fallback` instead.
function goBack(fallback) {
  if (history.state && history.state.inApp) history.back();
  else navigate(fallback, { replace: true });
}

function renderNav(activeTab) {
  nav.hidden = !activeTab;
  if (!activeTab) return;
  nav.replaceChildren(...TABS.map((tab) => h('a', {
    class: `nav-item${tab.id === activeTab ? ' is-active' : ''}`,
    href: tab.path,
    'aria-current': tab.id === activeTab ? 'page' : null,
    dataset: { link: '' },
  }, icon(tab.icon), h('span', { class: 'nav-label' }, tab.label))));
}

async function render() {
  const token = ++renderToken;
  const path = location.pathname;
  let route = null;
  let match = null;
  for (const candidate of ROUTES) {
    match = path.match(candidate.pattern);
    if (match) { route = candidate; break; }
  }
  if (!route) return navigate('/', { replace: true });

  if (!route.public && !state.me) return navigate('/login', { replace: true });
  if (route.public && state.me) return navigate('/', { replace: true });

  if (cleanup) { try { cleanup(); } catch (error) { /* ignore */ } cleanup = null; }
  resumeHandler = null;
  renderNav(route.public ? null : route.tab);
  const container = h('div', { class: 'view-inner' });
  viewRoot.replaceChildren(container);
  viewRoot.scrollTop = 0;
  const result = await route.view.mount(container, {
    params: match.slice(1),
    query: new URLSearchParams(location.search),
    navigate,
    isCurrent: () => token === renderToken,
    onResume: (handler) => { if (token === renderToken) resumeHandler = handler; },
    back: (fallback) => { if (token === renderToken) goBack(fallback); },
  });
  if (token === renderToken) {
    cleanup = typeof result === 'function' ? result : null;
    placeToasts(); // a toast shown before navigating moves above the new screen's bars
  } else if (typeof result === 'function') result();
  return undefined;
}

// Decide where to start: the app, the login screen, or first-run setup.
// 0.14.0: with the lists of the last session on the phone the app opens at
// once, before any answer from the server; the session and the lists are
// checked in the background (checkSession).
async function boot() {
  if (hydrate()) {
    checkSession();
    await render();
    return;
  }
  try {
    await loadMe();
  } catch (error) {
    if (error.network) {
      viewRoot.replaceChildren(h('div', { class: 'view-inner' }, errorBlock(error, boot)));
      return;
    }
    clearState();
    let needsSetup = false;
    try {
      needsSetup = (await api.get('/setup/status')).needs_setup;
    } catch (statusError) {
      viewRoot.replaceChildren(h('div', { class: 'view-inner' }, errorBlock(statusError, boot)));
      return;
    }
    const target = needsSetup ? '/setup' : '/login';
    if (location.pathname !== target) history.replaceState(null, '', target);
  }
  await render();
}

async function checkSession() {
  try {
    await loadMe();
  } catch (error) {
    if (error.status === 401) { // signed out or expired meanwhile
      clearState();
      navigate('/login', { replace: true });
    }
    return; // no network: keep going with what is on the phone
  }
  refreshLists().catch(() => { /* the lists of last time stay */ });
}

// In-app links: <a data-link href="/movimenti">
document.addEventListener('click', (event) => {
  const link = event.target.closest('a[data-link]');
  if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey) return;
  event.preventDefault();
  if (link.pathname + link.search !== location.pathname + location.search) {
    navigate(link.pathname + link.search);
  }
});

// Back closes the full-size photo first (overlay.js), then leaves screens.
window.addEventListener('popstate', () => {
  if (handleOverlayPop()) return;
  render();
});

// The session expired or was revoked while the app was open.
window.addEventListener('spese:unauthorized', () => {
  if (!state.me) return;
  clearState();
  navigate('/login', { replace: true });
});

// Back to the app. An installed PWA is rarely restarted: it sits in the
// background for hours, maybe until the next day. When it comes back the
// current view gets a chance to catch up: today's date, and what the other
// person entered meanwhile. After a short absence (switching to the bank
// app to check an amount) the cached lists are kept.
const RESUME_REFRESH_AFTER_MS = 60 * 1000;
let hiddenAt = 0;
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') { hiddenAt = Date.now(); return; }
  if (!state.me) return;
  const longAway = Boolean(hiddenAt) && Date.now() - hiddenAt >= RESUME_REFRESH_AFTER_MS;
  if (longAway) invalidateLists();
  if (resumeHandler) {
    try { resumeHandler({ longAway }); } catch (error) { /* a refresh must never break the view */ }
  }
});

// Hide the bottom navigation while the on-screen keyboard is open: it already
// takes half the screen and the Save button must stay visible. With
// interactive-widget=resizes-content the window gets shorter when the
// keyboard opens, so a clear drop from the tallest height seen means "open".
// Otherwise the bar never moves, scrolling included. The drop alone is not
// enough: without a text field in focus there is no keyboard, whatever made
// the window shorter, and the bar must come back as soon as the field is
// left, without waiting for the window to grow again.
const KEYBOARD_MIN_HEIGHT = 150;
// Inputs that never open the keyboard (Android shows a picker or nothing).
const NO_KEYBOARD_TYPES = new Set([
  'button', 'checkbox', 'color', 'date', 'datetime-local', 'file', 'hidden', 'image',
  'month', 'radio', 'range', 'reset', 'submit', 'time', 'week',
]);
function isEditingText() {
  const field = document.activeElement;
  if (!field) return false;
  if (field.isContentEditable) return true;
  if (field.tagName === 'TEXTAREA') return !field.readOnly && !field.disabled;
  if (field.tagName !== 'INPUT') return false;
  return !NO_KEYBOARD_TYPES.has(field.type) && !field.readOnly && !field.disabled;
}
let fullHeight = window.innerHeight;
let knownWidth = window.innerWidth;
function trackKeyboard() {
  if (window.innerWidth !== knownWidth) { // rotated or resized: start over
    knownWidth = window.innerWidth;
    fullHeight = window.innerHeight;
  }
  fullHeight = Math.max(fullHeight, window.innerHeight);
  const keyboardOpen = isEditingText() && fullHeight - window.innerHeight > KEYBOARD_MIN_HEIGHT;
  document.body.classList.toggle('is-typing', keyboardOpen);
  placeToasts(); // keep a visible toast just above the bottom bars
}
window.addEventListener('resize', trackKeyboard);
document.addEventListener('focusin', trackKeyboard);
// On focusout the next field (if any) is not focused yet: look a moment later.
document.addEventListener('focusout', () => setTimeout(trackKeyboard, 0));

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => { /* the app works without it */ });
  });
}

boot();
