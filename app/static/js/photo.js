// Photos of the Vinted items. Chosen with the phone's own picker (camera or
// gallery), made smaller on the phone before upload, shown small at the
// start of a row and full size on a tap.

import { api } from './api.js';
import { h, icon } from './ui.js';
import { openOverlay, overlayClosed } from './overlay.js';

const IMAGE_SIDE = 1200;    // long side of the stored photo, in pixels
const THUMB_SIDE = 160;     // square thumbnail of the lists (56 px on screen, sharp up to 3x)
const IMAGE_QUALITY = 0.82;
const THUMB_QUALITY = 0.8;

// The address carries the photo's token: a new photo is a new address, so
// the phone may keep each one in its cache for good.
export function photoUrl(item, { thumb = false } = {}) {
  return `/api/v1/vinted/items/${item.id}/photo${thumb ? '/thumb' : ''}?v=${encodeURIComponent(item.photo)}`;
}

// The phone's picker: Android offers the camera and the gallery. Resolves
// to the chosen file, or null when the picker is dismissed.
export function pickImage() {
  return new Promise((resolve) => {
    const input = h('input', { type: 'file', accept: 'image/*', hidden: true });
    const done = (file) => { input.remove(); resolve(file); };
    input.addEventListener('change', () => done(input.files[0] || null));
    input.addEventListener('cancel', () => done(null));
    document.body.append(input);
    input.click();
  });
}

function draw(bitmap, width, height, crop = null) {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext('2d');
  context.fillStyle = '#fff'; // a transparent PNG turns white, not black
  context.fillRect(0, 0, width, height);
  if (crop) context.drawImage(bitmap, crop.x, crop.y, crop.side, crop.side, 0, 0, width, height);
  else context.drawImage(bitmap, 0, 0, width, height);
  return canvas;
}

// JPEG as a data: URL. Not a blob: URL, which the page's security policy
// does not allow for images; the base64 part is what the API takes.
function jpeg(canvas, quality) {
  const url = canvas.toDataURL('image/jpeg', quality);
  return { url, data: url.slice(url.indexOf(',') + 1) };
}

// Resized photo, square thumbnail and a preview address. Re-encoding drops
// the metadata of the original, location included. The orientation the
// camera recorded is applied first, so portrait photos stay upright.
export async function preparePhoto(file) {
  let bitmap;
  try {
    bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' });
  } catch (error) {
    throw new Error('Questa foto non si può leggere: scegline un’altra (JPEG o PNG).');
  }
  try {
    const scale = Math.min(1, IMAGE_SIDE / Math.max(bitmap.width, bitmap.height));
    const image = jpeg(
      draw(bitmap, Math.round(bitmap.width * scale), Math.round(bitmap.height * scale)), IMAGE_QUALITY);
    const side = Math.min(bitmap.width, bitmap.height);
    const crop = { x: (bitmap.width - side) / 2, y: (bitmap.height - side) / 2, side };
    const thumb = jpeg(draw(bitmap, THUMB_SIDE, THUMB_SIDE, crop), THUMB_QUALITY);
    return { image: image.data, thumb: thumb.data, preview: thumb.url };
  } finally {
    if (bitmap.close) bitmap.close();
  }
}

// Pick, resize and upload in one go. Resolves to the updated item, or null
// when the picker was dismissed. Errors carry a message for the user.
export async function choosePhotoFor(item) {
  const file = await pickImage();
  if (!file) return null;
  const photo = await preparePhoto(file);
  return api.uploadPhoto(item.id, photo);
}

// The sold mark of Vinted's own lists, on the corner of the thumbnail.
function soldMark(item) {
  return item.status === 'sold' ? h('span', { class: 'thumb-sold', 'aria-hidden': 'true' }, icon('check')) : null;
}

// Start of a row: the photo, which opens full size on a tap.
export function thumbButton(item, { large = false, caption = '' } = {}) {
  return h('button', {
    class: `thumb${large ? ' thumb-large' : ''}`,
    type: 'button',
    'aria-label': `Ingrandisci la foto: ${item.title}`,
    onclick: (event) => { event.preventDefault(); openPhoto(item, caption); },
  },
  h('img', { src: photoUrl(item, { thumb: true }), alt: '', loading: 'lazy', decoding: 'async' }),
  // 0.16.0: the large photo of the item screen has a pencil beside it
  // (vinted-item.js) in place of the enlarge mark; a tap still enlarges.
  large ? null : soldMark(item));
}

// Start of a row without a photo: a dashed frame, part of the row's link.
export function thumbPlaceholder(item) {
  return h('span', { class: 'thumb is-empty', 'aria-hidden': 'true' }, icon('image'), soldMark(item));
}

// Full-size photo over the whole screen. Closed by the X, a tap on the dark
// area or Android's back button.
export function openPhoto(item, caption = '') {
  const dialog = h('dialog', { class: 'viewer', 'aria-label': `Foto: ${item.title}` });
  const close = () => { if (dialog.open) dialog.close(); };
  dialog.append(
    h('button', { class: 'viewer-close', type: 'button', 'aria-label': 'Chiudi la foto', onclick: close },
      icon('close')),
    h('img', { class: 'viewer-img', src: photoUrl(item), alt: item.title }),
    h('p', { class: 'viewer-caption' },
      h('strong', {}, item.title),
      caption ? h('span', {}, caption) : null));
  dialog.addEventListener('click', (event) => { if (event.target === dialog) close(); });
  dialog.addEventListener('close', () => {
    dialog.remove();
    overlayClosed();
  });
  document.body.append(dialog);
  dialog.showModal();
  openOverlay(close);
}
