/*!
 * Power-user tools — keyboard-driven productivity layer.
 *
 * - `?`           cheatsheet overlay
 * - `Ctrl/Cmd+K`  quick switcher (fuzzy component search)
 * - recents       last N components viewed, rendered in sidebar
 * - pins          starred components, rendered above recents
 *
 * Each feature self-installs via its `init…` and is bound once on boot.
 * The recents + pins backbones reach into the sidebar and inject DOM —
 * they're separate from `bindContent` because their data updates on
 * `popstate` / SPA-nav, not on every content swap.
 */

import { bindOnce, escapeHtml, focusTrapHandler, readJSON, writeJSON } from './helpers.js';
import { STORAGE_RECENTS, STORAGE_PINS } from './constants.js';
const RECENTS_MAX = 10;

/* ── Helper: are we inside an editable element? Used to skip global
   shortcuts so people can type `?` or `p` in the search box. ─────────── */
const isTypingTarget = (el) => {
  if (!el) return false;
  const tag = el.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable;
};

/**
 * Catalog snapshot — built lazily on first switcher open by walking the
 * sidebar's component links. Cached for the session; reset on `popstate`
 * AND on `cg-content-swapped` so the snapshot picks up dynamic pinned /
 * recents links that `initPins` / `initRecents` inject after each SPA nav.
 */
let _catalogCache = null;
// Path inside a sidebar link's href — `/django-cotton-gallery/atoms/button/` → `atoms/button`.
const _hrefToPath = (href) => {
  const m = (href || '').match(/\/django-cotton-gallery\/(.+?)\/?$/);
  return m ? m[1] : '';
};
const buildCatalogIndex = () => {
  if (_catalogCache) return _catalogCache;
  // Components surface in TWO places in the sidebar: the categorised
  // catalog tree AND the personal sections (pins, recents). Both render
  // `<a data-cg-component>` for the same component, so a naive walk
  // returns duplicates. Dedupe by path and prefer the entry with
  // category info (i.e. from the tree, not the flat pinned list).
  const byPath = new Map();
  document.querySelectorAll('a[data-cg-component]').forEach((a) => {
    const href = a.getAttribute('href') || '';
    const path = _hrefToPath(href);
    if (!path) return;
    const catEl = a.closest('[data-cg-category]');
    const subEl = a.closest('[data-cg-subcategory]');
    const cat = catEl ? catEl.querySelector('.cg-cat__name') : null;
    const sub = subEl ? subEl.querySelector('.cg-sub__name') : null;
    const entry = {
      name: a.getAttribute('data-cg-component') || '',
      href,
      path,
      description: a.getAttribute('title') || '',
      category: cat ? cat.textContent.trim() : '',
      subcategory: sub ? sub.textContent.trim() : '',
    };
    const existing = byPath.get(path);
    if (!existing || (entry.category && !existing.category)) {
      byPath.set(path, entry);
    }
  });
  _catalogCache = Array.from(byPath.values());
  return _catalogCache;
};
// Only the catalog snapshot varies per page; the props index is a static
// global JSON, so it stays cached for the whole session.
const invalidateCatalogIndex = () => { _catalogCache = null; };
window.addEventListener('popstate', invalidateCatalogIndex);
document.addEventListener('cg-content-swapped', invalidateCatalogIndex);

/**
 * Lazy-fetched parsed metadata per component (props, accepts_attrs, has_slots,
 * deprecated). Loaded only when a structured query (e.g. `prop:size`) is
 * issued — most users never trigger the fetch. Same invalidation contract as
 * `_catalogCache` so newly-pinned components reappear after SPA nav.
 */
let _propsIndexCache = null;
let _propsIndexFetchPromise = null;
const fetchPropsIndex = () => {
  if (_propsIndexCache) return Promise.resolve(_propsIndexCache);
  if (_propsIndexFetchPromise) return _propsIndexFetchPromise;
  _propsIndexFetchPromise = fetch('/django-cotton-gallery/_props-index.json', {
    headers: { 'Accept': 'application/json', 'X-Requested-With': 'fetch' },
    credentials: 'same-origin',
  })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status))))
    .then((data) => {
      _propsIndexCache = data;
      _propsIndexFetchPromise = null;
      return data;
    })
    .catch((err) => {
      _propsIndexFetchPromise = null;
      throw err;
    });
  return _propsIndexFetchPromise;
};

/**
 * Parse a switcher query into structured filters and free-text fragments.
 * Filters are AND'd together; the remaining text fuzzy-matches the name.
 *
 *   "button prop:size"             → text="button", filters=[prop name=size]
 *   "prop:vari"                    → text="",       filters=[prop name=vari, partial=true]
 *   "prop:"                        → text="",       filters=[prop-any]
 *   "prop:variant=primary"         → text="",       filters=[prop name=variant value=primary]
 *   "slot:actions"                 → text="",       filters=[slot name=actions]
 *   "slot:"                        → text="",       filters=[slot-any]
 *   "accepts-attrs has-slots"      → text="",       filters=[accepts-attrs, has-slots]
 *   "deprecated"                   → text="",       filters=[deprecated]
 *
 * `prop:NAME` (no `=`) and `slot:NAME` use SUBSTRING match on the prop /
 * slot name — typing `prop:vari` finds components with `variant`, `varies`,
 * etc. `prop:NAME=VALUE` requires an exact prop name (the value is what
 * the user is filtering on).
 */
const parseSwitcherQuery = (raw) => {
  const tokens = raw.split(/\s+/).filter(Boolean);
  const filters = [];
  const text = [];
  for (const tok of tokens) {
    const lower = tok.toLowerCase();
    if (lower === 'accepts-attrs') filters.push({ kind: 'accepts-attrs' });
    else if (lower === 'has-slots') filters.push({ kind: 'has-slots' });
    else if (lower === 'has-named-slots') filters.push({ kind: 'has-named-slots' });
    else if (lower === 'has-default-slot') filters.push({ kind: 'has-default-slot' });
    else if (lower === 'deprecated') filters.push({ kind: 'deprecated' });
    else if (lower === 'strict') filters.push({ kind: 'strict' });
    else if (lower === 'ignore-unused') filters.push({ kind: 'ignore-unused' });
    else if (lower.startsWith('prop:')) {
      const rest = tok.slice(5);
      // Empty value (just `prop:`) routes into the partial-name path so
      // the suggestion list shows every available prop name. Same for
      // slot below — `prop:` and `slot:` are entry points to the
      // autocomplete, not "any prop / any slot" filters.
      if (!rest) {
        filters.push({ kind: 'prop', name: '', partial: true });
        continue;
      }
      const eq = rest.indexOf('=');
      if (eq === -1) filters.push({ kind: 'prop', name: rest.toLowerCase(), partial: true });
      else filters.push({ kind: 'prop', name: rest.slice(0, eq).toLowerCase(), value: rest.slice(eq + 1).toLowerCase() });
    } else if (lower.startsWith('slot:')) {
      const rest = tok.slice(5);
      filters.push({ kind: 'slot', name: rest.toLowerCase() });
    } else {
      text.push(tok);
    }
  }
  return { filters, text: text.join(' ') };
};

const propsIndexMatches = (filter, propsData) => {
  if (!propsData) return false;
  if (filter.kind === 'accepts-attrs') return !!propsData.accepts_attrs;
  if (filter.kind === 'has-slots') return !!propsData.has_slots;
  if (filter.kind === 'has-named-slots') return !!propsData.has_named_slots;
  if (filter.kind === 'has-default-slot') return !!propsData.has_default_slot;
  if (filter.kind === 'deprecated') return !!propsData.deprecated;
  if (filter.kind === 'strict') return !!propsData.strict;
  if (filter.kind === 'ignore-unused') return !!propsData.ignore_unused;
  if (filter.kind === 'slot') {
    return (propsData.slots || []).some((s) => (s || '').toLowerCase().includes(filter.name));
  }
  if (filter.kind === 'prop') {
    const props = propsData.props || [];
    const found = props.find((p) => {
      const n = (p.name || '').toLowerCase();
      return filter.partial ? n.includes(filter.name) : n === filter.name;
    });
    if (!found) return false;
    if (filter.value === undefined) return true;
    return (found.options || []).some((o) => String(o).toLowerCase() === filter.value);
  }
  return false;
};

/**
 * Tiny fuzzy match — scores how well `query` is a subsequence of `target`.
 * Higher = better. 0 = no match. Handles substring boost so "btn" hits
 * "button" stronger than "abandon".
 */
const fuzzyScore = (query, target) => {
  if (!query) return 1;
  const q = query.toLowerCase();
  const t = target.toLowerCase();
  if (t.indexOf(q) !== -1) {
    // Substring match — score by inverse position so earlier hits rank higher.
    return 1000 - t.indexOf(q);
  }
  // Subsequence match — characters of q appear in order in t.
  let qi = 0;
  let score = 0;
  let lastIdx = -1;
  for (let i = 0; i < t.length && qi < q.length; i++) {
    if (t[i] === q[qi]) {
      score += (lastIdx === -1 || i - lastIdx === 1) ? 2 : 1;
      lastIdx = i;
      qi += 1;
    }
  }
  return qi === q.length ? score : 0;
};

/* ── (1) Cheatsheet ──────────────────────────────────────────────────── */
export const initCheatsheet = () => {
  const modal = document.querySelector('[data-cg-cheatsheet]');
  if (!modal) return;
  if (!bindOnce(modal, 'cheatsheet')) return;

  const open = () => {
    modal.removeAttribute('hidden');
    document.body.classList.add('cg-modal-open');
  };
  const close = () => {
    modal.setAttribute('hidden', '');
    document.body.classList.remove('cg-modal-open');
  };

  modal.querySelectorAll('[data-cg-cheatsheet-close]').forEach((b) =>
    b.addEventListener('click', close)
  );
  // External openers — the help footer hosts a click target so `?` is
  // discoverable without already knowing the shortcut. Bound on document
  // (delegation) so SPA-swapped pages keep working without re-init.
  document.addEventListener('click', (e) => {
    const opener = e.target.closest && e.target.closest('[data-cg-cheatsheet-open]');
    if (opener && modal.hasAttribute('hidden')) {
      e.preventDefault();
      open();
    }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !modal.hasAttribute('hidden')) {
      e.preventDefault();
      close();
      return;
    }
    // `?` opens — usually Shift+/ on US keyboards. Skip when typing.
    if (e.key === '?' && !isTypingTarget(e.target) && modal.hasAttribute('hidden')) {
      e.preventDefault();
      open();
    }
  });
};

/* ── (2) Quick switcher ──────────────────────────────────────────────── */
export const initQuickSwitcher = () => {
  const modal = document.querySelector('[data-cg-switcher]');
  if (!modal) return;
  if (!bindOnce(modal, 'switcher')) return;

  const input = modal.querySelector('[data-cg-switcher-input]');
  const list = modal.querySelector('[data-cg-switcher-list]');
  const empty = modal.querySelector('[data-cg-switcher-empty]');
  // Captured once so a fetch-error message can't permanently replace the
  // default "No matches." text.
  const emptyDefaultText = empty ? empty.textContent : '';
  const loading = modal.querySelector('[data-cg-switcher-loading]');
  let highlight = -1;
  let visible = [];

  const isOpen = () => !modal.hasAttribute('hidden');

  // Collect every unique prop / slot name across the catalog. Powers the
  // two-tier autocomplete: as the user types `prop:vari`, we list the
  // matching prop names ("variant", "variation"…) so they can pick one.
  // The component results only kick in once the name is unambiguous.
  const collectNames = (key) => {
    if (!_propsIndexCache) return [];
    const set = new Set();
    for (const path of Object.keys(_propsIndexCache)) {
      const meta = _propsIndexCache[path];
      if (key === 'prop') {
        for (const p of meta.props || []) if (p && p.name) set.add(p.name);
      } else if (key === 'slot') {
        for (const s of meta.slots || []) if (s) set.add(s);
      }
    }
    return Array.from(set).sort();
  };

  /**
   * Given the parsed filters, decide whether the user is mid-typing a
   * prop/slot NAME (suggestion mode) or has committed to one (results mode).
   * Suggestion mode kicks in when there's a single partial filter whose
   * value doesn't EXACTLY match any catalog prop/slot name — i.e. they're
   * still typing the identifier.
   */
  const detectSuggestionContext = (filters) => {
    if (filters.length !== 1) return null;
    const f = filters[0];
    if (f.kind === 'prop' && f.partial) {
      const all = collectNames('prop');
      const exact = all.some((n) => n.toLowerCase() === f.name);
      if (exact) return null; // committed → show components
      return { kind: 'prop', partial: f.name, candidates: all.filter((n) => n.toLowerCase().includes(f.name)) };
    }
    // `prop:NAME=` (typed `=` with empty value) → suggest the prop's
    // declared options. Closes the search-by-prop loop so the user
    // doesn't have to memorise the enum values.
    if (f.kind === 'prop' && !f.partial && f.value === '') {
      const optionsSet = new Set();
      for (const path of Object.keys(_propsIndexCache || {})) {
        const meta = _propsIndexCache[path];
        const prop = (meta.props || []).find((p) => (p.name || '').toLowerCase() === f.name);
        if (prop) for (const opt of prop.options || []) optionsSet.add(String(opt));
      }
      const candidates = Array.from(optionsSet).sort();
      if (!candidates.length) return null;
      return { kind: 'prop-value', propName: f.name, candidates };
    }
    if (f.kind === 'slot') {
      const all = collectNames('slot');
      const exact = all.some((n) => n.toLowerCase() === f.name);
      if (exact) return null;
      return { kind: 'slot', partial: f.name, candidates: all.filter((n) => n.toLowerCase().includes(f.name)) };
    }
    return null;
  };

  /**
   * Translate active filters into a human-readable section header.
   * Skips the header entirely on plain text searches — those are the
   * common "find a component by name" path and don't need context.
   */
  const describeFilters = (filters) => {
    if (!filters.length) return '';
    const parts = filters.map((f) => {
      if (f.kind === 'prop' && f.value !== undefined) return 'where ' + f.name + '=' + f.value;
      if (f.kind === 'prop') return 'with prop ' + f.name;
      if (f.kind === 'slot') return 'with slot ' + f.name;
      if (f.kind === 'accepts-attrs') return 'that accept attrs';
      if (f.kind === 'has-slots') return 'with at least one slot (default or named)';
      if (f.kind === 'has-named-slots') return 'with at least one named slot';
      if (f.kind === 'has-default-slot') return 'with a default slot';
      if (f.kind === 'deprecated') return 'with deprecated props';
      if (f.kind === 'strict') return 'that are @strict';
      if (f.kind === 'ignore-unused') return 'marked @ignore-unused';
      return '';
    }).filter(Boolean);
    return 'Components ' + parts.join(' · ');
  };

  const renderResults = (items, options) => {
    const opts = options || {};
    visible = items;
    let html = '';
    if (opts.header) {
      // Group header — non-clickable, non-selectable. Pure context.
      html += '<li class="cg-switcher__group-title" role="presentation">'
        + escapeHtml(opts.header) + '</li>';
    }
    html += items.map((it, i) => {
      const cls = 'cg-switcher__item' + (i === 0 ? ' cg-active' : '');
      if (it.kind === 'suggestion') {
        return (
          '<li class="' + cls + ' cg-switcher__item--suggestion" '
          + 'role="option" data-cg-switcher-suggest="' + escapeHtml(it.token) + '">'
          + '<span class="cg-switcher__name">' + escapeHtml(it.label) + '</span>'
          + '<span class="cg-switcher__path">' + escapeHtml(it.hint) + '</span>'
          + '</li>'
        );
      }
      const path = (it.category + (it.subcategory ? ' / ' + it.subcategory : '')).toLowerCase();
      return (
        '<li class="' + cls + '" role="option" data-cg-switcher-href="' + escapeHtml(it.href) + '">'
        + '<span class="cg-switcher__name">' + escapeHtml(it.name) + '</span>'
        + (path ? '<span class="cg-switcher__path">' + escapeHtml(path) + '</span>' : '')
        + '</li>'
      );
    }).join('');
    list.innerHTML = html;
    highlight = items.length ? 0 : -1;
    if (empty) {
      // Restore the default message — this is the normal empty state, never
      // the fetch-error one (only the catch branch sets the error text).
      empty.textContent = emptyDefaultText;
      empty.toggleAttribute('hidden', items.length > 0);
    }
    list.querySelectorAll('[data-cg-switcher-href], [data-cg-switcher-suggest]').forEach((li, i) => {
      li.addEventListener('mouseenter', () => setHighlight(i));
      li.addEventListener('click', () => accept(i));
    });
  };

  const render = () => {
    const raw = input.value.trim();
    const all = buildCatalogIndex();
    const { filters, text } = parseSwitcherQuery(raw);

    // Fast path: no structured filters → existing fuzzy-by-name logic.
    if (filters.length === 0) {
      if (loading) loading.toggleAttribute('hidden', true);
      const scored = all
        .map((c) => ({ c, score: fuzzyScore(text, c.name) }))
        .filter((s) => s.score > 0)
        .sort((a, b) => b.score - a.score)
        .slice(0, 50);
      renderResults(scored.map((s) => s.c));
      return;
    }

    // Structured query → need props-index. Lazy-fetch on first use.
    if (!_propsIndexCache) {
      if (loading) loading.toggleAttribute('hidden', false);
      if (empty) empty.toggleAttribute('hidden', true);
      list.innerHTML = '';
      const queryAtFetch = raw;
      fetchPropsIndex()
        .then(() => {
          if (input.value.trim() !== queryAtFetch) return;
          if (loading) loading.toggleAttribute('hidden', true);
          render();
        })
        .catch(() => {
          if (loading) loading.toggleAttribute('hidden', true);
          if (empty) {
            empty.textContent = (window.cgI18n && window.cgI18n.propIndexFailed) || 'Could not load prop index.';
            empty.toggleAttribute('hidden', false);
          }
        });
      return;
    }

    if (loading) loading.toggleAttribute('hidden', true);

    // Two-tier autocomplete — suggestion mode when the user is typing
    // a prop/slot name that hasn't matched any known identifier yet.
    const ctx = detectSuggestionContext(filters);
    if (ctx) {
      let items;
      let header;
      if (ctx.kind === 'prop-value') {
        items = ctx.candidates.slice(0, 50).map((value) => ({
          kind: 'suggestion',
          token: 'prop:' + ctx.propName + '=' + value,
          label: value,
          hint: ctx.propName + '=',
        }));
        const i = (window.cgI18n || {});
        header = (i.availableValuesForProp || 'Available values for prop') + ' ' + ctx.propName;
      } else {
        items = ctx.candidates.slice(0, 50).map((name) => ({
          kind: 'suggestion',
          token: ctx.kind + ':' + name,
          label: name,
          hint: ctx.kind === 'prop' ? 'prop' : 'slot',
        }));
        const i = (window.cgI18n || {});
        const base = ctx.kind === 'prop'
          ? (i.availableProps || 'Available props')
          : (i.availableNamedSlots || 'Available named slots');
        header = ctx.partial
          ? base + ' ' + (i.matching || 'matching') + ' "' + ctx.partial + '"'
          : base;
      }
      renderResults(items, { header: header });
      return;
    }

    const filtered = all.filter((c) => {
      const meta = _propsIndexCache[c.path];
      return meta && filters.every((f) => propsIndexMatches(f, meta));
    });
    const scored = filtered
      .map((c) => ({ c, score: text ? fuzzyScore(text, c.name) : 1 }))
      .filter((s) => s.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 50);
    renderResults(scored.map((s) => s.c), { header: describeFilters(filters) });
  };

  const setHighlight = (idx) => {
    highlight = idx;
    list.querySelectorAll('[data-cg-switcher-href], [data-cg-switcher-suggest]').forEach((li, i) => {
      li.classList.toggle('cg-active', i === idx);
      if (i === idx) li.scrollIntoView({ block: 'nearest' });
    });
  };

  const accept = (idx) => {
    const item = visible[idx];
    if (!item) return;
    if (item.kind === 'suggestion') {
      // Replace the partial token in the input with the full identifier
      // and re-render. Trailing space lets the user keep composing
      // (e.g. `prop:variant accepts-attrs` for compound queries).
      const raw = input.value;
      const replaced = raw.replace(/(prop|slot):[^\s]*/, item.token);
      input.value = replaced.endsWith(' ') ? replaced : replaced + ' ';
      input.focus();
      render();
      return;
    }
    close();
    spaNavigate(item.href);
  };

  // navigation.js only intercepts real anchor clicks — location.assign
  // would force a full reload. Click the sidebar link (or a synthetic one).
  const spaNavigate = (href) => {
    if (!href) return;
    const existing = document.querySelector(
      '[data-cg-sidebar] a[data-cg-component][href="' + href.replace(/"/g, '\\"') + '"]'
    );
    if (existing) { existing.click(); return; }
    const sidebar = document.querySelector('[data-cg-sidebar]');
    if (sidebar) {
      const a = document.createElement('a');
      a.href = href;
      a.setAttribute('data-cg-component', '');
      a.style.display = 'none';
      sidebar.appendChild(a);
      a.click();
      a.remove();
      return;
    }
    location.assign(href);
  };

  const open = () => {
    modal.removeAttribute('hidden');
    document.body.classList.add('cg-modal-open');
    input.value = '';
    render();
    // Defer focus until the modal has painted; otherwise some browsers
    // skip the focus when an element transitions from hidden.
    requestAnimationFrame(() => input.focus());
  };
  const close = () => {
    modal.setAttribute('hidden', '');
    document.body.classList.remove('cg-modal-open');
  };

  modal.querySelectorAll('[data-cg-switcher-close]').forEach((b) => b.addEventListener('click', close));
  // Hint chips (`prop:NAME`, `accepts-attrs`, etc.) — clicking inserts the
  // associated token into the input. Placeholder chips drop just the
  // prefix (so autocomplete picks up); complete tokens insert as-is.
  modal.querySelectorAll('[data-cg-hint-insert]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const insert = btn.getAttribute('data-cg-hint-insert') || '';
      const current = input.value;
      // Append with a leading space when the input already has content
      // and doesn't end in whitespace, so tokens stay separated.
      const sep = current && !/\s$/.test(current) ? ' ' : '';
      input.value = current + sep + insert;
      input.focus();
      render();
    });
  });
  input.addEventListener('input', render);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setHighlight((highlight + 1) % Math.max(1, visible.length)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setHighlight((highlight - 1 + visible.length) % Math.max(1, visible.length)); }
    else if (e.key === 'Enter') { e.preventDefault(); accept(highlight); }
    else if (e.key === 'Escape') { e.preventDefault(); close(); }
  });

  // Tab cycles only inside the modal — without this the focus leaks to
  // the page underneath and the Quick Switcher loses its dialog semantics.
  // Same helper editor-modal.js uses; gated by isOpen() so it's a no-op
  // while the modal is closed.
  document.addEventListener('keydown', focusTrapHandler(modal, isOpen));

  // Escape closes from anywhere — the input handler only fires while the
  // text field has focus, which would strand focus on a hint chip.
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && isOpen()) {
      e.preventDefault();
      close();
    }
  });

  document.addEventListener('keydown', (e) => {
    // Ctrl+K / Cmd+K opens the switcher. K is the modern convention
    // (GitHub, Linear, Vercel) and doesn't clash with the browser's
    // print dialog like Ctrl+P does.
    const inOurInput = e.target === input;
    if (inOurInput) return;
    if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
      e.preventDefault();
      if (isOpen()) { close(); return; }
      // Don't stack on top of an already-open modal (e.g. the editor).
      if (document.querySelector('[data-cg-editor-modal]:not([hidden])')
          || document.body.classList.contains('cg-modal-open')) return;
      open();
    }
  });
};

/* ── Shared sidebar renderer for recents + pins ──────────────────────── */
/**
 * Resolve a stored component path back into a {name, href, category, ...}
 * object by looking up the existing sidebar link. If the component has
 * been removed from the catalog since it was saved, returns null and the
 * caller should drop it from storage.
 */
const resolvePath = (path) => {
  // Each sidebar link's href looks like `/django-cotton-gallery/atoms/button/`.
  // Build a matcher that tolerates leading/trailing slashes.
  const norm = path.replace(/^\/+|\/+$/g, '');
  const link = document.querySelector(
    'a[data-cg-component][href$="/' + norm + '/"], a[data-cg-component][href$="/' + norm + '"]'
  );
  if (!link) return null;
  const catEl = link.closest('[data-cg-category]');
  const cat = catEl ? catEl.querySelector('.cg-cat__name') : null;
  return {
    path,
    name: link.getAttribute('data-cg-component') || norm.split('/').pop(),
    href: link.getAttribute('href') || '',
    category: cat ? cat.textContent.trim() : '',
  };
};

/**
 * Mount one of the personal lists (recents or pins) above the catalog
 * tree. `kind` is the storage key suffix; `title` and `emptyMessage` are
 * shown in the heading.
 */
const renderSidebarList = (kind, title, items, onRemove) => {
  const sidebar = document.querySelector('[data-cg-sidebar]');
  if (!sidebar) return;
  const id = 'cg-sidebar-' + kind;
  let section = sidebar.querySelector('#' + id);
  if (!section) {
    section = document.createElement('section');
    section.id = id;
    section.className = 'cg-sidebar__personal';
    section.setAttribute('data-cg-personal', kind);
    // Insert just after the "Components" toolbar so the header reads as
    // the section title and the personal lists hang under it. Pins go
    // first, recents second — this is the natural reading order and
    // matches how the personal-only filters annotate the toolbar label.
    const nav = sidebar.querySelector('.cg-sidebar__nav');
    const toolbar = nav.querySelector('.cg-sidebar__toolbar');
    const anchor = toolbar
      ? (kind === 'recents'
          ? (nav.querySelector('[data-cg-personal="pins"]') || toolbar)
          : toolbar)
      : null;
    if (anchor && anchor.nextSibling) nav.insertBefore(section, anchor.nextSibling);
    else if (anchor) nav.appendChild(section);
    else nav.appendChild(section);
  }

  // Hide entirely when empty — no point taking real estate for a header alone.
  if (!items.length) {
    section.setAttribute('hidden', '');
    section.innerHTML = '';
    return;
  }
  section.removeAttribute('hidden');

  const headerHtml = (
    '<h3 class="cg-sidebar__personal-title">' + escapeHtml(title) + '</h3>'
  );
  const itemsHtml = items.map((it) => (
    '<div class="cg-sidebar__personal-row">'
    + '<a href="' + escapeHtml(it.href) + '" data-cg-component="' + escapeHtml(it.name) + '" '
    + 'class="cg-sidebar__personal-link" title="' + escapeHtml(it.path) + '">'
    + escapeHtml(it.name)
    + '</a>'
    + '<button type="button" class="cg-sidebar__personal-remove" '
    + 'data-cg-personal-remove="' + escapeHtml(it.path) + '" '
    + 'aria-label="Remove">'
    + '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 18 18 6M6 6l12 12"/></svg>'
    + '</button>'
    + '</div>'
  )).join('');

  section.innerHTML = headerHtml + itemsHtml;

  section.querySelectorAll('[data-cg-personal-remove]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      onRemove(btn.getAttribute('data-cg-personal-remove'));
    });
  });
};

/* ── (3) Recently viewed ─────────────────────────────────────────────── */
export const initRecents = () => {
  // Track the current page if it's a component detail. The path is
  // available from `body[data-cg-component-path]` set by the detail
  // template; if absent, this isn't a component page.
  const refresh = () => {
    let stored = readJSON(STORAGE_RECENTS);
    if (!Array.isArray(stored)) stored = [];

    const items = stored.map(resolvePath).filter(Boolean);
    renderSidebarList('recents', 'Recent', items, (path) => {
      let cur = readJSON(STORAGE_RECENTS);
      if (!Array.isArray(cur)) cur = [];
      const next = cur.filter((p) => p !== path);
      writeJSON(STORAGE_RECENTS, next);
      refresh();
    });
  };

  // Push the current page to the front of the list (if it's a component).
  const remember = () => {
    const path = document.body.getAttribute('data-cg-component-path');
    if (!path) return;
    let stored = readJSON(STORAGE_RECENTS);
    if (!Array.isArray(stored)) stored = [];
    stored = [path, ...stored.filter((p) => p !== path)].slice(0, RECENTS_MAX);
    writeJSON(STORAGE_RECENTS, stored);
  };

  remember();
  refresh();

  // Hook SPA nav so subsequent visits also get tracked.
  window.addEventListener('popstate', () => { remember(); refresh(); });
  // Also refresh after content swaps because new sidebar links may appear.
  document.addEventListener('cg-content-swapped', () => { remember(); refresh(); });
};

/* ── (4) Pinned components ───────────────────────────────────────────── */
export const initPins = () => {
  const refresh = () => {
    let stored = readJSON(STORAGE_PINS);
    if (!Array.isArray(stored)) stored = [];
    const items = stored.map(resolvePath).filter(Boolean);
    renderSidebarList('pins', 'Pinned', items, (path) => {
      let cur = readJSON(STORAGE_PINS);
      if (!Array.isArray(cur)) cur = [];
      const next = cur.filter((p) => p !== path);
      writeJSON(STORAGE_PINS, next);
      refresh();
      syncStarButton();
    });
  };

  // Mirror the pin state on the star button if the current page has one.
  const syncStarButton = () => {
    const btn = document.querySelector('[data-cg-pin-toggle]');
    if (!btn) return;
    const path = btn.getAttribute('data-cg-pin-path');
    let stored = readJSON(STORAGE_PINS);
    if (!Array.isArray(stored)) stored = [];
    const pinned = stored.includes(path);
    btn.setAttribute('aria-pressed', pinned ? 'true' : 'false');
    btn.setAttribute('data-cg-pinned', pinned ? 'true' : 'false');
    btn.setAttribute('title', pinned ? 'Unpin from sidebar' : 'Pin to sidebar');
  };

  // Document-level delegation so the click works even after SPA swaps.
  document.addEventListener('click', (e) => {
    const btn = e.target.closest && e.target.closest('[data-cg-pin-toggle]');
    if (!btn) return;
    e.preventDefault();
    const path = btn.getAttribute('data-cg-pin-path');
    if (!path) return;
    let stored = readJSON(STORAGE_PINS) || [];
    if (!Array.isArray(stored)) stored = [];
    if (stored.includes(path)) stored = stored.filter((p) => p !== path);
    else stored = [...stored, path];
    writeJSON(STORAGE_PINS, stored);
    refresh();
    syncStarButton();
  });

  refresh();
  syncStarButton();
  window.addEventListener('popstate', () => { refresh(); syncStarButton(); });
  document.addEventListener('cg-content-swapped', () => { refresh(); syncStarButton(); });
};
