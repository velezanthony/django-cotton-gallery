/*!
 * Compare view — shared chrome controls + A/B pickers + swap.
 *
 * The two preview panels are wired by the existing `initPreview` (multi-instance),
 * so this module only owns:
 *   - Shared viewport switcher  → broadcasts `data-cg-viewport` to ALL devices
 *   - Shared background switcher → broadcasts `data-cg-bg` to ALL stages
 *   - A/B picker `<select>`s    → reload page with new `?a=...&b=...`
 *   - Swap button               → swap a and b in the URL
 *
 * Default viewport / bg are persisted to the same localStorage keys the
 * detail page uses, so your preference carries over.
 */

import { createIsolatedStage } from './isolated-stage.js';
import { attachResizeGrip } from './stage-resize.js';
import { bindOnce, buildQueryString, readJSON, wireFormDebounce } from './helpers.js';
import {
  PREVIEW_DEBOUNCE_MS,
  STORAGE_PREVIEW_BG as STORAGE_BG,
  STORAGE_PREVIEW_VIEWPORT as STORAGE_VP,
} from './constants.js';

const initSharedViewport = (root = document) => {
  const switcher = root.querySelector('[data-cg-shared-vp]');
  if (!switcher) return;
  if (!bindOnce(switcher, 'shared-vp')) return;

  const apply = (vp) => {
    root.querySelectorAll('[data-cg-preview-device]').forEach((d) => {
      d.setAttribute('data-cg-viewport', vp);
    });
    switcher.querySelectorAll('[data-cg-viewport]').forEach((b) => {
      b.classList.toggle('cg-active', b.getAttribute('data-cg-viewport') === vp);
    });
    try { localStorage.setItem(STORAGE_VP, JSON.stringify(vp)); } catch (_) { /* ignore */ }
  };

  // Initial state — read from storage, fall back to "desktop" (matches the
  // detail-page default in preview.js so the two don't diverge on ordering).
  const stored = readJSON(STORAGE_VP) || 'desktop';
  apply(stored);

  switcher.querySelectorAll('[data-cg-viewport]').forEach((btn) => {
    btn.addEventListener('click', () => apply(btn.getAttribute('data-cg-viewport')));
  });
};

const initSharedBg = (root = document) => {
  const switcher = root.querySelector('[data-cg-shared-bg]');
  if (!switcher) return;
  if (!bindOnce(switcher, 'shared-bg')) return;

  const apply = (bg) => {
    root.querySelectorAll('[data-cg-preview-stage]').forEach((s) => {
      s.setAttribute('data-cg-bg', bg);
    });
    switcher.querySelectorAll('[data-cg-bg]').forEach((b) => {
      b.classList.toggle('cg-active', b.getAttribute('data-cg-bg') === bg);
    });
    try { localStorage.setItem(STORAGE_BG, JSON.stringify(bg)); } catch (_) { /* ignore */ }
  };

  const stored = readJSON(STORAGE_BG) || 'checkered';
  apply(stored);

  switcher.querySelectorAll('[data-cg-bg]').forEach((btn) => {
    btn.addEventListener('click', () => apply(btn.getAttribute('data-cg-bg')));
  });
};

/**
 * Per-side AbortControllers — if the user picks two components quickly on
 * the same side, the second fetch wins; the first is cancelled so a stale
 * response can't overwrite the newer panel.
 */
const sideAbort = { a: null, b: null };

const buildUrl = (params) =>
  location.pathname + (params.toString() ? '?' + params.toString() : '');

/**
 * Fetch ONE side's partial and swap its panel into place.
 * Doesn't touch URL — caller is responsible for state sync (single source
 * of truth, easier to reason about for multi-side updates like swap).
 */
const fetchAndReplaceSide = async (side, params, bindContent) => {
  if (sideAbort[side]) sideAbort[side].abort();
  const ctrl = new AbortController();
  sideAbort[side] = ctrl;

  const fetchParams = new URLSearchParams(params);
  fetchParams.set('partial', side);
  const fetchUrl = location.pathname + '?' + fetchParams.toString();

  const container = document.querySelector('[data-cg-compare-side="' + side + '"]');
  if (!container) return;

  try {
    const res = await fetch(fetchUrl, {
      signal: ctrl.signal,
      headers: { 'X-Requested-With': 'cg-compare' },
    });
    if (!res.ok) return;
    const html = (await res.text()).trim();
    const tmpl = document.createElement('template');
    tmpl.innerHTML = html;
    const newPanel = tmpl.content.firstElementChild;
    if (!newPanel) return;
    // If the editor modal is open with an editor whose placeholder lives in
    // this panel, close it first — otherwise replacing the panel orphans
    // the editor inside the modal slot with no way back.
    const placeholder = container.querySelector('.cg-editor-modal__placeholder');
    if (placeholder) {
      document.querySelector('[data-cg-editor-modal] [data-cg-editor-modal-close]')?.click();
    }
    container.replaceWith(newPanel);
    if (typeof bindContent === 'function') bindContent();
    else initComparePanels(document);
  } catch (e) {
    if (e.name !== 'AbortError') console.error('[cg-compare] partial fetch failed', e);
  }
};

/**
 * Push a new {a, b} state and fetch only the sides that actually changed.
 * Single picker change → one fetch. Swap → two fetches in parallel.
 */
const applyState = async (a, b, sidesToFetch, bindContent) => {
  const params = new URLSearchParams();
  if (a) params.set('a', a);
  if (b) params.set('b', b);
  history.pushState(null, '', buildUrl(params));
  await Promise.all(sidesToFetch.map((s) => fetchAndReplaceSide(s, params, bindContent)));
};

/**
 * Searchable combobox — replaces native `<select>` for the A/B pickers.
 *
 * Native `<select>` dropdowns can't be styled in dark mode (the OS owns
 * the popup chrome) and don't filter — both blockers when the catalogue
 * grows past a few dozen components. This combobox is a button-trigger
 * + floating panel with a search input and a keyboard-navigable list.
 *
 * Wire-up is per-instance — each combo dispatches a `cg-combo-change`
 * CustomEvent so the picker layer can stay agnostic of the internals.
 */
const initCombo = (combo) => {
  if (!bindOnce(combo, 'combo')) return;
  const trigger = combo.querySelector('[data-cg-combo-trigger]');
  const labelEl = combo.querySelector('[data-cg-combo-label]');
  const panel = combo.querySelector('[data-cg-combo-panel]');
  const search = combo.querySelector('[data-cg-combo-search]');
  const list = combo.querySelector('[data-cg-combo-list]');
  const empty = combo.querySelector('[data-cg-combo-empty]');
  if (!trigger || !panel || !search || !list) return;

  const options = Array.from(list.querySelectorAll('[data-cg-combo-option]'));
  const groups = Array.from(list.querySelectorAll('[data-cg-combo-group]'));
  const placeholder = labelEl?.getAttribute('data-cg-combo-placeholder') || labelEl?.textContent || '';

  // Points at the current selection on open, so Enter confirms it instead
  // of the first visible entry (the "— None" clear option).
  let highlighted = null;

  const setOpen = (next) => {
    panel.toggleAttribute('hidden', !next);
    trigger.setAttribute('aria-expanded', String(next));
    combo.classList.toggle('cg-combo--open', next);
    if (next) {
      search.value = '';
      filter('');
      const current = combo.getAttribute('data-cg-combo-value') || '';
      highlighted = current
        ? options.find((o) => (o.getAttribute('data-cg-combo-option') || '') === current) || null
        : null;
      requestAnimationFrame(() => search.focus());
    }
  };
  const isOpen = () => !panel.hasAttribute('hidden');

  const filter = (q) => {
    const ql = q.toLowerCase().trim();
    let visibleCount = 0;
    options.forEach((o) => {
      const value = o.getAttribute('data-cg-combo-option') || '';
      const matches = !ql || value.toLowerCase().indexOf(ql) !== -1;
      o.toggleAttribute('hidden', !matches);
      if (matches) visibleCount += 1;
    });
    // Hide group headers whose options are all filtered out.
    groups.forEach((g) => {
      const visibleOpts = g.querySelectorAll('[data-cg-combo-option]:not([hidden])');
      g.toggleAttribute('hidden', visibleOpts.length === 0);
    });
    if (empty) empty.toggleAttribute('hidden', visibleCount > 0);
  };

  const choose = (value) => {
    // Unchanged pick — just close. Firing cg-combo-change would push a
    // redundant history entry and refetch the identical panel.
    if (value === (combo.getAttribute('data-cg-combo-value') || '')) {
      setOpen(false);
      trigger.focus();
      return;
    }
    combo.setAttribute('data-cg-combo-value', value);
    if (labelEl) {
      labelEl.textContent = value || placeholder;
      labelEl.classList.toggle('cg-combo__label--placeholder', !value);
    }
    options.forEach((o) => {
      o.classList.toggle('cg-active', (o.getAttribute('data-cg-combo-option') || '') === value);
    });
    setOpen(false);
    trigger.focus();
    combo.dispatchEvent(new CustomEvent('cg-combo-change', { detail: { value }, bubbles: true }));
  };

  const visibleOptions = () => options.filter((o) => !o.hasAttribute('hidden'));

  trigger.addEventListener('click', () => setOpen(!isOpen()));

  // Typing to filter drops the initial selection highlight so Enter picks
  // the first match instead of the (now possibly hidden) current value.
  search.addEventListener('input', () => { highlighted = null; filter(search.value); });
  search.addEventListener('keydown', (e) => {
    const visible = visibleOptions();
    if (e.key === 'Escape') {
      e.preventDefault();
      setOpen(false);
      trigger.focus();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      (highlighted || visible[0])?.focus();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const target = highlighted || visible[0];
      if (target) choose(target.getAttribute('data-cg-combo-option') || '');
    }
  });

  options.forEach((opt) => {
    opt.addEventListener('click', () => choose(opt.getAttribute('data-cg-combo-option') || ''));
    opt.addEventListener('keydown', (e) => {
      const visible = visibleOptions();
      const idx = visible.indexOf(document.activeElement);
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (idx === -1 || idx === visible.length - 1) visible[0]?.focus();
        else visible[idx + 1].focus();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (idx <= 0) search.focus();
        else visible[idx - 1].focus();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        setOpen(false);
        trigger.focus();
      } else if (e.key === 'Enter') {
        e.preventDefault();
        choose(opt.getAttribute('data-cg-combo-option') || '');
      }
    });
  });

  // Click outside or Esc — close.
  const onDocClick = (e) => { if (isOpen() && !combo.contains(e.target)) setOpen(false); };
  const onDocKey = (e) => { if (e.key === 'Escape' && isOpen()) { setOpen(false); trigger.focus(); } };
  document.addEventListener('click', onDocClick);
  document.addEventListener('keydown', onDocKey);
};

const initPickers = (root = document, { bindContent } = {}) => {
  const wrap = root.querySelector('[data-cg-compare-pickers]');
  if (!wrap) return;
  if (!bindOnce(wrap, 'compare-pickers')) return;

  wrap.querySelectorAll('[data-cg-combo]').forEach(initCombo);

  const comboA = wrap.querySelector('[data-cg-compare-combo="a"]');
  const comboB = wrap.querySelector('[data-cg-compare-combo="b"]');
  const valueOf = (combo) => (combo?.getAttribute('data-cg-combo-value') || '');

  if (comboA) {
    comboA.addEventListener('cg-combo-change', () => {
      applyState(valueOf(comboA), valueOf(comboB), ['a'], bindContent);
    });
  }
  if (comboB) {
    comboB.addEventListener('cg-combo-change', () => {
      applyState(valueOf(comboA), valueOf(comboB), ['b'], bindContent);
    });
  }

  const swap = wrap.querySelector('[data-cg-compare-swap]');
  if (swap) {
    swap.addEventListener('click', () => {
      const a = valueOf(comboA);
      const b = valueOf(comboB);
      // Swap the combo display values so the pickers visually flip too.
      setComboValue(comboA, b);
      setComboValue(comboB, a);
      applyState(b, a, ['a', 'b'], bindContent);
    });
  }

  // Browser back/forward — sync combos and panels to the new URL state
  // without pushing yet another history entry.
  window.addEventListener('popstate', () => {
    // Each SPA visit rebinds and stacks another listener — bail unless the
    // live wrap is ours, so stale listeners over detached combos no-op.
    if (document.querySelector('[data-cg-compare-pickers]') !== wrap) return;
    const params = new URLSearchParams(location.search);
    const a = params.get('a') || '';
    const b = params.get('b') || '';
    const sides = [];
    if (valueOf(comboA) !== a) { setComboValue(comboA, a); sides.push('a'); }
    if (valueOf(comboB) !== b) { setComboValue(comboB, b); sides.push('b'); }
    sides.forEach((s) => fetchAndReplaceSide(s, params, bindContent));
  });
};

/**
 * Mutate a combo's displayed value WITHOUT firing `cg-combo-change` —
 * used by the swap button so we can update both combos and trigger a
 * SINGLE atomic state update afterward (instead of two cascading ones).
 */
const setComboValue = (combo, value) => {
  if (!combo) return;
  combo.setAttribute('data-cg-combo-value', value);
  const label = combo.querySelector('[data-cg-combo-label]');
  const placeholder = label?.getAttribute('data-cg-combo-placeholder') || '';
  if (label) {
    label.textContent = value || placeholder;
    label.classList.toggle('cg-combo__label--placeholder', !value);
  }
  combo.querySelectorAll('[data-cg-combo-option]').forEach((o) => {
    o.classList.toggle('cg-active', (o.getAttribute('data-cg-combo-option') || '') === value);
  });
};

/**
 * Multi-instance preview wiring for the compare panels.
 *
 * `initPreview` (in preview.js) is singleton — it uses `querySelector` so
 * only the first `[data-cg-preview]` on the page gets fetched. This compare
 * module owns a simpler per-panel fetch loop that handles ALL panels:
 *
 *   - On boot, fetch each panel's preview-URL with its form's current values
 *   - On any form input, debounce + re-fetch THAT panel only
 *
 * The result HTML is injected into `[data-cg-preview-stage]` and the cotton
 * tag string into `[data-cg-preview-tag]`. No URL-state sync (the picker
 * dropdowns own URL state), no matrix mode, no raw-link mirror.
 */
const initComparePanels = (root = document) => {
  const panels = root.querySelectorAll('[data-cg-compare-side] [data-cg-preview]');
  panels.forEach((preview) => {
    if (!bindOnce(preview, 'compare-preview')) return;
    const url = preview.getAttribute('data-cg-preview');
    if (!url) return;
    const stage = preview.querySelector('[data-cg-preview-stage]');
    attachResizeGrip(stage);
    let frameStage = null;
    const isolated = () => (frameStage || (frameStage = createIsolatedStage(stage)));
    const dropFrame = () => { if (frameStage) { frameStage.destroy(); frameStage = null; } };
    const tagEl = preview.querySelector('[data-cg-preview-tag]');
    const form = preview.closest('[data-cg-compare-side]').querySelector('[data-cg-controls]');

    // Abort the in-flight fetch when a newer input supersedes it — a slow
    // stale response must not clobber the panel or a detached stage.
    let activeController = null;

    const fetchPreview = () => {
      const qs = form ? buildQueryString(form) : '';
      const fullUrl = url + (qs ? '?' + qs : '');

      if (activeController) activeController.abort();
      const controller = (typeof AbortController !== 'undefined') ? new AbortController() : null;
      activeController = controller;

      const fetchOpts = { headers: { 'X-Requested-With': 'cg-compare' } };
      if (controller) fetchOpts.signal = controller.signal;

      fetch(fullUrl, fetchOpts)
        .then((res) => res.ok ? res.json() : Promise.reject(new Error('HTTP ' + res.status)))
        .then((data) => {
          // Stage may have been swapped out between fetch start and resolve.
          if (!stage || !stage.isConnected) return;
          isolated().update(data.html || '');
          if (tagEl && tagEl.isConnected) {
            tagEl.textContent = data.tag || '';
            if (window.Prism) window.Prism.highlightElement(tagEl);
          }
        })
        .catch((err) => {
          if (err && err.name === 'AbortError') return;
          if (stage && stage.isConnected) {
            // Gallery chrome, not component output — render it in OUR document.
            dropFrame();
            stage.innerHTML = '<p class="cg-preview-error">Render error</p>';
          }
        });
    };

    // Same shared form-debounce wiring used by preview.js (helpers.js).
    wireFormDebounce(form, fetchPreview, PREVIEW_DEBOUNCE_MS);
    fetchPreview();
  });
};

export const initCompare = ({ bindContent } = {}) => {
  const root = document;
  initSharedViewport(root);
  initSharedBg(root);
  initPickers(root, { bindContent });
  initComparePanels(root);
};
