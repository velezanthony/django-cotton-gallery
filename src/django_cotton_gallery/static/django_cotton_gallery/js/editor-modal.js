/*!
 * Editor maximize modal.
 *
 * One shared modal in <body>; clicking a `[data-cg-editor-maximize]` button
 * MOVES its target editor (the closest matching `data-cg-editor-target`
 * selector) into the modal slot, leaving a placeholder behind. On close, the
 * editor is moved back to its placeholder. Listeners survive the move because
 * they're bound to the editor element itself, not its parent — so all
 * intellisense, autocomplete, syntax highlight, formatter, etc. keep working
 * inside the modal without any duplication.
 *
 * Header actions (Format, Reset) and footer stats are wired here on open
 * and torn down on close, scoped to whichever editor is currently active.
 */

import { bindOnce, focusTrapHandler } from './helpers.js';

const SELECTOR_MODAL = '[data-cg-editor-modal]';
const SELECTOR_SLOT = '[data-cg-editor-modal-slot]';
const SELECTOR_TITLE = '[data-cg-editor-modal-title]';
const SELECTOR_CLOSE = '[data-cg-editor-modal-close]';
const SELECTOR_MAXIMIZE = '[data-cg-editor-maximize]';
const SELECTOR_FORMAT = '[data-cg-editor-modal-format]';
const SELECTOR_RESET = '[data-cg-editor-modal-reset]';
const SELECTOR_STATS_CHARS = '[data-cg-editor-modal-chars]';
const SELECTOR_STATS_LINES = '[data-cg-editor-modal-lines]';

const SELECTOR_MINIFY = '[data-cg-editor-modal-minify]';

const SELECTOR_INNER_TEXTAREA = '[data-cg-slot-textarea]';
const SELECTOR_INNER_CE = '[data-cg-attrs-input]';
const SELECTOR_INNER_FORMAT = '[data-cg-textarea-format]';
const SELECTOR_INNER_MINIFY = '[data-cg-textarea-minify]';

let active = null;

/**
 * Read the editor's current value, regardless of whether it's a slot textarea
 * or the attrs contenteditable.
 */
const readEditorValue = (editor) => {
  const ta = editor.querySelector(SELECTOR_INNER_TEXTAREA);
  if (ta) return ta.value;
  const ce = editor.querySelector(SELECTOR_INNER_CE);
  if (ce) return ce.textContent || '';
  return '';
};

/**
 * Write a value to the editor. Dispatches `input` so dependent features
 * (preview-fetch debounce, syntax-highlight overlay, attrs hidden mirror)
 * pick the change up.
 */
const writeEditorValue = (editor, value) => {
  const ta = editor.querySelector(SELECTOR_INNER_TEXTAREA);
  if (ta) {
    ta.value = value;
    ta.dispatchEvent(new Event('input', { bubbles: true }));
    return;
  }
  const ce = editor.querySelector(SELECTOR_INNER_CE);
  if (ce) {
    ce.textContent = value;
    ce.dispatchEvent(new Event('input', { bubbles: true }));
  }
};

/** Find the actual editable element (textarea or contenteditable div). */
const innerEditable = (editor) =>
  editor.querySelector(SELECTOR_INNER_TEXTAREA) || editor.querySelector(SELECTOR_INNER_CE);

const updateStats = (modal, value) => {
  const charsEl = modal.querySelector(SELECTOR_STATS_CHARS);
  const linesEl = modal.querySelector(SELECTOR_STATS_LINES);
  if (charsEl) charsEl.textContent = String(value.length);
  if (linesEl) linesEl.textContent = String(value.split('\n').length);
};

const open = (modal, editor, title) => {
  if (active) close();

  const slot = modal.querySelector(SELECTOR_SLOT);
  const titleEl = modal.querySelector(SELECTOR_TITLE);
  if (!slot || !editor) return;

  const placeholder = document.createElement('div');
  placeholder.className = 'cg-editor-modal__placeholder';
  placeholder.setAttribute('aria-hidden', 'true');
  editor.parentNode.insertBefore(placeholder, editor);

  editor.classList.add('cg-editor--maximized');
  slot.appendChild(editor);

  if (titleEl && title) titleEl.textContent = title;
  modal.removeAttribute('hidden');
  document.body.classList.add('cg-modal-open');

  // Snapshot the value at open time so Reset can restore it.
  const initialValue = readEditorValue(editor);

  /* ── Format / Minify buttons: delegate to the editor's own buttons if any.
        Attrs has no formatter — hide both ours when the inner ones are
        missing so the chrome doesn't expose features the editor can't run. */
  const formatBtn = modal.querySelector(SELECTOR_FORMAT);
  const innerFormatBtn = editor.querySelector(SELECTOR_INNER_FORMAT);
  let formatHandler = null;
  if (formatBtn) {
    if (innerFormatBtn) {
      formatBtn.style.display = '';
      formatHandler = () => innerFormatBtn.click();
      formatBtn.addEventListener('click', formatHandler);
    } else {
      formatBtn.style.display = 'none';
    }
  }

  const minifyBtn = modal.querySelector(SELECTOR_MINIFY);
  const innerMinifyBtn = editor.querySelector(SELECTOR_INNER_MINIFY);
  let minifyHandler = null;
  if (minifyBtn) {
    if (innerMinifyBtn) {
      minifyBtn.style.display = '';
      minifyHandler = () => innerMinifyBtn.click();
      minifyBtn.addEventListener('click', minifyHandler);
    } else {
      minifyBtn.style.display = 'none';
    }
  }

  /* ── Reset button: restore the snapshotted initial value. */
  const resetBtn = modal.querySelector(SELECTOR_RESET);
  let resetHandler = null;
  if (resetBtn) {
    resetHandler = () => {
      writeEditorValue(editor, initialValue);
      updateStats(modal, initialValue);
    };
    resetBtn.addEventListener('click', resetHandler);
  }

  /* ── Live stats: chars + lines, refreshed on every input. */
  const editable = innerEditable(editor);
  let statsHandler = null;
  if (editable) {
    statsHandler = () => updateStats(modal, readEditorValue(editor));
    editable.addEventListener('input', statsHandler);
    statsHandler(); // initial paint
  }

  active = {
    modal, editor, placeholder, initialValue,
    formatBtn, formatHandler,
    minifyBtn, minifyHandler,
    resetBtn, resetHandler,
    editable, statsHandler,
  };

  // Focus the editable so the user can keep typing.
  if (editable && typeof editable.focus === 'function') editable.focus();
};

const close = () => {
  if (!active) return;
  const {
    modal, editor, placeholder,
    formatBtn, formatHandler,
    minifyBtn, minifyHandler,
    resetBtn, resetHandler,
    editable, statsHandler,
  } = active;

  // Unbind all open-time listeners — they shouldn't outlive this maximize.
  if (formatBtn && formatHandler) formatBtn.removeEventListener('click', formatHandler);
  if (minifyBtn && minifyHandler) minifyBtn.removeEventListener('click', minifyHandler);
  if (resetBtn && resetHandler) resetBtn.removeEventListener('click', resetHandler);
  if (editable && statsHandler) editable.removeEventListener('input', statsHandler);

  editor.classList.remove('cg-editor--maximized');
  if (placeholder.parentNode) {
    placeholder.parentNode.replaceChild(editor, placeholder);
  }
  modal.setAttribute('hidden', '');
  document.body.classList.remove('cg-modal-open');
  active = null;
};

export const initEditorModal = (root = document) => {
  const modal = root.querySelector(SELECTOR_MODAL);
  if (!modal) return;
  if (!bindOnce(modal, 'editor-modal')) return;

  modal.querySelectorAll(SELECTOR_CLOSE).forEach((btn) => {
    btn.addEventListener('click', close);
  });
  // Esc closes; Tab cycle delegated to the shared `focusTrapHandler`
  // helper so the Quick Switcher (and any future modal) can copy this
  // pattern by importing the same function.
  document.addEventListener('keydown', (e) => {
    if (!active) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      close();
    }
  });
  document.addEventListener('keydown', focusTrapHandler(modal, () => active));

  // Document-level delegation so SPA-swapped pages get maximize buttons wired.
  document.addEventListener('click', (e) => {
    const btn = e.target.closest && e.target.closest(SELECTOR_MAXIMIZE);
    if (!btn) return;
    const targetSel = btn.getAttribute('data-cg-editor-target');
    if (!targetSel) return;
    const ancestor = btn.closest(targetSel);
    const editor = ancestor || document.querySelector(targetSel);
    if (!editor) return;
    e.preventDefault();
    const title = btn.getAttribute('data-cg-editor-title') || 'Editor';
    open(modal, editor, title);
  });
};
