/*!
 * Cotton Gallery — preview surface.
 *
 * The mechanism every place that shows a component repeats: fetch, drop what a
 * newer request supersedes, paint into an isolated stage, tear down.
 *
 * No policy. When to load, what to do afterwards, whether the host gets a
 * resize grip or gets recycled — that is the page's, and lives in its file.
 */

import { createIsolatedStage } from './isolated-stage.js';

/**
 * How the endpoint answers: detail, compare and matrix return `{html, tag}`;
 * thumbnails return the fragment.
 *
 * @enum {string}
 */
export const ResponseShape = Object.freeze({
  JSON: 'json',
  HTML: 'html',
});

/** One surface per host — the registry each caller used to keep itself. */
const surfaces = new WeakMap();

/**
 * @typedef {Object} SurfaceOptions
 * @property {boolean} [autoHeight]  Size the frame to its content. False where
 *                                   the host already has a height of its own.
 * @property {string}  [response]    A `ResponseShape`.
 */

/**
 * @typedef {Object} PreviewSurface
 * @property {(url: string) => Promise<Object|null>} load  Fetch and paint. Resolves
 *           with the parsed payload, or null if superseded or the host is gone.
 * @property {(html: string) => void} render   Paint markup already in hand.
 * @property {(html: string) => void} fail     Paint chrome — an error — in OUR document.
 * @property {() => void} destroy
 * @property {HTMLElement} host
 */

/**
 * @param {HTMLElement} host
 * @param {SurfaceOptions} [options]
 * @returns {PreviewSurface}
 */
export const createPreviewSurface = (host, { autoHeight = true, response = ResponseShape.JSON } = {}) => {
  let stage = null;
  let inFlight = null;
  let destroyed = false;

  const stageOrNew = () => stage || (stage = createIsolatedStage(host, { autoHeight }));

  const dropStage = () => {
    if (!stage) return;
    stage.destroy();
    stage = null;
  };

  const surface = {
    host,

    async load(url) {
      if (destroyed) return null;
      // A slower answer landing after a faster one would paint stale markup.
      if (inFlight) inFlight.abort();
      const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
      inFlight = controller;

      // No `host.isConnected` guard: a thumbnail host is built off-DOM on
      // purpose. A host that goes away is torn down through `destroy`, which
      // aborts — and that is the difference `isConnected` cannot tell.
      try {
        const res = await fetch(url, {
          headers: { 'X-Requested-With': 'cg-preview', Accept: 'application/json, text/html' },
          credentials: 'same-origin',
          signal: controller ? controller.signal : undefined,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const payload = response === ResponseShape.JSON ? await res.json() : { html: await res.text() };
        if (destroyed) return null;
        surface.render(payload.html || '');
        return payload;
      } finally {
        if (inFlight === controller) inFlight = null;
      }
    },

    render(html) {
      if (destroyed) return;
      stageOrNew().update(html);
    },

    fail(html) {
      if (destroyed) return;
      // Gallery chrome, not component output — it belongs in our document.
      dropStage();
      host.innerHTML = html;
    },

    destroy() {
      destroyed = true;
      if (inFlight) inFlight.abort();
      inFlight = null;
      dropStage();
      surfaces.delete(host);
    },
  };

  surfaces.set(host, surface);
  return surface;
};

/**
 * The surface for `host`, created on first ask.
 *
 * @param {HTMLElement} host
 * @param {SurfaceOptions} [options]
 * @returns {PreviewSurface}
 */
export const surfaceFor = (host, options) => surfaces.get(host) || createPreviewSurface(host, options);

/**
 * Tear down `host`'s surface. A host without one is a no-op.
 *
 * @param {HTMLElement} host
 */
export const releaseSurface = (host) => {
  const surface = surfaces.get(host);
  if (surface) surface.destroy();
};
