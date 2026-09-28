/*!
 * Shared popover positioning + lifecycle.
 *
 * Four places used to repeat this logic verbatim: enum dropdowns, attrs
 * autocomplete, slot intellisense, language switcher. Each one had its own
 * `getBoundingClientRect → position:fixed → flip-above` boilerplate, plus
 * its own outside-click + scroll-close + resize-reposition handlers.
 *
 * `createPopover(anchor, menu, options)` returns a `{ open, close, isOpen,
 * reposition }` controller that owns those concerns.
 */

import {
  POPOVER_FLIP_THRESHOLD_PX,
  POPOVER_OFFSET_PX,
  POPOVER_VIEWPORT_MARGIN_PX,
} from './constants.js';

/**
 * Wire a popover menu to its anchor element.
 *
 * @param {HTMLElement} anchor — the element the popover floats next to (e.g. a button)
 * @param {HTMLElement} menu — the popover element itself (sibling, position:fixed in CSS)
 * @param {Object} [options]
 * @param {boolean} [options.matchAnchorWidth=true] — set menu.style.width to anchor's width
 * @param {boolean} [options.flipAbove=true] — flip above the anchor when there's no room below
 * @param {number} [options.flipThresholdPx=240] — minimum space below to stay below
 * @param {() => void} [options.onClose] — called after `close()` runs
 * @returns {{open: () => void, close: () => void, isOpen: () => boolean, reposition: () => void, destroy: () => void}}
 */
export const createPopover = (anchor, menu, options) => {
  const opts = Object.assign({
    matchAnchorWidth: true,
    flipAbove: true,
    flipThresholdPx: POPOVER_FLIP_THRESHOLD_PX,
    onClose: null,
    /**
     * Optional callback returning a viewport-coords rect to position against
     * instead of `anchor.getBoundingClientRect()`. Useful for caret tracking
     * inside textareas / contenteditables — see js/caret-rect.js.
     * @type {(() => DOMRect|null) | null}
     */
    getAnchorRect: null,
  }, options || {});

  const reposition = () => {
    const rect = (opts.getAnchorRect && opts.getAnchorRect()) || anchor.getBoundingClientRect();
    if (opts.matchAnchorWidth) {
      menu.style.width = rect.width + 'px';
    }
    // clientWidth, not innerWidth: the latter counts the vertical scrollbar, so
    // clamping to it leaves the menu's last pixels underneath it.
    const margin = POPOVER_VIEWPORT_MARGIN_PX;
    const width = menu.offsetWidth || rect.width;
    const viewportWidth = document.documentElement.clientWidth || window.innerWidth;
    const maxLeft = viewportWidth - width - margin;
    menu.style.left = Math.max(margin, Math.min(rect.left, maxLeft)) + 'px';

    if (opts.flipAbove) {
      const spaceBelow = window.innerHeight - rect.bottom;
      if (spaceBelow >= opts.flipThresholdPx) {
        menu.style.top = (rect.bottom + POPOVER_OFFSET_PX) + 'px';
        menu.style.bottom = '';
      } else {
        menu.style.top = '';
        menu.style.bottom = (window.innerHeight - rect.top + POPOVER_OFFSET_PX) + 'px';
      }
    } else {
      menu.style.top = (rect.bottom + POPOVER_OFFSET_PX) + 'px';
    }
  };

  const open = () => {
    // Unhide first: `reposition()` measures the menu to clamp it, and a hidden
    // menu measures 0. Both happen in the same task, so nothing paints between.
    menu.removeAttribute('hidden');
    reposition();
  };

  const close = () => {
    menu.setAttribute('hidden', '');
    if (opts.onClose) opts.onClose();
  };

  const isOpen = () => !menu.hasAttribute('hidden');

  // Named handlers so `destroy()` can detach them. Without this teardown,
  // every popover ever created stays bound to document/window — and SPA
  // navigation removes the anchor/menu from the DOM but leaks listeners
  // and pinned closures (~9 listeners per detail page).
  const onDocClick = (e) => {
    if (!isOpen()) return;
    if (anchor.contains(e.target) || menu.contains(e.target)) return;
    close();
  };
  // Capture-phase to catch any scroll container under the anchor — but the
  // menu's own list scrolls too (scrollIntoView, wheel) and must survive it.
  const onWindowScroll = (e) => {
    if (!isOpen()) return;
    if (e && e.target instanceof Node && menu.contains(e.target)) return;
    close();
  };
  const onWindowResize = () => { if (isOpen()) reposition(); };
  const onContentSwapped = () => {
    // After an SPA swap, if anchor/menu are no longer in the document
    // the popover is dead — release its global listeners.
    if (!anchor.isConnected || !menu.isConnected) destroy();
  };

  document.addEventListener('click', onDocClick);
  window.addEventListener('scroll', onWindowScroll, true);
  window.addEventListener('resize', onWindowResize);
  document.addEventListener('cg-content-swapped', onContentSwapped);

  let destroyed = false;
  const destroy = () => {
    if (destroyed) return;
    destroyed = true;
    document.removeEventListener('click', onDocClick);
    window.removeEventListener('scroll', onWindowScroll, true);
    window.removeEventListener('resize', onWindowResize);
    document.removeEventListener('cg-content-swapped', onContentSwapped);
  };

  return { open, close, isOpen, reposition, destroy };
};
