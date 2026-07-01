/*!
 * _debug_dropdowns.js — opt-in dropdown timeline recorder.
 *
 * Loaded by base.html when the URL has `?cgdebug=1`. Captures clicks,
 * pointer events, [hidden] toggles on dropdown menus, and SPA swaps.
 *
 * Exposed as `window.__d` with `dump()` to print the timeline.
 *
 * Disable by removing `?cgdebug=1` from the URL.
 */
(function () {
  'use strict';

  var t0 = performance.now();
  var events = [];

  function log(kind, info) {
    events.push({
      ms: Math.round(performance.now() - t0),
      kind: kind,
      info: info || {}
    });
  }

  // What chrome elements are dropdown triggers? We tag each click with
  // whether it landed on (or inside) one of these.
  var TRIGGER_SEL = [
    '[data-cg-mini-trigger]',
    '[data-cg-combo-trigger]',
    '.cg-combo__trigger',
    '.cg-sidebar__tools-trigger',
    '.cg-sidebar__lang-trigger',
    '[data-cg-tools-trigger]',
    '[data-cg-lang-trigger]',
    '[aria-haspopup]'
  ].join(', ');

  // 1) Pointer + click events at document level, capture phase. We log
  //    pointerdown, mousedown, click, pointerup separately so a flicker
  //    that's actually multiple events firing on the SAME human gesture
  //    becomes visible in the timeline.
  ['pointerdown', 'mousedown', 'click', 'pointerup'].forEach(function (type) {
    document.addEventListener(type, function (e) {
      var t = e.target;
      var trigger = t.closest && t.closest(TRIGGER_SEL);
      log(type, {
        tag: t.tagName,
        cls: String(t.className || '').slice(0, 60),
        text: String(t.textContent || '').trim().slice(0, 30),
        on_trigger: !!trigger,
        trigger_cls: trigger ? String(trigger.className || '').slice(0, 60) : null
      });
    }, true);
  });

  // 2) SPA navigation events.
  document.addEventListener('cg-content-swapped', function () {
    log('spa-swap', { url: location.pathname });
  });

  // 3) Watch every dropdown menu for [hidden] attribute toggles.
  function watchMenu(el) {
    var observer = new MutationObserver(function (muts) {
      muts.forEach(function (m) {
        if (m.attributeName === 'hidden') {
          log('hidden-change', {
            cls: String(el.className || '').slice(0, 50),
            now_hidden: el.hasAttribute('hidden')
          });
        }
      });
    });
    observer.observe(el, { attributes: true, attributeFilter: ['hidden'] });
  }

  var menuSelector = [
    '[data-cg-mini-menu]',
    '[data-cg-combo-panel]',
    '.cg-combo__menu',
    '.cg-combo__panel',
    '.cg-sidebar__lang-menu',
    '.cg-sidebar__tools-menu',
    '[data-cg-tools-menu]',
    '[data-cg-lang-menu]',
    '[role="menu"]'
  ].join(', ');
  document.querySelectorAll(menuSelector).forEach(watchMenu);

  // 4) Watch for menus added later (after SPA swap or dynamic insertion).
  new MutationObserver(function (muts) {
    muts.forEach(function (m) {
      m.addedNodes.forEach(function (n) {
        if (n.nodeType !== 1) return;
        if (n.matches && n.matches(menuSelector)) watchMenu(n);
        if (n.querySelectorAll) {
          n.querySelectorAll(menuSelector).forEach(watchMenu);
        }
      });
    });
  }).observe(document.body, { childList: true, subtree: true });

  // 5) Public API.
  window.__d = {
    events: events,
    dump: function () {
      console.log('=== Cotton Gallery dropdown timeline ===');
      console.table(events);
      console.log('Total events: ' + events.length);
      return events;
    },
    clear: function () { events.length = 0; },
    summary: function () {
      // Quick "is this a flicker?" report. Walks the timeline and pairs
      // each user-click against the hidden-changes that followed within
      // 200ms, flagging any pair where the menu opened then closed in
      // quick succession.
      var flickers = [];
      events.forEach(function (e, i) {
        if (e.kind !== 'click' || !e.info.on_trigger) return;
        var window200 = events.slice(i + 1).filter(function (n) { return n.ms - e.ms <= 200; });
        var changes = window200.filter(function (n) { return n.kind === 'hidden-change'; });
        if (changes.length >= 2) {
          flickers.push({
            click_at_ms: e.ms,
            trigger: e.info.trigger_cls,
            hidden_changes: changes.map(function (c) {
              return { ms: c.ms, hidden: c.info.now_hidden, menu: c.info.cls };
            })
          });
        }
      });
      console.log('Flicker candidates (click followed by 2+ hidden-changes within 200ms):');
      console.table(flickers);
      return flickers;
    }
  };

  console.log('%c[cgdebug] dropdown recorder ON', 'color: #16a34a; font-weight: bold');
  console.log('  Run __d.dump()    — full timeline');
  console.log('  Run __d.summary() — flicker candidates only');
})();
