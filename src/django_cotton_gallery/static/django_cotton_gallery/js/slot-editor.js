/*!
 * Slot editor feature module.
 *
 * Owns: slot textarea expand toggle, syntax highlighting overlay, HTML
 * formatter, and intellisense (HTML tags + Cotton component tags + props).
 *
 * SPA-safe via `bindOnce` so re-running after a partial DOM swap doesn't
 * stack listeners on the same node.
 */

import { bindOnce, escapeHtml } from './helpers.js';
import { BLUR_HIDE_DELAY_MS, SYNTAX_HIGHLIGHT_DEBOUNCE_MS } from './constants.js';
import { createPopover } from './popover.js';
import { cssContext, filterCssProperties, suggestCssValue } from './css-properties.js';
import { caretRectFromTextarea } from './caret-rect.js';
import { ATTR_SUGGESTIONS, tokenName, writtenAttrNames } from './html-attrs.js';

/* ── Slot textarea expand toggle ────────────────────────────────────── */
// Each slot control has a small icon button that toggles the textarea
// between a compact 4-row default and an 18-rem expanded height.
export const initSlotExpanders = (root = document) => {
  const btns = root.querySelectorAll('[data-cg-textarea-expand]');
  btns.forEach((btn) => {
    if (!bindOnce(btn, 'expand')) return;
    btn.addEventListener('click', () => {
      const control = btn.closest('.cg-control');
      if (!control) return;
      const ta = control.querySelector('[data-cg-slot-textarea]');
      if (!ta) return;
      const expanded = ta.classList.toggle('cg-textarea--expanded');
      btn.setAttribute('aria-pressed', expanded ? 'true' : 'false');
    });
  });
};

/* ── Slot syntax highlighting (Prism overlay) ───────────────────────── */
// Overlay technique: a <pre><code> stacked under a transparent-text textarea
// via CSS grid. On every input, we re-tokenise the text with Prism into the
// <code> element. Caret stays visible via caret-color; selection still works
// because ::selection draws its own background.
export const initSlotHighlighters = (root = document) => {
  const editors = root.querySelectorAll('[data-cg-slot-editor]');
  editors.forEach((wrap) => {
    if (!bindOnce(wrap, 'hl')) return;
    const ta = wrap.querySelector('[data-cg-slot-textarea]');
    if (!ta) return;

    // Build the highlight overlay BEFORE the textarea so the textarea sits on
    // top via DOM order. The <code> intentionally has NO `language-*` class
    // so initSyntaxHighlight's Prism.highlightAllUnder skips it — otherwise
    // Prism stamps `language-markup` onto the parent <pre>, making its theme
    // CSS target it and override our matched padding/font-size/line-height.
    const pre = document.createElement('pre');
    pre.className = 'cg-slot-highlight';
    pre.setAttribute('aria-hidden', 'true');
    const code = document.createElement('code');
    pre.appendChild(code);
    ta.parentNode.insertBefore(pre, ta);
    ta.classList.add('cg-textarea--highlighted');

    const refresh = () => {
      let text = ta.value;
      // Append a trailing space so a final newline keeps line height in the
      // overlay — without it Prism collapses the empty last line.
      if (!text || text.charAt(text.length - 1) === '\n') text += ' ';
      if (window.Prism && window.Prism.languages && window.Prism.languages.markup) {
        code.innerHTML = window.Prism.highlight(text, window.Prism.languages.markup, 'markup');
      } else {
        code.textContent = text;
      }
    };

    const syncScroll = () => {
      pre.scrollTop = ta.scrollTop;
      pre.scrollLeft = ta.scrollLeft;
    };

    // Debounce Prism re-tokenisation so fast typing in long slot content
    // doesn't fragment input. 50ms is below the perception threshold.
    let refreshTimer;
    const scheduleRefresh = () => {
      clearTimeout(refreshTimer);
      refreshTimer = setTimeout(refresh, SYNTAX_HIGHLIGHT_DEBOUNCE_MS);
    };

    ta.addEventListener('input', scheduleRefresh);
    ta.addEventListener('scroll', syncScroll);
    // First render — defer slightly so Prism finishes loading on first paint.
    if (window.Prism) refresh();
    else window.addEventListener('load', refresh, { once: true });
  });
};

/* ── Slot HTML formatter ────────────────────────────────────────────── */
// Minimal HTML/Cotton pretty-printer. Tokenises into tags + text, walks them
// tracking indent depth: opening tag → depth++, closing tag → depth--,
// self-closing / void tags don't shift. Triggered by toolbar button or
// Shift+Alt+F inside any slot textarea.

const VOID_HTML_TAGS = /^<(area|base|br|col|embed|hr|img|input|link|meta|source|track|wbr)\b/i;

const formatSlotHtml = (input, indentStr = '  ') => {
  const html = (input || '').trim();
  if (!html) return '';

  const tokens = [];
  let pos = 0;
  while (pos < html.length) {
    if (html[pos] === '<') {
      const end = html.indexOf('>', pos);
      if (end === -1) {
        tokens.push({ type: 'text', value: html.slice(pos) });
        break;
      }
      const tag = html.slice(pos, end + 1);
      const isClosing = tag.indexOf('</') === 0;
      const isSelfClosing = tag.slice(-2) === '/>' || VOID_HTML_TAGS.test(tag);
      const isComment = tag.indexOf('<!') === 0;
      tokens.push({
        type: 'tag',
        value: tag,
        opening: !isClosing && !isSelfClosing && !isComment,
        closing: isClosing,
      });
      pos = end + 1;
    } else {
      const next = html.indexOf('<', pos);
      const text = html.slice(pos, next === -1 ? html.length : next).trim();
      if (text) tokens.push({ type: 'text', value: text });
      pos = next === -1 ? html.length : next;
    }
  }

  const out = [];
  let depth = 0;
  for (let i = 0; i < tokens.length; i++) {
    const t = tokens[i];
    if (t.type === 'tag' && t.closing) depth = Math.max(0, depth - 1);
    // Inline-collapse when an opening tag wraps a single text token + matching close —
    // keeps `<p>Hello</p>` on one line instead of expanding into 3 lines.
    if (t.type === 'tag' && t.opening &&
        tokens[i + 1] && tokens[i + 1].type === 'text' &&
        tokens[i + 2] && tokens[i + 2].type === 'tag' && tokens[i + 2].closing) {
      out.push(indentStr.repeat(depth) + t.value + tokens[i + 1].value + tokens[i + 2].value);
      i += 2;
      continue;
    }
    out.push(indentStr.repeat(depth) + t.value);
    if (t.type === 'tag' && t.opening) depth++;
  }
  return out.join('\n');
};

/**
 * Inverse of `formatSlotHtml` — strip newlines and collapse whitespace between
 * tags so the entire HTML lives on a single line, left-aligned. Internal text
 * spacing is preserved (e.g. `Hello world` stays one space, not zero).
 */
const minifySlotHtml = (input) => {
  const oneLine = (input || '')
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .join(' ');
  return oneLine.replace(/>\s+</g, '><').trim();
};

const applyTransform = (ta, transform) => {
  const next = transform(ta.value);
  if (next === ta.value) return;
  ta.value = next;
  ta.dispatchEvent(new Event('input', { bubbles: true }));
};

/* ── Tab / Shift+Tab indentation ────────────────────────────────────── */
const TAB_INDENT = '  ';

const indentSelection = (ta) => {
  const { selectionStart, selectionEnd, value } = ta;
  if (selectionStart === selectionEnd) {
    // Empty selection — insert 2 spaces at the cursor.
    const pos = selectionStart + TAB_INDENT.length;
    ta.value = value.slice(0, selectionStart) + TAB_INDENT + value.slice(selectionStart);
    ta.selectionStart = ta.selectionEnd = pos;
  } else {
    // Range selection — prefix every touched line with the indent.
    const lineStart = value.lastIndexOf('\n', selectionStart - 1) + 1;
    // If the selection ends on a line break, don't indent the trailing
    // empty line — same heuristic VS Code uses.
    let blockEnd = selectionEnd;
    if (blockEnd > selectionStart && value[blockEnd - 1] === '\n') blockEnd--;
    const block = value.slice(lineStart, blockEnd);
    const before = value.slice(0, lineStart);
    const after = value.slice(blockEnd);
    const lineCount = (block.match(/\n/g) || []).length + 1;
    const indented = block.replace(/^/gm, TAB_INDENT);
    ta.value = before + indented + after;
    ta.selectionStart = selectionStart + TAB_INDENT.length;
    ta.selectionEnd = selectionEnd + TAB_INDENT.length * lineCount;
  }
  ta.dispatchEvent(new Event('input', { bubbles: true }));
};

const outdentSelection = (ta) => {
  const { selectionStart, selectionEnd, value } = ta;
  const lineStart = value.lastIndexOf('\n', selectionStart - 1) + 1;
  let blockEnd = selectionEnd > selectionStart && value[selectionEnd - 1] === '\n'
    ? selectionEnd - 1
    : selectionEnd;
  if (blockEnd < lineStart) blockEnd = lineStart; // empty line at cursor
  const before = value.slice(0, lineStart);
  const block = value.slice(lineStart, blockEnd);
  const after = value.slice(blockEnd);

  let totalRemoved = 0;
  let firstLineRemoved = 0;
  let firstLine = true;
  // Match up to 2 leading spaces OR a single tab — same as TAB_INDENT width.
  const outdented = block.replace(/^( {1,2}|\t)/gm, (match) => {
    totalRemoved += match.length;
    if (firstLine) { firstLineRemoved = match.length; firstLine = false; }
    return '';
  });
  if (totalRemoved === 0) return;
  ta.value = before + outdented + after;
  ta.selectionStart = Math.max(lineStart, selectionStart - firstLineRemoved);
  ta.selectionEnd = Math.max(ta.selectionStart, selectionEnd - totalRemoved);
  ta.dispatchEvent(new Event('input', { bubbles: true }));
};

export const initSlotFormatters = (root = document) => {
  // Format toolbar button (Shift+Alt+F).
  root.querySelectorAll('[data-cg-textarea-format]').forEach((btn) => {
    if (!bindOnce(btn, 'format')) return;
    btn.addEventListener('click', () => {
      const ta = btn.closest('.cg-control')?.querySelector('[data-cg-slot-textarea]');
      if (ta) applyTransform(ta, formatSlotHtml);
    });
  });

  // Minify toolbar button (Shift+Alt+M) — collapses to a single line.
  root.querySelectorAll('[data-cg-textarea-minify]').forEach((btn) => {
    if (!bindOnce(btn, 'minify')) return;
    btn.addEventListener('click', () => {
      const ta = btn.closest('.cg-control')?.querySelector('[data-cg-slot-textarea]');
      if (ta) applyTransform(ta, minifySlotHtml);
    });
  });

  // Keyboard shortcuts inside slot textareas: Shift+Alt+F (format),
  // Shift+Alt+M (minify), Tab / Shift+Tab (indent / outdent). Bound on
  // the textarea itself so they only fire while the editor has focus —
  // no global key collisions.
  root.querySelectorAll('[data-cg-slot-textarea]').forEach((ta) => {
    if (!bindOnce(ta, 'formatShortcut')) return;
    ta.addEventListener('keydown', (e) => {
      // Tab — defer to the intellisense menu when it's open (it consumes
      // Tab for accept-suggestion). Otherwise: indent / outdent.
      if (e.key === 'Tab') {
        const menu = ta.parentElement && ta.parentElement.querySelector('[data-cg-intellisense]');
        const menuOpen = menu && !menu.hasAttribute('hidden');
        if (menuOpen) return;
        e.preventDefault();
        if (e.shiftKey) outdentSelection(ta);
        else indentSelection(ta);
        return;
      }
      if (e.shiftKey && e.altKey) {
        const k = e.key.toLowerCase();
        if (k === 'f') { e.preventDefault(); applyTransform(ta, formatSlotHtml); }
        else if (k === 'm') { e.preventDefault(); applyTransform(ta, minifySlotHtml); }
      }
    });
  });
};

/* ── Slot intellisense (HTML + Cotton tag suggestions) ──────────────── */
// Triggers on `<` inside any slot textarea. Suggests HTML tags + every
// Cotton component in the catalog (extracted from the sidebar links).
// Tab/Enter inserts the chosen tag.

const HTML_TAG_SUGGESTIONS = [
  { tag: 'div',     desc: 'Block container',     container: true },
  { tag: 'span',    desc: 'Inline container',    container: true },
  { tag: 'p',       desc: 'Paragraph',           container: true },
  { tag: 'a',       desc: 'Anchor / link',       container: true,  attrs: 'href=""' },
  { tag: 'button',  desc: 'Button',              container: true,  attrs: 'type="button"' },
  { tag: 'h1',      desc: 'Heading 1',           container: true },
  { tag: 'h2',      desc: 'Heading 2',           container: true },
  { tag: 'h3',      desc: 'Heading 3',           container: true },
  { tag: 'h4',      desc: 'Heading 4',           container: true },
  { tag: 'ul',      desc: 'Unordered list',      container: true },
  { tag: 'ol',      desc: 'Ordered list',        container: true },
  { tag: 'li',      desc: 'List item',           container: true },
  { tag: 'img',     desc: 'Image',               container: false, attrs: 'src="" alt=""' },
  { tag: 'svg',     desc: 'SVG vector graphic',  container: true,  attrs: 'viewBox="0 0 24 24"' },
  { tag: 'section', desc: 'Page section',        container: true },
  { tag: 'article', desc: 'Self-contained block',container: true },
  { tag: 'header',  desc: 'Section header',      container: true },
  { tag: 'footer',  desc: 'Section footer',      container: true },
  { tag: 'nav',     desc: 'Navigation',          container: true },
  { tag: 'main',    desc: 'Main content',        container: true },
  { tag: 'aside',   desc: 'Sidebar / aside',     container: true },
  { tag: 'form',    desc: 'Form',                container: true,  attrs: 'method="post"' },
  { tag: 'label',   desc: 'Form label',          container: true },
  { tag: 'input',   desc: 'Form input',          container: false, attrs: 'type="text" name=""' },
  { tag: 'textarea',desc: 'Multi-line input',    container: true,  attrs: 'name=""' },
  { tag: 'select',  desc: 'Native dropdown',     container: true,  attrs: 'name=""' },
  { tag: 'option',  desc: 'Dropdown option',     container: true,  attrs: 'value=""' },
  { tag: 'table',   desc: 'Table',               container: true },
  { tag: 'thead',   desc: 'Table head',          container: true },
  { tag: 'tbody',   desc: 'Table body',          container: true },
  { tag: 'tr',      desc: 'Table row',           container: true },
  { tag: 'td',      desc: 'Table cell',          container: true },
  { tag: 'th',      desc: 'Table header cell',   container: true },
  { tag: 'strong',  desc: 'Strong emphasis',     container: true },
  { tag: 'em',      desc: 'Emphasis',            container: true },
  { tag: 'code',    desc: 'Inline code',         container: true },
  { tag: 'pre',     desc: 'Preformatted text',   container: true },
  { tag: 'br',      desc: 'Line break',          container: false },
  { tag: 'hr',      desc: 'Horizontal rule',     container: false },
  { tag: 'small',   desc: 'Smaller text',        container: true },
];

let _cottonIndexCache = null;
const getCottonIndex = () => {
  if (_cottonIndexCache) return _cottonIndexCache;
  // Mine the sidebar — every link with data-cg-component is a component.
  // The cotton tag for `cotton/atoms/button.html` is `<c-atoms.button>`, so
  // we need the path segments AFTER the gallery mount. The mount itself is
  // user-configurable (defaults to `/django-cotton-gallery/` but consumers
  // can mount anywhere), so we derive it at runtime from the current page:
  // the body carries `data-cg-component-path="atoms/button"` on detail
  // pages, and `location.pathname` ends with that same path — stripping
  // one from the other yields the mount prefix.
  const currentPath = document.body.getAttribute('data-cg-component-path') || '';
  const pathname = location.pathname.replace(/\/+$/, '');
  let mount = '';
  if (currentPath && pathname.endsWith('/' + currentPath)) {
    mount = pathname.slice(0, pathname.length - currentPath.length - 1);
  }
  const index = [];
  const seen = new Set();
  document.querySelectorAll('a[data-cg-component]').forEach((a) => {
    const href = (a.getAttribute('href') || '').replace(/\/+$/, '');
    if (!mount || !href.startsWith(mount + '/')) return;
    const path = href.slice(mount.length + 1).replace(/\//g, '.');
    if (!path || seen.has(path)) return;
    seen.add(path);
    index.push({
      tag: 'c-' + path,
      desc: a.getAttribute('title') || '',
      container: true,  // Cotton components default to having a slot
    });
  });
  _cottonIndexCache = index;
  return index;
};

// Lazy-loaded per-component prop catalog. Cached across navigations and
// flushed on `cg-content-swapped` so a freshly-edited component picks up
// new props without requiring a full reload.
let _propsCache = {};
document.addEventListener('cg-content-swapped', () => { _propsCache = {}; });
const getPropsForCottonTag = (cottonTag, callback) => {
  // cottonTag is `c-atoms.ui.button`. Convert to URL path `atoms/ui/button`.
  if (cottonTag.indexOf('c-') !== 0) { callback(null); return; }
  const path = cottonTag.slice(2).replace(/\./g, '/');
  if (Object.prototype.hasOwnProperty.call(_propsCache, path)) {
    callback(_propsCache[path]);
    return;
  }
  const preview = document.querySelector('[data-cg-preview]');
  const template = preview && preview.getAttribute('data-cg-props-url-template');
  if (!template) { callback(null); return; }
  const url = template.replace('__PATH__', path);
  fetch(url, { headers: { 'Accept': 'application/json' }, credentials: 'same-origin' })
    .then((res) => (res.ok ? res.json() : null))
    .then((data) => {
      _propsCache[path] = data;  // cache even null so we don't retry on 404
      callback(data);
    })
    .catch(() => { _propsCache[path] = null; callback(null); });
};

export const initSlotIntellisense = (root = document) => {
  const editors = root.querySelectorAll('[data-cg-slot-editor]');
  editors.forEach((wrap) => {
    if (!bindOnce(wrap, 'intellisense')) return;
    const ta = wrap.querySelector('[data-cg-slot-textarea]');
    const menu = wrap.querySelector('[data-cg-intellisense]');
    if (!ta || !menu) return;

    let currentItems = [];
    let highlight = -1;
    let lastTagStart = -1; // Position of the `<` that opened the current context

    const tagContext = () => {
      // Detects three contexts inside a slot textarea:
      //   1. tag-name: caret right after `<...partial` (no whitespace yet)
      //      → suggest HTML/Cotton tags
      //   2. prop-name: caret inside `<c-foo |partial` (after tag name + ws,
      //      not inside `="..."`) → suggest props for that Cotton component
      //   3. prop-value: caret inside `<c-foo prop="|partial` → suggest the
      //      enum options for that prop (select-type only)
      const caret = ta.selectionStart || 0;
      const text = ta.value.slice(0, caret);
      const lt = text.lastIndexOf('<');
      if (lt === -1) return null;
      const gt = text.lastIndexOf('>');
      if (gt > lt) return null;
      const afterLt = text.slice(lt + 1);
      if (afterLt.charAt(0) === '!' || afterLt.charAt(0) === '?' || afterLt.charAt(0) === '/') return null;

      const firstSpace = afterLt.search(/\s/);
      if (firstSpace === -1) {
        if (afterLt.indexOf('/') !== -1) return null;
        return { kind: 'tag-name', partial: afterLt, insertStart: lt };
      }

      const tagName = afterLt.slice(0, firstSpace);
      if (!/^[\w.-]+$/.test(tagName)) return null;

      // Walk the remainder past the tag name to find the current context.
      const rest = afterLt.slice(firstSpace + 1);
      let inQuote = false;
      let quoteStart = -1;
      let tokenStart = 0;
      for (let i = 0; i < rest.length; i++) {
        const ch = rest[i];
        if (ch === '"') {
          if (inQuote) inQuote = false;
          else { inQuote = true; quoteStart = i; }
        } else if (/\s/.test(ch) && !inQuote) {
          tokenStart = i + 1;
        }
      }

      if (inQuote) {
        // prop-value: extract attribute name preceding the open quote.
        const pre = rest.slice(0, quoteStart);
        if (!pre.endsWith('=')) return null;
        const nameTail = pre.slice(0, -1);
        const wsMatch = nameTail.match(/(\S+)$/);
        if (!wsMatch) return null;
        const attrName = wsMatch[1];
        const partial = rest.slice(quoteStart + 1);
        const valueAbsStart = lt + 1 + firstSpace + 1 + quoteStart + 1;

        // Inside `style="..."` we delegate to a CSS-aware sub-detector that
        // returns either css-prop-name (after `;` or at start) or
        // css-prop-value (after `:`). Falls through to the generic
        // prop-value path on null so we degrade gracefully.
        if (attrName === 'style') {
          const cssCtx = cssContext(partial);
          if (cssCtx) {
            return {
              kind: cssCtx.kind,
              partial: cssCtx.partial,
              tagName,
              attrName,
              propName: cssCtx.propName,
              insertStart: valueAbsStart + cssCtx.insertStart,
            };
          }
        }

        return {
          kind: 'prop-value',
          partial,
          tagName,
          attrName,
          insertStart: valueAbsStart,
        };
      }

      const partial = rest.slice(tokenStart);
      if (partial.indexOf('=') !== -1) return null;
      return {
        kind: 'prop-name',
        partial,
        tagName,
        insertStart: lt + 1 + firstSpace + 1 + tokenStart,
      };
    };

    // Slot popover flips above the textarea when the slot lives near the
    // bottom of the controls panel.
    const popover = createPopover(ta, menu, {
      flipAbove: true,
      matchAnchorWidth: false,
      getAnchorRect: () => caretRectFromTextarea(ta),
    });

    const suggestTags = (partial) => {
      const q = (partial || '').toLowerCase();
      const all = HTML_TAG_SUGGESTIONS.concat(getCottonIndex());
      const prefix = all.filter((s) => s.tag.toLowerCase().indexOf(q) === 0);
      const subs = q ? all.filter((s) =>
        s.tag.toLowerCase().indexOf(q) > 0 && prefix.indexOf(s) === -1) : [];
      return prefix.concat(subs).slice(0, 50);
    };

    const suggestProps = (partial, propsList) => {
      const q = (partial || '').toLowerCase();
      const prefix = propsList.filter((p) => p.clean_name.toLowerCase().indexOf(q) === 0);
      const subs = q ? propsList.filter((p) =>
        p.clean_name.toLowerCase().indexOf(q) > 0 && prefix.indexOf(p) === -1) : [];
      return prefix.concat(subs);
    };

    const paintTagItems = (items) => {
      let html = '';
      for (let i = 0; i < items.length; i++) {
        const s = items[i];
        const iconCls = s.tag.indexOf('c-') === 0 ? 'cg-intellisense__icon--cotton' : 'cg-intellisense__icon--html';
        html += '<button type="button" class="cg-intellisense__item' + (i === 0 ? ' cg-highlighted' : '') +
          '" data-cg-intel-idx="' + i + '" role="option">' +
          '<span class="cg-intellisense__icon ' + iconCls + '">' + (iconCls.indexOf('cotton') !== -1 ? 'C' : '<>') + '</span>' +
          '<code class="cg-intellisense__tag">&lt;' + escapeHtml(s.tag) + '&gt;</code>' +
          '<span class="cg-intellisense__desc">' + escapeHtml(s.desc || '') + '</span>' +
          '</button>';
      }
      return html;
    };

    const paintPropItems = (items) => {
      let html = '';
      for (let i = 0; i < items.length; i++) {
        const p = items[i];
        const typeBadge = p.type === 'boolean' ? 'bool' :
                          p.type === 'select' ? 'enum' :
                          p.type === 'number' ? 'num' : 'str';
        html += '<button type="button" class="cg-intellisense__item' + (i === 0 ? ' cg-highlighted' : '') +
          '" data-cg-intel-idx="' + i + '" role="option">' +
          '<span class="cg-intellisense__icon cg-intellisense__icon--prop">' + escapeHtml(typeBadge) + '</span>' +
          '<code class="cg-intellisense__tag">' + escapeHtml(p.name) + '</code>' +
          '<span class="cg-intellisense__desc">' + escapeHtml(p.description || '') + '</span>' +
          '</button>';
      }
      return html;
    };

    const paintValueItems = (items) => {
      let html = '';
      for (let i = 0; i < items.length; i++) {
        const v = items[i];
        html += '<button type="button" class="cg-intellisense__item' + (i === 0 ? ' cg-highlighted' : '') +
          '" data-cg-intel-idx="' + i + '" role="option">' +
          '<span class="cg-intellisense__icon cg-intellisense__icon--value">opt</span>' +
          '<code class="cg-intellisense__tag">' + escapeHtml(v) + '</code>' +
          '</button>';
      }
      return html;
    };

    const paintCssPropItems = (items) => {
      let html = '';
      for (let i = 0; i < items.length; i++) {
        const p = items[i];
        html += '<button type="button" class="cg-intellisense__item' + (i === 0 ? ' cg-highlighted' : '') +
          '" data-cg-intel-idx="' + i + '" role="option">' +
          '<span class="cg-intellisense__icon cg-intellisense__icon--css">css</span>' +
          '<code class="cg-intellisense__tag">' + escapeHtml(p.name) + '</code>' +
          '</button>';
      }
      return html;
    };

    const paintAttrItems = (items) => {
      let html = '';
      for (let i = 0; i < items.length; i++) {
        const s = items[i];
        html += '<button type="button" class="cg-intellisense__item' + (i === 0 ? ' cg-highlighted' : '') +
          '" data-cg-intel-idx="' + i + '" role="option">' +
          '<span class="cg-intellisense__icon cg-intellisense__icon--prop">attr</span>' +
          '<code class="cg-intellisense__tag">' + escapeHtml(s.token) + '</code>' +
          '<span class="cg-intellisense__desc">' + escapeHtml(s.desc || '') + '</span>' +
          '</button>';
      }
      return html;
    };

    /**
     * Given the textarea content sliced to `ctx.insertStart` (the start of
     * the partial currently under edit), find the boundary of the current
     * tag's attribute region and return the names already typed inside it.
     * The partial is excluded so editing an existing attr still suggests it.
     */
    const writtenAttrsInTag = (insertStart) => {
      const text = ta.value.slice(0, insertStart);
      const lt = text.lastIndexOf('<');
      if (lt === -1) return new Set();
      // Skip tag-name characters.
      let i = lt + 1;
      while (i < text.length && /[\w.\-:]/.test(text[i])) i++;
      // Slice from end of tag-name to the partial start; that's the attr region.
      const region = text.slice(i, insertStart);
      return writtenAttrNames(region);
    };

    const paintCssValueItems = (items) => {
      let html = '';
      for (let i = 0; i < items.length; i++) {
        const it = items[i];
        html += '<button type="button" class="cg-intellisense__item' + (i === 0 ? ' cg-highlighted' : '') +
          '" data-cg-intel-idx="' + i + '" role="option">' +
          '<span class="cg-intellisense__icon cg-intellisense__icon--css">' + escapeHtml(it.hint || 'val') + '</span>' +
          '<code class="cg-intellisense__tag">' + escapeHtml(it.value) + '</code>' +
          '</button>';
      }
      return html;
    };

    const bindMenuClicks = () => {
      menu.querySelectorAll('[data-cg-intel-idx]').forEach((btn) => {
        btn.addEventListener('mousedown', (e) => {
          e.preventDefault();
          insertSuggestion(currentItems[parseInt(btn.getAttribute('data-cg-intel-idx'), 10)]);
        });
      });
    };

    const show = popover.open;
    const hide = popover.close;

    const render = () => {
      const ctx = tagContext();
      if (!ctx) { hide(); return; }
      lastTagStart = ctx.insertStart;

      if (ctx.kind === 'tag-name') {
        currentItems = suggestTags(ctx.partial).map((s) => Object.assign({ _kind: 'tag' }, s));
        if (!currentItems.length) {
          menu.innerHTML = '<p class="cg-intellisense__empty">' + ((window.cgI18n && window.cgI18n.noMatches) || 'No matches') + '</p>';
          show();
          return;
        }
        menu.innerHTML = paintTagItems(currentItems);
        highlight = 0;
        bindMenuClicks();
        show();
        return;
      }

      // CSS suggestions inside `style="..."` — synchronous, no fetch needed.
      if (ctx.kind === 'css-prop-name') {
        const items = filterCssProperties(ctx.partial);
        if (!items.length) {
          menu.innerHTML = '<p class="cg-intellisense__empty">' + ((window.cgI18n && window.cgI18n.noCssPropsMatch) || 'No CSS properties match') + '</p>';
          show();
          return;
        }
        currentItems = items.map((p) => Object.assign({ _kind: 'css-prop' }, p));
        menu.innerHTML = paintCssPropItems(currentItems);
        highlight = 0;
        bindMenuClicks();
        show();
        return;
      }
      if (ctx.kind === 'css-prop-value') {
        const result = suggestCssValue(ctx.propName, ctx.partial);
        if (!result.items.length) { hide(); return; }
        // suggestCssValue may narrow the replace target to the active chunk
        // (the bit after the last whitespace inside the value). Shift the
        // anchor accordingly so insertion replaces only that chunk.
        const chunkOffset = ctx.partial.length - result.partial.length;
        lastTagStart = ctx.insertStart + chunkOffset;
        currentItems = result.items.map((it) => ({ _kind: 'css-value', value: it.value, hint: it.hint }));
        menu.innerHTML = paintCssValueItems(currentItems);
        highlight = 0;
        bindMenuClicks();
        show();
        return;
      }

      // Plain HTML tag (not Cotton): suggest generic HTML attributes.
      if (ctx.tagName.indexOf('c-') !== 0) {
        if (ctx.kind !== 'prop-name') { hide(); return; }
        const q = (ctx.partial || '').toLowerCase().trim();
        // Already typed a complete suggestion → close.
        if (q && ATTR_SUGGESTIONS.some((s) => s.token.toLowerCase() === q)) { hide(); return; }
        const taken = writtenAttrsInTag(ctx.insertStart);
        const visible = ATTR_SUGGESTIONS.filter((s) => !taken.has(tokenName(s.token)));
        const prefix = visible.filter((s) => !q || s.token.toLowerCase().indexOf(q) === 0);
        const subs = q ? visible.filter((s) =>
          s.token.toLowerCase().indexOf(q) > 0 && prefix.indexOf(s) === -1) : [];
        const items = prefix.concat(subs);
        if (!items.length) {
          menu.innerHTML = '<p class="cg-intellisense__empty">' + ((window.cgI18n && window.cgI18n.noHtmlAttrsMatch) || 'No HTML attributes match') + '</p>';
          currentItems = [];
          show();
          return;
        }
        currentItems = items.map((s) => Object.assign({ _kind: 'attr' }, s));
        menu.innerHTML = paintAttrItems(currentItems);
        highlight = 0;
        bindMenuClicks();
        show();
        return;
      }

      // Cotton tag: fetch declared props and suggest them.
      getPropsForCottonTag(ctx.tagName, (data) => {
        // Re-check context — caret may have moved while we were fetching.
        const ctx2 = tagContext();
        if (!ctx2 || ctx2.tagName !== ctx.tagName) return;

        if (ctx2.kind === 'prop-value') {
          const lookup = ctx2.attrName.replace(/^:/, '').replace(/-/g, '_');
          const prop = (data && data.props || []).find((p) => {
            const clean = p.clean_name.replace(/-/g, '_');
            return clean === lookup;
          });
          if (!prop || prop.type !== 'select' || !prop.options || !prop.options.length) {
            hide();
            return;
          }
          const q = (ctx2.partial || '').toLowerCase();
          const opts = prop.options.filter((o) => !q || o.toLowerCase().indexOf(q) !== -1);
          if (!opts.length) { hide(); return; }
          currentItems = opts.map((o) => ({ _kind: 'value', value: o }));
          menu.innerHTML = paintValueItems(opts);
          highlight = 0;
          bindMenuClicks();
          show();
          return;
        }

        // prop-name for Cotton tag — filter out props already present.
        if (!data || !data.props || !data.props.length) {
          currentItems = [];
          menu.innerHTML = '<p class="cg-intellisense__empty">' + ((window.cgI18n && window.cgI18n.noPropsOn) || 'No props on') + ' ' + escapeHtml(ctx.tagName) + '</p>';
          show();
          return;
        }
        const taken = writtenAttrsInTag(ctx2.insertStart);
        const available = data.props.filter((p) =>
          !taken.has(p.clean_name) && !taken.has(p.name) && !taken.has(':' + p.clean_name));
        const filtered = suggestProps(ctx2.partial, available);
        currentItems = filtered.map((p) => Object.assign({ _kind: 'prop' }, p));
        if (!currentItems.length) {
          menu.innerHTML = '<p class="cg-intellisense__empty">' + ((window.cgI18n && window.cgI18n.noMatchingProps) || 'No matching props') + '</p>';
          show();
          return;
        }
        menu.innerHTML = paintPropItems(currentItems);
        highlight = 0;
        bindMenuClicks();
        show();
      });
    };

    const setHighlight = (idx) => {
      const btns = menu.querySelectorAll('[data-cg-intel-idx]');
      if (!btns.length) return;
      if (idx < 0) idx = btns.length - 1;
      if (idx >= btns.length) idx = 0;
      btns.forEach((b, i) => {
        if (i === idx) b.classList.add('cg-highlighted');
        else b.classList.remove('cg-highlighted');
      });
      highlight = idx;
      if (btns[idx]) btns[idx].scrollIntoView({ block: 'nearest' });
    };

    const insertSuggestion = (s) => {
      if (!s || lastTagStart < 0) return;
      const caret = ta.selectionStart;
      const before = ta.value.slice(0, lastTagStart);
      const after = ta.value.slice(caret);
      let insertion, caretPos;

      if (s._kind === 'value') {
        // Replace the partial inside the quotes with the chosen option.
        insertion = s.value;
        caretPos = before.length + insertion.length;
        ta.value = before + insertion + after;
        ta.setSelectionRange(caretPos, caretPos);
        ta.focus();
        ta.dispatchEvent(new Event('input', { bubbles: true }));
        hide();
        return;
      }

      if (s._kind === 'attr') {
        // HTML attribute token — same parking trick as Cotton prop tokens:
        // if the snippet contains `""`, drop the caret between the quotes.
        insertion = s.token;
        const quoteIdx = insertion.indexOf('""');
        if (quoteIdx !== -1) {
          caretPos = before.length + quoteIdx + 1;
        } else {
          caretPos = before.length + insertion.length;
        }
        ta.value = before + insertion + after;
        ta.setSelectionRange(caretPos, caretPos);
        ta.focus();
        ta.dispatchEvent(new Event('input', { bubbles: true }));
        hide();
        return;
      }

      if (s._kind === 'css-prop') {
        // Insert `name: ` so the caret lands ready to type the value.
        insertion = s.name + ': ';
        caretPos = before.length + insertion.length;
        ta.value = before + insertion + after;
        ta.setSelectionRange(caretPos, caretPos);
        ta.focus();
        ta.dispatchEvent(new Event('input', { bubbles: true }));
        return;
      }

      if (s._kind === 'css-value') {
        // Always trail with a single space — never auto-terminate with `;`.
        // The value may be a piece of a shorthand (e.g. `2px` inside `border: 2px solid red`),
        // and we don't want to end the declaration prematurely. The user types
        // `;` themselves when the declaration is complete.
        const hasTrailingPunct = /^\s*[;}"']/.test(after);
        insertion = s.value + (hasTrailingPunct ? '' : ' ');
        caretPos = before.length + insertion.length;
        ta.value = before + insertion + after;
        ta.setSelectionRange(caretPos, caretPos);
        ta.focus();
        ta.dispatchEvent(new Event('input', { bubbles: true }));
        return;
      }

      if (s._kind === 'prop') {
        if (s.type === 'boolean') {
          insertion = s.name;
          caretPos = before.length + insertion.length;
        } else if (s.type === 'select' && s.options && s.options.length) {
          insertion = s.name + '="' + s.options[0] + '"';
          caretPos = before.length + insertion.length;
        } else {
          insertion = s.name + '=""';
          caretPos = before.length + insertion.length - 1; // inside the ""
        }
      } else if (s.container) {
        // <tag attrs>|</tag> — caret between body
        const open = '<' + s.tag + (s.attrs ? ' ' + s.attrs : '') + '>';
        const close = '</' + s.tag + '>';
        insertion = open + close;
        caretPos = before.length + open.length;
        if (s.attrs && open.indexOf('""') !== -1) {
          caretPos = before.length + open.indexOf('""') + 1;
        }
      } else {
        // Self-closing void tag: <tag attrs />
        insertion = '<' + s.tag + (s.attrs ? ' ' + s.attrs : '') + ' />';
        caretPos = before.length + insertion.length;
        if (s.attrs && insertion.indexOf('""') !== -1) {
          caretPos = before.length + insertion.indexOf('""') + 1;
        }
      }
      ta.value = before + insertion + after;
      ta.setSelectionRange(caretPos, caretPos);
      ta.focus();
      ta.dispatchEvent(new Event('input', { bubbles: true }));
      hide();
    };

    ta.addEventListener('input', render);
    ta.addEventListener('click', render);
    ta.addEventListener('keyup', (e) => {
      // Re-evaluate after caret-moving keys
      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight' ||
          e.key === 'Home' || e.key === 'End') render();
    });
    ta.addEventListener('keydown', (e) => {
      if (menu.hasAttribute('hidden')) return;
      if (e.key === 'ArrowDown') { e.preventDefault(); setHighlight(highlight + 1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); setHighlight(highlight - 1); }
      else if (e.key === 'Enter' || e.key === 'Tab') {
        // Menu is open — eat Tab/Enter unconditionally so they never leak
        // to focus traversal or newline insertion. If there's a highlighted
        // suggestion, accept it; otherwise just swallow the key.
        e.preventDefault();
        if (highlight < 0 || !currentItems[highlight]) return;
        insertSuggestion(currentItems[highlight]);
      } else if (e.key === 'Escape') {
        e.preventDefault();
        hide();
      }
    });
    ta.addEventListener('blur', () => {
      // Delay so mousedown on a menu item can fire first.
      setTimeout(hide, BLUR_HIDE_DELAY_MS);
    });
  });
};
