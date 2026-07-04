# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`@strict` annotation** — `{# @strict #}` declares a **closed prop set**: every prop the component accepts is documented with `@prop`. Shows a `@strict` badge on the detail page and adds a `strict` filter to the Ctrl+K quick switcher. Under `@strict` the linter tightens: an undocumented `<c-vars>` prop escalates from warning to **error** (`missing-annotation`), and a component that also spreads `{{ attrs }}` raises the new `strict-with-attrs` **error** (the "Extra attrs" editor is shown disabled and flagged) — the two contradict, since arbitrary attributes would keep the set open.
- **`@ignore-unused` annotation** — `{# @ignore-unused #}` excludes a component from the Insights **zombie** list (components referenced nowhere, surfaced only when `DJANGO_COTTON_GALLERY_SCAN_EXTERNAL_USERS` is on). For deliberately unreferenced components — a published library atom, a work-in-progress. Adds an `@ignore-unused` badge, an `ignore-unused` switcher filter, and a Dependencies-tab banner.
- **`DJANGO_COTTON_GALLERY_SIGNATURE_TTL`** setting — seconds to reuse the catalog signature snapshot before re-walking `cotton/` (**default `0.5`**; `0` disables, e.g. in tests).
- **Demo catalog** now showcases the new annotations — `atoms/status-dot`, `lint/strict-000`, `molecules/wip-panel`.

### Changed

- **Annotation builder** (`/django-cotton-gallery/builder/`) now composes a component's **whole annotation block** — `@description`, the `@strict` / `@ignore-unused` flags, every `@prop`, `@slot` (0..n) and `@trigger` — not just the `@prop` lines. The output round-trips through the parser.
- **Catalog signature walk** now uses `os.scandir` (not `Path.rglob`) plus a TTL memo — roughly one walk per request instead of 3–4, fewer syscalls, faster warm renders (noticeably so on Docker bind-mounts).
- **Debug Toolbar coexistence** — template contexts get a source-free `ComponentSummary` projection and the sidebar tree is pre-rendered and cached, so the toolbar no longer snapshots `Component.source` per render and OOM-kills the dev server while browsing.

## [0.1.0] - 2026-07-01

Initial public release.

### Added

- **Annotation system**: `@prop` (with `text`, `number`, `boolean`, `select` types), `@slot`, `@slot:name`, `@trigger`, and `@description` annotations.
- **Component catalog** with consumer-driven category/subcategory ordering. Supports flexible folder layouts: components without a category folder, and `<dir>/index.html` as the entry point for `<dir>`.
- **Live preview** with auto-generated controls per declared prop, default-prop thumbnail rendering, and mtime-based caching.
- **Pass-through HTML attribute sanitizer** — XSS, event-handler, and tag-boundary protection. Property-tested with `hypothesis` (6 invariants × 500 random inputs each).
- **Frontend dependency detection** from CDN asset URLs (Tailwind, HTMX, Alpine, etc.).
- **ETag + `Cache-Control`** headers on thumbnail responses.
- **Lint engine** (`cotton_lint` management command + `/lint/` page): cross-checks `@prop` comments against `<c-vars>` declarations. Three severities — `error` / `warning` / `hint` — with hints as first-class citizens (filterable, paginated, externalized JS strings for i18n).
- **Insights page** (`/insights/`): Cotton configuration health card with live `COTTON_DIR` + scanning path + `COTTON_SNAKE_CASED_NAMES` detection. 3-state visual feedback (good/warn/bad).
- **Internationalization**: full `es` / `eu` / `fr` translations (466 entries per locale). `get-started.html` fully internationalized via `{% trans %}` / `{% blocktranslate %}`. JS i18n bridge via `window.cgI18n` for switcher headers, intellisense empty states, and lint UI.
- **Setup guide** (`setup_guide.html`): standalone first-run page with locale dropdown — surfaces blocking misconfigurations before the catalog flow runs.
- **Consumer asset injection** via `DJANGO_COTTON_GALLERY_EXTRA_CSS` and `DJANGO_COTTON_GALLERY_EXTRA_JS` settings. Optional `_extra_head.html` / `_extra_body.html` partials via `maybe_include` template tag.
- **Settings + URL contract** (1.0-stable): all settings prefixed `DJANGO_COTTON_GALLERY_*`. URL prefix is `/django-cotton-gallery/` (consumers mount with `path("", include(...))`).
- **Compatibility**: Python 3.10–3.13, Django 4.2 LTS through 6.0.

### Fixed

- **Memory leaks (3 SPA-swap leaks closed)**: `popover.js` (`destroy()` removes `document.click` / `window.scroll` / `window.resize`); `ui-bits.js` tabs (`ResizeObserver.disconnect()` + `window.resize` removal); `preview.js` matrix (`IntersectionObserver` stashed on `container.__cgMatrixObserver`, disconnected before recreate, plus `AbortController` for in-flight cell fetches). All driven by the gallery-wide `cg-content-swapped` event.
- **Backend redundancy**: `_cached_lint_summary` keyed by `signature(catalog.config)` `(count, max_mtime)`; `scan_external_users` cache keyed by `(catalog_paths, scan_roots, exclude_root, fingerprint)` with stat-only walk. ~50 % wall-time reduction on warm detail loads.
- **Chrome reset cascade**: 4-commit chain stabilizing the preflight slice the gallery depends on — extends to form controls/headings/lists, correct specificity model for `preflight reset & user-revert`, zero `<button>` background+border, inline preflight scoped to gallery roots so consumers without Tailwind aren't affected.
- **`get-started.html` `blocktranslate`** containing `{% verbatim %}{% include %}{% endverbatim %}` raised `TemplateSyntaxError: 'blocktranslate' doesn't allow other block tags` at runtime. Replaced nested tags with HTML entities (`&#123;% include %&#125;`).
- **Lint pagination bar** stayed hidden when severity filter narrowed results to fewer than the page size — now visible across all filter states.
- **Preview CSS isolation** + slot intellisense suggestions correctness.
- **Constants in user-visible text** always show full names (`COTTON_*` / `DJANGO_*`) — abbreviations led to copy-paste mistakes.
- **Dark-mode code blocks**: documentation code blocks that matched the page background in dark mode now sit on a translucent film with a hairline border.

### Removed

- **`axe-core` integration**: out of scope for the gallery. Component authors run their own accessibility tooling — the gallery only renders. Removed button, results panel, JS, CSS, lazy-loader, and related strings from `detail.html`, `gallery.js`, `gallery.css`, `_helpers.js`.
- **Bundled Tailwind**: the gallery is now stack-agnostic. Consumers bring their own Tailwind (or none) — the gallery only ships its preflight slice and design tokens.

### Refactored

- **JS monolith eliminated**: `gallery.js` (2308 lines) and `gallery/{_helpers,_popover}.js` deleted. Replaced by 9 modules under `js/`: `main.js` (entry), `constants.js`, `helpers.js`, `popover.js`, `sidebar.js`, `ui-bits.js`, `navigation.js`, `preview.js`, `slot-editor.js`, plus `power-tools.js` for the Ctrl/Cmd+K quick switcher and `editor-modal.js` / `compare.js` for the comparison flow. All arrow functions, all `const`/`let`. DI via callbacks (`rebindAfterSwap`, `bindContent`). Every `init*` returns a teardown. JSDoc on public APIs.
- **CSS monolith eliminated**: `gallery.css` (3106 lines) deleted. Replaced by 7 files under `css/`: `main.css` (entry, `@import` cascade), `tokens.css` (design tokens + dark theme overrides), `base.css` (reset + layout + drawer), `sidebar.css`, `preview.css`, `index.css`, `docs.css`.
- **Templates**: `base.html` references `js/main.js` and `css/main.css`.
- **Repository layout**: the demo project and test suite live under `src/` (`src/demo/`, `src/tests/`) alongside the package; pure-domain logic is grouped under `src/django_cotton_gallery/core/` (`catalog/`, `preview/`, `linter/`). The published wheel ships only `src/django_cotton_gallery/`.

### Tests

- **Architecture test** (`src/tests/test_architecture.py`): AST walker that asserts every pure-domain module never imports Django. 14 invariants — adding a Django import to `schemas.py` (or any other listed pure module) fails the build.
- **HTML view integration tests** (`src/tests/integration/test_views_html.py`): 20 tests covering `index`, `get_started`, `docs`, `component_detail`, `component_raw` — status, content, i18n, 404 paths, traversal blocks.
- **Property-based sanitizer tests** (`src/tests/core/preview/test_sanitizer_fuzz.py`): 6 invariants × 500 random inputs each via `hypothesis`.
- **E2E tests** (`pytest-playwright`) covering SPA navigation, search, live preview update, theme toggle. Viewport 1600×1000 for popover positioning headroom.
- **Coverage**: pytest-cov configured with branch coverage. Baseline **91.9 %**. CI uploads to Codecov on every push.
- **Suite runs in ~35 s** on CI (e2e included). 426 tests, all passing.

### Documentation

- **Contributor docs** under `docs/contributors/`: `index.md`, `development.md`, `testing.md`, `architecture.md`, `i18n.md`, `release.md`. README rewritten as an orchestrator linking to all of them.
- **`docs/users/getting-started.md`** new section covering 4 access-restriction patterns (DEBUG-only, feature flag, staff-only, split URL configs) — security guidance for production deployments.
- **Folder layout flexibility** explained: components without a category folder, `<dir>/index.html` as the entry, and how naming maps to URL/tag.
- **Full audit + reorganization + screenshot regeneration** of public docs.

[0.1.0]: https://github.com/velezanthony/django-cotton-gallery/releases/tag/v0.1.0
