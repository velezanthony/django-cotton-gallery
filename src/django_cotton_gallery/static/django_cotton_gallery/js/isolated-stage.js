/*!
 * Cotton Gallery — isolated preview stage.
 *
 * Renders a user component in its own document. Rationale in
 * docs/contributors/architecture.md ("Preview: the component gets its own
 * document"). Same-origin via `srcdoc`, so the parent reads `contentDocument`
 * directly — no postMessage.
 */

/** @typedef {{ head: string, body: string }} ShellParts */

/**
 * The consumer's stack, as base.html emitted it into two inert `<template>`s.
 * Markup and not a URL list: a stack declared inline in `_extra_head.html` has
 * no URLs to rebuild from. Read once — it cannot change without a page load.
 *
 * @returns {ShellParts}
 */
let _shell = null;
const readShellParts = () => {
  if (_shell) return _shell;
  const head = document.getElementById('cg-frame-head');
  const body = document.getElementById('cg-frame-body');
  _shell = {
    head: head ? head.innerHTML : '',
    body: body ? body.innerHTML : '',
  };
  return _shell;
};

/**
 * The shell document — mirrors raw.html. Transparent body so the stage's
 * backdrop shows through.
 *
 * @param {ShellParts} parts
 * @returns {string}
 */
const buildShell = ({ head, body }) => (
  '<!DOCTYPE html><html><head><meta charset="utf-8">' +
  '<meta name="viewport" content="width=device-width, initial-scale=1.0">' +
  head +
  '<style>html,body{margin:0;background:transparent}[x-cloak]{display:none!important}</style>' +
  '</head><body><div data-cg-stage-root></div>' +
  body +
  '</body></html>'
);

/**
 * Alpine teardown against the frame's own Alpine — the consumer's copy lives
 * in there, not in the gallery window.
 *
 * @param {HTMLElement} root
 * @param {Window} win
 */
const teardownInFrame = (root, win) => {
  const Alpine = win && win.Alpine;
  if (!Alpine || typeof Alpine.destroyTree !== 'function') return;
  try {
    const nodes = root.querySelectorAll('[x-data]');
    for (let i = 0; i < nodes.length; i++) {
      if (nodes[i]._x_dataStack) {
        try { Alpine.destroyTree(nodes[i]); } catch (_) { /* ignore */ }
      }
    }
  } catch (_) { /* ignore */ }
};

/**
 * Alpine + HTMX rehydration inside the frame. No gallery behaviors (tabs,
 * copy): those are chrome, not component.
 *
 * @param {HTMLElement} root
 * @param {Window} win
 */
const rebindInFrame = (root, win) => {
  if (!win) return;
  if (win.Alpine && typeof win.Alpine.initTree === 'function') {
    try { win.Alpine.initTree(root); } catch (_) { /* ignore */ }
  }
  if (win.htmx && typeof win.htmx.process === 'function') {
    try { win.htmx.process(root); } catch (_) { /* ignore */ }
  }
};

/**
 * @typedef {Object} IsolatedStage
 * @property {Promise<void>} ready    Resolves once the frame document is usable.
 * @property {(html: string) => Promise<void>} update  Render markup into the frame.
 * @property {() => void} destroy     Tear down observers and remove the frame.
 * @property {HTMLIFrameElement} frame
 */

/**
 * Mount an isolated stage inside `host`, replacing whatever it holds.
 *
 * Loads ONCE; `update()` swaps the body. A fresh `src` per keystroke would
 * reload the document and restart Alpine on every character typed.
 *
 * @param {HTMLElement} host  Usually `[data-cg-preview-stage]`, a matrix cell
 *                            or a `[data-cg-thumb]` card.
 * @param {{ onHeight?: (px: number) => void, autoHeight?: boolean }} [options]
 *        `autoHeight` (default true) sizes the frame to its content. Pass
 *        false where the host already constrains height (thumbnails).
 * @returns {IsolatedStage}
 */
export const createIsolatedStage = (host, { onHeight, autoHeight = true } = {}) => {
  const frame = document.createElement('iframe');
  frame.className = 'cg-stage-frame';
  frame.setAttribute('title', 'Component preview');
  frame.setAttribute('scrolling', 'no');
  frame.srcdoc = buildShell(readShellParts());

  host.innerHTML = '';
  host.appendChild(frame);

  let observer = null;
  let destroyed = false;
  // The markup currently on screen. Moving an iframe in the DOM reloads its
  // document — the fullscreen modal does exactly that — and everything written
  // in after load is gone. Keeping it lets the frame repaint itself without a
  // round trip; `update()` replaces it, so it never goes stale.
  let currentHtml = '';

  const measure = () => {
    if (destroyed || !frame.contentDocument) return;
    const px = frame.contentDocument.documentElement.scrollHeight;
    if (autoHeight) frame.style.height = px + 'px';
    if (onHeight) onHeight(px);
  };

  /** Paint `currentHtml` into a freshly loaded document. */
  const paint = () => {
    const doc = frame.contentDocument;
    const root = doc && doc.querySelector('[data-cg-stage-root]');
    if (!root) return;
    teardownInFrame(root, frame.contentWindow);
    root.innerHTML = currentHtml;
    rebindInFrame(root, frame.contentWindow);
    measure();
  };

  let markReady;
  const ready = new Promise((resolve) => { markReady = resolve; });

  // Permanent, not `{ once: true }`: this fires again on every reload, which is
  // what reparenting causes. The observer watched the previous document, so it
  // gets rebound too.
  frame.addEventListener('load', () => {
    if (destroyed) return markReady();
    const win = frame.contentWindow;
    if (observer) { try { observer.disconnect(); } catch (_) { /* ignore */ } }
    // Content grows after render (x-cloak reveal, HTMX swap, webfont).
    if (win && typeof win.ResizeObserver === 'function') {
      observer = new win.ResizeObserver(measure);
      observer.observe(frame.contentDocument.documentElement);
    }
    if (currentHtml) paint();
    markReady();
  });

  return {
    ready,
    frame,
    async update(html) {
      await ready;
      if (destroyed) return;
      currentHtml = html || '';
      paint();
    },
    destroy() {
      destroyed = true;
      if (observer) { try { observer.disconnect(); } catch (_) { /* ignore */ } }
      observer = null;
      if (frame.parentNode) frame.parentNode.removeChild(frame);
    },
  };
};
