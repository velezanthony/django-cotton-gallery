/**
 * CSS property catalog + contextual detector for `style="…"` autocomplete.
 *
 * Used by the slot editor (when typing inside `<foo style="|">`) and the
 * extra-attrs input (when typing `style="|"`). Both call `cssContext()` with
 * whatever the user has typed inside the quoted style value up to the caret;
 * it returns either a `prop-name` context (suggest property keys) or a
 * `prop-value` context (suggest values for the current property).
 *
 * Value suggestions are category-aware:
 *   - color properties (color, background-color, …) → named colors + hex samples
 *   - length properties (width, padding, …) → if partial ends in digits, suggest
 *     length units (px / rem / vh / dvh / …); otherwise the keywords (`auto`)
 *   - shorthand properties (border, margin, transition, box-shadow, …) →
 *     tokenize the partial, classify what's already filled, suggest only the
 *     remaining slot types (e.g. `border: 2px solid |` → suggest colors)
 *   - keyword properties (display, position, …) → static value list
 */

/* ── Tokens / palettes ──────────────────────────────────────────────────── */

/** Common named colors — curated subset of CSS's 147 to keep popover focused. */
const NAMED_COLORS = [
  'transparent', 'currentColor', 'inherit',
  'black', 'white', 'gray', 'silver',
  'red', 'orange', 'yellow', 'green', 'lime', 'teal', 'cyan',
  'blue', 'indigo', 'violet', 'purple', 'magenta', 'pink',
  'brown', 'maroon', 'navy', 'olive', 'gold', 'salmon', 'coral', 'tomato',
];

/** Hex shorthand samples — quick-pick scaffolds the user can edit. */
const HEX_SAMPLES = ['#000', '#fff', '#888', '#ccc', '#f00', '#0f0', '#00f'];

/** Functional color templates with caret-park spots (`|` placeholder). */
const COLOR_FUNCTIONS = ['rgb(0, 0, 0)', 'rgba(0, 0, 0, 0.5)', 'hsl(0, 0%, 0%)', 'hsla(0, 0%, 0%, 0.5)'];

/** Length units. Order matters — most-used first since suggestions truncate. */
const LENGTH_UNITS = ['px', 'rem', 'em', '%', 'vh', 'vw', 'dvh', 'dvw', 'svh', 'lvh', 'ch', 'ex'];

/** Time units for transition / animation. */
const TIME_UNITS = ['ms', 's'];

/** Angle units for transform / gradient. */
const ANGLE_UNITS = ['deg', 'rad', 'turn'];

/** Border-style keywords (also valid for outline-style). */
const BORDER_STYLES = ['none', 'solid', 'dashed', 'dotted', 'double', 'hidden', 'groove', 'ridge', 'inset', 'outset'];

/** Border-width keywords (in addition to lengths). */
const BORDER_WIDTH_KEYWORDS = ['thin', 'medium', 'thick'];

/** transition-timing-function keywords. */
const TIMING_FUNCTIONS = ['ease', 'linear', 'ease-in', 'ease-out', 'ease-in-out', 'step-start', 'step-end'];

/** Common transition properties (also accept `all`/`none`). */
const TRANSITION_PROPS = ['all', 'none', 'transform', 'opacity', 'background-color', 'color', 'box-shadow', 'border-color', 'visibility', 'width', 'height'];

/* ── Token classifiers ──────────────────────────────────────────────────── */

const LENGTH_RE = /^-?\d+(\.\d+)?(px|rem|em|%|vh|vw|dvh|dvw|svh|lvh|ch|ex)$/i;
const TIME_RE = /^\d+(\.\d+)?(ms|s)$/i;
const NUMBER_ONLY_RE = /^-?\d+(\.\d+)?$/;
/** Matches `<number>` or `<number><unit-prefix>` — used to detect a length
 *  the user is actively typing so we can offer matching unit completions. */
const LENGTH_IN_PROGRESS_RE = /^(-?\d+(?:\.\d+)?)([a-z%]*)$/i;
const HEX_COLOR_RE = /^#[0-9a-f]{3,8}$/i;
const COLOR_FN_RE = /^(rgb|rgba|hsl|hsla)\([^)]*\)$/i;

const isLength = (t) => LENGTH_RE.test(t);
const isTime = (t) => TIME_RE.test(t);
const isColor = (t) => HEX_COLOR_RE.test(t) || COLOR_FN_RE.test(t) || NAMED_COLORS.indexOf(t) !== -1;
const isBorderStyle = (t) => BORDER_STYLES.indexOf(t) !== -1;
const isBorderWidthKeyword = (t) => BORDER_WIDTH_KEYWORDS.indexOf(t) !== -1;
const isTimingFunction = (t) => TIMING_FUNCTIONS.indexOf(t) !== -1;
const isTransitionProp = (t) => TRANSITION_PROPS.indexOf(t) !== -1;

/* ── Property catalog ───────────────────────────────────────────────────── */

/**
 * @typedef {{
 *   name: string,
 *   values?: string[],
 *   category?: 'color' | 'length' | 'time' | 'angle' | 'shorthand-border' |
 *              'shorthand-margin' | 'shorthand-padding' | 'shorthand-transition' |
 *              'shorthand-box-shadow' | 'shorthand-transform' | 'shorthand-font'
 * }} CssProperty
 */

/** @type {CssProperty[]} */
export const CSS_PROPERTIES = [
  // ── Layout / display ─────────────────────────────────────────────
  { name: 'display', values: ['block', 'inline', 'inline-block', 'flex', 'inline-flex', 'grid', 'inline-grid', 'none', 'contents'] },
  { name: 'position', values: ['static', 'relative', 'absolute', 'fixed', 'sticky'] },
  { name: 'top', category: 'length' },
  { name: 'right', category: 'length' },
  { name: 'bottom', category: 'length' },
  { name: 'left', category: 'length' },
  { name: 'z-index', values: ['0', '1', '10', '100', 'auto'] },
  { name: 'visibility', values: ['visible', 'hidden', 'collapse'] },
  { name: 'overflow', values: ['visible', 'hidden', 'scroll', 'auto', 'clip'] },
  { name: 'overflow-x', values: ['visible', 'hidden', 'scroll', 'auto', 'clip'] },
  { name: 'overflow-y', values: ['visible', 'hidden', 'scroll', 'auto', 'clip'] },
  { name: 'float', values: ['left', 'right', 'none'] },
  { name: 'clear', values: ['left', 'right', 'both', 'none'] },
  { name: 'isolation', values: ['auto', 'isolate'] },
  // ── Box model ────────────────────────────────────────────────────
  { name: 'width', category: 'length', values: ['auto', '100%', 'fit-content', 'min-content', 'max-content'] },
  { name: 'height', category: 'length', values: ['auto', '100%', 'fit-content'] },
  { name: 'min-width', category: 'length', values: ['0', 'auto'] },
  { name: 'min-height', category: 'length', values: ['0', 'auto'] },
  { name: 'max-width', category: 'length', values: ['none', '100%'] },
  { name: 'max-height', category: 'length', values: ['none', '100%'] },
  { name: 'margin', category: 'shorthand-margin' },
  { name: 'margin-top', category: 'length', values: ['auto', '0'] },
  { name: 'margin-right', category: 'length', values: ['auto', '0'] },
  { name: 'margin-bottom', category: 'length', values: ['auto', '0'] },
  { name: 'margin-left', category: 'length', values: ['auto', '0'] },
  { name: 'padding', category: 'shorthand-padding' },
  { name: 'padding-top', category: 'length', values: ['0'] },
  { name: 'padding-right', category: 'length', values: ['0'] },
  { name: 'padding-bottom', category: 'length', values: ['0'] },
  { name: 'padding-left', category: 'length', values: ['0'] },
  { name: 'box-sizing', values: ['content-box', 'border-box'] },
  // ── Border / outline ─────────────────────────────────────────────
  { name: 'border', category: 'shorthand-border' },
  { name: 'border-top', category: 'shorthand-border' },
  { name: 'border-right', category: 'shorthand-border' },
  { name: 'border-bottom', category: 'shorthand-border' },
  { name: 'border-left', category: 'shorthand-border' },
  { name: 'outline', category: 'shorthand-border' },
  { name: 'border-width', category: 'length', values: BORDER_WIDTH_KEYWORDS.slice() },
  { name: 'border-style', values: BORDER_STYLES.slice() },
  { name: 'border-color', category: 'color' },
  { name: 'border-radius', category: 'length', values: ['0', '50%'] },
  { name: 'outline-offset', category: 'length' },
  // ── Background ───────────────────────────────────────────────────
  { name: 'background', values: ['transparent', 'none'] },
  { name: 'background-color', category: 'color' },
  { name: 'background-image', values: ['none'] },
  { name: 'background-size', values: ['auto', 'cover', 'contain', '100% 100%'] },
  { name: 'background-position', values: ['center', 'top', 'right', 'bottom', 'left'] },
  { name: 'background-repeat', values: ['no-repeat', 'repeat', 'repeat-x', 'repeat-y'] },
  // ── Typography ───────────────────────────────────────────────────
  { name: 'color', category: 'color' },
  { name: 'font-family', values: ['inherit', 'sans-serif', 'serif', 'monospace', 'system-ui'] },
  { name: 'font-size', category: 'length', values: ['inherit', '0.875rem', '1rem', '1.25rem'] },
  { name: 'font-weight', values: ['normal', 'bold', '400', '500', '600', '700'] },
  { name: 'font-style', values: ['normal', 'italic', 'oblique'] },
  { name: 'line-height', values: ['1', '1.25', '1.5', 'normal'] },
  { name: 'text-align', values: ['left', 'center', 'right', 'justify', 'start', 'end'] },
  { name: 'text-decoration', values: ['none', 'underline', 'line-through', 'overline'] },
  { name: 'text-transform', values: ['none', 'uppercase', 'lowercase', 'capitalize'] },
  { name: 'letter-spacing', category: 'length', values: ['normal'] },
  { name: 'white-space', values: ['normal', 'nowrap', 'pre', 'pre-wrap', 'pre-line'] },
  { name: 'word-break', values: ['normal', 'break-all', 'keep-all', 'break-word'] },
  // ── Flexbox ──────────────────────────────────────────────────────
  { name: 'flex', values: ['1', '0 1 auto', 'none', '1 1 0', '0 0 auto'] },
  { name: 'flex-direction', values: ['row', 'column', 'row-reverse', 'column-reverse'] },
  { name: 'flex-wrap', values: ['nowrap', 'wrap', 'wrap-reverse'] },
  { name: 'justify-content', values: ['flex-start', 'center', 'flex-end', 'space-between', 'space-around', 'space-evenly'] },
  { name: 'align-items', values: ['stretch', 'flex-start', 'center', 'flex-end', 'baseline'] },
  { name: 'align-self', values: ['auto', 'stretch', 'flex-start', 'center', 'flex-end', 'baseline'] },
  { name: 'align-content', values: ['flex-start', 'center', 'flex-end', 'space-between', 'space-around', 'stretch'] },
  { name: 'gap', category: 'length', values: ['0'] },
  { name: 'flex-grow', values: ['0', '1'] },
  { name: 'flex-shrink', values: ['0', '1'] },
  { name: 'flex-basis', category: 'length', values: ['auto', '0'] },
  // ── Grid ─────────────────────────────────────────────────────────
  { name: 'grid-template-columns', values: ['auto', 'repeat(auto-fill, minmax(0, 1fr))'] },
  { name: 'grid-template-rows', values: ['auto'] },
  { name: 'grid-column', values: [] },
  { name: 'grid-row', values: [] },
  // ── Effects / interaction ────────────────────────────────────────
  { name: 'opacity', values: ['0', '0.5', '1'] },
  { name: 'box-shadow', category: 'shorthand-box-shadow' },
  { name: 'transform', values: ['none', 'scale(1)', 'translateY(-2px)', 'rotate(45deg)'] },
  { name: 'transition', category: 'shorthand-transition' },
  { name: 'filter', values: ['none', 'blur(4px)', 'brightness(1.1)', 'drop-shadow(0 1px 2px rgba(0,0,0,0.1))'] },
  { name: 'backdrop-filter', values: ['none', 'blur(8px)'] },
  { name: 'cursor', values: ['default', 'pointer', 'text', 'not-allowed', 'grab', 'wait', 'help', 'move'] },
  { name: 'pointer-events', values: ['auto', 'none'] },
  { name: 'user-select', values: ['auto', 'none', 'text', 'all'] },
  { name: 'will-change', values: ['auto', 'transform', 'opacity'] },
];

/* ── Context detector inside style="…" ──────────────────────────────────── */

/**
 * @returns {null | {kind: 'css-prop-name', partial: string, insertStart: number}
 *                | {kind: 'css-prop-value', partial: string, propName: string, insertStart: number}}
 */
export const cssContext = (styleText) => {
  if (typeof styleText !== 'string') return null;

  let lastSemi = -1;
  let lastColon = -1;
  for (let i = styleText.length - 1; i >= 0; i--) {
    const ch = styleText[i];
    if (ch === ';') { lastSemi = i; break; }
    if (ch === ':' && lastColon === -1) lastColon = i;
  }

  if (lastColon !== -1 && lastColon > lastSemi) {
    const propName = styleText.slice(lastSemi + 1, lastColon).trim();
    const partial = styleText.slice(lastColon + 1).replace(/^\s+/, '');
    const insertStart = styleText.length - partial.length;
    return { kind: 'css-prop-value', partial, propName, insertStart };
  }

  const partial = styleText.slice(lastSemi + 1).replace(/^\s+/, '');
  const insertStart = styleText.length - partial.length;
  return { kind: 'css-prop-name', partial, insertStart };
};

/* ── Suggesters ─────────────────────────────────────────────────────────── */

export const filterCssProperties = (partial) => {
  const q = (partial || '').toLowerCase();
  if (!q) return CSS_PROPERTIES.slice(0, 50);
  const prefix = CSS_PROPERTIES.filter((p) => p.name.indexOf(q) === 0);
  const subs = CSS_PROPERTIES.filter((p) =>
    p.name.indexOf(q) > 0 && prefix.indexOf(p) === -1);
  return prefix.concat(subs).slice(0, 50);
};

const COLOR_SUGGESTIONS = NAMED_COLORS.concat(HEX_SAMPLES).concat(COLOR_FUNCTIONS);

/** Filter a flat string list with prefix-first / substring-fallback ranking. */
const rankFilter = (items, partial) => {
  const q = (partial || '').toLowerCase().trim();
  if (!q) return items;
  const prefix = items.filter((v) => v.toLowerCase().indexOf(q) === 0);
  const subs = items.filter((v) =>
    v.toLowerCase().indexOf(q) > 0 && prefix.indexOf(v) === -1);
  return prefix.concat(subs);
};

/**
 * If `chunk` looks like a length the user is mid-typing (`2`, `2p`, `0.5dv`),
 * return suggestion items completing it with each matching unit (`2px`,
 * `2pc`, …  or  `0.5dvh`, `0.5dvw`). Returns null if not a length pattern.
 *
 * @param {string} chunk
 * @param {string[]} units
 * @param {string} hint
 * @returns {Array<{value:string,label:string,hint:string}> | null}
 */
const tryLengthInProgress = (chunk, units, hint) => {
  const m = chunk.match(LENGTH_IN_PROGRESS_RE);
  if (!m) return null;
  const num = m[1];
  const unitPrefix = m[2].toLowerCase();
  // No prefix → all units. Prefix → keep only units that start with it; if
  // nothing matches the prefix, fall through to null so the caller can pick
  // a different suggester (otherwise we'd silently swallow the input).
  const matched = unitPrefix
    ? units.filter((u) => u.indexOf(unitPrefix) === 0)
    : units;
  if (!matched.length) return null;
  return matched.map((u) => ({ value: num + u, label: num + u, hint: hint || 'unit' }));
};

/**
 * Last whitespace-separated chunk of `partial` — that's the bit the user is
 * actively typing inside a multi-token shorthand value. Skips quoted regions
 * (e.g. inside `rgb(…)`, `linear-gradient(…)`).
 */
const currentChunk = (partial) => {
  let depth = 0;
  let start = 0;
  for (let i = 0; i < partial.length; i++) {
    const ch = partial[i];
    if (ch === '(') depth++;
    else if (ch === ')') depth = Math.max(0, depth - 1);
    else if (/\s/.test(ch) && depth === 0) start = i + 1;
  }
  return { start, value: partial.slice(start) };
};

/** Tokenize a value into completed (trailing-whitespace-terminated) chunks. */
const completedTokens = (partial) => {
  const tokens = [];
  let depth = 0;
  let buf = '';
  for (let i = 0; i < partial.length; i++) {
    const ch = partial[i];
    if (ch === '(') { depth++; buf += ch; }
    else if (ch === ')') { depth = Math.max(0, depth - 1); buf += ch; }
    else if (/\s/.test(ch) && depth === 0) {
      if (buf) { tokens.push(buf); buf = ''; }
    } else { buf += ch; }
  }
  // Last buf is the active chunk — only return tokens BEFORE that.
  return tokens;
};

/**
 * Suggestions for `border` / `border-top` / `outline` etc.
 * Slots: width (length OR keyword), style (keyword), color. Order is free.
 * - If the active chunk is a number-only → suggest length units to complete it.
 * - Otherwise → suggest only the slot types not yet present.
 */
const suggestBorderShorthand = (partial) => {
  const chunk = currentChunk(partial);
  const filled = { width: false, style: false, color: false };
  for (const tok of completedTokens(partial)) {
    if (isLength(tok) || isBorderWidthKeyword(tok)) filled.width = true;
    else if (isBorderStyle(tok)) filled.style = true;
    else if (isColor(tok)) filled.color = true;
  }

  // Mid-typing a length (number or number + unit prefix) → offer matching units.
  const lengthItems = tryLengthInProgress(chunk.value, LENGTH_UNITS, 'length');
  if (lengthItems) {
    return { partial: chunk.value, replaceMode: 'token', items: lengthItems };
  }

  const items = [];
  if (!filled.width) {
    items.push(...['1px', '2px', '4px'].map((v) => ({ value: v, label: v, hint: 'width' })));
    items.push(...BORDER_WIDTH_KEYWORDS.map((v) => ({ value: v, label: v, hint: 'width' })));
  }
  if (!filled.style) items.push(...BORDER_STYLES.map((v) => ({ value: v, label: v, hint: 'style' })));
  if (!filled.color) items.push(...COLOR_SUGGESTIONS.map((v) => ({ value: v, label: v, hint: 'color' })));
  return { partial: chunk.value, replaceMode: 'token', items: rankItems(items, chunk.value) };
};

const rankItems = (items, partial) => {
  const q = (partial || '').toLowerCase().trim();
  if (!q) return items;
  const prefix = items.filter((it) => it.value.toLowerCase().indexOf(q) === 0);
  const subs = items.filter((it) =>
    it.value.toLowerCase().indexOf(q) > 0 && prefix.indexOf(it) === -1);
  return prefix.concat(subs);
};

/** margin / padding: 1-4 lengths (margin also accepts `auto`). */
const suggestSpacingShorthand = (partial, allowAuto) => {
  const chunk = currentChunk(partial);
  const lengthItems = tryLengthInProgress(chunk.value, LENGTH_UNITS, 'length');
  if (lengthItems) {
    return { partial: chunk.value, replaceMode: 'token', items: lengthItems };
  }
  const items = ['0', '0.25rem', '0.5rem', '0.75rem', '1rem', '1.5rem', '2rem']
    .concat(allowAuto ? ['auto'] : [])
    .map((v) => ({ value: v, label: v, hint: 'length' }));
  return { partial: chunk.value, replaceMode: 'token', items: rankItems(items, chunk.value) };
};

/** transition: property | duration | timing | delay  (positional but we don't enforce). */
const suggestTransitionShorthand = (partial) => {
  const chunk = currentChunk(partial);
  const filled = { prop: false, duration: false, timing: false };
  for (const tok of completedTokens(partial)) {
    if (isTime(tok)) {
      if (!filled.duration) filled.duration = true;
      // second time token = delay; don't track separately
    } else if (isTimingFunction(tok)) filled.timing = true;
    else if (isTransitionProp(tok) || /^[a-z-]+$/i.test(tok)) filled.prop = true;
  }

  const timeItems = tryLengthInProgress(chunk.value, TIME_UNITS, 'time');
  if (timeItems) {
    return { partial: chunk.value, replaceMode: 'token', items: timeItems };
  }

  const items = [];
  if (!filled.prop) items.push(...TRANSITION_PROPS.map((v) => ({ value: v, label: v, hint: 'property' })));
  if (!filled.duration) items.push(...['0.15s', '0.2s', '0.3s', '150ms', '300ms'].map((v) => ({ value: v, label: v, hint: 'duration' })));
  if (!filled.timing) items.push(...TIMING_FUNCTIONS.map((v) => ({ value: v, label: v, hint: 'timing' })));
  return { partial: chunk.value, replaceMode: 'token', items: rankItems(items, chunk.value) };
};

/** box-shadow: x y blur spread color [inset] */
const suggestBoxShadowShorthand = (partial) => {
  const chunk = currentChunk(partial);
  const tokens = completedTokens(partial);
  let lengthsCount = 0;
  let hasColor = false;
  let hasInset = false;
  for (const tok of tokens) {
    if (isLength(tok) || NUMBER_ONLY_RE.test(tok)) lengthsCount++;
    else if (isColor(tok)) hasColor = true;
    else if (tok === 'inset') hasInset = true;
  }

  const lengthItems = tryLengthInProgress(chunk.value, LENGTH_UNITS, 'length');
  if (lengthItems) {
    return { partial: chunk.value, replaceMode: 'token', items: lengthItems };
  }

  const items = [];
  if (lengthsCount < 4) items.push(...['0', '1px', '2px', '4px', '8px', '16px'].map((v) => ({ value: v, label: v, hint: lengthsCount < 2 ? 'offset' : lengthsCount < 3 ? 'blur' : 'spread' })));
  if (!hasColor) items.push(...COLOR_SUGGESTIONS.slice(0, 12).map((v) => ({ value: v, label: v, hint: 'color' })));
  if (!hasInset) items.push({ value: 'inset', label: 'inset', hint: 'modifier' });
  return { partial: chunk.value, replaceMode: 'token', items: rankItems(items, chunk.value) };
};

/**
 * Color category: just colors. Numbers fall through to hex/rgb if user types `#` / `r` / `h`.
 */
const suggestColor = (partial) => {
  return { partial, replaceMode: 'token', items: rankItems(COLOR_SUGGESTIONS.map((v) => ({ value: v, label: v, hint: 'color' })), partial) };
};

/**
 * Length category: if partial looks like a length the user is typing
 * (digits, optionally followed by unit-prefix letters), suggest matching
 * units. Otherwise fall through to keyword values from the property's
 * static `values` list (auto / 100% / …).
 */
const suggestLength = (partial, prop) => {
  const lengthItems = tryLengthInProgress(partial, LENGTH_UNITS, 'unit');
  if (lengthItems) {
    return { partial, replaceMode: 'token', items: lengthItems };
  }
  const keywords = (prop && prop.values) ? prop.values : [];
  const sizeSamples = ['0', '0.5rem', '1rem', '1.5rem', '2rem', '100%', 'auto'];
  const all = keywords.length ? keywords : sizeSamples;
  return { partial, replaceMode: 'token', items: rankItems(all.map((v) => ({ value: v, label: v, hint: 'value' })), partial) };
};

/**
 * Master dispatcher — given a property name and the current partial value,
 * returns an array of suggestion items. Each item has:
 *   - value: the literal text to insert
 *   - label: how to render it (usually same as value)
 *   - hint:  short type label shown next to the value (e.g. 'color', 'length')
 *   - replaceMode: 'token' (replace the current chunk) or 'append' (append to caret)
 *
 * @param {string} propName
 * @param {string} partial
 * @returns {{items: Array<{value:string,label:string,hint:string}>, partial:string, replaceMode:'token'|'append'}}
 */
export const suggestCssValue = (propName, partial) => {
  const prop = CSS_PROPERTIES.find((p) => p.name === propName);
  const cat = prop && prop.category;

  if (cat === 'shorthand-border') return suggestBorderShorthand(partial);
  if (cat === 'shorthand-margin') return suggestSpacingShorthand(partial, true);
  if (cat === 'shorthand-padding') return suggestSpacingShorthand(partial, false);
  if (cat === 'shorthand-transition') return suggestTransitionShorthand(partial);
  if (cat === 'shorthand-box-shadow') return suggestBoxShadowShorthand(partial);
  if (cat === 'color') return suggestColor(partial);
  if (cat === 'length') return suggestLength(partial, prop);

  // Default: enum-style values from the property's static list.
  const items = (prop && prop.values || []).map((v) => ({ value: v, label: v, hint: 'value' }));
  return { partial, replaceMode: 'token', items: rankItems(items, partial) };
};

/* ── Backwards-compat wrapper ──────────────────────────────────────────── */

/**
 * Legacy entrypoint kept for callers that want a flat string list. New
 * callers should use `suggestCssValue(propName, partial)` for hint info.
 */
export const filterCssValues = (propName, partial) => {
  const result = suggestCssValue(propName, partial);
  return result.items.map((it) => it.value);
};
