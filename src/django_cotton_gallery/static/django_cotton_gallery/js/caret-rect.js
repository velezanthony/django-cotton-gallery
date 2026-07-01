/*!
 * Caret position helpers — return a viewport-coords rect that marks where
 * the caret currently sits inside a textarea or contenteditable. Used to
 * anchor autocomplete popovers to the caret instead of the input element
 * (which can be huge inside the maximize modal).
 *
 * For contenteditable: the browser's Selection API gives us a rect directly.
 * For textarea: there's no native API. We build a mirror div with identical
 * box-model + text-flow CSS, copy the value up to the caret, drop a marker
 * span at the end, and read the span's rect. Standard technique used by
 * editors like Slate, Lexical, and intelliscroll libraries.
 */

/**
 * Return a viewport-coords DOMRect-like for the caret inside a contenteditable.
 * Returns null if there's no selection inside `el`.
 *
 * @param {HTMLElement} el — the contenteditable element
 * @returns {{top:number, bottom:number, left:number, right:number, width:number, height:number} | null}
 */
export const caretRectFromContenteditable = (el) => {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0) return null;
  const range = sel.getRangeAt(0);
  if (!el.contains(range.endContainer)) return null;

  let rect = range.getBoundingClientRect();
  // Collapsed range at the start of an empty node returns a zero rect on
  // some browsers — work around by inserting a zero-width space marker.
  if (rect.width === 0 && rect.height === 0) {
    const marker = document.createElement('span');
    marker.textContent = '​';
    range.insertNode(marker);
    rect = marker.getBoundingClientRect();
    marker.remove();
    // Restore caret to where it was — `insertNode` left it after the marker.
    sel.removeAllRanges();
    sel.addRange(range);
  }
  return rect;
};

/* CSS properties that affect text layout — we copy ALL of these from the
   textarea to the mirror div so each character lands in the same x/y. */
const MIRROR_PROPS = [
  'boxSizing', 'width',
  'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft',
  'borderTopWidth', 'borderRightWidth', 'borderBottomWidth', 'borderLeftWidth',
  'borderTopStyle', 'borderRightStyle', 'borderBottomStyle', 'borderLeftStyle',
  'fontFamily', 'fontSize', 'fontWeight', 'fontStyle', 'fontVariant',
  'lineHeight', 'letterSpacing', 'wordSpacing', 'textTransform',
  'whiteSpace', 'wordWrap', 'tabSize',
];

/**
 * Return a viewport-coords rect for the caret inside a textarea.
 * Returns null if the textarea has no value or selection.
 *
 * @param {HTMLTextAreaElement} ta
 */
export const caretRectFromTextarea = (ta) => {
  if (!ta || typeof ta.selectionStart !== 'number') return null;
  const caret = ta.selectionStart;
  const computed = window.getComputedStyle(ta);

  const mirror = document.createElement('div');
  for (const p of MIRROR_PROPS) mirror.style[p] = computed[p];
  mirror.style.position = 'absolute';
  mirror.style.visibility = 'hidden';
  mirror.style.overflow = 'hidden';
  mirror.style.top = '0';
  mirror.style.left = '-9999px';
  mirror.style.whiteSpace = computed.whiteSpace || 'pre-wrap';

  const before = ta.value.substring(0, caret);
  // Newlines + trailing space need to keep their height in the mirror —
  // text nodes alone don't honour a final '\n' for layout purposes.
  mirror.textContent = before;
  const marker = document.createElement('span');
  marker.textContent = '​';
  mirror.appendChild(marker);

  document.body.appendChild(mirror);
  const taRect = ta.getBoundingClientRect();
  const mirrorRect = mirror.getBoundingClientRect();
  const markerRect = marker.getBoundingClientRect();

  // Translate the marker's offset inside the mirror to viewport coords on
  // top of the textarea, accounting for the textarea's scroll position.
  const x = taRect.left + (markerRect.left - mirrorRect.left) - ta.scrollLeft;
  const y = taRect.top + (markerRect.top - mirrorRect.top) - ta.scrollTop;
  const h = markerRect.height || parseFloat(computed.lineHeight) || 16;

  document.body.removeChild(mirror);

  return {
    top: y,
    bottom: y + h,
    left: x,
    right: x + 1,
    width: 1,
    height: h,
  };
};
