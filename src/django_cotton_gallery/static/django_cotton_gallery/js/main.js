/*!
 * Cotton Gallery — entry module.
 *
 * Pure ES module, no IIFE wrapper. Each feature lives in its own file under
 * ./ (sidebar, preview, slot-editor, navigation, ui-bits) and is imported
 * here. This file is the only one referenced from base.html — everything
 * else is reachable via static imports.
 *
 * Behaviors are driven by `data-cg-*` attributes — see ./helpers.js for the
 * WeakSet-backed bind-once registry that prevents listener stacking on SPA
 * swapped subtrees.
 *
 * SPA navigation: `<a>` clicks inside .cg-app that resolve to a same-origin
 * URL are intercepted, fetched, and the <main class="cg-main"> content is
 * swapped. The sidebar stays mounted so its state (search, collapse,
 * scroll) survives. Modifier-key clicks, external URLs, downloads,
 * hash-only links, and target="_blank" use full navigation.
 *
 * If the consumer loaded Alpine or HTMX, we re-init them on swapped content.
 */

import { initSidebar, initActiveLink } from './sidebar.js';
import {
  initTabs,
  initCopy,
  initLintPanel,
  initLintFilters,
  initLintPage,
  initAnnotationBuilder,
} from './ui-bits.js';
import { initNavigation, initCardThumbs } from './navigation.js';
import {
  initPreview,
  initPreviewBgSwitcher,
  initPreviewViewportSwitcher,
  initFullscreenPreview,
  initDropdowns,
  initAttrsAutocomplete,
  initAttrsExpanders,
  initViewSwitcher,
  initSyntaxHighlight,
} from './preview.js';
import {
  initSlotExpanders,
  initSlotFormatters,
  initSlotHighlighters,
  initSlotIntellisense,
} from './slot-editor.js';
import { initEditorModal } from './editor-modal.js';
import { initCheatsheet, initQuickSwitcher, initRecents, initPins } from './power-tools.js';
import { initTooltips } from './tooltip.js';
import { initCompare } from './compare.js';

/**
 * Re-bind gallery behaviors on a freshly-swapped subtree. Idempotent —
 * bindOnce() guards every init function, so this only wires NEW elements.
 *
 * Also rehydrates Alpine and HTMX if the consumer loaded them.
 *
 * @param {HTMLElement} root
 */
const rebindAfterSwap = (root) => {
  initTabs(root);
  initCopy(root);
  if (typeof window.Alpine !== 'undefined' && typeof window.Alpine.initTree === 'function') {
    try { window.Alpine.initTree(root); } catch (_) { /* ignore */ }
  }
  if (typeof window.htmx !== 'undefined' && typeof window.htmx.process === 'function') {
    try { window.htmx.process(root); } catch (_) { /* ignore */ }
  }
};

/**
 * Wire every behavior that lives inside the SPA swap zone — re-run after
 * every navigation, idempotent via bindOnce().
 */
const bindContent = () => {
  initTabs();
  initCopy();
  initLintPanel();
  initLintFilters();
  initLintPage();
  initAnnotationBuilder();
  initDropdowns();
  initAttrsAutocomplete();
  initAttrsExpanders();
  initTooltips();
  initCompare({ bindContent });
  initSlotExpanders();
  initSlotFormatters();
  initSlotHighlighters();
  initSlotIntellisense();
  initPreview({ rebindAfterSwap });
  initPreviewBgSwitcher();
  initPreviewViewportSwitcher();
  initFullscreenPreview();
  initViewSwitcher();
  initCardThumbs({ rebindAfterSwap });
  initSyntaxHighlight();
  // Sidebar lives outside the swap zone, but its active-link marker depends on
  // location.pathname — re-run it after every SPA swap so the highlight tracks
  // the URL. Without this it freezes on whichever link matched at first load.
  initActiveLink();
};

const boot = () => {
  initSidebar();                                         // outside swap — bind once
  initEditorModal();                                     // outside swap — bind once
  initCheatsheet();                                      // global shortcut listener — bind once
  initQuickSwitcher();                                   // Ctrl+K / Cmd+K fuzzy switcher — bind once
  initPins();                                            // star button + sidebar Pinned section
  initRecents();                                         // last N components → sidebar Recent section
  initNavigation({ rebindAfterSwap, bindContent });      // delegated to document — bind once
  bindContent();                                         // initial content
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot);
} else {
  boot();
}
