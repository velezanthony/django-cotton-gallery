/*!
 * _debug_dropdowns.js — dropdown timeline recorder, on with `?cgdebug=1`.
 *
 * Finds flickers: a click on a trigger answered by two menu toggles inside
 * 200ms is a handler fighting itself. Pointer phases are logged separately
 * because one gesture fires four of them.
 *
 * A classic script, not a module — hence the closure and the trailing global.
 */
const dropdownRecorder = (() => {
  'use strict';

  /* ── Private ──────────────────────────────────────────────────────── */

  /**
   * @typedef {Object} TimelineEvent
   * @property {number} ms    Milliseconds since the recorder started.
   * @property {string} kind  One of `EventKind`.
   * @property {Object} info  Kind-specific detail.
   */

  /** @enum {string} */
  const EventKind = Object.freeze({
    POINTER_DOWN: 'pointerdown',
    MOUSE_DOWN: 'mousedown',
    CLICK: 'click',
    POINTER_UP: 'pointerup',
    SPA_SWAP: 'spa-swap',
    HIDDEN_CHANGE: 'hidden-change',
  });

  /** Logged separately: one human gesture fires several of these. */
  const POINTER_KINDS = Object.freeze([
    EventKind.POINTER_DOWN,
    EventKind.MOUSE_DOWN,
    EventKind.CLICK,
    EventKind.POINTER_UP,
  ]);

  /** A click is tagged with whether it landed on one of these. */
  const TRIGGER_SELECTOR = [
    '[data-cg-mini-trigger]',
    '[data-cg-combo-trigger]',
    '.cg-combo__trigger',
    '.cg-sidebar__tools-trigger',
    '.cg-sidebar__lang-trigger',
    '[data-cg-tools-trigger]',
    '[data-cg-lang-trigger]',
    '[aria-haspopup]',
  ].join(', ');

  const MENU_SELECTOR = [
    '[data-cg-mini-menu]',
    '[data-cg-combo-panel]',
    '.cg-combo__menu',
    '.cg-combo__panel',
    '.cg-sidebar__lang-menu',
    '.cg-sidebar__tools-menu',
    '[data-cg-tools-menu]',
    '[data-cg-lang-menu]',
    '[role="menu"]',
  ].join(', ');

  /** A click and the menu toggles that answer it within this window. */
  const FLICKER_WINDOW_MS = 200;
  const FLICKER_MIN_CHANGES = 2;

  const startedAt = performance.now();

  /** @type {TimelineEvent[]} */
  const events = [];

  /** @param {string} kind @param {Object} [info] */
  const log = (kind, info) => {
    events.push({ ms: Math.round(performance.now() - startedAt), kind, info: info || {} });
  };

  /** @param {unknown} value @param {number} max @returns {string} */
  const truncate = (value, max) => String(value || '').slice(0, max);

  /** @param {Element} menu */
  const watchMenu = (menu) => {
    new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.attributeName !== 'hidden') return;
        log(EventKind.HIDDEN_CHANGE, {
          cls: truncate(menu.className, 50),
          now_hidden: menu.hasAttribute('hidden'),
        });
      });
    }).observe(menu, { attributes: true, attributeFilter: ['hidden'] });
  };

  /** Toggles close enough after `click` to be its answer. @returns {TimelineEvent[]} */
  const answersTo = (click, index) =>
    events
      .slice(index + 1)
      .filter((next) => next.ms - click.ms <= FLICKER_WINDOW_MS)
      .filter((next) => next.kind === EventKind.HIDDEN_CHANGE);

  /** @returns {Object[]} Clicks answered by enough toggles to read as a flicker. */
  const flickers = () =>
    events.flatMap((event, index) => {
      if (event.kind !== EventKind.CLICK || !event.info.on_trigger) return [];
      const changes = answersTo(event, index);
      if (changes.length < FLICKER_MIN_CHANGES) return [];
      return [{
        click_at_ms: event.ms,
        trigger: event.info.trigger_cls,
        hidden_changes: changes.map((change) => ({
          ms: change.ms,
          hidden: change.info.now_hidden,
          menu: change.info.cls,
        })),
      }];
    });

  const recordPointerEvents = () => {
    POINTER_KINDS.forEach((kind) => {
      document.addEventListener(kind, (event) => {
        const target = event.target;
        const trigger = target.closest && target.closest(TRIGGER_SELECTOR);
        log(kind, {
          tag: target.tagName,
          cls: truncate(target.className, 60),
          text: truncate(target.textContent, 30).trim(),
          on_trigger: !!trigger,
          trigger_cls: trigger ? truncate(trigger.className, 60) : null,
        });
      }, true);
    });
  };

  const recordNavigation = () => {
    document.addEventListener('cg-content-swapped', () => {
      log(EventKind.SPA_SWAP, { url: location.pathname });
    });
  };

  /** Menus present now, plus any inserted later. */
  const recordMenus = () => {
    document.querySelectorAll(MENU_SELECTOR).forEach(watchMenu);
    new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType !== Node.ELEMENT_NODE) return;
          if (node.matches && node.matches(MENU_SELECTOR)) watchMenu(node);
          if (node.querySelectorAll) node.querySelectorAll(MENU_SELECTOR).forEach(watchMenu);
        });
      });
    }).observe(document.body, { childList: true, subtree: true });
  };

  const announce = () => {
    console.log('%c[cgdebug] dropdown recorder ON', 'color: #16a34a; font-weight: bold');
    console.log('  Run __d.dump()    — full timeline');
    console.log('  Run __d.summary() — flicker candidates only');
  };

  /** @returns {TimelineEvent[]} */
  const dump = () => {
    console.log('=== Cotton Gallery dropdown timeline ===');
    console.table(events);
    console.log(`Total events: ${events.length}`);
    return events;
  };

  const clear = () => { events.length = 0; };

  /** @returns {Object[]} */
  const summary = () => {
    const found = flickers();
    console.log('Flicker candidates (click followed by 2+ hidden-changes within 200ms):');
    console.table(found);
    return found;
  };

  /* ── Start ────────────────────────────────────────────────────────── */

  recordPointerEvents();
  recordNavigation();
  recordMenus();
  announce();

  /* ── Public ───────────────────────────────────────────────────────── */

  return { events, dump, clear, summary };
})();

window.__d = dropdownRecorder;
