/*!
 * Sidebar feature module.
 *
 * Owns: mobile drawer, scroll memory, language switcher, theme toggle,
 * bulk collapse/expand, search shortcut, collapsible categories, search
 * input + typeahead suggestions, active-link highlight.
 *
 * Each `init*` returns a teardown so a future SPA-aware orchestrator can
 * dispose listeners. `bindContent` stays SPA-safe today via `bindOnce`.
 */

import {
  cssEscape,
  escapeHtml,
  readJSON,
  toggleHidden,
  writeJSON,
} from './helpers.js';
import {
  SIDEBAR_DESKTOP_BREAKPOINT_PX,
  SIDEBAR_SCROLL_DEBOUNCE_MS,
  STORAGE_COLLAPSED,
  STORAGE_SIDEBAR_SCROLL,
  STORAGE_THEME,
  STORAGE_HIDE_LINT,
  STORAGE_PERSONAL_FILTER,
  STORAGE_SIDEBAR_COLLAPSED,
} from './constants.js';

/**
 * Wire every sidebar behavior. Idempotent for SPA-swapped sidebars: each
 * sub-init binds only the elements it owns, so re-running is safe.
 *
 * @param {Document|HTMLElement} [root=document]
 * @returns {Teardown}
 */
export const initSidebar = (root = document) => {
  const sidebar = root.querySelector('[data-cg-sidebar]');
  if (!sidebar) return () => {};

  const teardowns = [
    initCollapsibles(sidebar),
    initBulkToggle(sidebar),
    initSearch(sidebar),
    initSearchShortcut(sidebar),
    initThemeToggle(sidebar),
    initLangSwitcher(sidebar),
    initToolsDropdown(sidebar),
    initIssuesToggle(sidebar),
    initPersonalToggle(sidebar),
    initScrollMemory(sidebar),
    initMobileDrawer(sidebar),
    initCollapseToggle(sidebar),
    initActiveLink(),
  ];

  const onPopstate = () => initActiveLink();
  window.addEventListener('popstate', onPopstate);
  teardowns.push(() => window.removeEventListener('popstate', onPopstate));

  return () => teardowns.forEach((t) => t && t());
};

/* Below 1024px the sidebar slides in as a drawer. Hamburger toggles, the
   backdrop closes, Esc closes, clicking a component link auto-closes
   before the SPA swap so the drawer doesn't sit open over the new page.
   Body scroll locks while the drawer is open so the page underneath
   doesn't move when the user drags. */

const initMobileDrawer = (sidebar) => {
  const app = document.querySelector('[data-cg-app]');
  const toggle = document.querySelector('[data-cg-mobile-toggle]');
  const backdrop = document.querySelector('[data-cg-sidebar-backdrop]');
  if (!app || !toggle) return () => {};

  const isDesktop = () => window.innerWidth >= SIDEBAR_DESKTOP_BREAKPOINT_PX;

  const open = () => {
    if (isDesktop()) return;
    app.setAttribute('data-cg-sidebar-open', '');
    toggle.setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden';
  };
  const close = () => {
    app.removeAttribute('data-cg-sidebar-open');
    toggle.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
  };

  const onToggle = () => {
    if (app.hasAttribute('data-cg-sidebar-open')) close();
    else open();
  };
  const onBackdrop = () => close();
  const onKeydown = (e) => {
    if (e.key === 'Escape' && app.hasAttribute('data-cg-sidebar-open')) close();
  };
  const onSidebarClick = (e) => {
    if (isDesktop()) return;
    const link = e.target.closest('a[href]');
    if (!link) return;
    const href = link.getAttribute('href') || '';
    if (href.charAt(0) === '#') return; // hash-only links keep the drawer open
    close();
  };
  const onResize = () => {
    if (isDesktop() && app.hasAttribute('data-cg-sidebar-open')) close();
  };

  toggle.addEventListener('click', onToggle);
  if (backdrop) backdrop.addEventListener('click', onBackdrop);
  document.addEventListener('keydown', onKeydown);
  sidebar.addEventListener('click', onSidebarClick);
  window.addEventListener('resize', onResize);

  return () => {
    toggle.removeEventListener('click', onToggle);
    if (backdrop) backdrop.removeEventListener('click', onBackdrop);
    document.removeEventListener('keydown', onKeydown);
    sidebar.removeEventListener('click', onSidebarClick);
    window.removeEventListener('resize', onResize);
  };
};

/* Persist the sidebar's scrollTop across navigations (full reloads, language
   switches, SPA swaps) so the user doesn't lose their place after picking a
   component near the bottom of the list. Restored as soon as the nav is
   laid out — without rAF the assignment lands before category heights are
   computed and the offset reads as 0. */

const initScrollMemory = (sidebar) => {
  const nav = sidebar.querySelector('.cg-sidebar__nav');
  if (!nav) return () => {};

  const saved = readJSON(STORAGE_SIDEBAR_SCROLL);
  if (typeof saved === 'number' && saved > 0) {
    requestAnimationFrame(() => { nav.scrollTop = saved; });
  }

  let saveTimer;
  const onScroll = () => {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(
      () => writeJSON(STORAGE_SIDEBAR_SCROLL, nav.scrollTop),
      SIDEBAR_SCROLL_DEBOUNCE_MS,
    );
  };
  nav.addEventListener('scroll', onScroll, { passive: true });

  return () => {
    clearTimeout(saveTimer);
    nav.removeEventListener('scroll', onScroll);
  };
};

/* Custom language dropdown — trigger toggles the menu, options submit
   the form with the chosen language code, click-outside / Esc close.
   Strips the current language prefix from `next` before submitting so
   Django's LocaleMiddleware re-prefixes with the new language and
   lands on the equivalent component page (instead of the old prefix
   forcing the previous locale to render). */

const initLangSwitcher = (sidebar) => {
  const form = sidebar.querySelector('[data-cg-lang]');
  if (!form) return () => {};
  const trigger = form.querySelector('[data-cg-lang-trigger]');
  const menu = form.querySelector('[data-cg-lang-menu]');
  const input = form.querySelector('[data-cg-lang-input]');
  const nextInput = form.querySelector('input[name="next"]');
  if (!trigger || !menu || !input) return () => {};

  const availableLangs = Array.from(
    menu.querySelectorAll('[data-cg-lang-option]'),
    (b) => b.getAttribute('data-cg-lang-option'),
  );
  const stripLangPrefix = (path) => {
    const m = path.match(/^\/([a-z]{2})(\/|$)/);
    if (m && availableLangs.indexOf(m[1]) !== -1) {
      return path.replace(/^\/[a-z]{2}/, '') || '/';
    }
    return path;
  };

  const open = () => {
    menu.removeAttribute('hidden');
    trigger.setAttribute('aria-expanded', 'true');
  };
  const close = () => {
    menu.setAttribute('hidden', '');
    trigger.setAttribute('aria-expanded', 'false');
  };

  const onTrigger = (e) => {
    e.stopPropagation();
    if (menu.hasAttribute('hidden')) open();
    else close();
  };
  const optionHandlers = [];
  menu.querySelectorAll('[data-cg-lang-option]').forEach((btn) => {
    const onClick = () => {
      input.value = btn.getAttribute('data-cg-lang-option');
      if (nextInput) nextInput.value = stripLangPrefix(location.pathname) + location.search;
      form.submit();
    };
    btn.addEventListener('click', onClick);
    optionHandlers.push({ btn, onClick });
  });
  const onDocClick = (e) => {
    if (menu.hasAttribute('hidden')) return;
    if (!form.contains(e.target)) close();
  };
  const onKeydown = (e) => {
    if (e.key === 'Escape' && !menu.hasAttribute('hidden')) close();
  };

  trigger.addEventListener('click', onTrigger);
  document.addEventListener('click', onDocClick);
  document.addEventListener('keydown', onKeydown);

  return () => {
    trigger.removeEventListener('click', onTrigger);
    optionHandlers.forEach(({ btn, onClick }) => btn.removeEventListener('click', onClick));
    document.removeEventListener('click', onDocClick);
    document.removeEventListener('keydown', onKeydown);
  };
};

/* Tools dropdown — Compare / Lint / Builder collapsed under one trigger.
   Click toggles the menu, click outside / Esc close. Same UX as the lang
   switcher in the footer; pop direction is DOWN since the trigger lives
   in the upper part of the sidebar. */

const initToolsDropdown = (sidebar) => {
  const wrap = sidebar.querySelector('[data-cg-tools]');
  if (!wrap) return () => {};
  const trigger = wrap.querySelector('[data-cg-tools-trigger]');
  const menu = wrap.querySelector('[data-cg-tools-menu]');
  if (!trigger || !menu) return () => {};

  const open = () => {
    menu.removeAttribute('hidden');
    trigger.setAttribute('aria-expanded', 'true');
    wrap.classList.add('cg-sidebar__tools--open');
  };
  const close = () => {
    menu.setAttribute('hidden', '');
    trigger.setAttribute('aria-expanded', 'false');
    wrap.classList.remove('cg-sidebar__tools--open');
  };

  const onTrigger = (e) => {
    e.stopPropagation();
    if (menu.hasAttribute('hidden')) open();
    else close();
  };
  const onDocClick = (e) => {
    if (menu.hasAttribute('hidden')) return;
    if (!wrap.contains(e.target)) close();
  };
  const onKeydown = (e) => {
    if (e.key === 'Escape' && !menu.hasAttribute('hidden')) {
      close();
      trigger.focus();
    }
  };
  // Click on a menu item also closes (the page navigates away anyway,
  // but if the user clicks the active item, we still want it to dismiss).
  const onItemClick = () => close();

  trigger.addEventListener('click', onTrigger);
  document.addEventListener('click', onDocClick);
  document.addEventListener('keydown', onKeydown);
  menu.querySelectorAll('a').forEach((a) => a.addEventListener('click', onItemClick));

  return () => {
    trigger.removeEventListener('click', onTrigger);
    document.removeEventListener('click', onDocClick);
    document.removeEventListener('keydown', onKeydown);
    menu.querySelectorAll('a').forEach((a) => a.removeEventListener('click', onItemClick));
  };
};

/* Theme toggle — flips between light/dark by setting data-theme on <html>.
   The early script in <head> applies the saved value before paint to
   avoid the flash of light theme on first load. */

const initThemeToggle = (sidebar) => {
  const btn = sidebar.querySelector('[data-cg-theme-toggle]');
  if (!btn) return () => {};
  const onClick = () => {
    const current = document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
    const next = current === 'dark' ? 'light' : 'dark';
    if (next === 'dark') {
      document.documentElement.dataset.theme = 'dark';
    } else {
      delete document.documentElement.dataset.theme;
    }
    try { localStorage.setItem(STORAGE_THEME, next); } catch (_) { /* quota or disabled */ }
  };
  btn.addEventListener('click', onClick);
  return () => btn.removeEventListener('click', onClick);
};

/* Single state-aware toggle for the whole category tree. Reads the
   current state (any category expanded?) and flips: any-open → collapse
   all, all-closed → expand all. Persists to the same localStorage key
   that `initCollapsibles` reads, so reloads keep the user's choice.
   The chevron icon rotates 180° to mirror the next action. */

const initBulkToggle = (sidebar) => {
  const btn = sidebar.querySelector('[data-cg-toggle-all]');
  if (!btn) return () => {};

  const icon = btn.querySelector('.cg-sidebar__toolbar-icon');

  const anyOpen = () => Array.from(sidebar.querySelectorAll('[data-cg-collapse]'))
    .some((el) => !el.hasAttribute('hidden'));

  const updateState = () => {
    const open = anyOpen();
    btn.setAttribute('data-cg-state', open ? 'collapse' : 'expand');
    // Chevron up = "collapse" (currently expanded → click to collapse);
    // chevron down = "expand" (currently closed → click to expand).
    if (icon) icon.style.transform = open ? 'rotate(180deg)' : '';
  };

  const setAll = (collapsed) => {
    const state = {};
    sidebar.querySelectorAll('[data-cg-toggle]').forEach((toggleBtn) => {
      const key = toggleBtn.getAttribute('data-cg-toggle');
      const target = sidebar.querySelector('[data-cg-collapse="' + cssEscape(key) + '"]');
      if (!target) return;
      applyCollapsed(toggleBtn, target, collapsed);
      state[key] = collapsed;
    });
    writeJSON(STORAGE_COLLAPSED, state);
    updateState();
  };

  const onClick = () => setAll(anyOpen());

  // Per-category clicks also flip the bulk button label — keep it honest.
  const onSubToggle = () => updateState();
  sidebar.querySelectorAll('[data-cg-toggle]').forEach((toggleBtn) => {
    toggleBtn.addEventListener('click', onSubToggle);
  });

  btn.addEventListener('click', onClick);
  updateState();  // initial paint based on server-rendered state

  return () => {
    btn.removeEventListener('click', onClick);
    sidebar.querySelectorAll('[data-cg-toggle]').forEach((toggleBtn) => {
      toggleBtn.removeEventListener('click', onSubToggle);
    });
  };
};

/* Toggle visibility of the lint badges next to each component link.
   Pure UI — no data change. State persists in localStorage so the user
   gets their preferred view back on reload. */

// STORAGE_HIDE_LINT now imported from constants.js (single source of truth).

const initIssuesToggle = (sidebar) => {
  const btn = sidebar.querySelector('[data-cg-toggle-issues]');
  if (!btn) return () => {};

  const apply = (hidden) => {
    sidebar.classList.toggle('cg-sidebar--hide-lint', hidden);
    btn.setAttribute('aria-pressed', hidden ? 'true' : 'false');
    btn.setAttribute('data-cg-hidden', hidden ? 'true' : 'false');
  };

  // Default: badges visible. Flip if user previously hid them.
  apply(readJSON(STORAGE_HIDE_LINT) === true);

  const onClick = () => {
    const next = btn.getAttribute('data-cg-hidden') !== 'true';
    apply(next);
    writeJSON(STORAGE_HIDE_LINT, next);
  };
  btn.addEventListener('click', onClick);
  return () => btn.removeEventListener('click', onClick);
};

/* Personal-mode filter — two mutually-exclusive toggles in the toolbar:
   star (pins-only) and clock (recents-only). Click flips it on; click
   again flips it back off (default = catalog visible). Picking one
   automatically deactivates the other. Persists the active filter as
   `'pins' | 'recents' | null` in localStorage. */

// STORAGE_PERSONAL_FILTER now imported from constants.js.

const initPersonalToggle = (sidebar) => {
  const wrap = sidebar.querySelector('[data-cg-personal-filter]');
  if (!wrap) return () => {};
  const buttons = Array.from(wrap.querySelectorAll('[data-cg-filter]'));
  if (!buttons.length) return () => {};

  const apply = (mode) => {
    // Drive the sidebar with one class per mode — CSS does the rest.
    sidebar.classList.toggle('cg-sidebar--show-pins-only', mode === 'pins');
    sidebar.classList.toggle('cg-sidebar--show-recents-only', mode === 'recents');
    buttons.forEach((b) => {
      const active = b.getAttribute('data-cg-filter') === mode;
      b.setAttribute('aria-pressed', active ? 'true' : 'false');
      b.setAttribute('data-cg-on', active ? 'true' : 'false');
    });
  };

  const stored = readJSON(STORAGE_PERSONAL_FILTER);
  apply(stored === 'pins' || stored === 'recents' ? stored : null);

  const handlers = buttons.map((b) => {
    const onClick = () => {
      const kind = b.getAttribute('data-cg-filter');
      const next = b.getAttribute('data-cg-on') === 'true' ? null : kind;
      apply(next);
      writeJSON(STORAGE_PERSONAL_FILTER, next);
    };
    b.addEventListener('click', onClick);
    return { b, onClick };
  });

  return () => handlers.forEach(({ b, onClick }) => b.removeEventListener('click', onClick));
};

/* Press "/" anywhere on the page (outside form fields) to focus the sidebar
   search. Matches the kbd hint shown in the search input. Bound on document
   instead of the input itself so the shortcut works from anywhere. */

const initSearchShortcut = (sidebar) => {
  const input = sidebar.querySelector('[data-cg-search]');
  if (!input) return () => {};
  const onKeydown = (e) => {
    if (e.key !== '/') return;
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const t = e.target;
    if (t && t.tagName && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable)) return;
    e.preventDefault();
    input.focus();
    input.select();
  };
  document.addEventListener('keydown', onKeydown);
  return () => document.removeEventListener('keydown', onKeydown);
};

const initCollapsibles = (sidebar) => {
  const collapsed = readJSON(STORAGE_COLLAPSED) || {};
  const handlers = [];

  sidebar.querySelectorAll('[data-cg-toggle]').forEach((btn) => {
    const key = btn.getAttribute('data-cg-toggle');
    const target = sidebar.querySelector('[data-cg-collapse="' + cssEscape(key) + '"]');
    if (!target) return;

    const isActiveBranch =
      sidebar.getAttribute('data-cg-active-category') === key ||
      sidebar.getAttribute('data-cg-active-subcategory-key') === key;

    const startCollapsed = collapsed[key] === true && !isActiveBranch;
    applyCollapsed(btn, target, startCollapsed);

    const onClick = () => {
      const nowCollapsed = !target.hasAttribute('hidden');
      applyCollapsed(btn, target, nowCollapsed);
      collapsed[key] = nowCollapsed;
      writeJSON(STORAGE_COLLAPSED, collapsed);
    };
    btn.addEventListener('click', onClick);
    handlers.push({ btn, onClick });
  });

  return () => handlers.forEach(({ btn, onClick }) => btn.removeEventListener('click', onClick));
};

const applyCollapsed = (btn, target, isCollapsed) => {
  if (isCollapsed) {
    target.setAttribute('hidden', '');
    btn.classList.add('cg-collapsed');
  } else {
    target.removeAttribute('hidden');
    btn.classList.remove('cg-collapsed');
  }
};

const initSearch = (sidebar) => {
  const input = sidebar.querySelector('[data-cg-search]');
  const clearBtn = sidebar.querySelector('[data-cg-search-clear]');
  const suggestions = sidebar.querySelector('[data-cg-suggestions]');
  if (!input) return () => {};

  const apply = () => {
    filterSidebar(sidebar, input.value);
    if (clearBtn) toggleHidden(clearBtn, input.value.length === 0);
  };

  const onInput = apply;

  // Keyboard:
  //   Esc        — clear the query (or blur if already empty)
  //   Tab        — autocomplete to the first suggestion's name
  //   ↓          — move focus into the suggestions dropdown
  //   Enter      — navigate to the first match
  const onKeydown = (e) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      if (input.value !== '') {
        input.value = '';
        apply();
      } else {
        input.blur();
      }
      return;
    }
    // Not gated on visibility: Tab collapses the dropdown but keeps the
    // match node, so Enter must still be able to navigate to it.
    const first = suggestions ? suggestions.querySelector('.cg-sidebar__suggestion') : null;
    const firstName = first ? first.getAttribute('data-cg-suggestion-name') : null;

    if (e.key === 'Tab' && firstName && !e.shiftKey) {
      // Always accept the top-ranked suggestion — the list is sorted best-first,
      // so completing to it is right whether or not it's a strict prefix. Always
      // preventDefault so Tab never steals focus out of the search box.
      e.preventDefault();
      if (firstName.toLowerCase() !== input.value.toLowerCase()) {
        input.value = firstName;
        apply();
      }
      // Accept-and-collapse like the attrs autocomplete; the hidden match
      // node keeps Enter working.
      if (suggestions) suggestions.setAttribute('hidden', '');
    } else if (e.key === 'ArrowDown' && first) {
      e.preventDefault();
      // Re-open if a prior Tab collapsed the menu, then dive into the list.
      if (suggestions.hasAttribute('hidden')) suggestions.removeAttribute('hidden');
      first.focus();
    } else if (e.key === 'Enter' && first) {
      e.preventDefault();
      first.click();
    }
  };

  // Click outside the search section closes the dropdown but keeps the
  // tree filter alive (the user can still browse the filtered list).
  const onDocClick = (e) => {
    if (!suggestions || suggestions.hasAttribute('hidden')) return;
    const wrap = sidebar.querySelector('.cg-sidebar__search-wrap');
    if (wrap && !wrap.contains(e.target)) {
      suggestions.setAttribute('hidden', '');
    }
  };

  // Re-show the dropdown when the input regains focus, if there's still
  // a query and matches.
  const onFocus = () => {
    if (input.value && suggestions && suggestions.children.length > 0) {
      suggestions.removeAttribute('hidden');
    }
  };

  const onClear = clearBtn ? () => {
    input.value = '';
    apply();
    input.focus();
  } : null;

  // The SPA keeps the sidebar mounted, so reset the query AFTER the swap —
  // resetting mid-click would detach the link and strand the navigation.
  const onContentSwap = () => {
    if (input.value !== '') {
      input.value = '';
      apply();
    }
  };

  const onSuggestionsKeydown = suggestions ? (e) => {
    const items = Array.from(suggestions.querySelectorAll('.cg-sidebar__suggestion'));
    const idx = items.indexOf(document.activeElement);
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      const next = items[(idx + 1) % items.length];
      if (next) next.focus();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (idx <= 0) input.focus();
      else items[idx - 1].focus();
    } else if (e.key === 'Tab' && !e.shiftKey && idx >= 0) {
      // Autocomplete from a focused suggestion.
      const name = items[idx].getAttribute('data-cg-suggestion-name');
      if (name) {
        e.preventDefault();
        input.value = name;
        apply();
        input.focus();
        input.setSelectionRange(name.length, name.length);
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      input.focus();
      input.value = '';
      apply();
    }
  } : null;

  input.addEventListener('input', onInput);
  input.addEventListener('keydown', onKeydown);
  document.addEventListener('click', onDocClick);
  input.addEventListener('focus', onFocus);
  if (clearBtn && onClear) clearBtn.addEventListener('click', onClear);
  if (suggestions && onSuggestionsKeydown) suggestions.addEventListener('keydown', onSuggestionsKeydown);
  document.addEventListener('cg-content-swapped', onContentSwap);

  apply();

  return () => {
    input.removeEventListener('input', onInput);
    input.removeEventListener('keydown', onKeydown);
    document.removeEventListener('click', onDocClick);
    input.removeEventListener('focus', onFocus);
    if (clearBtn && onClear) clearBtn.removeEventListener('click', onClear);
    if (suggestions && onSuggestionsKeydown) suggestions.removeEventListener('keydown', onSuggestionsKeydown);
    document.removeEventListener('cg-content-swapped', onContentSwap);
  };
};

// Cached snapshot of the catalogue parsed from the rendered link tree.
// Built lazily on first filter; invalidated when SPA nav fires
// `cg-content-swapped` because `initPins` / `initRecents` add and remove
// `<a data-cg-component>` links in the sidebar after every navigation.
let _componentsCache = null;
const getAllComponents = (sidebar) => {
  if (_componentsCache) return _componentsCache;
  // Skip pins/recents links: they duplicate catalog entries, which would
  // double the suggestions and inflate the "X of N" count.
  const links = sidebar.querySelectorAll('a[data-cg-component]');
  _componentsCache = Array.from(links)
    .filter((a) => !a.closest('[data-cg-personal]'))
    .map((a) => {
      const catEl = a.closest('[data-cg-category]');
      const subEl = a.closest('[data-cg-subcategory]');
      const category = catEl ? catEl.querySelector('.cg-cat__name') : null;
      const subcat = subEl ? subEl.querySelector('.cg-sub__name') : null;
      return {
        name: a.getAttribute('data-cg-component') || '',
        href: a.getAttribute('href') || '',
        description: a.getAttribute('title') || '',
        category: category ? category.textContent.trim() : '',
        subcategory: subcat ? subcat.textContent.trim() : '',
      };
    });
  return _componentsCache;
};
document.addEventListener('cg-content-swapped', () => { _componentsCache = null; });

const highlightMatch = (name, q) => {
  if (!q) return escapeHtml(name);
  const lower = name.toLowerCase();
  const i = lower.indexOf(q);
  if (i === -1) return escapeHtml(name);
  return escapeHtml(name.slice(0, i)) +
         '<mark>' + escapeHtml(name.slice(i, i + q.length)) + '</mark>' +
         escapeHtml(name.slice(i + q.length));
};

const renderSuggestions = (sidebar, query, matches) => {
  const box = sidebar.querySelector('[data-cg-suggestions]');
  if (!box) return;
  if (!query || !matches.length) {
    box.setAttribute('hidden', '');
    box.innerHTML = '';
    return;
  }
  box.innerHTML = matches.map((c) => {
    const path = (c.category + (c.subcategory ? ' / ' + c.subcategory : '')).toLowerCase();
    return '<a class="cg-sidebar__suggestion" href="' + escapeHtml(c.href) + '" role="option" data-cg-suggestion-name="' + escapeHtml(c.name) + '">' +
      '<span class="cg-sidebar__suggestion-head">' +
        '<span class="cg-sidebar__suggestion-name">' + highlightMatch(c.name, query) + '</span>' +
        (path ? '<span class="cg-sidebar__suggestion-path">' + escapeHtml(path) + '</span>' : '') +
      '</span>' +
      (c.description ? '<span class="cg-sidebar__suggestion-desc">' + escapeHtml(c.description) + '</span>' : '') +
    '</a>';
  }).join('');
  box.removeAttribute('hidden');
};

const filterSidebar = (sidebar, query) => {
  const q = (query || '').toLowerCase().trim();
  const allComps = getAllComponents(sidebar);
  const total = allComps.length;
  // Rank by WHERE the query hits the name: a prefix match (index 0, e.g.
  // `button` for "butt") beats a mid-name match (`floating-button`). Ties
  // break to the shorter, then alphabetical name so exact hits lead.
  const matches = q
    ? allComps
        .filter((c) => c.name.toLowerCase().indexOf(q) !== -1)
        .sort((a, b) => {
          const an = a.name.toLowerCase();
          const bn = b.name.toLowerCase();
          const ai = an.indexOf(q);
          const bi = bn.indexOf(q);
          if (ai !== bi) return ai - bi;
          if (an.length !== bn.length) return an.length - bn.length;
          return an < bn ? -1 : an > bn ? 1 : 0;
        })
    : [];

  renderSuggestions(sidebar, q, matches);
  updateSearchCount(sidebar, q, matches.length, total);
  toggleEmptySearch(sidebar, q !== '' && matches.length === 0, q);
};

const updateSearchCount = (sidebar, query, visible, total) => {
  const el = sidebar.querySelector('[data-cg-search-count]');
  if (!el) return;
  if (query === '') {
    toggleHidden(el, true);
    el.innerHTML = '';
    return;
  }
  toggleHidden(el, false);
  const tpl = el.getAttribute('data-cg-count-template') || '{visible} of {total} components';
  el.innerHTML = tpl
    .replace('{visible}', '<strong>' + visible + '</strong>')
    .replace('{total}', '<em>' + total + '</em>');
};

const toggleEmptySearch = (sidebar, show, query) => {
  const el = sidebar.querySelector('[data-cg-empty-search]');
  if (!el) return;
  toggleHidden(el, !show);
  if (show) {
    const queryEl = el.querySelector('[data-cg-empty-search-query]');
    if (queryEl) queryEl.textContent = query;
  }
};

/**
 * Collapse-to-rail toggle (desktop only).
 *
 * Click flips the `data-cg-sidebar-collapsed` attribute on `<html>` and
 * persists the choice in localStorage so it survives reloads. The matching
 * inline script in <head> applies the attribute before first paint to
 * avoid a flash of expanded sidebar — same FOUC-prevention pattern as
 * the dark theme toggle.
 *
 * @param {HTMLElement} sidebar
 * @returns {Teardown}
 */
const initCollapseToggle = (sidebar) => {
  const btn = sidebar.querySelector('[data-cg-collapse-toggle]');
  if (!btn) return () => {};

  const STORAGE_KEY = STORAGE_SIDEBAR_COLLAPSED;
  const html = document.documentElement;

  const apply = (collapsed) => {
    if (collapsed) html.dataset.cgSidebarCollapsed = '';
    else delete html.dataset.cgSidebarCollapsed;
  };

  const onClick = () => {
    const next = !('cgSidebarCollapsed' in html.dataset);
    apply(next);
    try { localStorage.setItem(STORAGE_KEY, next ? '1' : '0'); } catch (_) { /* ignore */ }
  };

  btn.addEventListener('click', onClick);
  return () => btn.removeEventListener('click', onClick);
};

/**
 * Highlight every sidebar link that matches the current pathname:
 *
 *   - `[data-cg-component]` — catalog component links.
 *   - `[data-cg-doclink]`   — Menu items (Get started / Documentation /
 *                             Compare / Lint / Builder). The trigger
 *                             reflects the aggregate: any item active
 *                             → trigger active.
 *
 * Re-runnable — `bindContent` runs this after every SPA navigation so the
 * active marker keeps up. The server's initial `cg-active` classes are
 * accurate on full reload; this function is what keeps them honest after
 * client-side swaps. No teardown needed (no listeners).
 */
export const initActiveLink = () => {
  // Strip trailing slash AND any locale prefix (`/es`, `/eu`, `/fr`) so
  // the comparison works regardless of which language the user is in.
  // Both the link `href` and `location.pathname` carry the prefix
  // identically, so we can compare them after stripping the same way.
  const normalize = (p) => p.replace(/\/$/, '');
  const path = normalize(location.pathname);

  document.querySelectorAll('[data-cg-component]').forEach((link) => {
    link.classList.toggle('cg-active', normalize(link.getAttribute('href') || '') === path);
  });

  // Menu items + propagate to the trigger.
  let menuMatch = false;
  document.querySelectorAll('[data-cg-doclink]').forEach((link) => {
    const match = normalize(link.getAttribute('href') || '') === path;
    link.classList.toggle('cg-active', match);
    if (match) menuMatch = true;
  });
  const trigger = document.querySelector('[data-cg-tools-trigger]');
  if (trigger) trigger.classList.toggle('cg-active', menuMatch);
};
