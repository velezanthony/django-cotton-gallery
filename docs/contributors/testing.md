# Testing

Where tests live, how to run them, how the suite is structured, and how to add new ones.

## Quick reference

```bash
# Canonical — works from a clean shell (bare `pytest` is NOT on PATH):
uv run --extra test python -m pytest      # Full suite (e2e included)

# Shortcut — activate the venv once, then use plain `pytest`:
#   uv sync --extra dev && source .venv/bin/activate
pytest -v                                 # Verbose
pytest -k "sanitiz"                       # By name pattern
pytest --lf                               # Last failed only

# Selective runs by category
pytest src/tests/core/                    # Pure-domain unit tests, no Django
pytest src/tests/integration/             # Django integration tests
pytest src/tests/e2e/                     # Browser tests via Playwright (slowest)
pytest --ignore=src/tests/e2e             # Everything except browser

# Cross-version (run via uv so tox resolves)
uv run tox                                # Full Python × Django matrix (slow)
uv run tox -e py312-django52              # One specific combo
uv run tox -p auto                        # Run matrix in parallel
```

!!! note "First e2e run needs a browser"
    The e2e tier drives a real Chromium browser via Playwright. Install it once with
    `uv run --extra test python -m playwright install chromium` — CI runs the same
    step. Without it, the Playwright tests error with "Executable doesn't exist… run
    `playwright install`".

## Suite structure

`src/tests/` mirrors the source layout for the pure-domain tests, groups Django-aware tests by their nature, and isolates browser tests:

```
src/tests/
├── conftest.py                  # gallery_setup fixture (Django settings + cotton tree)
├── settings.py                  # DJANGO_SETTINGS_MODULE for the suite
├── urls.py                      # URL config for the test client
├── urls_no_i18n.py             # Variant without the i18n include
├── urls_unmounted.py           # Variant with the gallery unmounted
├── test_smoke.py                # Cross-cutting: package import + AppConfig
├── test_architecture.py         # Cross-cutting: AST walker enforcing dependency rules
│
├── core/                        # MIRRORS src/django_cotton_gallery/core/
│   ├── test_schemas.py          # Frozen dataclasses
│   ├── test_annotations.py      # @prop / @slot / @trigger parser
│   ├── test_component_graph.py  # Component dependency graph
│   ├── test_cvars.py            # <c-vars> extraction
│   ├── test_dependencies.py     # CDN URL → library detection
│   ├── test_linter.py           # Lint rules + scanners
│   ├── test_path_safety.py      # Traversal validation
│   ├── test_source_reader.py    # utf-8 + cp1252 fallback
│   ├── catalog/
│   │   ├── test_scanner.py
│   │   ├── test_resolver.py
│   │   ├── test_orderer.py
│   │   ├── test_cache.py
│   │   └── test_service.py
│   └── preview/
│       ├── test_sanitizer.py
│       ├── test_sanitizer_fuzz.py   # Hypothesis property-based
│       ├── test_tag_builder.py
│       ├── test_thumb_cache.py
│       └── test_service.py
│
├── integration/                 # Django-aware (views, templatetags, lint cmd,
│   │                            # insights, factories, setup guide, …)
│   └── test_*.py
│
└── e2e/                         # Browser tests via Playwright
    ├── conftest.py              # live_gallery fixture (Django LiveServer + override settings)
    ├── test_navigation.py       # SPA navigation, back button, active link
    ├── test_search.py           # Sidebar search + suggestions + shortcuts
    ├── test_preview.py          # Live preview update on control change
    ├── test_theme.py            # Theme toggle + persistence
    ├── test_editor_modal.py     # Editor modal flow
    └── test_css_autocomplete.py # CSS class autocomplete
```

## Why this layout

- **`core/`** mirrors `src/.../core/`. If you touch `core/schemas.py`, the test is at `src/tests/core/test_schemas.py`. Zero mental load.
- **`integration/`** groups Django-aware tests by their nature, not by source location. Factories, context processors, views, templatetags are all "Django glue" — they live together.
- **`e2e/`** is isolated because it has its own toolchain (Playwright, headless Chromium) and is the slowest tier. You can `--ignore=src/tests/e2e` for fast local feedback.
- **Top-level `test_smoke.py` and `test_architecture.py`** are cross-cutting invariants — they don't belong in any tier, so they stay flat.

## Tier ratios

The suite is heavily weighted toward fast pure-domain tests, with a thinner band of Django integration tests and a small set of slow browser flows. Use this shape as a sanity check when adding tests — if you find yourself piling new cases into a single tier, something has slid out of shape.

| Tier | Weight | What |
|------|--------|------|
| `core/` | heaviest (most of the suite) | Pure Python unit tests + parser/sanitizer fuzz |
| `integration/` | moderate | Django factories, views, templatetags, insights, lint cmd |
| `e2e/` | small but slowest | Playwright browser flows |
| Cross-cutting | smallest | Smoke, architecture |

For the live test count, run the suite with `make test`.

## Running the matrix locally

`tox` builds isolated venvs for each Python × Django combination. The matrix is defined in `tox.ini`:

```
py310-django{42,50,51,52}
py311-django{42,50,51,52}
py312-django{42,50,51,52,60}
py313-django{51,52,60}
```

First run is slow (uv has to download every Django version); subsequent runs are fast thanks to the venv cache.

To run only one combination:

```bash
uv run tox -e py312-django52
```

## CI

GitHub Actions (`.github/workflows/test.yml`) runs the same matrix as `tox`, plus cross-OS smoke tests (Windows + macOS × Python 3.12 × Django 4.2/5.2 LTS).

The `matrix-summary` job is the **single check** branch protection should require — it succeeds only if every matrix job succeeded.

## Adding a new test

Pick the right tier:

| New code is | Test goes in |
|-------------|--------------|
| under `src/.../core/` | `src/tests/core/<same path>` |
| `views.py`, `factories.py`, `context_processors.py`, `templatetags/` | `src/tests/integration/test_*.py` |
| Browser-driven flow (click, type, navigate) | `src/tests/e2e/test_*.py` |
| Architectural invariant (dependency rule, naming convention) | `src/tests/test_architecture.py` |
| Sanity-check that `import django_cotton_gallery` works | `src/tests/test_smoke.py` |

For tests that need Django settings or HTTP, use the `gallery_setup` fixture from the top-level `src/tests/conftest.py`. It builds a temporary `cotton/` tree, overrides `TEMPLATES`, and resets the lru_caches automatically.

```python
import pytest

@pytest.mark.django_db  # only if the test hits the ORM
def test_my_thing(gallery_setup):
    ...
```

For pure unit tests under `src/tests/core/`, don't use the fixture — keep them fast.

For E2E, use the `live_gallery` fixture from `src/tests/e2e/conftest.py` — it starts Django's `LiveServer`, points it at a temp cotton tree, and yields the base URL.

```python
def test_browser_flow(page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/")
    page.click("[data-cg-component='button']")
    expect(page).to_have_url(re.compile(r"/cotton/atoms/button/"))
```

## Coverage

Configured via `pytest-cov` in `pyproject.toml`. Run with:

```bash
make coverage   # terminal report + htmlcov/index.html
```

Branch coverage is configured and kept high. CI uploads to Codecov on every push. <!-- TODO: the exact baseline % drifts release to release — check Codecov for the current figure. -->

## Performance notes

The non-`e2e/` tiers run fast (a few seconds). If you find yourself adding a slow test (>100ms) under `src/tests/core/`, consider whether it really needs Django or if it can be a pure unit test. The `core/` tier is supposed to be fast feedback.
