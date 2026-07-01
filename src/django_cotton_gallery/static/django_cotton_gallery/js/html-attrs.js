/*!
 * Catalog of HTML / ARIA / Alpine / HTMX attributes used as autocomplete
 * suggestions in BOTH the extra-attrs input and the slot editor (when the
 * user types attributes inside a plain HTML tag like `<div |>`).
 *
 * Each entry has:
 *   - token: the snippet inserted on selection (with `""` for parking the caret)
 *   - desc:  short description shown in the suggestion popover
 */

/** @typedef {{ token: string, desc: string }} AttrSuggestion */

/** @type {AttrSuggestion[]} */
export const ATTR_SUGGESTIONS = [
  // ── Universal ────────────────────────────────────────────────
  { token: 'class=""',          desc: 'CSS classes — Tailwind utilities or custom' },
  { token: 'style=""',          desc: 'Inline CSS' },
  { token: 'id=""',             desc: 'Element id' },
  { token: 'title=""',          desc: 'Native tooltip / hint' },
  { token: 'tabindex=""',       desc: 'Focus order (-1 = unreachable)' },
  { token: 'role=""',           desc: 'ARIA role override' },
  { token: 'autofocus',         desc: 'Focus this element on mount' },
  { token: 'hidden',            desc: 'Hide from layout entirely' },
  { token: 'lang=""',           desc: 'Element language code' },
  { token: 'dir=""',            desc: 'Text direction (ltr / rtl / auto)' },
  // ── Form ─────────────────────────────────────────────────────
  { token: 'disabled',          desc: 'Disable the form control' },
  { token: 'readonly',          desc: 'Read-only form control' },
  { token: 'required',          desc: 'Required form control' },
  { token: 'placeholder=""',    desc: 'Placeholder text' },
  { token: 'value=""',          desc: 'Initial value' },
  { token: 'name=""',           desc: 'Form field name' },
  { token: 'type=""',           desc: 'Input type (text / email / password / …)' },
  { token: 'autocomplete=""',   desc: 'Browser autofill hint' },
  { token: 'min=""',            desc: 'Minimum value' },
  { token: 'max=""',            desc: 'Maximum value' },
  { token: 'step=""',           desc: 'Step increment' },
  { token: 'maxlength=""',      desc: 'Max characters' },
  { token: 'pattern=""',        desc: 'Validation regex' },
  // ── Links ────────────────────────────────────────────────────
  { token: 'href=""',           desc: 'Link target URL' },
  { token: 'target="_blank"',   desc: 'Open in new tab' },
  { token: 'rel=""',            desc: 'Link relation (noopener, noreferrer…)' },
  { token: 'download',          desc: 'Force file download' },
  // ── Accessibility ────────────────────────────────────────────
  { token: 'aria-label=""',         desc: 'Accessible name when no visible label' },
  { token: 'aria-labelledby=""',    desc: 'Reference labelling element id' },
  { token: 'aria-describedby=""',   desc: 'Reference description element id' },
  { token: 'aria-hidden="true"',    desc: 'Hide from screen readers' },
  { token: 'aria-expanded="false"', desc: 'Disclosure state (true/false)' },
  { token: 'aria-pressed="false"',  desc: 'Toggle button state' },
  { token: 'aria-current=""',       desc: 'Current item in a set (page / step…)' },
  { token: 'aria-live=""',          desc: 'Live region announcement (polite / assertive)' },
  // ── Data + framework ─────────────────────────────────────────
  { token: 'data-',             desc: 'Custom data attribute' },
  { token: 'x-data=""',         desc: 'Alpine.js component state' },
  { token: 'x-on:click=""',     desc: 'Alpine click handler' },
  { token: 'x-show=""',         desc: 'Alpine conditional visibility' },
  { token: 'x-text=""',         desc: 'Alpine text binding' },
  { token: 'x-model=""',        desc: 'Alpine 2-way binding' },
  { token: 'x-bind:class=""',   desc: 'Alpine class binding' },
  { token: 'hx-get=""',         desc: 'HTMX GET request' },
  { token: 'hx-post=""',        desc: 'HTMX POST request' },
  { token: 'hx-target=""',      desc: 'HTMX target selector' },
  { token: 'hx-swap=""',        desc: 'HTMX swap mode (innerHTML, outerHTML…)' },
  { token: 'hx-trigger=""',     desc: 'HTMX trigger event' },
];

/**
 * Return the leading-name part of a suggestion's token. Used for de-dupe
 * checks against attrs already present in the input.
 *
 *   `class=""`        → `class`
 *   `disabled`        → `disabled`
 *   `target="_blank"` → `target`
 *   `data-`           → `data-`
 */
export const tokenName = (token) => {
  const eq = token.indexOf('=');
  return eq === -1 ? token : token.slice(0, eq);
};

/**
 * Parse `text` as a sequence of HTML attribute tokens (separated by
 * whitespace, with quoted regions kept opaque) and return the set of
 * attribute names already present.
 *
 *   `class="btn" disabled  data-x="1"` → Set(['class', 'disabled', 'data-x'])
 *
 * @param {string} text
 * @returns {Set<string>}
 */
export const writtenAttrNames = (text) => {
  const names = new Set();
  if (!text) return names;
  let inQuote = false;
  let quoteCh = null;
  let buf = '';
  const flush = () => {
    if (!buf) return;
    const eq = buf.indexOf('=');
    const name = eq === -1 ? buf : buf.slice(0, eq);
    if (name) names.add(name);
    buf = '';
  };
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (inQuote) {
      buf += ch;
      if (ch === quoteCh) { inQuote = false; quoteCh = null; }
    } else if (ch === '"' || ch === "'") {
      inQuote = true; quoteCh = ch; buf += ch;
    } else if (/\s/.test(ch)) {
      flush();
    } else {
      buf += ch;
    }
  }
  flush();
  return names;
};
