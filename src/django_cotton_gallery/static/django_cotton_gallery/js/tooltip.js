/*!
 * Tooltip positioning for `.cg-info` bubbles.
 *
 * Why JS instead of pure CSS?
 *   `.cg-controls__form` has `overflow-y: auto`, which (per spec) pins
 *   `overflow-x` to non-`visible` too — meaning ANY `position: absolute`
 *   descendant gets clipped at the panel edges. The bubble used to sit
 *   right next to the icon as `position: absolute`; on hover the right
 *   half disappeared off the panel.
 *
 * Fix: put the bubble at `position: fixed` and compute its top/right at
 * hover time from the icon's bounding rect. Fixed elements escape any
 * overflow-hidden ancestor and pin to the viewport.
 *
 * Visibility is still pure CSS (`.cg-info__bubble--shown` class), so
 * fade-in transitions stay declarative.
 */

import { bindOnce } from './helpers.js';
import { TOOLTIP_OFFSET_PX as OFFSET_PX, TOOLTIP_BUBBLE_FALLBACK_HEIGHT_PX } from './constants.js';

const SHOWN = 'cg-info__bubble--shown';

const repositionBubble = (icon, bubble) => {
  const rect = icon.getBoundingClientRect();
  // Anchor to the icon's bottom-right by default; flip up if there's not
  // enough room below the icon for the bubble height.
  const bubbleH = bubble.offsetHeight || TOOLTIP_BUBBLE_FALLBACK_HEIGHT_PX;
  const spaceBelow = window.innerHeight - rect.bottom;
  if (spaceBelow >= bubbleH + OFFSET_PX + 16) {
    bubble.style.top = (rect.bottom + OFFSET_PX) + 'px';
    bubble.style.bottom = '';
  } else {
    bubble.style.top = '';
    bubble.style.bottom = (window.innerHeight - rect.top + OFFSET_PX) + 'px';
  }
  // Right-align the bubble's right edge to the icon's right edge.
  bubble.style.right = Math.max(8, window.innerWidth - rect.right) + 'px';
  bubble.style.left = '';
};

export const initTooltips = (root = document) => {
  const infos = root.querySelectorAll('.cg-info');
  infos.forEach((icon) => {
    if (!bindOnce(icon, 'tooltip')) return;
    const bubble = icon.querySelector('.cg-info__bubble');
    if (!bubble) return;

    const show = () => {
      repositionBubble(icon, bubble);
      bubble.classList.add(SHOWN);
    };
    const hide = () => bubble.classList.remove(SHOWN);

    icon.addEventListener('mouseenter', show);
    icon.addEventListener('mouseleave', hide);
    icon.addEventListener('focus', show);
    icon.addEventListener('blur', hide);
  });
};
