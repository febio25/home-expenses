// "Annuncio" (0.10.0): the ad of a Vinted item, as it goes on Vinted (title,
// description, asking price and the lowest one). "Incolla risposta di
// Claude" fills title, description and prices from Claude's answer; nothing
// is saved until "Salva annuncio".
//
// 0.11.0: the details have a screen of their own ("Dettagli", step 1 of the
// card). The title starts from the item's name when the ad has none of its
// own, and stays "none of its own" while it is left like that.

import { api } from '../api.js';
import { h, toast, vibrate, centsToInput, loadingBlock, errorBlock } from '../ui.js';
import { itemPath } from './vinted.js';
import { readAnswer, takeAnswer, priceInput } from '../vinted-listing.js';
import { planPayload } from '../vinted-markdown.js';

export async function mount(root, ctx) {
  const itemId = Number(ctx.params[0]);
  root.append(loadingBlock());
  let item;
  try {
    item = await api.get(`/vinted/items/${itemId}`);
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
  const listing = item.listing;
  const errorBanner = h('div', { class: 'banner banner-error', role: 'alert', hidden: true });
  const checkBanner = h('div', { class: 'banner banner-check', role: 'status', hidden: true });
  const hideError = () => { errorBanner.hidden = true; };

  const titleInput = h('input', {
    class: 'input', id: 'listing-title', type: 'text', maxLength: 200, autocomplete: 'off',
    autocapitalize: 'sentences', value: listing.effective_title, placeholder: item.title,
    enterkeyhint: 'next', oninput: hideError,
  });
  const descriptionInput = h('textarea', {
    class: 'input textarea', id: 'listing-description', maxLength: 5000, rows: 7,
    autocapitalize: 'sentences', placeholder: 'Com’è fatto, stato e difetti, misure.', oninput: hideError,
  }, listing.description || '');
  const priceField = priceInput('listing-price', listing.price_cents);
  const minField = priceInput('listing-min', listing.min_price_cents, 'Es. 18');
  const priceError = h('p', { class: 'field-error', hidden: true });
  // 0.19.0: the plan of the line RIBASSO, saved with the ad; without the
  // line the item keeps its plan.
  let markdown = null;
  const markdownHint = h('p', { class: 'form-hint md-hint', hidden: true });

  // Fill the form with what was recognised in Claude's answer.
  function apply(answer) {
    if (answer.title) titleInput.value = answer.title;
    if (answer.description) descriptionInput.value = answer.description;
    if (answer.price_cents) priceField.value = centsToInput(answer.price_cents);
    if (answer.min_price_cents) minField.value = centsToInput(answer.min_price_cents);
    markdown = answer.markdown ? planPayload(answer.markdown, 'claude') : null;
    markdownHint.hidden = !answer.markdown;
    if (answer.markdown) markdownHint.textContent = `Ribasso: ${answer.markdown.text} (proposto da Claude).`;
    const parts = [];
    if (!answer.recognized) parts.push('Risposta non nel formato atteso: tutto il testo è nella descrizione, controlla i campi.');
    if (answer.markdown_text && !answer.markdown) {
      parts.push(`Ribasso non letto («${answer.markdown_text}»): resta quello di prima, si cambia dalla scheda.`);
    }
    if (answer.check) parts.push(`Da controllare prima di pubblicare: ${answer.check}`);
    checkBanner.replaceChildren(...parts.map((text) => h('p', {}, text)));
    checkBanner.hidden = parts.length === 0;
    if (parts.length === 0) toast('Risposta inserita: controlla e salva.', { kind: 'success' });
  }

  async function paste() {
    const answer = await readAnswer();
    if (answer && ctx.isCurrent()) apply(answer);
  }

  const saveButton = h('button', {
    class: 'btn btn-primary btn-block btn-save', type: 'button',
    onpointerdown: (event) => event.preventDefault(), onclick: save,
  }, 'Salva annuncio');

  async function save() {
    if (saveButton.disabled) return;
    hideError();
    priceError.hidden = true;
    saveButton.disabled = true;
    // The item's name is the default title: kept as "no title of its own",
    // so a rename in the app still reaches the ad.
    const title = titleInput.value.trim().replace(/\s+/g, ' ');
    const payload = {
      listing_title: title && title !== item.title ? title : null,
      listing_description: descriptionInput.value.trim() || null,
      price: priceField.value.trim() || null,
      min_price: minField.value.trim() || null,
    };
    if (markdown) payload.markdown = markdown;
    try {
      await api.patch(`/vinted/items/${itemId}`, payload);
      vibrate();
      toast('Annuncio salvato.', { kind: 'success' });
      goBack();
    } catch (error) {
      saveButton.disabled = false;
      if (error.status === 401) return;
      if (error.status === 422 && /mporto|decimali|prezzo|minimo/i.test(error.message)) {
        priceError.textContent = error.message;
        priceError.hidden = false;
        priceField.scrollIntoView({ block: 'center' });
        return;
      }
      errorBanner.replaceChildren(
        h('strong', {}, 'Annuncio non salvato.'),
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
      h('h1', { class: 'page-title' }, 'Annuncio')),
    h('div', { class: 'vinted-form' },
      h('p', { class: 'form-hint form-hint-top' }, item.title),
      h('button', { class: 'btn btn-quiet btn-block', type: 'button', onclick: paste }, 'Incolla risposta di Claude'),
      checkBanner,
      h('label', { class: 'label', for: 'listing-title' }, 'Titolo'), titleInput,
      h('label', { class: 'label', for: 'listing-description' }, 'Descrizione'), descriptionInput,
      h('div', { class: 'price-pair' },
        h('div', {}, h('label', { class: 'label', for: 'listing-price' }, 'Prezzo'), priceField),
        h('div', {}, h('label', { class: 'label', for: 'listing-min' }, 'Minimo'), minField)),
      priceError,
      markdownHint,
      item.status === 'listed'
        ? h('p', { class: 'form-hint' }, 'È già su Vinted: un prezzo nuovo entra nello storico dei prezzi.')
        : null),
    h('div', { class: 'footer-bar' }, errorBanner, saveButton));

  const answer = takeAnswer(); // pasted from the item's screen just before
  if (answer) apply(answer);
}
