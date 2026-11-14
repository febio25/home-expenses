// "Riepilogo": month total and total per category. Deliberately simple:
// the real analysis happens on the exported CSV.

import { api } from '../api.js';
import { h, formatEuro, formatShare, monthLabel, currentMonth, loadingBlock, errorBlock } from '../ui.js';
import { monthSwitcher } from './movements.js';

// Donut of the month: the five largest categories plus "Altre". Colors go
// by rank within the month (largest first); the legend next to the ring
// names every slice with its share, so color is never the only cue.
// Palette checked with the dataviz validator (light surface, adjacent pairs).
const SLICE_COLORS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4'];
const OTHER_COLOR = '#8a9690';
const MAX_SLICES = 5;
const SVG = 'http://www.w3.org/2000/svg';

function svg(tag, attrs = {}) {
  const node = document.createElementNS(SVG, tag);
  for (const [name, value] of Object.entries(attrs)) node.setAttribute(name, String(value));
  return node;
}

function slicesOf(summary) {
  const top = summary.by_category.slice(0, MAX_SLICES).map((category, index) => ({
    name: category.category_name, cents: category.total_cents, color: SLICE_COLORS[index],
  }));
  const rest = summary.by_category.slice(MAX_SLICES);
  if (rest.length) {
    top.push({
      name: rest.length === 1 ? rest[0].category_name : `Altre (${rest.length})`,
      cents: rest.reduce((sum, category) => sum + category.total_cents, 0),
      color: OTHER_COLOR,
    });
  }
  return top;
}

function donut(summary) {
  const slices = slicesOf(summary);
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const gap = slices.length > 1 ? 1.2 : 0; // thin surface gap between slices
  const ring = svg('svg', { viewBox: '0 0 100 100', class: 'donut-svg', 'aria-hidden': 'true' });
  ring.append(svg('circle', { cx: 50, cy: 50, r: radius, fill: 'none', stroke: '#EEF2F0', 'stroke-width': 16 }));
  let start = 0;
  for (const slice of slices) {
    const length = (slice.cents / summary.total_cents) * circumference;
    const arc = svg('circle', {
      cx: 50, cy: 50, r: radius, fill: 'none', stroke: slice.color, 'stroke-width': 16,
      'stroke-dasharray': `${Math.max(0.5, length - gap)} ${circumference}`,
      'stroke-dashoffset': -start,
      transform: 'rotate(-90 50 50)',
    });
    const tip = svg('title');
    tip.textContent = `${slice.name}: ${formatEuro(slice.cents)}`;
    arc.append(tip);
    ring.append(arc);
    start += length;
  }

  const legend = h('ul', { class: 'donut-legend' }, slices.map((slice) => {
    const swatch = h('span', { class: 'donut-swatch' });
    swatch.style.background = slice.color;
    return h('li', { class: 'donut-item' },
      swatch,
      h('span', { class: 'donut-name' }, slice.name),
      h('span', { class: 'donut-share' }, formatShare(slice.cents, summary.total_cents)));
  }));

  const label = slices.map((slice) =>
    `${slice.name} ${formatShare(slice.cents, summary.total_cents)}`).join(', ');
  // No figure in the hole: the total is written right above the chart, and a
  // five-digit amount did not fit inside the ring.
  return h('figure', { class: 'card donut', 'aria-label': `Ripartizione del mese: ${label}` },
    h('div', { class: 'donut-ring' }, ring),
    legend);
}

export async function mount(root, ctx) {
  let month = currentMonth();
  const switcherSlot = h('div');
  const body = h('div');
  root.append(
    h('header', { class: 'page-head' }, h('h1', { class: 'page-title' }, 'Riepilogo')),
    switcherSlot, body);

  // quiet: see the same option in movements.js.
  async function show(nextMonth, { quiet = false } = {}) {
    month = nextMonth;
    switcherSlot.replaceChildren(monthSwitcher(month, show));
    if (!quiet) body.replaceChildren(loadingBlock());
    let summary;
    try {
      summary = await api.get(`/summary?month=${month}`);
    } catch (error) {
      if (!quiet && ctx.isCurrent() && month === nextMonth) body.replaceChildren(errorBlock(error, () => show(month)));
      return;
    }
    if (!ctx.isCurrent() || month !== nextMonth) return;

    if (summary.expense_count === 0) {
      body.replaceChildren(h('div', { class: 'empty' },
        h('p', { class: 'empty-title' }, `Nessuna spesa a ${monthLabel(month)}`)));
      return;
    }

    const largest = summary.by_category[0].total_cents;
    body.replaceChildren(
      h('div', { class: 'receipt receipt-total' },
        h('span', { class: 'receipt-label' }, `Totale di ${monthLabel(month)}`),
        h('span', { class: 'receipt-figure' }, formatEuro(summary.total_cents)),
        h('span', { class: 'receipt-sub' },
          summary.expense_count === 1 ? '1 spesa' : `${summary.expense_count} spese`)),
      donut(summary),
      h('h2', { class: 'section-title' }, 'Per categoria'),
      h('ul', { class: 'card bars' }, summary.by_category.map((category) => {
        const fill = h('span', { class: 'bar-fill' });
        // Bars are relative to the largest category, so the top one is full width.
        fill.style.width = `${Math.max(2, Math.round((category.total_cents / largest) * 100))}%`;
        return h('li', { class: 'bar' },
          h('span', { class: 'bar-head' },
            h('span', { class: 'bar-name' }, category.category_name),
            h('span', { class: 'bar-amount' }, formatEuro(category.total_cents))),
          h('span', { class: 'bar-track' }, fill),
          h('span', { class: 'bar-meta' },
            `${formatShare(category.total_cents, summary.total_cents)} del mese, ${category.expense_count === 1 ? '1 spesa' : `${category.expense_count} spese`}`));
      })));
  }

  ctx.onResume(({ longAway }) => { if (longAway) show(month, { quiet: true }); });
  await show(month);
}
