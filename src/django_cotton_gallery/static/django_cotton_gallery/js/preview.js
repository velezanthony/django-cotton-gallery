/*!
 * Preview feature module.
 *
 * Owns: background switcher, viewport switcher, custom dropdowns, extra-attrs
 * autocomplete, live preview fetch/render, URL state sync, form helpers.
 *
 * The live preview renders into an iframe (js/isolated-stage.js): Alpine and
 * HTMX are rehydrated in there, not here.
 */

import {
  bindOnce,
  buildQueryString,
  escapeHtml,
  readJSON,
  toggleHidden,
  wireFormDebounce,
  writeJSON,
} from './helpers.js';
import {
  PREVIEW_DEBOUNCE_MS,
  STORAGE_PREVIEW_BG,
  STORAGE_PREVIEW_BG_COLORS,
  STORAGE_PREVIEW_VIEWPORT,
  MATRIX_CELL_ROOT_MARGIN,
} from './constants.js';
import { initMiniSelect } from './ui-bits.js';
import { createPopover } from './popover.js';
import { createIsolatedStage } from './isolated-stage.js';
import { attachResizeGrip } from './stage-resize.js';
import { cssContext, filterCssProperties, suggestCssValue } from './css-properties.js';
import { caretRectFromContenteditable } from './caret-rect.js';
import { ATTR_SUGGESTIONS, tokenName, writtenAttrNames } from './html-attrs.js';

// STORAGE_PREVIEW_BG / STORAGE_PREVIEW_VIEWPORT come from constants.js — see imports.

/* ── Preview background switcher ────────────────────────────────────── */
// Persists the user's preferred preview backdrop across sessions and SPA navs.
// Re-queries stages on every `applyBg` so the compare view (two stages) and
// post-swap fresh stages from `_compare_panel.html` partials all stay in sync
// with the toolbar state. Without this, only the first stage gets the
// attribute and side B falls back to its default (no bg, no theme tint).
export const initPreviewBgSwitcher = () => {
  const buttons = document.querySelectorAll('.cg-bg-btn[data-cg-bg]');
  if (!buttons.length) return;

  // Edit controls live on the detail page only; the compare view reuses the
  // same swatches without them, so everything below degrades to null/empty.
  const editBtn = document.querySelector('[data-cg-bg-editcmd="edit"]');
  const doneBtn = document.querySelector('[data-cg-bg-editcmd="done"]');
  const resetBtn = document.querySelector('[data-cg-bg-editcmd="reset"]');
  const editInputs = document.querySelectorAll('[data-cg-bg-edit]');
  const switcher = editBtn ? editBtn.closest('.cg-preview__bg-switcher') : null;
  const DEFAULTS = { white: '#ffffff', dark: '#111827', brand: '#ff9d0a' };

  // Unsaved swatch-color edits. Null outside edit mode; while editing it holds
  // the working colors — they only reach localStorage when the user hits Done.
  let draft = null;

  // Push a color map into the CSS vars (or clear back to the CSS defaults) and
  // sync each picker's value.
  const applyColors = (colors) => {
    editInputs.forEach((inp) => {
      const name = inp.getAttribute('data-cg-bg-edit');
      if (colors[name]) {
        document.documentElement.style.setProperty('--cg-bg-' + name, colors[name]);
        inp.value = colors[name];
      } else {
        document.documentElement.style.removeProperty('--cg-bg-' + name);
        inp.value = DEFAULTS[name] || '#ffffff';
      }
    });
  };

  // Re-query stages on every apply so compare's two stages stay in sync.
  const applyBg = (value) => {
    document
      .querySelectorAll('[data-cg-preview-stage]')
      .forEach((stage) => stage.setAttribute('data-cg-bg', value));
    buttons.forEach((btn) => {
      const isActive = btn.getAttribute('data-cg-bg') === value;
      btn.classList.toggle('cg-active', isActive);
      btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });
  };

  applyColors(readJSON(STORAGE_PREVIEW_BG_COLORS) || {});
  applyBg(readJSON(STORAGE_PREVIEW_BG) || 'checkered');

  // A swatch selects that background; in edit mode an editable swatch also
  // opens its color picker (guard against the programmatic click bubbling back).
  buttons.forEach((btn) => {
    if (!bindOnce(btn, 'bg')) return;
    btn.addEventListener('click', (e) => {
      const input = btn.querySelector('[data-cg-bg-edit]');
      if (e.target === input) return;
      const value = btn.getAttribute('data-cg-bg');
      applyBg(value);
      writeJSON(STORAGE_PREVIEW_BG, value);
      if (switcher && switcher.classList.contains('cg-editing') && input) input.click();
    });
  });

  // Picking a color previews it live and stages it in the draft — not saved
  // until Done.
  editInputs.forEach((inp) => {
    if (!bindOnce(inp, 'bg')) return;
    inp.addEventListener('input', () => {
      const name = inp.getAttribute('data-cg-bg-edit');
      document.documentElement.style.setProperty('--cg-bg-' + name, inp.value);
      if (draft) draft[name] = inp.value;
    });
  });

  const setEditing = (on) => {
    if (switcher) switcher.classList.toggle('cg-editing', on);
    if (editBtn) editBtn.hidden = on;
    if (doneBtn) doneBtn.hidden = !on;
    if (resetBtn) resetBtn.hidden = !on;
  };

  // Enter edit mode with a working copy of the saved colors.
  if (editBtn && bindOnce(editBtn, 'bg')) {
    editBtn.addEventListener('click', () => {
      draft = { ...(readJSON(STORAGE_PREVIEW_BG_COLORS) || {}) };
      setEditing(true);
    });
  }
  // Done commits the draft; leaving without it keeps localStorage untouched.
  if (doneBtn && bindOnce(doneBtn, 'bg')) {
    doneBtn.addEventListener('click', () => {
      if (draft) writeJSON(STORAGE_PREVIEW_BG_COLORS, draft);
      draft = null;
      setEditing(false);
    });
  }
  // Reset stages a return to the CSS defaults (still only saved on Done).
  if (resetBtn && bindOnce(resetBtn, 'bg')) {
    resetBtn.addEventListener('click', () => {
      draft = {};
      applyColors({});
    });
  }
};

/* ── Preview viewport switcher ──────────────────────────────────────── */
// Constrains the stage's max-width to simulate device viewports. Same
// "query inside applyViewport" pattern as the bg switcher so the compare
// view's two panels (and any panel re-rendered via partial swap) all
// receive the current viewport attribute.
export const initPreviewViewportSwitcher = () => {
  const buttons = document.querySelectorAll('.cg-vp-btn[data-cg-viewport]');
  if (!buttons.length) return;
  // Quick existence check — bail if no targets at all.
  const probe =
    document.querySelector('[data-cg-preview-device]') ||
    document.querySelector('[data-cg-preview-stage]');
  if (!probe) return;

  const validValues = Array.from(buttons, (b) => b.getAttribute('data-cg-viewport'));

  const applyViewport = (value) => {
    // Prefer the device wrapper(s) so chrome scales with the viewport;
    // fall back to stages on pages that don't render a device chrome.
    const targets = document.querySelectorAll('[data-cg-preview-device]');
    const finalTargets = targets.length
      ? targets
      : document.querySelectorAll('[data-cg-preview-stage]');
    finalTargets.forEach((t) => t.setAttribute('data-cg-viewport', value));
    buttons.forEach((btn) => {
      const isActive = btn.getAttribute('data-cg-viewport') === value;
      btn.classList.toggle('cg-active', isActive);
      btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });
  };

  // Old saved values may reference a viewport that no longer exists on
  // this page (e.g. `full` was retired on detail). Fall back gracefully.
  const saved = readJSON(STORAGE_PREVIEW_VIEWPORT);
  const initial = validValues.indexOf(saved) !== -1
    ? saved
    : (validValues.indexOf('desktop') !== -1 ? 'desktop' : validValues[validValues.length - 1]);
  applyViewport(initial);

  buttons.forEach((btn) => {
    if (!bindOnce(btn, 'vp')) return;
    btn.addEventListener('click', () => {
      const value = btn.getAttribute('data-cg-viewport');
      applyViewport(value);
      writeJSON(STORAGE_PREVIEW_VIEWPORT, value);
    });
  });
};

/* ── Custom dropdown (with search) ──────────────────────────────────── */
// Replaces native <select> in the controls panel. SPA-safe via `bindOnce`.
export const initDropdowns = (root = document) => {
  const dropdowns = root.querySelectorAll('[data-cg-dropdown]');
  dropdowns.forEach((dropdown) => {
    if (!bindOnce(dropdown, 'dropdown')) return;

    const trigger = dropdown.querySelector('[data-cg-dropdown-trigger]');
    const valueEl = dropdown.querySelector('[data-cg-dropdown-value]');
    const menu = dropdown.querySelector('[data-cg-dropdown-menu]');
    const search = dropdown.querySelector('[data-cg-dropdown-search]');
    const input = dropdown.querySelector('[data-cg-dropdown-input]');
    const emptyEl = dropdown.querySelector('[data-cg-dropdown-empty]');
    if (!trigger || !menu || !input) return;

    const items = Array.from(menu.querySelectorAll('[data-cg-dropdown-option]'));
    let highlighted = -1;

    // Shared popover handles position:fixed (escapes overflow:clip parents),
    // outside-click, scroll-close, resize-reposition. Dropdown-specific
    // setup (search, highlight) wraps open/close below.
    const popover = createPopover(trigger, menu, { flipAbove: false });

    const setHighlight = (idx) => {
      items.forEach((it, i) => {
        if (i === idx) it.classList.add('cg-highlighted');
        else it.classList.remove('cg-highlighted');
      });
      highlighted = idx;
      if (idx >= 0 && items[idx]) items[idx].scrollIntoView({ block: 'nearest' });
    };

    const visibleItems = () => items.filter((it) => it.style.display !== 'none');

    const filterItems = (query) => {
      const q = (query || '').toLowerCase().trim();
      let anyVisible = false;
      items.forEach((it) => {
        const match = !q || it.textContent.toLowerCase().indexOf(q) !== -1;
        it.style.display = match ? '' : 'none';
        if (match) anyVisible = true;
      });
      if (emptyEl) toggleHidden(emptyEl, anyVisible);
      const visible = visibleItems();
      setHighlight(visible.length ? items.indexOf(visible[0]) : -1);
    };

    const open = () => {
      popover.open();
      trigger.setAttribute('aria-expanded', 'true');
      if (search) {
        search.value = '';
        filterItems('');
        // Slight delay so the focus transition lands after the menu paints.
        setTimeout(() => search.focus(), 0);
      }
      let selectedIdx = -1;
      items.forEach((it, i) => {
        if (it.getAttribute('data-cg-dropdown-option') === input.value) selectedIdx = i;
      });
      setHighlight(selectedIdx >= 0 ? selectedIdx : 0);
    };

    const close = () => {
      popover.close();
      trigger.setAttribute('aria-expanded', 'false');
    };

    const selectValue = (value) => {
      input.value = value;
      if (valueEl) valueEl.textContent = value;
      items.forEach((it) => {
        const match = it.getAttribute('data-cg-dropdown-option') === value;
        it.setAttribute('aria-selected', match ? 'true' : 'false');
        // Toggle the inline check icon on the right of each item.
        const existingCheck = it.querySelector('.cg-dropdown__item-check');
        if (match && !existingCheck) {
          const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
          svg.setAttribute('class', 'cg-dropdown__item-check');
          svg.setAttribute('viewBox', '0 0 24 24');
          svg.setAttribute('fill', 'none');
          svg.setAttribute('stroke', 'currentColor');
          svg.setAttribute('stroke-width', '2.5');
          svg.setAttribute('stroke-linecap', 'round');
          svg.setAttribute('stroke-linejoin', 'round');
          svg.setAttribute('aria-hidden', 'true');
          svg.innerHTML = '<path d="M20 6 9 17l-5-5"/>';
          it.appendChild(svg);
        } else if (!match && existingCheck) {
          existingCheck.remove();
        }
      });
      // Dispatch input + change so the form's preview handler fires.
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
      close();
      trigger.focus();
    };

    trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      if (menu.hasAttribute('hidden')) open();
      else close();
    });
    items.forEach((it) => {
      it.addEventListener('click', () => {
        selectValue(it.getAttribute('data-cg-dropdown-option'));
      });
    });
    if (search) {
      search.addEventListener('input', () => filterItems(search.value));
      search.addEventListener('keydown', (e) => {
        const visible = visibleItems();
        if (!visible.length) return;
        const currentVisIdx = visible.indexOf(items[highlighted]);
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          const next = (currentVisIdx + 1) % visible.length;
          setHighlight(items.indexOf(visible[next]));
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          const prev = (currentVisIdx - 1 + visible.length) % visible.length;
          setHighlight(items.indexOf(visible[prev]));
        } else if (e.key === 'Enter') {
          e.preventDefault();
          if (highlighted >= 0 && items[highlighted].style.display !== 'none') {
            selectValue(items[highlighted].getAttribute('data-cg-dropdown-option'));
          }
        } else if (e.key === 'Escape') {
          e.preventDefault();
          close();
          trigger.focus();
        }
      });
    }
  });
};

/* ── Extra-attrs autocomplete ───────────────────────────────────────── */
// `ATTR_SUGGESTIONS` is shared with the slot editor — see js/html-attrs.js.

/**
 * Expand toggle for the attrs contenteditable — flips between the default
 * single-line look and a taller multi-line area. Mirrors the slot expander.
 */
export const initAttrsExpanders = (root = document) => {
  const btns = root.querySelectorAll('[data-cg-attrs-expand]');
  btns.forEach((btn) => {
    if (!bindOnce(btn, 'attrs-expand')) return;
    btn.addEventListener('click', () => {
      const control = btn.closest('.cg-control');
      if (!control) return;
      const editor = control.querySelector('[data-cg-attrs-input]');
      if (!editor) return;
      const expanded = editor.classList.toggle('cg-attrs__input--expanded');
      btn.setAttribute('aria-pressed', expanded ? 'true' : 'false');
    });
  });
};

/**
 * Mini tokenizer for HTML attribute syntax. Produces the same
 * `<span class="token …">` markup Prism uses so the existing theme CSS
 * recolors it. Pure function — exported so `initAttrsAutocomplete` can
 * paint the contenteditable on every keystroke.
 */
const tokenizeAttrs = (text) => {
  const esc = (s) => s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  let out = '';
  let i = 0;
  while (i < text.length) {
    const ch = text[i];
    if (ch === '"' || ch === "'") {
      const quote = ch;
      const start = i;
      i++;
      while (i < text.length && text[i] !== quote) i++;
      if (i < text.length) i++;
      out += '<span class="token attr-value">' + esc(text.slice(start, i)) + '</span>';
    } else if (ch === '=') {
      out += '<span class="token punctuation">=</span>';
      i++;
    } else if (/\s/.test(ch)) {
      out += esc(ch);
      i++;
    } else {
      const start = i;
      while (i < text.length && !/[\s="']/.test(text[i])) i++;
      out += '<span class="token attr-name">' + esc(text.slice(start, i)) + '</span>';
    }
  }
  return out;
};

/**
 * Convert a Selection caret to a numeric offset within `el.textContent`,
 * walking the DOM in document order and accumulating text-node lengths.
 * Returns 0 when the selection is outside `el`.
 */
const getCaretOffset = (el) => {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0) return 0;
  const range = sel.getRangeAt(0);
  if (!el.contains(range.endContainer)) return 0;
  const pre = range.cloneRange();
  pre.selectNodeContents(el);
  pre.setEnd(range.endContainer, range.endOffset);
  return pre.toString().length;
};

/**
 * Place the caret at character offset `pos` within `el.textContent`,
 * walking the DOM until enough text-node characters have been counted.
 * Used after re-rendering tokenized HTML to keep the caret stable.
 */
const setCaretOffset = (el, pos) => {
  const range = document.createRange();
  let remaining = pos;
  let node = null;
  let nodeOffset = 0;
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null);
  let n;
  while ((n = walker.nextNode())) {
    const len = n.nodeValue.length;
    if (remaining <= len) { node = n; nodeOffset = remaining; break; }
    remaining -= len;
  }
  if (node) {
    range.setStart(node, nodeOffset);
  } else {
    // Empty editor or pos beyond content — collapse at the end.
    range.selectNodeContents(el);
    range.collapse(false);
  }
  range.collapse(true);
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
};

export const initAttrsAutocomplete = (root = document) => {
  const wrappers = root.querySelectorAll('[data-cg-attrs]');
  wrappers.forEach((wrap) => {
    if (!bindOnce(wrap, 'attrs')) return;

    const input = wrap.querySelector('[data-cg-attrs-input]');
    const menu = wrap.querySelector('[data-cg-attrs-menu]');
    const hidden = wrap.querySelector('[data-cg-attrs-hidden]');
    if (!input || !menu) return;

    let highlighted = -1;
    let currentItems = [];

    /* ── Editor abstraction layer ──────────────────────────────────────
       The DOM element is a `<div contenteditable>`. These helpers expose
       the same `value` / `selectionStart` semantics the rest of this
       module was originally written for, so most logic stays unchanged.

       `getText()` returns the current plain-text contents.
       `getCaret()` returns the character offset of the caret.
       `setText(text, caret)` re-renders tokenized HTML, restores caret,
         and mirrors the value to the hidden input that the form submits.
    */
    const getText = () => input.textContent || '';
    const getCaret = () => getCaretOffset(input);
    const setText = (text, caret) => {
      input.innerHTML = tokenizeAttrs(text);
      if (hidden) hidden.value = text;
      if (typeof caret === 'number') setCaretOffset(input, caret);
    };
    /** Mirror current text to hidden input + dispatch the change event the
     *  rest of the gallery (preview fetch debounce) listens for. */
    const syncToHidden = () => {
      if (!hidden) return;
      hidden.value = getText();
      hidden.dispatchEvent(new Event('input', { bubbles: true }));
    };

    const currentToken = () => {
      // The substring from the previous whitespace boundary up to the caret.
      // Quoted regions are treated as opaque so a space inside `"foo bar"`
      // does NOT split the token — the whole `attr="foo bar"` is one unit.
      const caret = getCaret();
      const text = getText().slice(0, caret);
      let inQuote = false;
      let start = 0;
      for (let i = 0; i < text.length; i++) {
        const ch = text[i];
        if (ch === '"') inQuote = !inQuote;
        else if (ch === ' ' && !inQuote) start = i + 1;
      }
      return { start, end: caret, value: text.slice(start) };
    };

    /**
     * If the caret sits inside an unclosed `style="…"` (or `style='…'`),
     * return the start offset of its content. Otherwise -1.
     */
    const findStyleOpening = () => {
      const caret = getCaret();
      const text = getText().slice(0, caret);
      const re = /style=(["'])/g;
      let m;
      let lastOpen = -1;
      while ((m = re.exec(text)) !== null) {
        const quoteCh = m[1];
        const valueStart = m.index + m[0].length;
        const closeIdx = text.indexOf(quoteCh, valueStart);
        if (closeIdx === -1) {
          lastOpen = valueStart;
        }
      }
      return lastOpen;
    };

    /**
     * Composite context resolver. Returns either an attr-suggestion context
     * (existing behavior) or a CSS context if the caret is inside a
     * `style="…"`. This is what `render()` and `insertSuggestion()` switch on.
     */
    const currentContext = () => {
      const styleStart = findStyleOpening();
      if (styleStart !== -1) {
        const caret = getCaret();
        const styleText = getText().slice(styleStart, caret);
        const cssCtx = cssContext(styleText);
        if (cssCtx) {
          return {
            kind: cssCtx.kind,
            partial: cssCtx.partial,
            propName: cssCtx.propName,
            replaceStart: styleStart + cssCtx.insertStart,
            replaceEnd: caret,
          };
        }
      }
      const tok = currentToken();
      return { kind: 'attr', partial: tok.value, replaceStart: tok.start, replaceEnd: tok.end };
    };

    const popover = createPopover(input, menu, {
      flipAbove: true,
      matchAnchorWidth: false,
      getAnchorRect: () => caretRectFromContenteditable(input),
    });

    const insertSuggestion = (s) => {
      if (!s) return;
      const ctx = currentContext();
      const replaceStart = (typeof s.replaceStart === 'number') ? s.replaceStart : ctx.replaceStart;
      const replaceEnd = (typeof s.replaceEnd === 'number') ? s.replaceEnd : ctx.replaceEnd;
      const text = getText();
      const before = text.slice(0, replaceStart);
      const after = text.slice(replaceEnd);

      let insertion;
      let caretPos;
      let appendTrailingSpace = false;

      if (s._kind === 'css-prop') {
        insertion = s.name + ': ';
        caretPos = before.length + insertion.length;
      } else if (s._kind === 'css-value') {
        const hasTrailingPunct = /^\s*[;"']/.test(after);
        insertion = s.value + (hasTrailingPunct ? '' : ' ');
        caretPos = before.length + insertion.length;
      } else {
        insertion = s.token;
        const quoteIdx = insertion.indexOf('""');
        if (quoteIdx !== -1) {
          caretPos = before.length + quoteIdx + 1; // park inside the ""
        } else {
          caretPos = before.length + insertion.length;
          if (after === '') appendTrailingSpace = true;
        }
      }

      let newValue = before + insertion + after;
      if (appendTrailingSpace) {
        newValue += ' ';
        caretPos += 1;
      }
      setText(newValue, caretPos);
      input.focus();
      syncToHidden();
      render();
    };

    const bindMenuClicks = () => {
      menu.querySelectorAll('[data-cg-attr-idx]').forEach((btn) => {
        btn.addEventListener('mousedown', (e) => {
          // mousedown so the input doesn't lose focus before the click lands.
          e.preventDefault();
          const idx = parseInt(btn.getAttribute('data-cg-attr-idx'), 10);
          insertSuggestion(currentItems[idx]);
        });
      });
    };

    const render = () => {
      const ctx = currentContext();

      // CSS context — caret inside style="…".
      if (ctx.kind === 'css-prop-name') {
        const props = filterCssProperties(ctx.partial);
        if (!props.length) {
          menu.innerHTML = '<p class="cg-attrs__empty">No CSS properties</p>';
          currentItems = [];
          return;
        }
        currentItems = props.map((p) => ({ _kind: 'css-prop', name: p.name }));
        let html = '';
        for (let i = 0; i < currentItems.length; i++) {
          const item = currentItems[i];
          html += '<button type="button" class="cg-attrs__item' + (i === 0 ? ' cg-highlighted' : '') +
            '" data-cg-attr-idx="' + i + '" role="option">' +
            '<code class="cg-attrs__token">' + escapeHtml(item.name) + '</code>' +
            '<span class="cg-attrs__desc">CSS property</span>' +
            '</button>';
        }
        menu.innerHTML = html;
        highlighted = 0;
        bindMenuClicks();
        return;
      }
      if (ctx.kind === 'css-prop-value') {
        const result = suggestCssValue(ctx.propName, ctx.partial);
        if (!result.items.length) {
          menu.innerHTML = '<p class="cg-attrs__empty">No suggestions for ' + escapeHtml(ctx.propName) + '</p>';
          currentItems = [];
          return;
        }
        // Shift the replace anchor forward when suggestCssValue narrows the
        // partial to the active chunk (multi-token shorthand values).
        const chunkOffset = ctx.partial.length - result.partial.length;
        const replaceStart = ctx.replaceStart + chunkOffset;
        currentItems = result.items.map((it) => ({
          _kind: 'css-value',
          value: it.value,
          hint: it.hint,
          replaceStart,
          replaceEnd: ctx.replaceEnd,
        }));
        let html = '';
        for (let i = 0; i < currentItems.length; i++) {
          const item = currentItems[i];
          html += '<button type="button" class="cg-attrs__item' + (i === 0 ? ' cg-highlighted' : '') +
            '" data-cg-attr-idx="' + i + '" role="option">' +
            '<code class="cg-attrs__token">' + escapeHtml(item.value) + '</code>' +
            '<span class="cg-attrs__desc">' + escapeHtml(item.hint || ctx.propName) + '</span>' +
            '</button>';
        }
        menu.innerHTML = html;
        highlighted = 0;
        bindMenuClicks();
        return;
      }

      // Default attr-suggestion path.
      const q = (ctx.partial || '').toLowerCase().trim();

      // If the partial already matches a suggestion EXACTLY, the user has
      // finished typing an attribute — close the popover and let them move
      // on (space → next attr) instead of suggesting "the same thing again".
      if (q && ATTR_SUGGESTIONS.some((s) => s.token.toLowerCase() === q)) {
        currentItems = [];
        close();
        return;
      }

      // Build a set of attribute names already present in the input EXCEPT
      // the one currently under edit (the partial), so editing an existing
      // attr keeps suggesting it. Slice the rest by removing [replaceStart, replaceEnd].
      const fullText = getText();
      const restText = fullText.slice(0, ctx.replaceStart) + ' ' + fullText.slice(ctx.replaceEnd);
      const taken = writtenAttrNames(restText);

      const visible = ATTR_SUGGESTIONS.filter((s) => !taken.has(tokenName(s.token)));
      const prefix = visible.filter((s) => !q || s.token.toLowerCase().indexOf(q) === 0);
      const subs = q ? visible.filter((s) =>
        s.token.toLowerCase().indexOf(q) > 0 && prefix.indexOf(s) === -1,
      ) : [];
      currentItems = prefix.concat(subs);

      if (!currentItems.length) {
        menu.innerHTML = '<p class="cg-attrs__empty">No suggestions</p>';
        return;
      }

      let html = '';
      for (let i = 0; i < currentItems.length; i++) {
        const s = currentItems[i];
        html += '<button type="button" class="cg-attrs__item' + (i === 0 ? ' cg-highlighted' : '') +
          '" data-cg-attr-idx="' + i + '" role="option">' +
          '<code class="cg-attrs__token">' + escapeHtml(s.token) + '</code>' +
          '<span class="cg-attrs__desc">' + escapeHtml(s.desc) + '</span>' +
          '</button>';
      }
      menu.innerHTML = html;
      highlighted = 0;
      bindMenuClicks();
    };

    const setHighlight = (idx) => {
      const btns = menu.querySelectorAll('[data-cg-attr-idx]');
      if (!btns.length) return;
      if (idx < 0) idx = btns.length - 1;
      if (idx >= btns.length) idx = 0;
      btns.forEach((b, i) => {
        if (i === idx) b.classList.add('cg-highlighted');
        else b.classList.remove('cg-highlighted');
      });
      highlighted = idx;
      if (btns[idx]) btns[idx].scrollIntoView({ block: 'nearest' });
    };

    const open = () => {
      popover.open();
      render();
    };
    const close = popover.close;

    input.addEventListener('focus', open);
    input.addEventListener('click', () => {
      // Re-open if it was closed by Esc, refresh suggestions for new caret.
      if (menu.hasAttribute('hidden')) open();
      else render();
    });

    /* On every keystroke we re-render the tokenized HTML and restore the
       caret. Browsers fire `input` AFTER updating the DOM, so we read the
       current text + caret from the post-edit state, then replace innerHTML
       and place the caret at the same character offset. The hidden input is
       mirrored so the form-level preview-fetch debounce sees the change. */
    input.addEventListener('input', () => {
      const text = getText();
      const caret = getCaret();
      setText(text, caret);
      syncToHidden();
      if (menu.hasAttribute('hidden')) open();
      else render();
    });

    /* Sanitize pasted content: never let formatted HTML or styles through —
       insert as plain text only, then re-tokenize. */
    input.addEventListener('paste', (e) => {
      e.preventDefault();
      const plain = (e.clipboardData || window.clipboardData).getData('text/plain') || '';
      const text = getText();
      const caret = getCaret();
      // Split current text at caret and insert. (No selection range support
      // for simplicity — pasting over a selection collapses to the caret pos.)
      const newText = text.slice(0, caret) + plain.replace(/[\r\n]+/g, ' ') + text.slice(caret);
      setText(newText, caret + plain.length);
      syncToHidden();
      render();
    });

    input.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowDown') {
        if (menu.hasAttribute('hidden')) { open(); return; }
        e.preventDefault();
        setHighlight(highlighted + 1);
      } else if (e.key === 'ArrowUp') {
        if (menu.hasAttribute('hidden')) return;
        e.preventDefault();
        setHighlight(highlighted - 1);
      } else if (e.key === 'Enter') {
        // Single-line by design — Enter never inserts a newline; if the menu
        // is open it accepts the highlighted suggestion.
        e.preventDefault();
        if (menu.hasAttribute('hidden') || highlighted < 0) return;
        if (!currentItems[highlighted]) return;
        insertSuggestion(currentItems[highlighted]);
      } else if (e.key === 'Tab') {
        if (menu.hasAttribute('hidden')) return;
        // Menu is open — always consume Tab so it never leaks to focus
        // traversal, even when there's no highlighted item yet.
        e.preventDefault();
        if (highlighted < 0 || !currentItems[highlighted]) return;
        insertSuggestion(currentItems[highlighted]);
      } else if (e.key === 'Escape') {
        if (menu.hasAttribute('hidden')) return;
        e.preventDefault();
        close();
      }
    });

    // Initial paint — if the field has any pre-populated content (e.g. from
    // form state restore), tokenize it so colors render before first focus.
    if (input.textContent) {
      setText(input.textContent, 0);
    }
  });
};

/* ── Form helpers (URL state sync) ──────────────────────────────────── */

// Snapshot every named control's initial value — used by initPreview to
// tell apart "this matches the page's default" (omit from the URL) from
// "the user changed this" (write to the URL).
const captureFormDefaults = (form) => {
  const defaults = {};
  const elements = form.elements;
  for (let i = 0; i < elements.length; i++) {
    const el = elements[i];
    if (!el.name) continue;
    if (el.type === 'checkbox' || el.type === 'radio') {
      defaults[el.name] = el.checked;
    } else {
      defaults[el.name] = el.value;
    }
  }
  return defaults;
};

// Read the URL query string and apply any matching params back into the
// form. Custom dropdowns also need their visible label and the option's
// aria-selected synced — the form field is the hidden input, but the
// user-facing trigger lives elsewhere in the markup.
const applyUrlParamsToForm = (form) => {
  const params = new URLSearchParams(location.search);
  if (!params.toString()) return;
  const elements = form.elements;
  for (let i = 0; i < elements.length; i++) {
    const el = elements[i];
    if (!el.name || !params.has(el.name)) continue;
    const value = params.get(el.name);
    if (el.type === 'checkbox' || el.type === 'radio') {
      el.checked = value === 'true' || value === 'on' || value === '1';
    } else {
      el.value = value;
      // Extra-attrs: `el` is the hidden mirror — paint the visible editor too,
      // or the first keystroke (which reads textContent) wipes the attrs.
      const attrsWrap = el.closest && el.closest('[data-cg-attrs]');
      if (attrsWrap) {
        const editor = attrsWrap.querySelector('[data-cg-attrs-input]');
        if (editor) editor.textContent = value;
      }
      // Custom dropdown — sync the trigger label and the option states
      // so the visible UI matches the param we just wrote.
      const dropdown = el.closest && el.closest('[data-cg-dropdown]');
      if (dropdown) {
        const valEl = dropdown.querySelector('[data-cg-dropdown-value]');
        if (valEl) valEl.textContent = value;
        dropdown.querySelectorAll('[data-cg-dropdown-option]').forEach((opt) => {
          opt.setAttribute('aria-selected',
            opt.getAttribute('data-cg-dropdown-option') === value ? 'true' : 'false');
        });
      }
    }
  }
};

/* ── Live preview ───────────────────────────────────────────────────── */
/**
 * Wire the live preview pane: fetch on mount, debounce on form input,
 * sync URL state, swap the isolated stage's content.
 */
export const initPreview = () => {
  // The compare view has its own multi-instance handler in compare.js —
  // skip the singleton path here so they don't bind two fetch loops to
  // the first panel's form.
  if (document.querySelector('[data-cg-compare-side]')) return;
  const preview = document.querySelector('[data-cg-preview]');
  if (!preview) return;

  const url = preview.getAttribute('data-cg-preview');
  const form = document.querySelector('[data-cg-controls]');
  // Cancel an in-flight fetch when a newer keystroke supersedes it.
  // Without this, a slow request landing AFTER a faster one would clobber
  // `stage.innerHTML` with stale HTML — and if the user has already SPA-navved
  // away, the fetch would mutate a detached DOM node.
  let activeController = null;

  const stage = preview.querySelector('[data-cg-preview-stage]');
  const tagEl = preview.querySelector('[data-cg-preview-tag]');
  attachResizeGrip(stage);

  // Created on first render so the loading spinner stays visible until then;
  // dropped on error so the next success mounts a clean frame.
  let frameStage = null;
  const isolated = () => (frameStage || (frameStage = createIsolatedStage(stage)));
  const dropFrame = () => {
    if (frameStage) { frameStage.destroy(); frameStage = null; }
  };

  // Shareable URL state: capture each control's initial value as its
  // default BEFORE applying URL params, so syncUrlFromForm can omit
  // anything that matches the default and keep the bar tidy. Then apply
  // any params already in the URL so the first fetch reflects them.
  const formDefaults = form ? captureFormDefaults(form) : null;
  if (form) applyUrlParamsToForm(form);

  const syncUrlFromForm = () => {
    if (!form || !formDefaults) return;
    const params = new URLSearchParams();
    const elements = form.elements;
    for (let i = 0; i < elements.length; i++) {
      const el = elements[i];
      if (!el.name) continue;
      let current, def;
      if (el.type === 'checkbox' || el.type === 'radio') {
        current = el.checked ? 'true' : 'false';
        def = formDefaults[el.name] ? 'true' : 'false';
      } else {
        current = el.value;
        def = formDefaults[el.name];
      }
      if (String(current) !== String(def)) params.set(el.name, current);
    }
    const qs = params.toString();
    const newUrl = location.pathname + (qs ? '?' + qs : '') + location.hash;
    if (newUrl !== location.pathname + location.search + location.hash) {
      try { history.replaceState(history.state, '', newUrl); } catch (_) { /* ignore */ }
    }
    // Mirror the same params onto the "View raw" link so the user opens
    // the raw version with the exact same configuration, in a new tab.
    const rawLink = document.querySelector('[data-cg-raw-link]');
    if (rawLink) {
      const base = rawLink.getAttribute('href').split('?')[0];
      rawLink.setAttribute('href', base + (qs ? '?' + qs : ''));
    }
  };

  const fetchPreview = () => {
    const qs = form ? buildQueryString(form) : '';
    const fullUrl = qs ? url + '?' + qs : url;

    if (activeController) activeController.abort();
    const controller = (typeof AbortController !== 'undefined') ? new AbortController() : null;
    activeController = controller;

    const fetchOpts = {
      headers: { 'X-Requested-With': 'fetch', 'Accept': 'application/json' },
      credentials: 'same-origin',
    };
    if (controller) fetchOpts.signal = controller.signal;

    fetch(fullUrl, fetchOpts)
      .then((res) => {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then((data) => {
        // Stage may have been swapped out from under us between fetch start
        // and resolve — if so, drop the result silently.
        if (stage && stage.isConnected) {
          isolated().update(data.html || '');
        }
        if (tagEl && tagEl.isConnected) {
          tagEl.textContent = data.tag || '';
          // Re-tokenise — Prism's highlightAllUnder ran once at boot, but
          // the tag content changes on every form mutation.
          if (window.Prism && window.Prism.highlightElement) {
            try { window.Prism.highlightElement(tagEl); } catch (_) { /* ignore */ }
          }
        }
        syncUrlFromForm();
      })
      .catch((err) => {
        if (err && err.name === 'AbortError') return;
        if (stage && stage.isConnected) {
          // Gallery chrome, not component output — render it in OUR document.
          dropFrame();
          stage.innerHTML = '<p class="cg-preview-error">Render error: ' + escapeHtml(err.message) + '</p>';
        }
      })
      .then(() => {
        if (activeController === controller) activeController = null;
      });
  };

  fetchPreview();

  // Debounce free-text inputs (300ms); fire instantly for selects /
  // checkboxes / radios / `data-cg-instant`. Same wiring lives in
  // compare.js — both share `wireFormDebounce` from helpers.js.
  wireFormDebounce(form, fetchPreview, PREVIEW_DEBOUNCE_MS);
};

/* ── Variants matrix view ───────────────────────────────────────────── */
// Toggle between the single preview and a grid of all discrete-prop
// combinations. Enums (selects) and booleans (checkboxes) both qualify;
// text / number / slot inputs don't because they aren't bounded sets.
// First two discrete props become the Y/X axes; everything else propagates
// as base params so the grid stays consistent across cells.

// Discrete props that can be matrix axes: enums (select dropdowns) and
// booleans (checkboxes). Enums come first because they typically have
// more visual variation than two-state toggles.
//
// Two enum widgets exist in the codebase: the custom `[data-cg-dropdown]`
// (detail page — searchable, fully styled) and the native `<select>`
// (compare panels — compact, no popup). Both contribute to discovery.
const discoverAxes = (form) => {
  const axes = [];
  if (!form) return axes;
  const seen = Object.create(null);

  // Custom dropdown widget — used on the detail page.
  form.querySelectorAll('[data-cg-dropdown]').forEach((dd) => {
    const input = dd.querySelector('[data-cg-dropdown-input]');
    if (!input || !input.name) return;
    const opts = Array.from(
      dd.querySelectorAll('[data-cg-dropdown-option]'),
      (o) => o.getAttribute('data-cg-dropdown-option'),
    );
    if (opts.length && !seen[input.name]) {
      seen[input.name] = true;
      axes.push({ name: input.name, type: 'enum', options: opts });
    }
  });

  // Native <select> — used on compare panels.
  form.querySelectorAll('select[name]').forEach((sel) => {
    if (seen[sel.name]) return;
    const opts = Array.from(sel.options, (o) => o.value).filter((v) => v !== '');
    if (opts.length) {
      seen[sel.name] = true;
      axes.push({ name: sel.name, type: 'enum', options: opts });
    }
  });

  // Booleans — same on both pages.
  form.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
    if (!cb.name || seen[cb.name]) return;
    seen[cb.name] = true;
    // 'false' / 'true' aren't UI labels — they're the two possible states
    // of any boolean prop; the server maps each back to a Python bool
    // via TRUTHY_TOKENS in annotations.py.
    axes.push({ name: cb.name, type: 'boolean', options: ['false', 'true'] });
  });

  return axes;
};

/**
 * Wire every Single | Matrix view switcher under `root`. Multi-instance —
 * the detail page has one switcher, the compare page has two (A and B).
 * Each switcher's scope is its closest `[data-cg-compare-side]` panel, or
 * `document` if there's no panel ancestor (single-page detail view).
 */
export const initViewSwitcher = (root = document) => {
  root.querySelectorAll('[data-cg-view-switcher]').forEach(initOneViewSwitcher);
};

/**
 * The matrix replaces the single stage, so viewport sizes have nothing to
 * apply to. In compare the switcher is shared by both panels, so it only goes
 * away once BOTH are in matrix — otherwise the panel still showing a preview
 * would lose its control.
 */
const syncViewportAvailability = () => {
  const panels = document.querySelectorAll('[data-cg-compare-side]');
  const inMatrix = (root) => !!root.querySelector("[data-cg-view='matrix'].cg-active");
  const off = panels.length
    ? [...panels].every(inMatrix)
    : inMatrix(document);
  document.querySelectorAll('.cg-vp-btn[data-cg-viewport]').forEach((b) => { b.disabled = off; });
};

const initOneViewSwitcher = (switcher) => {
  // Per-side scoping: in compare, look up rendered/matrix/form/preview only
  // inside this panel. Outside compare (detail page), fall back to the
  // document so existing behavior is unchanged.
  const scope = switcher.closest('[data-cg-compare-side]') || document;
  const rendered = scope.querySelector('[data-cg-preview-rendered]');
  const matrix = scope.querySelector('[data-cg-preview-matrix]');
  const form = scope.querySelector('[data-cg-controls]');
  const preview = scope.querySelector('[data-cg-preview]');
  if (!rendered || !matrix || !preview) return;

  // Matrix is part of the gallery toolkit — always visible. When the form
  // has no discrete axes (or no form at all), `buildMatrix` renders the
  // friendly "No discrete props" empty state instead of hiding the feature.
  switcher.removeAttribute('hidden');
  if (!bindOnce(switcher, 'view')) return;

  const previewUrl = preview.getAttribute('data-cg-preview');
  // In compare each panel is half-width — default to a 1D (Y-only) grid so
  // cells aren't crushed. The user can still pick X via the axis selector.
  const inCompare = !!switcher.closest('[data-cg-compare-side]');

  const btns = switcher.querySelectorAll('[data-cg-view]');
  btns.forEach((btn) => {
    btn.addEventListener('click', () => {
      const view = btn.getAttribute('data-cg-view');
      btns.forEach((b) => {
        const active = b === btn;
        b.classList.toggle('cg-active', active);
        b.setAttribute('aria-pressed', active ? 'true' : 'false');
      });
      syncViewportAvailability();
      if (view === 'matrix') {
        rendered.setAttribute('hidden', '');
        matrix.removeAttribute('hidden');
        buildMatrix(matrix, form, previewUrl, { default1D: inCompare });
      } else {
        matrix.setAttribute('hidden', '');
        rendered.removeAttribute('hidden');
      }
    });
  });
};

// Build the matrix grid for the given Y/X axes. Wrapped so the axis selector
// can rebuild on change without rerunning discovery.
const buildMatrix = (container, form, previewUrl, opts = {}) => {
  const url = previewUrl;
  if (!url) return;

  const axes = discoverAxes(form);
  if (!axes.length) {
    container.innerHTML = '<p class="cg-matrix-empty">No discrete props on this component.</p>';
    return;
  }

  let state = container._cgMatrixState;
  if (!state) {
    // In compare panels, default to 1D (Y axis only) — narrow viewport.
    // In detail, default to 2D when 2+ axes are available.
    const xDefault = opts.default1D ? null : (axes[1] ? axes[1].name : null);
    state = { yName: axes[0].name, xName: xDefault };
    container._cgMatrixState = state;
  }
  const findAxis = (name) => {
    for (let i = 0; i < axes.length; i++) if (axes[i].name === name) return axes[i];
    return null;
  };
  const yAxis = findAxis(state.yName) || axes[0];
  const xAxis = state.xName ? findAxis(state.xName) : null;

  // Capture every other form value as base params.
  const baseParams = new URLSearchParams();
  const elements = form.elements;
  const axisNames = {};
  axisNames[yAxis.name] = true;
  if (xAxis) axisNames[xAxis.name] = true;
  for (let i = 0; i < elements.length; i++) {
    const el = elements[i];
    if (!el.name || axisNames[el.name]) continue;
    if ((el.type === 'checkbox' || el.type === 'radio') && !el.checked) continue;
    baseParams.append(el.name, el.value);
  }

  // Skip rebuild only when axes AND base params are unchanged — otherwise
  // editing a non-axis prop left the grid showing the stale configuration.
  const key = yAxis.name + '|' + (xAxis ? xAxis.name : '') + '|' + baseParams.toString();
  if (state.lastBuiltKey === key) return;
  state.lastBuiltKey = key;

  const labelFor = (axis, value) => {
    if (axis.type === 'boolean') return value === 'true' ? 'on' : 'off';
    return value;
  };

  const cornerLabel = xAxis ? (yAxis.name + ' / ' + xAxis.name) : yAxis.name;

  /**
   * Build a single mini-select dropdown for an axis picker.
   *
   * Mirrors the page-size dropdown on the lint page — same component, just
   * with axis names instead of numeric counts. The `--down` modifier flips
   * the menu to open BELOW the trigger because the picker lives at the top
   * of the matrix container.
   */
  const renderAxisSelect = (axisKey, currentValue, options) => {
    const valueFor = currentValue === null ? '' : currentValue;
    const labelFor = (v) => (v === '' ? '—' : v);
    const optionMarkup = options.map((opt) => {
      const v = opt === null ? '' : opt;
      const active = v === valueFor;
      return (
        '<button type="button" class="cg-mini-select__option' + (active ? ' cg-active' : '') + '" '
        + 'data-cg-mini-option="' + escapeHtml(v) + '" role="option" aria-selected="' + (active ? 'true' : 'false') + '">'
        + '<span class="cg-mini-select__option-label">' + escapeHtml(labelFor(v)) + '</span>'
        + '<svg class="cg-mini-select__check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>'
        + '</button>'
      );
    }).join('');
    return (
      '<div class="cg-mini-select cg-mini-select--down" data-cg-mini-select '
      + 'data-cg-matrix-axis="' + axisKey + '" data-cg-mini-value="' + escapeHtml(valueFor) + '">'
      + '<button type="button" class="cg-mini-select__trigger" data-cg-mini-trigger aria-haspopup="listbox" aria-expanded="false">'
      + '<span class="cg-mini-select__label" data-cg-mini-label>' + escapeHtml(labelFor(valueFor)) + '</span>'
      + '<svg class="cg-mini-select__chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>'
      + '</button>'
      + '<div class="cg-mini-select__menu" data-cg-mini-menu hidden role="listbox">'
      + optionMarkup
      + '</div>'
      + '</div>'
    );
  };

  const yOptions = axes.map((a) => a.name);
  // X allows an explicit "no axis" choice plus every non-Y axis.
  const xOptions = [null, ...axes.filter((a) => a.name !== yAxis.name).map((a) => a.name)];

  const pickerHtml = (
    '<div class="cg-matrix__picker">'
    + '<div class="cg-matrix__picker-field">'
    + '<span class="cg-matrix__picker-label">Y</span>'
    + renderAxisSelect('y', yAxis.name, yOptions)
    + '</div>'
    + '<div class="cg-matrix__picker-field">'
    + '<span class="cg-matrix__picker-label">X</span>'
    + renderAxisSelect('x', xAxis ? xAxis.name : null, xOptions)
    + '</div>'
    + '</div>'
  );

  let html = pickerHtml + '<table class="cg-matrix"><thead><tr><th class="cg-matrix__corner">' +
             escapeHtml(cornerLabel) + '</th>';
  const xValues = xAxis ? xAxis.options : [null];
  xValues.forEach((xv) => {
    html += '<th>' + (xv === null ? '' : escapeHtml(labelFor(xAxis, xv))) + '</th>';
  });
  html += '</tr></thead><tbody>';
  yAxis.options.forEach((yv) => {
    html += '<tr><th>' + escapeHtml(labelFor(yAxis, yv)) + '</th>';
    xValues.forEach((xv) => {
      const p = new URLSearchParams(baseParams);
      p.set(yAxis.name, yv);
      if (xAxis) p.set(xAxis.name, xv);
      html += '<td><div class="cg-matrix-cell" data-cg-matrix-cell data-cg-fetch="' +
              escapeHtml(url + '?' + p.toString()) +
              '"><div class="cg-spinner" aria-hidden="true"></div></div></td>';
    });
    html += '</tr>';
  });
  html += '</tbody></table>';
  // innerHTML detaches the cells; their frames keep observers running unless
  // torn down first.
  container.querySelectorAll('[data-cg-matrix-cell]').forEach((c) => {
    if (c.__cgStage) { c.__cgStage.destroy(); c.__cgStage = null; }
  });
  container.innerHTML = html;

  // Wire the freshly-rendered mini-selects (each `cg-matrix__picker` has
  // its own dropdown to drive). bindOnce inside initMiniSelect makes
  // re-running on already-bound elements a no-op.
  initMiniSelect(container);

  const ySel = container.querySelector('[data-cg-matrix-axis="y"]');
  const xSel = container.querySelector('[data-cg-matrix-axis="x"]');
  if (ySel) ySel.addEventListener('cg-mini-change', (e) => {
    state.yName = e.detail.value;
    if (state.xName === state.yName) state.xName = null;
    buildMatrix(container, form, previewUrl, opts);
  });
  if (xSel) xSel.addEventListener('cg-mini-change', (e) => {
    state.xName = e.detail.value || null;
    buildMatrix(container, form, previewUrl, opts);
  });

  // Abort any in-flight cell fetches from a previous matrix configuration —
  // otherwise resolving fetches would write into cells that no longer exist
  // (axis changed) or were detached (SPA-navved away).
  if (container.__cgMatrixAbort) container.__cgMatrixAbort.abort();
  const matrixController = (typeof AbortController !== 'undefined') ? new AbortController() : null;
  container.__cgMatrixAbort = matrixController;

  // Lazy-load each cell as it scrolls into view. `buildMatrix` is called on
  // every axis change, so stash the observer on the container and disconnect
  // any prior one before creating a new one — otherwise stale observers pin
  // the previous matrix cells in memory. Same listener cleans up on SPA swap.
  const cells = container.querySelectorAll('[data-cg-matrix-cell]');
  if (container.__cgMatrixObserver) {
    container.__cgMatrixObserver.disconnect();
    container.__cgMatrixObserver = null;
  }
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        observer.unobserve(entry.target);
        loadMatrixCell(entry.target, matrixController ? matrixController.signal : null);
      });
    }, { root: container, rootMargin: MATRIX_CELL_ROOT_MARGIN, threshold: 0.01 });
    cells.forEach((c) => observer.observe(c));
    container.__cgMatrixObserver = observer;
    if (!container.__cgMatrixSwapBound) {
      const onContentSwapped = () => {
        if (container.isConnected) return;
        if (container.__cgMatrixObserver) {
          container.__cgMatrixObserver.disconnect();
          container.__cgMatrixObserver = null;
        }
        if (container.__cgMatrixAbort) {
          container.__cgMatrixAbort.abort();
          container.__cgMatrixAbort = null;
        }
        document.removeEventListener('cg-content-swapped', onContentSwapped);
      };
      document.addEventListener('cg-content-swapped', onContentSwapped);
      container.__cgMatrixSwapBound = true;
    }
  } else {
    cells.forEach((c) => loadMatrixCell(c, null));
  }
};

const loadMatrixCell = (cell, signal) => {
  const url = cell.getAttribute('data-cg-fetch');
  if (!url) return;
  const opts = { headers: { 'X-Requested-With': 'fetch', 'Accept': 'application/json' }, credentials: 'same-origin' };
  if (signal) opts.signal = signal;
  fetch(url, opts)
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status))))
    .then((data) => {
      // Cell may have been replaced by an axis change or SPA swap while the
      // request was in flight — drop the result if the node is detached.
      if (!cell.isConnected) return;
      // Own document per cell: `position: fixed` anchors to the cell instead of
      // the page, and Alpine and HTMX rehydrate in there.
      const stage = createIsolatedStage(cell);
      cell.__cgStage = stage;
      stage.update(data.html || '');
    })
    .catch((err) => {
      if (err && err.name === 'AbortError') return;
      if (cell.isConnected) {
        cell.innerHTML = '<p class="cg-preview-error">Render error</p>';
      }
    });
};

/**
 * Run Prism on any [class*="language-"] element under the swapped main.
 * base.html loads Prism with data-manual so we control when it tokenizes.
 * On first boot Prism may not be ready yet, so fall back to window.load.
 */
export const initSyntaxHighlight = () => {
  const run = () => {
    if (typeof window.Prism === 'undefined') return;
    const main = document.querySelector('main.cg-main') || document.body;
    try { window.Prism.highlightAllUnder(main); } catch (_) { /* ignore */ }
  };
  if (typeof window.Prism !== 'undefined') {
    run();
  } else {
    window.addEventListener('load', run, { once: true });
  }
};

/* ── Inline lint markers in the Source tab ──────────────────────────────
 * Surfaces the component's lint issues — already rendered AND translated in
 * the lint panel — directly on the source lines: a severity icon in a left
 * gutter, a tinted line with a colored bar, and a hover tooltip carrying the
 * message + a copy-fix. Issues are read straight from the lint-panel DOM, so
 * all i18n / suggestion rendering is reused (no re-serialization). Positions
 * are (re)computed when the Source tab is shown — a hidden tab has no layout
 * to measure — and rebuilt on SPA swaps.
 */
const CG_SEV_SVG = {
  error:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M15 9l-6 6M9 9l6 6"/></svg>',
  warning:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 2 21h20L12 3z"/><path d="M12 10v4M12 18h.01"/></svg>',
  hint:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 8h.01M11 12h1v4h1"/></svg>',
};

export const initSourceLint = () => {
  const RANK = { error: 3, warning: 2, hint: 1 };
  let tip = null;
  let hideTimer = 0;

  const ensureTip = () => {
    if (tip) return tip;
    tip = document.createElement('div');
    tip.className = 'cg-src-tip';
    tip.hidden = true;
    tip.addEventListener('mouseenter', () => clearTimeout(hideTimer));
    tip.addEventListener('mouseleave', hideTip);
    document.body.appendChild(tip);
    return tip;
  };
  const hideTip = () => {
    hideTimer = setTimeout(() => {
      if (tip) tip.hidden = true;
    }, 140);
  };
  const showTip = (anchor, issues) => {
    clearTimeout(hideTimer);
    const t = ensureTip();
    t.innerHTML = '';
    issues.forEach((iss) => {
      const row = document.createElement('div');
      row.className = 'cg-src-tip__row cg-src-tip__row--' + iss.sev;
      const msg = document.createElement('span');
      msg.className = 'cg-src-tip__msg';
      msg.textContent = iss.msg;
      row.appendChild(msg);
      if (iss.suggestion) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'cg-src-tip__fix';
        btn.textContent = (window.cgI18n && window.cgI18n.copyFix) || 'Copy fix';
        btn.addEventListener('click', () => {
          try {
            navigator.clipboard.writeText(iss.suggestion);
            btn.textContent = (window.cgI18n && window.cgI18n.copied) || 'Copied';
          } catch (_) {
            /* clipboard blocked — ignore */
          }
        });
        row.appendChild(btn);
      }
      t.appendChild(row);
    });
    t.hidden = false;
    const r = anchor.getBoundingClientRect();
    t.style.left = r.right + 8 + 'px';
    t.style.top = r.top + 'px';
  };

  const build = () => {
    const code = document.querySelector('#cg-source-code');
    if (!code) return;
    const pre = code.closest('pre');
    if (!pre || !pre.offsetHeight) return; // hidden / not laid out yet

    pre.querySelectorAll('.cg-src-mark, .cg-src-gutter-icon').forEach((n) => n.remove());

    const byLine = new Map();
    document
      .querySelectorAll('[data-cg-lint-panel] .cg-lint__issue[data-cg-issue-line]')
      .forEach((li) => {
        const line = parseInt(li.getAttribute('data-cg-issue-line'), 10);
        if (!line) return; // issue without a line stays in the panel only
        const sev = li.getAttribute('data-cg-issue-severity') || 'error';
        const msgEl = li.querySelector('.cg-lint__msg');
        const fix = li.querySelector('.cg-lint__fix');
        if (!byLine.has(line)) byLine.set(line, []);
        byLine.get(line).push({
          sev,
          msg: (msgEl ? msgEl.textContent : '').trim(),
          suggestion: fix ? fix.getAttribute('data-cg-copy') : '',
        });
      });

    if (byLine.size === 0) {
      pre.classList.remove('cg-source--linted');
      return;
    }
    pre.classList.add('cg-source--linted');

    const cs = getComputedStyle(pre);
    const lineH = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.5;
    const top0 = parseFloat(cs.paddingTop) || 0;

    byLine.forEach((issues, line) => {
      const worst = issues.reduce((a, b) => (RANK[b.sev] > RANK[a.sev] ? b : a));
      const y = top0 + (line - 1) * lineH;

      const mark = document.createElement('div');
      mark.className = 'cg-src-mark cg-src-mark--' + worst.sev;
      mark.style.cssText = `top:${y}px;height:${lineH}px`;
      pre.appendChild(mark);

      const icon = document.createElement('button');
      icon.type = 'button';
      icon.className = 'cg-src-gutter-icon cg-src-gutter-icon--' + worst.sev;
      icon.style.cssText = `top:${y}px;height:${lineH}px`;
      icon.setAttribute('aria-label', worst.msg);
      icon.innerHTML = CG_SEV_SVG[worst.sev] || CG_SEV_SVG.error;
      icon.addEventListener('mouseenter', () => showTip(icon, issues));
      icon.addEventListener('mouseleave', hideTip);
      icon.addEventListener('focus', () => showTip(icon, issues));
      icon.addEventListener('blur', hideTip);
      pre.appendChild(icon);
    });
  };

  // Bound once at boot: delegate the Source-tab click (the button is recreated
  // on SPA swaps) and rebuild on every content swap. A hidden tab has no layout
  // to measure, so defer to the next frame once it's shown.
  document.addEventListener('click', (e) => {
    if (e.target && e.target.closest && e.target.closest('[data-cg-tab="source"]')) {
      requestAnimationFrame(build);
    }
  });
  window.addEventListener('cg-content-swapped', () => requestAnimationFrame(build));
  requestAnimationFrame(build); // in case the Source tab is already visible on load
};

/* ── Fullscreen preview modal ───────────────────────────────────────── */
/**
 * Click on `[data-cg-preview-fullscreen]` MOVES the live preview device
 * (chrome dots + stage with rendered HTML) into a fullscreen modal at
 * `position: fixed; inset: 0`. Inside the modal the device fills the
 * actual browser viewport so media queries on the rendered component
 * fire against the real window size.
 *
 * Same DOM-move pattern used by the editor-modal — listeners and the
 * preview-fetch loop survive the move because they're bound to elements
 * that travel with the device. On close, the device gets moved back to
 * its original spot via a placeholder that marks the position.
 */
export const initFullscreenPreview = () => {
  const modal = document.querySelector('[data-cg-fs-preview]');
  if (!modal) return;
  if (!bindOnce(modal, 'fs-preview')) return;

  const slot = modal.querySelector('[data-cg-fs-preview-slot]');
  const titleEl = modal.querySelector('[data-cg-fs-preview-title]');
  const closeBtns = modal.querySelectorAll('[data-cg-fs-preview-close]');

  let active = null;  // { device, placeholder }

  const open = () => {
    if (active) return;
    const device = document.querySelector('[data-cg-preview-device]');
    if (!device || !slot) return;

    const placeholder = document.createElement('div');
    placeholder.className = 'cg-fs-preview__placeholder';
    placeholder.setAttribute('aria-hidden', 'true');
    device.parentNode.insertBefore(placeholder, device);

    device.classList.add('cg-preview__device--fullscreen');
    slot.appendChild(device);

    if (titleEl) {
      const titleSrc = document.querySelector('.cg-detail__title');
      if (titleSrc) titleEl.textContent = titleSrc.textContent;
    }

    modal.removeAttribute('hidden');
    document.body.classList.add('cg-modal-open');

    active = { device, placeholder };
  };

  const close = () => {
    if (!active) return;
    const { device, placeholder } = active;
    device.classList.remove('cg-preview__device--fullscreen');
    if (placeholder.parentNode) {
      placeholder.parentNode.replaceChild(device, placeholder);
    }
    modal.setAttribute('hidden', '');
    document.body.classList.remove('cg-modal-open');
    active = null;
  };

  // Document-level delegation so SPA-swapped pages get the trigger wired
  // without a per-page init step.
  document.addEventListener('click', (e) => {
    const trigger = e.target.closest && e.target.closest('[data-cg-preview-fullscreen]');
    if (trigger) {
      e.preventDefault();
      open();
      return;
    }
    // Backdrop click — but the modal IS the backdrop here, so only count
    // clicks directly on the modal container (not bubbled from the slot).
    if (active && e.target === modal) close();
  });

  closeBtns.forEach((b) => b.addEventListener('click', close));
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && active) close();
  });

  // A SPA nav destroys the moved device AND its placeholder, so close()
  // could never restore it and the modal stayed stuck open. Reset instead:
  // the fresh page brings its own device.
  document.addEventListener('cg-content-swapped', () => {
    if (!active) return;
    modal.setAttribute('hidden', '');
    document.body.classList.remove('cg-modal-open');
    active = null;
  });
};
