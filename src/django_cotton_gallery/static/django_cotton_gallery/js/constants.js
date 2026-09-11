/*!
 * Named constants used across modules. No magic numbers in feature files.
 *
 * Anything that's a millisecond value, a pixel offset, or a localStorage
 * key lives here. Touch one to change behaviour app-wide.
 */

/* ── Timing (milliseconds) ──────────────────────────────────────────── */

export const PREVIEW_DEBOUNCE_MS = 300;
export const SYNTAX_HIGHLIGHT_DEBOUNCE_MS = 50;
export const BLUR_HIDE_DELAY_MS = 120;
export const SIDEBAR_SCROLL_DEBOUNCE_MS = 120;
export const COPY_FLASH_MS = 1500;            // copy-to-clipboard "copied!" flash
export const TOOLTIP_BUBBLE_FALLBACK_HEIGHT_PX = 120;  // assumed bubble height before paint

/* ── Geometry (pixels / px-strings) ─────────────────────────────────── */

export const POPOVER_FLIP_THRESHOLD_PX = 240;
export const POPOVER_OFFSET_PX = 4;
export const TOOLTIP_OFFSET_PX = 6;
export const SIDEBAR_DESKTOP_BREAKPOINT_PX = 1024;
// rootMargin strings for IntersectionObservers — kept as strings since
// IO API expects them in CSS units, not raw numbers.
export const THUMB_OBSERVER_ROOT_MARGIN = '200px 0px';
// Hysteresis: wider than the load margin so one edge does not thrash frames.
export const THUMB_RECYCLE_ROOT_MARGIN = '1200px 0px';
export const MATRIX_CELL_ROOT_MARGIN = '100px 0px';

/* ── localStorage keys (single source of truth) ─────────────────────── */
// Standardised on dashes. Any key the gallery writes to localStorage
// MUST live here so a `grep` of this file is the storage schema.

export const STORAGE_THEME = 'cg-theme';
export const STORAGE_SIDEBAR_SCROLL = 'cg-sidebar-scroll';
export const STORAGE_COLLAPSED = 'cg-collapsed';
export const STORAGE_SIDEBAR_COLLAPSED = 'cg-sidebar-collapsed';
export const STORAGE_HIDE_LINT = 'cg-sidebar-hide-lint';
export const STORAGE_PERSONAL_FILTER = 'cg-sidebar-personal-filter';
export const STORAGE_PREVIEW_BG = 'cg-preview-bg';
export const STORAGE_PREVIEW_BG_COLORS = 'cg-preview-bg-colors';
export const STORAGE_PREVIEW_VIEWPORT = 'cg-preview-viewport';
export const STORAGE_LINT_PAGE_SIZE = 'cg-lint-page-size';
export const STORAGE_RECENTS = 'cg-recent-components';
export const STORAGE_PINS = 'cg-pinned-components';

/* The collapsed-state key is read from inline `<script>` in base.html
   BEFORE this module loads (FOUC prevention). Keep that string in sync
   with `STORAGE_SIDEBAR_COLLAPSED` above and `STORAGE_THEME` for theme. */
