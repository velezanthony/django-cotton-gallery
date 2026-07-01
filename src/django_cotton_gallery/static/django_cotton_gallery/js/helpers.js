/*!
 * Pure utility functions reused across feature modules.
 * No DOM-state mutation tricks like `el._cgFooBound = true` — use bindOnce instead.
 */

// ── HTML / CSS escaping ───────────────────────────────────────────────────

export const escapeHtml = (s) => {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
};

// CSS.escape polyfill — IE11 is dead, but Safari 15.0 still has gaps.
export const cssEscape = (s) => {
  if (window.CSS && window.CSS.escape) return window.CSS.escape(s);
  return String(s).replace(/[^\w-]/g, (c) => '\\' + c);
};

// ── localStorage with try/catch ────────────────────────────────────────────

export const readJSON = (key) => {
  try { return JSON.parse(window.localStorage.getItem(key) || 'null'); }
  catch (_) { return null; }
};

export const writeJSON = (key, value) => {
  try { window.localStorage.setItem(key, JSON.stringify(value)); } catch (_) { /* quota or disabled */ }
};

// ── DOM helpers ────────────────────────────────────────────────────────────

export const toggleHidden = (el, hidden) => {
  if (hidden) el.setAttribute('hidden', '');
  else el.removeAttribute('hidden');
};

// ── bind-once via WeakSet ──────────────────────────────────────────────────
// Replaces the old `el._cgFooBound = true` pattern. WeakSet doesn't mutate
// the DOM and gets garbage-collected with the elements.
//
// Use as a guard at the top of init functions:
//   if (!bindOnce(el, 'tabs')) return;
//   // …setup that should run once per (el, key) pair…
const bindRegistries = new Map();

export const bindOnce = (el, key) => {
  let registry = bindRegistries.get(key);
  if (!registry) {
    registry = new WeakSet();
    bindRegistries.set(key, registry);
  }
  if (registry.has(el)) return false;
  registry.add(el);
  return true;
};

// ── Debounce ───────────────────────────────────────────────────────────────

export const debounce = (fn, delay) => {
  let timer = null;
  return (...args) => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
};

// ── Modal focus trap ───────────────────────────────────────────────────────
// Returns a `keydown` handler. Wire it as `document.addEventListener('keydown', handler)`
// while the modal is open; the caller decides when to attach/detach (or
// gates with an `active` flag).

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[contenteditable="true"]',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

const visibleFocusables = (root) =>
  Array.from(root.querySelectorAll(FOCUSABLE_SELECTOR)).filter((el) => {
    if (el.getAttribute('aria-hidden') === 'true') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  });

/**
 * Build a Tab-cycling focus trap for `modalEl`. Caller decides when it's
 * active by passing an `isActive` thunk — the trap no-ops while inactive,
 * which lets a single shared handler serve a modal that mounts/unmounts.
 *
 * Inner handlers (e.g. textareas that own Tab for indent) can call
 * `e.preventDefault()` BEFORE the trap runs and the trap will skip — so
 * editor-style components keep their semantics inside trapped modals.
 *
 * @param {HTMLElement} modalEl
 * @param {() => boolean} isActive
 * @returns {(e: KeyboardEvent) => void}
 */
export const focusTrapHandler = (modalEl, isActive) => (e) => {
  if (!isActive()) return;
  if (e.key !== 'Tab' || e.defaultPrevented) return;
  const items = visibleFocusables(modalEl);
  if (!items.length) return;
  const first = items[0];
  const last = items[items.length - 1];
  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault();
    first.focus();
  } else if (!modalEl.contains(document.activeElement)) {
    e.preventDefault();
    first.focus();
  }
};

// ── Form-debounce wiring ──────────────────────────────────────────────────
// Both the detail page and the compare view used to repeat the same input/
// change debounce dance: free-text inputs go through a delay, selects /
// checkboxes / `data-cg-instant` controls fire immediately. Extracted here
// so both call sites stay terse and any future caller (e.g. props builder)
// gets the same behaviour for free.

const isInstantTarget = (t) =>
  !!t && (
    t.tagName === 'SELECT' ||
    t.type === 'checkbox' ||
    t.type === 'radio' ||
    (t.hasAttribute && t.hasAttribute('data-cg-instant'))
  );

/**
 * Wire `form` so that `fetchFn` runs on every input/change with the right
 * cadence: instant for selects / checkboxes / radios / `data-cg-instant`
 * controls; debounced (`delayMs`) for everything else.
 *
 * Returns a teardown that removes the listeners — useful if the caller
 * may swap forms (e.g. compare view).
 *
 * @param {HTMLFormElement} form
 * @param {() => void} fetchFn
 * @param {number} delayMs
 * @returns {() => void}
 */
export const wireFormDebounce = (form, fetchFn, delayMs) => {
  if (!form) return () => {};
  let timer = null;
  const onInput = (e) => {
    if (timer) clearTimeout(timer);
    if (isInstantTarget(e.target)) fetchFn();
    else timer = setTimeout(fetchFn, delayMs);
  };
  const onChange = (e) => {
    if (!isInstantTarget(e.target)) return;
    if (timer) clearTimeout(timer);
    fetchFn();
  };
  form.addEventListener('input', onInput);
  form.addEventListener('change', onChange);
  return () => {
    if (timer) clearTimeout(timer);
    form.removeEventListener('input', onInput);
    form.removeEventListener('change', onChange);
  };
};
