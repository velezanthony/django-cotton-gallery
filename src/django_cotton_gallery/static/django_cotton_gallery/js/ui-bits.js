/*!
 * UI bits — small leaf modules that don't fit elsewhere.
 *
 * Currently:
 *   - tabs (initTabs): generic tabbed control with animated underline
 *   - clipboard (initCopy): copy-to-clipboard buttons with three lookup modes
 *
 * Both are SPA-safe via `bindOnce` so re-running after a partial DOM swap
 * doesn't stack listeners on the same node.
 */

import { bindOnce, readJSON, toggleHidden, writeJSON } from './helpers.js';
import { STORAGE_LINT_PAGE_SIZE, COPY_FLASH_MS } from './constants.js';

/**
 * Tiny custom dropdown — replacement for `<select>` when we need full
 * styling control (native popup chrome can't be themed for dark mode).
 *
 * Markup contract:
 *   <div data-cg-mini-select data-cg-mini-value="X">
 *     <button data-cg-mini-trigger>
 *       <span data-cg-mini-label>X</span> ▾
 *     </button>
 *     <div data-cg-mini-menu hidden>
 *       <button data-cg-mini-option="A">A</button>
 *       <button data-cg-mini-option="B">B</button>
 *     </div>
 *   </div>
 *
 * Emits a `cg-mini-change` CustomEvent on the wrapper when the value
 * changes; consumers listen for it instead of the native `change` event.
 */
export const initMiniSelect = (root = document) => {
  root.querySelectorAll('[data-cg-mini-select]').forEach((select) => {
    if (!bindOnce(select, 'mini-select')) return;
    const trigger = select.querySelector('[data-cg-mini-trigger]');
    const menu = select.querySelector('[data-cg-mini-menu]');
    const label = select.querySelector('[data-cg-mini-label]');
    const options = Array.from(select.querySelectorAll('[data-cg-mini-option]'));
    if (!trigger || !menu) return;

    const isOpen = () => !menu.hasAttribute('hidden');
    const setOpen = (open) => {
      menu.toggleAttribute('hidden', !open);
      trigger.setAttribute('aria-expanded', String(open));
      select.classList.toggle('cg-mini-select--open', open);
    };

    const setValue = (value) => {
      select.setAttribute('data-cg-mini-value', value);
      if (label) label.textContent = value;
      options.forEach((o) => {
        const on = o.getAttribute('data-cg-mini-option') === value;
        o.classList.toggle('cg-active', on);
        o.setAttribute('aria-selected', on ? 'true' : 'false');
      });
      select.dispatchEvent(new CustomEvent('cg-mini-change', { detail: { value }, bubbles: true }));
    };

    trigger.addEventListener('click', () => setOpen(!isOpen()));
    options.forEach((opt) => {
      opt.addEventListener('click', () => {
        setValue(opt.getAttribute('data-cg-mini-option') || '');
        setOpen(false);
        trigger.focus();
      });
      opt.addEventListener('keydown', (e) => {
        const idx = options.indexOf(opt);
        if (e.key === 'ArrowDown') { e.preventDefault(); options[(idx + 1) % options.length]?.focus(); }
        else if (e.key === 'ArrowUp') { e.preventDefault(); options[(idx - 1 + options.length) % options.length]?.focus(); }
        else if (e.key === 'Escape') { e.preventDefault(); setOpen(false); trigger.focus(); }
      });
    });

    // Named handlers so we can detach them on SPA swap. `buildMatrix`
    // recreates its mini-select pickers every axis change — without this
    // teardown each rebuild stacks two more global listeners forever.
    const onDocClick = (e) => {
      if (isOpen() && !select.contains(e.target)) setOpen(false);
    };
    const onDocKey = (e) => {
      if (e.key === 'Escape' && isOpen()) { setOpen(false); trigger.focus(); }
    };
    const onContentSwapped = () => {
      if (select.isConnected) return;
      document.removeEventListener('click', onDocClick);
      document.removeEventListener('keydown', onDocKey);
      document.removeEventListener('cg-content-swapped', onContentSwapped);
    };
    document.addEventListener('click', onDocClick);
    document.addEventListener('keydown', onDocKey);
    document.addEventListener('cg-content-swapped', onContentSwapped);
  });
};

/**
 * Wire every `[data-cg-tabs]` container under `root`. Idempotent — re-running
 * after a swap binds only new containers.
 *
 * @param {Document|HTMLElement} [root=document]
 */
export const initTabs = (root = document) => {
  const containers = root.querySelectorAll('[data-cg-tabs]');
  containers.forEach((container) => {
    if (!bindOnce(container, 'tabs')) return;

    const list = container.querySelector('.cg-tabs__list');
    const buttons = container.querySelectorAll('[data-cg-tab]');
    const panels = container.querySelectorAll('[data-cg-panel]');

    const moveUnderline = (activeBtn) => {
      if (!list || !activeBtn) return;
      const listRect = list.getBoundingClientRect();
      const btnRect = activeBtn.getBoundingClientRect();
      list.style.setProperty('--cg-tab-x', (btnRect.left - listRect.left) + 'px');
      list.style.setProperty('--cg-tab-w', btnRect.width + 'px');
      list.classList.add('cg-tabs__list--ready');
    };

    buttons.forEach((btn) => {
      btn.addEventListener('click', () => {
        const target = btn.getAttribute('data-cg-tab');
        buttons.forEach((b) => {
          b.classList.toggle('cg-active', b === btn);
        });
        panels.forEach((p) => {
          toggleHidden(p, p.getAttribute('data-cg-panel') !== target);
        });
        moveUnderline(btn);
      });
    });

    const repositionActive = () => {
      moveUnderline(container.querySelector('[data-cg-tab].cg-active'));
    };
    // Position the underline on the initial active tab + every time a tab
    // resizes (initial layout, font-load reflows, container width change).
    // ResizeObserver fires as soon as the buttons have their final size,
    // so the underline lands without a visible jump even when Tailwind
    // applies styles asynchronously after the first paint.
    let ro = null;
    if (typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver(repositionActive);
      buttons.forEach((btn) => ro.observe(btn));
    } else {
      requestAnimationFrame(repositionActive);
    }
    window.addEventListener('resize', repositionActive);

    // Tear down the RO + window listener when the container leaves the DOM
    // via SPA swap. Without this, every detail page visited stacks one
    // ResizeObserver + one resize listener forever.
    const onContentSwapped = () => {
      if (container.isConnected) return;
      if (ro) ro.disconnect();
      window.removeEventListener('resize', repositionActive);
      document.removeEventListener('cg-content-swapped', onContentSwapped);
    };
    document.addEventListener('cg-content-swapped', onContentSwapped);
  });
};

/**
 * Wire every copy-to-clipboard button under `root`. Four lookup modes, in
 * priority order:
 *   - `data-cg-copy-permalink`     → copy `location.href` (live page URL)
 *   - `data-cg-copy-target="#sel"` → copy textContent of a CSS selector
 *   - `data-cg-copy="literal"`     → copy the attribute's literal value
 *   - `data-cg-copy=""`            → copy <pre> textContent inside the closest
 *                                     `[data-cg-copy-wrap]` (or the parent if absent)
 *
 * The empty fallback lets us drop a copy button next to any code block
 * without picking unique ids per snippet.
 *
 * @param {Document|HTMLElement} [root=document]
 */
export const initCopy = (root = document) => {
  const buttons = root.querySelectorAll(
    '[data-cg-copy], [data-cg-copy-target], [data-cg-copy-permalink]'
  );
  buttons.forEach((btn) => {
    if (!bindOnce(btn, 'copy')) return;

    btn.addEventListener('click', () => {
      let text;
      if (btn.hasAttribute('data-cg-copy-permalink')) {
        // Live URL — read at click time, not at bind time, because the
        // detail page rewrites `location.href` on every form change.
        text = location.href;
      } else {
        const sel = btn.getAttribute('data-cg-copy-target');
        if (sel) {
          const node = document.querySelector(sel);
          text = node ? node.textContent : '';
        } else {
          const raw = btn.getAttribute('data-cg-copy');
          if (raw) {
            text = raw;
          } else {
            const wrap = btn.closest('[data-cg-copy-wrap]') || btn.parentElement;
            const pre = wrap ? wrap.querySelector('pre') : null;
            text = pre ? pre.textContent : '';
          }
        }
      }
      text = text.trim();
      if (!text || !navigator.clipboard) return;
      navigator.clipboard.writeText(text).then(() => {
        btn.classList.add('cg-copied');
        setTimeout(() => btn.classList.remove('cg-copied'), COPY_FLASH_MS);
      });
    });
  });
};

/**
 * Lint badge → inline issues panel. Click toggles the collapsible panel
 * below the header. Idempotent via bindOnce so SPA-swapped detail pages
 * don't stack listeners.
 *
 * @param {Document|HTMLElement} [root=document]
 */
export const initLintPanel = (root = document) => {
  const btn = root.querySelector('[data-cg-lint-toggle]');
  const panel = root.querySelector('[data-cg-lint-panel]');
  if (!btn || !panel) return;
  if (!bindOnce(btn, 'lint-toggle')) return;
  btn.addEventListener('click', () => {
    const open = !panel.hasAttribute('hidden');
    if (open) {
      panel.setAttribute('hidden', '');
      btn.setAttribute('aria-expanded', 'false');
    } else {
      panel.removeAttribute('hidden');
      btn.setAttribute('aria-expanded', 'true');
    }
  });
};

/**
 * Lint issue list filter — chips (All/Errors/Warnings) + free-text rule
 * search + click-to-filter on individual rule chips. Multi-instance,
 * scoped to each `[data-cg-lint-list]` container.
 *
 * @param {Document|HTMLElement} [root=document]
 */
export const initLintFilters = (root = document) => {
  root.querySelectorAll('[data-cg-lint-list]').forEach((list) => {
    if (!bindOnce(list, 'lint-list')) return;
    const chips = list.querySelectorAll('[data-cg-filter]');
    const search = list.querySelector('[data-cg-lint-search]');
    const issues = list.querySelectorAll('[data-cg-issue-severity]');
    const empty = list.querySelector('[data-cg-lint-empty]');
    if (!issues.length) return;

    let activeSeverity = 'all';
    let ruleQuery = '';

    const apply = () => {
      let visible = 0;
      issues.forEach((issue) => {
        const sev = issue.getAttribute('data-cg-issue-severity');
        const rule = issue.getAttribute('data-cg-issue-rule') || '';
        const sevMatch = activeSeverity === 'all' || sev === activeSeverity;
        const ruleMatch = !ruleQuery || rule.toLowerCase().indexOf(ruleQuery) !== -1;
        const show = sevMatch && ruleMatch;
        issue.toggleAttribute('hidden', !show);
        if (show) visible += 1;
      });
      if (empty) empty.toggleAttribute('hidden', visible > 0);
    };

    chips.forEach((chip) => {
      chip.addEventListener('click', () => {
        activeSeverity = chip.getAttribute('data-cg-filter');
        chips.forEach((c) => c.classList.toggle('cg-active', c === chip));
        apply();
      });
    });

    if (search) {
      search.addEventListener('input', () => {
        ruleQuery = search.value.trim().toLowerCase();
        apply();
      });
    }

    // Click on the rule chip in any row → mirror it into the search box
    // so the whole list narrows to that rule. Click again on a different
    // rule swaps the filter; clear via Esc or backspace.
    list.querySelectorAll('[data-cg-rule-filter]').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const rule = btn.getAttribute('data-cg-rule-filter') || '';
        if (search) {
          // Toggle: clicking the same rule clears the filter.
          search.value = (search.value === rule) ? '' : rule;
          ruleQuery = search.value.toLowerCase();
          search.focus();
        }
        apply();
      });
    });

    if (search) {
      search.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
          search.value = '';
          ruleQuery = '';
          apply();
        }
      });
    }
  });
};

/**
 * /django-cotton-gallery/lint/ page — global filter toolbar (severity + free-text search
 * across component path AND rule name), bulk Expand-all / Collapse-all,
 * and click-to-filter on individual rule chips.
 *
 * Components whose issues are all filtered out hide entirely so the user
 * doesn't scroll past empty headers. Idempotent via bindOnce.
 *
 * @param {Document|HTMLElement} [root=document]
 */
export const initLintPage = (root = document) => {
  const page = root.querySelector('[data-cg-lint-page]');
  if (!page) return;
  if (!bindOnce(page, 'lint-page')) return;

  const components = Array.from(page.querySelectorAll('[data-cg-lint-component]'));
  const chips = page.querySelectorAll('[data-cg-filter]');
  const search = page.querySelector('[data-cg-lint-search]');
  const noMatch = page.querySelector('[data-cg-lint-no-match]');

  const toggleBtn = page.querySelector('[data-cg-lint-toggle-all]');
  const toggleLabel = toggleBtn?.querySelector('[data-cg-lint-toggle-label]');
  const toggleIcon = toggleBtn?.querySelector('.cg-lint-page__bulk-icon');

  const pagination = page.querySelector('[data-cg-lint-pagination]');
  const pageInfo = page.querySelector('[data-cg-page-info]');
  const prevBtn = page.querySelector('[data-cg-page="prev"]');
  const nextBtn = page.querySelector('[data-cg-page="next"]');
  const pagesEl = page.querySelector('[data-cg-pagination-pages]');
  const pageSizeSel = page.querySelector('[data-cg-lint-page-size]');

  let activeSeverity = 'all';
  let query = '';
  let currentPage = 1;
  // Wire the custom dropdown that replaces the native <select> (so dark
  // mode works — native popup chrome can't be themed).
  initMiniSelect(pageSizeSel?.parentElement || document);

  // Page size: prefer the user's last choice (localStorage), fall back to
  // whichever option the server pre-selected, then a sane default of 5.
  const allowedSizes = pageSizeSel
    ? Array.from(pageSizeSel.querySelectorAll('[data-cg-mini-option]'),
                 (o) => parseInt(o.getAttribute('data-cg-mini-option'), 10))
    : [5];
  const stored = readJSON(STORAGE_LINT_PAGE_SIZE);
  let pageSize = 5;
  if (allowedSizes.indexOf(stored) !== -1) pageSize = stored;
  else if (pageSizeSel) pageSize = parseInt(pageSizeSel.getAttribute('data-cg-mini-value'), 10) || 5;
  if (pageSizeSel) {
    pageSizeSel.setAttribute('data-cg-mini-value', String(pageSize));
    const label = pageSizeSel.querySelector('[data-cg-mini-label]');
    if (label) label.textContent = String(pageSize);
    pageSizeSel.querySelectorAll('[data-cg-mini-option]').forEach((o) => {
      o.classList.toggle('cg-active', o.getAttribute('data-cg-mini-option') === String(pageSize));
    });
  }

  /**
   * Filter pipeline:
   *   1. For each component, hide individual issues that don't match severity / query.
   *   2. A component is "matched" if it has at least one visible issue.
   *   3. Slice the matched list into pages of pageSize.
   *   4. Hide every component not in the current page slice.
   */
  const apply = () => {
    const matched = [];
    components.forEach((cmp) => {
      const path = (cmp.getAttribute('data-cg-component-path') || '').toLowerCase();
      const issues = cmp.querySelectorAll('[data-cg-issue-severity]');
      let visibleIssues = 0;
      issues.forEach((issue) => {
        const sev = issue.getAttribute('data-cg-issue-severity');
        const rule = (issue.getAttribute('data-cg-issue-rule') || '').toLowerCase();
        const sevMatch = activeSeverity === 'all' || sev === activeSeverity;
        const queryMatch = !query || path.indexOf(query) !== -1 || rule.indexOf(query) !== -1;
        const show = sevMatch && queryMatch;
        issue.toggleAttribute('hidden', !show);
        if (show) visibleIssues += 1;
      });
      if (visibleIssues > 0) matched.push(cmp);
    });

    const totalPages = Math.max(1, Math.ceil(matched.length / pageSize));
    if (currentPage > totalPages) currentPage = totalPages;
    if (currentPage < 1) currentPage = 1;
    const start = (currentPage - 1) * pageSize;
    const end = start + pageSize;
    const pageSlice = matched.slice(start, end);
    const inPage = new Set(pageSlice);

    components.forEach((cmp) => cmp.toggleAttribute('hidden', !inPage.has(cmp)));
    // When filter narrows results, auto-open visible sections so the user
    // doesn't have to click each one.
    if (activeSeverity !== 'all' || query) pageSlice.forEach((c) => { c.open = true; });

    // Always show the pagination bar when there's at least one match — the
    // page-size selector and the "Showing X of Y" info are useful even with
    // few items, and disappearing UI on filter change is disorienting.
    // Hide only on 0 matches, where the no-results banner takes over.
    if (pagination) pagination.toggleAttribute('hidden', matched.length === 0);
    if (pageInfo) {
      if (matched.length === 0) {
        pageInfo.textContent = pageInfo.getAttribute('data-cg-empty-label') || '0 components';
      } else {
        const tpl = pageInfo.getAttribute('data-cg-range-template')
          || 'Showing {start}–{end} of {total}';
        pageInfo.textContent = tpl
          .replace('{start}', start + 1)
          .replace('{end}', Math.min(end, matched.length))
          .replace('{total}', matched.length);
      }
    }
    if (prevBtn) prevBtn.disabled = currentPage <= 1;
    if (nextBtn) nextBtn.disabled = currentPage >= totalPages;
    if (noMatch) noMatch.toggleAttribute('hidden', matched.length > 0);
    renderPageButtons(currentPage, totalPages);

    updateToggleLabel();
  };

  /**
   * Compute which page slots to surface in the numbered nav.
   *
   * Patterns:
   *   ≤ 7 pages       → render every page (no ellipsis fits)
   *   current near 1  → 1 2 3 4 5 … last
   *   current near N  → 1 … last-4 last-3 last-2 last-1 last
   *   middle          → 1 … current-1 current current+1 … last
   *
   * Returns a list of numbers and `'…'` placeholders.
   */
  const computePageSlots = (current, total) => {
    if (total <= 7) {
      return Array.from({ length: total }, (_, i) => i + 1);
    }
    if (current <= 4) {
      return [1, 2, 3, 4, 5, '…', total];
    }
    if (current >= total - 3) {
      return [1, '…', total - 4, total - 3, total - 2, total - 1, total];
    }
    return [1, '…', current - 1, current, current + 1, '…', total];
  };

  const renderPageButtons = (current, total) => {
    if (!pagesEl) return;
    const slots = computePageSlots(current, total);
    pagesEl.innerHTML = slots.map((slot) => {
      if (slot === '…') {
        return '<span class="cg-lint-pagination__ellipsis" aria-hidden="true">…</span>';
      }
      const active = slot === current ? ' cg-active' : '';
      const ariaCurrent = slot === current ? ' aria-current="page"' : '';
      return `<button type="button" class="cg-lint-pagination__page${active}" data-cg-goto-page="${slot}"${ariaCurrent}>${slot}</button>`;
    }).join('');
    // Wire the freshly-rendered buttons. Replacing innerHTML resets
    // listeners every render — that's fine, the alternative (delegate on
    // the container) is cheaper but harder to read.
    pagesEl.querySelectorAll('[data-cg-goto-page]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const target = parseInt(btn.getAttribute('data-cg-goto-page'), 10);
        if (target && target !== currentPage) {
          currentPage = target;
          apply();
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }
      });
    });
  };

  const updateToggleLabel = () => {
    if (!toggleBtn || !toggleLabel) return;
    const anyOpen = components.some((c) => c.open && !c.hasAttribute('hidden'));
    const i = (window.cgI18n || {});
    if (anyOpen) {
      toggleBtn.setAttribute('data-cg-state', 'collapse');
      toggleLabel.textContent = i.collapseAll || 'Collapse all';
      if (toggleIcon) toggleIcon.style.transform = 'rotate(180deg)';
    } else {
      toggleBtn.setAttribute('data-cg-state', 'expand');
      toggleLabel.textContent = i.expandAll || 'Expand all';
      if (toggleIcon) toggleIcon.style.transform = '';
    }
  };

  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      const state = toggleBtn.getAttribute('data-cg-state') || 'expand';
      // Only act on currently-visible (in-page, in-filter) components.
      const target = components.filter((c) => !c.hasAttribute('hidden'));
      if (state === 'expand') target.forEach((c) => { c.open = true; });
      else target.forEach((c) => { c.open = false; });
      updateToggleLabel();
    });
    components.forEach((c) => c.addEventListener('toggle', updateToggleLabel));
  }

  chips.forEach((chip) => {
    chip.addEventListener('click', () => {
      activeSeverity = chip.getAttribute('data-cg-filter');
      chips.forEach((c) => c.classList.toggle('cg-active', c === chip));
      currentPage = 1;
      apply();
    });
  });

  if (search) {
    search.addEventListener('input', () => {
      query = search.value.trim().toLowerCase();
      currentPage = 1;
      apply();
    });
    search.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        search.value = '';
        query = '';
        currentPage = 1;
        apply();
      }
    });
  }

  page.querySelectorAll('[data-cg-rule-filter]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      const rule = btn.getAttribute('data-cg-rule-filter') || '';
      if (search) {
        search.value = (search.value === rule) ? '' : rule;
        query = search.value.toLowerCase();
        search.focus();
      }
      currentPage = 1;
      apply();
    });
  });

  if (prevBtn) prevBtn.addEventListener('click', () => { currentPage -= 1; apply(); window.scrollTo({ top: 0, behavior: 'smooth' }); });
  if (nextBtn) nextBtn.addEventListener('click', () => { currentPage += 1; apply(); window.scrollTo({ top: 0, behavior: 'smooth' }); });

  if (pageSizeSel) {
    pageSizeSel.addEventListener('cg-mini-change', (e) => {
      pageSize = parseInt(e.detail.value, 10) || 5;
      writeJSON(STORAGE_LINT_PAGE_SIZE, pageSize);
      currentPage = 1;
      apply();
    });
  }

  apply();
};

/**
 * Annotation builder — composes a single `@prop` line live as the user
 * types. Pure UI: no backend round-trips, no persistence. Output goes to
 * `[data-cg-bld-output]` and the existing copy button picks it up.
 */
export const initAnnotationBuilder = (root = document) => {
  const builder = root.querySelector('[data-cg-builder]');
  if (!builder) return;
  if (!bindOnce(builder, 'builder')) return;

  const entriesContainer = builder.querySelector('[data-cg-builder-entries]');
  const addBtn = builder.querySelector('[data-cg-builder-add]');
  const tpl = builder.querySelector('[data-cg-bld-entry-tpl]');
  const annotationsEl = builder.querySelector('[data-cg-bld-annotations]');
  const cvarsEl = builder.querySelector('[data-cg-bld-cvars]');
  const outputEl = builder.querySelector('[data-cg-bld-output]');
  const validationEl = builder.querySelector('[data-cg-bld-validation]');
  if (!entriesContainer || !tpl || !annotationsEl || !cvarsEl || !outputEl) return;

  const VALID_BOOL = new Set(['True', 'False', 'true', 'false', '1', '0']);
  // Annotation filter values are double-quoted with backslash escapes —
  // the exact convention the @prop parser resolves (`\"` → `"`, `\\` → `\`).
  const escapeQuotes = (s) => String(s).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  const escapeOptionsList = (raw) =>
    raw.split(',')
      .map((s) => s.trim())
      .filter(Boolean)
      // Single-quoted options use the same escape convention (`\'`).
      .map((s) => `'${s.replace(/\\/g, '\\\\').replace(/'/g, "\\'")}'`)
      .join(', ');
  // <c-vars> is HTML (no backslash escapes) — pick the quote style the value
  // doesn't collide with. Both quote types → &quot; fallback + warning.
  const quoteAttrValue = (s) => {
    const v = String(s);
    if (!v.includes('"')) return `"${v}"`;
    if (!v.includes("'")) return `'${v}'`;
    return `"${v.replace(/"/g, '&quot;')}"`;
  };

  /**
   * Read every entry in DOM order and produce its `@prop` annotation line
   * + matching `<c-vars>` attribute fragment + per-entry warnings. Empty
   * entries (no name yet) contribute nothing — the user is just adding
   * placeholders.
   */
  const composeEntry = (entry, index) => {
    const get = (sel) => entry.querySelector(sel);
    const name = (get('[data-cg-bld-name]')?.value || '').trim();
    const dynamic = !!get('[data-cg-bld-dynamic]')?.checked;
    const type = get('[data-cg-bld-type]')?.getAttribute('data-cg-mini-value') || 'text';
    const options = (get('[data-cg-bld-options]')?.value || '').trim();
    const def = (get('[data-cg-bld-default]')?.value || '').trim();
    const description = (get('[data-cg-bld-description]')?.value || '').trim();
    const required = !!get('[data-cg-bld-required]')?.checked;
    const deprecated = (get('[data-cg-bld-deprecated]')?.value || '').trim();
    const example = (get('[data-cg-bld-example]')?.value || '').trim();

    // Reflect the chosen type into the visibility of the options field.
    const optionsField = get('[data-cg-bld-options-field]');
    if (optionsField) optionsField.toggleAttribute('hidden', type !== 'select');

    // Update the entry's title chip with the live name (or fallback).
    const titleEl = get('[data-cg-bld-entry-title]');
    if (titleEl) titleEl.textContent = name || `Prop #${index + 1}`;

    if (!name) return { annotation: null, cvar: null, warnings: [] };

    // ── Build the @prop line.
    const propName = (dynamic ? ':' : '') + name;
    const head = `${propName}:` + (
      type === 'select' && options ? `select[${escapeOptionsList(options)}]` : type
    );
    const annotationParts = [head];
    if (def !== '') {
      if (type === 'boolean' || type === 'number') {
        annotationParts.push(`default:${def}`);
      } else {
        annotationParts.push(`default:"${escapeQuotes(def)}"`);
      }
    }
    if (required) annotationParts.push('required');
    if (description) annotationParts.push(`description:"${escapeQuotes(description)}"`);
    if (deprecated) annotationParts.push(`deprecated:"${escapeQuotes(deprecated)}"`);
    if (example) annotationParts.push(`example:"${escapeQuotes(example)}"`);
    const annotation = `{# @prop ${annotationParts.join(' | ')} #}`;

    // ── Build the matching <c-vars> attribute fragment.
    let cvar;
    if (def === '' && !required) {
      // Bare attribute (no value) — Cotton uses empty string default.
      cvar = propName;
    } else if (type === 'boolean' || type === 'number') {
      cvar = `${propName}=${def || ''}`;
    } else {
      cvar = `${propName}=${quoteAttrValue(def)}`;
    }

    // ── Collect warnings.
    const warnings = [];
    if (required && def !== '') warnings.push(`<code>${name}</code>: \`required\` cannot coexist with a default — pick one.`);
    if (def.includes('"') && def.includes("'")) {
      warnings.push(`<code>${name}</code>: default mixes both quote types — the &lt;c-vars&gt; line falls back to &amp;quot; entities; consider simplifying the value.`);
    }
    if (type === 'select' && !options) warnings.push(`<code>${name}</code>: select needs an options list.`);
    if (type === 'select' && options && def !== '' && !options.split(',').map((s) => s.trim()).includes(def)) {
      warnings.push(`<code>${name}</code>: default "${def}" is not in the options list.`);
    }
    if (type === 'boolean' && def !== '' && !VALID_BOOL.has(def)) {
      warnings.push(`<code>${name}</code>: boolean default "${def}" should be True / False / 1 / 0.`);
    }
    if (type === 'number' && def !== '' && Number.isNaN(parseFloat(def))) {
      warnings.push(`<code>${name}</code>: number default "${def}" is not numeric.`);
    }
    return { annotation, cvar, warnings };
  };

  const render = () => {
    const entries = Array.from(entriesContainer.querySelectorAll('[data-cg-bld-entry]'));
    const annotations = [];
    const cvarParts = [];
    const allWarnings = [];

    entries.forEach((entry, i) => {
      const { annotation, cvar, warnings } = composeEntry(entry, i);
      if (annotation) annotations.push(annotation);
      if (cvar) cvarParts.push(cvar);
      allWarnings.push(...warnings);
    });

    // Detect duplicate names across entries — both the @prop and the
    // <c-vars> would shadow each other in the same component.
    const names = entries
      .map((e) => (e.querySelector('[data-cg-bld-name]')?.value || '').trim())
      .filter(Boolean);
    const dupes = names.filter((n, i) => names.indexOf(n) !== i);
    dupes.forEach((n) => allWarnings.push(`<code>${n}</code>: duplicate name — every prop must be unique.`));

    const annotationsBlock = annotations.length
      ? annotations.join('\n')
      : '{# @prop name:text | description:"" #}';
    const cvarsLine = cvarParts.length
      ? `<c-vars ${cvarParts.join(' ')} />`
      : '<c-vars name="" />';

    annotationsEl.textContent = annotationsBlock;
    cvarsEl.textContent = cvarsLine;
    if (window.Prism) {
      window.Prism.highlightElement(annotationsEl);
      window.Prism.highlightElement(cvarsEl);
    }

    // Hidden combined output is what the Copy button targets — both
    // blocks together with a blank line between them, ready to paste.
    outputEl.textContent = annotationsBlock + '\n\n' + cvarsLine;

    if (validationEl) {
      if (allWarnings.length) {
        validationEl.removeAttribute('hidden');
        validationEl.innerHTML = allWarnings.map((w) => '⚠ ' + w).join('<br>');
      } else {
        validationEl.setAttribute('hidden', '');
        validationEl.innerHTML = '';
      }
    }
  };

  /** Wire every input/select inside a freshly-spawned entry. */
  const wireEntry = (entry) => {
    [
      '[data-cg-bld-name]',
      '[data-cg-bld-options]',
      '[data-cg-bld-default]',
      '[data-cg-bld-description]',
      '[data-cg-bld-deprecated]',
      '[data-cg-bld-example]',
    ].forEach((sel) => {
      const el = entry.querySelector(sel);
      if (el) el.addEventListener('input', render);
    });
    ['[data-cg-bld-dynamic]', '[data-cg-bld-required]'].forEach((sel) => {
      const el = entry.querySelector(sel);
      if (el) el.addEventListener('change', render);
    });
    const typeEl = entry.querySelector('[data-cg-bld-type]');
    if (typeEl) typeEl.addEventListener('cg-mini-change', render);

    const removeBtn = entry.querySelector('[data-cg-bld-remove]');
    if (removeBtn) {
      removeBtn.addEventListener('click', () => {
        entry.remove();
        // Always keep at least one entry visible — easier than empty state.
        if (!entriesContainer.querySelector('[data-cg-bld-entry]')) addEntry();
        render();
      });
    }
  };

  const addEntry = () => {
    const fragment = tpl.content.cloneNode(true);
    entriesContainer.appendChild(fragment);
    const entry = entriesContainer.lastElementChild;
    initMiniSelect(entry);  // wire the new entry's mini-select
    wireEntry(entry);
    render();
    // Focus the name input so the user can type immediately.
    entry.querySelector('[data-cg-bld-name]')?.focus();
    return entry;
  };

  if (addBtn) addBtn.addEventListener('click', addEntry);

  // Spawn the first entry on init (cleaner than rendering a fixed one
  // server side that we'd then have to wire imperatively).
  addEntry();
};
