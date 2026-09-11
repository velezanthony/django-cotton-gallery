/*!
 * Cotton Gallery — stage resize grip.
 *
 * `resize: vertical` only ever hands out the bottom-right corner, which is a
 * pixel hunt. This puts a full-width bar under the stage instead.
 *
 * Why a manual height at all: a component built for a screen — a modal, a
 * drawer, a toast layer — is anchored to the viewport and contributes nothing
 * to `scrollHeight`, so there is no content height to measure. Rather than
 * guess one, hand the user the edge. See js/isolated-stage.js for how the
 * dragged height then takes over from auto-sizing.
 */

import { bindOnce } from './helpers.js';

const MIN_HEIGHT = 120;

/**
 * Put a drag handle on the bottom edge of `host`.
 *
 * @param {HTMLElement} host  The stage, `[data-cg-preview-stage]`.
 */
export const attachResizeGrip = (host) => {
  if (!host || !bindOnce(host, 'grip')) return;

  const label = (window.cgI18n && window.cgI18n.dragPreviewHeight) || 'Drag to resize the preview';
  const grip = document.createElement('div');
  grip.className = 'cg-stage-grip';
  grip.setAttribute('data-cg-stage-grip', '');
  grip.setAttribute('role', 'separator');
  grip.setAttribute('aria-orientation', 'horizontal');
  grip.setAttribute('aria-label', label);
  grip.setAttribute('tabindex', '0');
  grip.title = label;
  host.after(grip);

  const resizeTo = (px) => { host.style.height = Math.max(MIN_HEIGHT, Math.round(px)) + 'px'; };

  grip.addEventListener('pointerdown', (event) => {
    // Stop the browser from starting a text selection across the drag.
    event.preventDefault();
    const startY = event.clientY;
    const startHeight = host.getBoundingClientRect().height;

    const onMove = (moveEvent) => resizeTo(startHeight + moveEvent.clientY - startY);
    const onUp = () => {
      grip.releasePointerCapture(event.pointerId);
      grip.removeEventListener('pointermove', onMove);
    };

    grip.setPointerCapture(event.pointerId);
    grip.addEventListener('pointermove', onMove);
    grip.addEventListener('pointerup', onUp, { once: true });
    grip.addEventListener('pointercancel', onUp, { once: true });
  });

  // `role="separator"` promises arrow keys work — so they do.
  grip.addEventListener('keydown', (event) => {
    const step = event.shiftKey ? 100 : 20;
    if (event.key === 'ArrowDown') resizeTo(host.getBoundingClientRect().height + step);
    else if (event.key === 'ArrowUp') resizeTo(host.getBoundingClientRect().height - step);
    else return;
    event.preventDefault();
  });
};
