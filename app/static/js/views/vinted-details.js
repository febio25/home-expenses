// "Dettagli" (0.11.0): step 1 of an item's ad. What it is, brand, size,
// condition, measurements, defects (for books author, publisher and year)
// and the prices seen on Vinted: the request for Claude is written from
// these. Until 0.10.0 they sat at the bottom of the "Annuncio" screen.

import { api } from '../api.js';
import { h, toast, vibrate, loadingBlock, errorBlock } from '../ui.js';
import { itemPath } from './vinted.js';
import { loadListingOptions, detailsFields } from '../vinted-listing.js';

export async function mount(root, ctx) {
  const itemId = Number(ctx.params[0]);
  root.append(loadingBlock());
  let item;
  let options;
  try {
    [item, options] = await Promise.all([api.get(`/vinted/items/${itemId}`), loadListingOptions()]);
  } catch (error) {
    if (!ctx.isCurrent()) return;
    if (error.status === 404) {
      toast('Questo articolo non esiste più.', { kind: 'error' });
      ctx.back('/vinted');
    } else {
      root.replaceChildren(errorBlock(error, () => ctx.navigate(location.pathname, { replace: true })));
    }
    return;
  }
  if (!ctx.isCurrent()) return;

  const goBack = () => ctx.back(itemPath(itemId));
  const details = detailsFields({ options, details: item.details, idPrefix: 'details' });
  const errorBanner = h('div', { class: 'banner banner-error', role: 'alert', hidden: true });

  const saveButton = h('button', {
    class: 'btn btn-primary btn-block btn-save', type: 'button',
    onpointerdown: (event) => event.preventDefault(), onclick: save,
  }, 'Salva dettagli');

  async function save() {
    if (saveButton.disabled) return;
    errorBanner.hidden = true;
    saveButton.disabled = true;
    try {
      await api.patch(`/vinted/items/${itemId}`, details.toPayload());
      vibrate();
      toast('Dettagli salvati.', { kind: 'success' });
      goBack();
    } catch (error) {
      saveButton.disabled = false;
      if (error.status === 401) return;
      errorBanner.replaceChildren(
        h('strong', {}, 'Dettagli non salvati.'),
        h('span', {}, error.network
          ? ' La connessione è caduta: i dati sono ancora qui. Controlla Tailscale e riprova.'
          : ` ${error.message}`));
      errorBanner.hidden = false;
    }
  }

  root.replaceChildren(
    h('header', { class: 'page-head' },
      h('a', {
        class: 'page-back', href: itemPath(itemId), 'aria-label': 'Torna all’articolo',
        onclick: (event) => { event.preventDefault(); goBack(); },
      }, '‹'),
      h('h1', { class: 'page-title' }, 'Dettagli')),
    h('div', { class: 'vinted-form' },
      h('p', { class: 'form-hint form-hint-top' }, item.title),
      h('p', { class: 'form-hint' }, 'Servono a Claude per scrivere l’annuncio. Per un annuncio completo: tipo, stato e marca (l’autore per i libri).'),
      details.element),
    h('div', { class: 'footer-bar' }, errorBanner, saveButton));
}
