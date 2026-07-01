/*!
 * SPA navigation + thumbnail lazy loading.
 *
 * Two related concerns living together because both deal with batched DOM
 * mutations and need the same `rebindAfterSwap` callback to re-init Alpine
 * / HTMX / behaviors after content lands.
 *
 * Public API:
 *   - initNavigation({ rebindAfterSwap, bindContent })
 *       Intercepts gallery-chrome links and swaps <main class="cg-main">
 *       contents in place. Modifier-key clicks, externals, downloads,
 *       hash-only and target="_blank" use the browser's native nav.
 *
 *   - initCardThumbs({ rebindAfterSwap, root })
 *       Lazy-loads each [data-cg-thumb] card via IntersectionObserver,
 *       batches DOM insertions in a single rAF so observer callbacks
 *       coalesce, and runs rebindAfterSwap once per burst.
 */

import { THUMB_OBSERVER_ROOT_MARGIN } from './constants.js';

// Only intercept clicks on links that are part of the gallery chrome itself —
// sidebar, breadcrumb, index cards. Component-internal links (nav-item, navbar
// dropdowns, etc.) keep native browser behavior so we never accidentally fetch
// a URL the consumer didn't intend us to navigate to.
const SPA_CHROME_SELECTOR =
  '[data-cg-sidebar] a[href], .cg-breadcrumb a[href], .cg-card[href], .cg-sidebar__logo[href]';

// Tracks the SPA's last known location (path + search, no hash) so that a
// popstate firing for an in-page hash change can be distinguished from a
// real back/forward across pages.
let _spaLastUrl = typeof location !== 'undefined' ? location.pathname + location.search : '';

// Single in-flight nav at a time — rapid clicks abort the previous fetch.
let _activeNavController = null;

/**
 * Wire SPA-style navigation onto the gallery chrome. Returns a teardown.
 *
 * @param {NavigationOptions} options
 * @returns {Teardown}
 */
export const initNavigation = ({ rebindAfterSwap, bindContent }) => {
  const onClick = (e) => {
    if (!e.target || !e.target.closest) return;
    const link = e.target.closest(SPA_CHROME_SELECTOR);
    if (!link || !shouldIntercept(e, link)) return;
    e.preventDefault();
    const href = link.href || link.getAttribute('href');
    if (!href) return;
    if (href === location.href) return; // no-op nav
    navigate(href, true, { rebindAfterSwap, bindContent });
  };

  const onPopstate = () => {
    const currentUrl = location.pathname + location.search;
    if (currentUrl === _spaLastUrl) return; // hash-only — let the browser handle scroll
    _spaLastUrl = currentUrl;
    navigate(location.href, false, { rebindAfterSwap, bindContent });
  };

  document.addEventListener('click', onClick);
  window.addEventListener('popstate', onPopstate);

  return () => {
    document.removeEventListener('click', onClick);
    window.removeEventListener('popstate', onPopstate);
  };
};

const shouldIntercept = (event, link) => {
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return false;
  if (event.button !== 0) return false;

  const target = link.getAttribute('target');
  if (target && target !== '' && target !== '_self') return false;
  if (link.hasAttribute('download')) return false;
  if (link.getAttribute('rel') === 'external') return false;

  const href = link.getAttribute('href');
  if (!href || href.charAt(0) === '#') return false;
  if (/^(mailto|tel|javascript|data):/i.test(href)) return false;

  let dest;
  try { dest = new URL(link.href || href, location.href); } catch (_) { return false; }
  if (dest.origin !== location.origin) return false;
  if (dest.pathname === location.pathname && dest.search === location.search && dest.hash) return false;

  return true;
};

/**
 * Tear down Alpine on a subtree before innerHTML replaces it. Without this,
 * reactivities / watchers / setIntervals from x-init keep running attached
 * to nodes that no longer exist in the DOM.
 *
 * Exported because the live-preview pane also swaps content in place and
 * must clean up the same way.
 *
 * @param {HTMLElement|null} root
 */
export const teardownBeforeSwap = (root) => {
  if (!root) return;
  if (typeof window.Alpine !== 'undefined' && typeof window.Alpine.destroyTree === 'function') {
    try {
      const nodes = root.querySelectorAll('[x-data]');
      for (let i = 0; i < nodes.length; i++) {
        if (nodes[i]._x_dataStack) {
          try { window.Alpine.destroyTree(nodes[i]); } catch (_) { /* ignore */ }
        }
      }
    } catch (_) { /* ignore */ }
  }
};

const navigate = (url, push, { rebindAfterSwap, bindContent }) => {
  const app = document.querySelector('.cg-app');
  if (app) app.classList.add('cg-loading');

  if (_activeNavController) _activeNavController.abort();
  const controller = (typeof AbortController !== 'undefined') ? new AbortController() : null;
  _activeNavController = controller;

  const fetchOpts = { headers: { 'X-Requested-With': 'cg-spa' }, credentials: 'same-origin' };
  if (controller) fetchOpts.signal = controller.signal;

  fetch(url, fetchOpts)
    .then((res) => {
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return res.text().then((text) => ({ text, url: res.url || url }));
    })
    .then((payload) => {
      const doc = new DOMParser().parseFromString(payload.text, 'text/html');
      const newMain = doc.querySelector('main.cg-main');
      const currentMain = document.querySelector('main.cg-main');
      if (!newMain || !currentMain) {
        window.location.href = url;
        return;
      }

      // CRITICAL: tear down Alpine on the outgoing subtree first.
      teardownBeforeSwap(currentMain);

      currentMain.innerHTML = newMain.innerHTML;
      if (doc.title) document.title = doc.title;
      // The body's `data-cg-component-path` is set on the detail page —
      // mirror it from the swapped doc so client-side features that read
      // it (recents tracker, pin button) see the right value.
      const newBody = doc.body;
      if (newBody) {
        const newPath = newBody.getAttribute('data-cg-component-path');
        if (newPath) document.body.setAttribute('data-cg-component-path', newPath);
        else document.body.removeAttribute('data-cg-component-path');
      }

      if (push) history.pushState({ cg: true }, '', payload.url);
      _spaLastUrl = location.pathname + location.search;

      rebindAfterSwap(currentMain);
      bindContent();
      // Notify personal-list features (recents, pins) so they re-track
      // and re-render against the new pathname + body attribute.
      document.dispatchEvent(new CustomEvent('cg-content-swapped'));
      // Force instant scroll on page swap — html has scroll-behavior: smooth
      // for anchor links, but on a full page change the user expects to land
      // at the top immediately, not watch a 300ms scroll animation.
      window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
    })
    .catch((err) => {
      // Aborted by a newer click → ignore silently. Anything else → full reload fallback.
      if (err && err.name === 'AbortError') return;
      window.location.href = url;
    })
    .then(() => {
      if (_activeNavController === controller) _activeNavController = null;
      if (app) app.classList.remove('cg-loading');
    });
};

/* ── Card thumbnails (lazy via IntersectionObserver) ────────────────── */
// Each [data-cg-thumb] card on the index renders its component when scrolled
// into view. One fetch per card; cached server-side so subsequent visits are
// immediate. Falls back to the static tag-string if IO is unavailable.
//
// PERF: two layers of batching to keep this cheap on a 93-card index.
//
// 1) DOM insertion batching (rAF). Each fetch resolves in its own microtask,
//    so without batching every appendChild fires Tailwind's, HTMX's, and
//    Alpine's MutationObservers separately — N times for N thumbs. We queue
//    fetched fragments and flush them inside a single requestAnimationFrame
//    so all appendChild calls happen synchronously and the observers
//    coalesce them into a single callback.
//
// 2) Manual init batching (timeout). After the rAF flush, schedule a single
//    rebindAfterSwap on cg-main. Alpine.initTree / htmx.process are
//    idempotent so this is just a safety-net walk for anything the auto
//    observers missed.

const THUMB_BATCH_MS = 80;

let _thumbObserver = null;
let _thumbCleanupBound = false;
const _thumbInsertQueue = [];
let _thumbInsertFrame = null;
let _thumbBatchTimer = null;

/**
 * Lazy-load every `[data-cg-thumb]` card under `root`. Idempotent.
 *
 * @param {ThumbsOptions} options
 */
export const initCardThumbs = ({ rebindAfterSwap, root = document }) => {
  const cards = root.querySelectorAll('[data-cg-thumb]:not([data-cg-thumb-loaded])');
  if (!cards.length) return;

  if (!('IntersectionObserver' in window)) {
    // No IO support → show the static tag, skip live thumbs.
    cards.forEach((el) => { el.dataset.cgThumbLoaded = '1'; });
    return;
  }

  if (!_thumbObserver) {
    _thumbObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const el = entry.target;
        _thumbObserver.unobserve(el);
        loadThumb(el, rebindAfterSwap);
      });
    }, { rootMargin: THUMB_OBSERVER_ROOT_MARGIN, threshold: 0.01 });
  }

  // The IO retains strong refs to every card it observes. When the user
  // SPA-navs away from the index, those cards become detached but stay
  // pinned (they never intersect again to trigger unobserve). One global
  // listener disconnects the observer when the swapped main has no more
  // thumb cards — the next initCardThumbs call will create a fresh one.
  if (!_thumbCleanupBound) {
    document.addEventListener('cg-content-swapped', () => {
      if (!_thumbObserver) return;
      const main = document.querySelector('main.cg-main');
      if (!main || !main.querySelector('[data-cg-thumb]')) {
        _thumbObserver.disconnect();
        _thumbObserver = null;
      }
    });
    _thumbCleanupBound = true;
  }

  cards.forEach((el) => _thumbObserver.observe(el));
};

const loadThumb = (el, rebindAfterSwap) => {
  const url = el.getAttribute('data-cg-thumb');
  if (!url) return;
  el.dataset.cgThumbLoaded = '1';

  fetch(url, { headers: { 'X-Requested-With': 'cg-thumb' }, credentials: 'same-origin' })
    .then((r) => (r.ok ? r.text() : Promise.reject(new Error('HTTP ' + r.status))))
    .then((html) => {
      if (!html.trim()) return;
      // Build the thumb subtree off-DOM — innerHTML on a detached element
      // does NOT trigger Tailwind/Alpine/HTMX MutationObservers. They only
      // fire when the holder is appended into the live DOM.
      const holder = document.createElement('div');
      holder.className = 'cg-card__thumb';
      holder.innerHTML = html;
      _thumbInsertQueue.push({ card: el, holder });
      scheduleThumbInsertFlush(rebindAfterSwap);
    })
    .catch(() => {
      // Render failed → leave the static tag visible, hide skeleton
      const skel = el.querySelector('.cg-card__skeleton');
      if (skel) skel.remove();
    });
};

const scheduleThumbInsertFlush = (rebindAfterSwap) => {
  if (_thumbInsertFrame !== null) return;
  _thumbInsertFrame = requestAnimationFrame(() => flushThumbInserts(rebindAfterSwap));
};

const flushThumbInserts = (rebindAfterSwap) => {
  _thumbInsertFrame = null;
  if (!_thumbInsertQueue.length) return;
  const batch = _thumbInsertQueue.splice(0);
  for (let i = 0; i < batch.length; i++) {
    const item = batch[i];
    const skel = item.card.querySelector('.cg-card__skeleton');
    const tag = item.card.querySelector('.cg-card__tag');
    if (skel) skel.remove();
    if (tag) tag.remove();
    item.card.appendChild(item.holder);
  }
  scheduleThumbBatchInit(rebindAfterSwap);
};

const scheduleThumbBatchInit = (rebindAfterSwap) => {
  if (_thumbBatchTimer) clearTimeout(_thumbBatchTimer);
  _thumbBatchTimer = setTimeout(() => {
    _thumbBatchTimer = null;
    const root = document.querySelector('main.cg-main') || document.body;
    rebindAfterSwap(root);
  }, THUMB_BATCH_MS);
};
