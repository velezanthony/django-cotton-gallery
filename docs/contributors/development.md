# Development setup

How to clone the repo, install everything, and run the demo locally.

## Prerequisites

- **Python 3.10+** (3.12 is what CI's primary matrix runs)
- **[uv](https://github.com/astral-sh/uv)** — fast Python package manager. Install with `curl -LsSf https://astral.sh/uv/install.sh | sh`.
- **A Chromium browser** for the Playwright e2e tests — installed via `playwright` in the setup below (also used for capturing screenshots locally; CI uses headless Chrome).

## First-time setup

```bash
git clone https://github.com/velezanthony/django-cotton-gallery.git
cd django-cotton-gallery
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
pre-commit install
python -m playwright install chromium   # browser for the e2e suite
```

The `[dev]` extra pulls in `[test]` (pytest, pytest-django, pytest-playwright) and `[docs]` (mkdocs-material), plus `tox`, `build`, `twine`, `ruff`, `polib`, and `pre-commit`. The `playwright install` step fetches the Chromium build the e2e tests drive — skip it and those tests error with "Executable doesn't exist".

## Run the demo

The demo project lives at `src/demo/` (`config/`, `manage.py`, `templates/cotton/`) and is a real Django app that depends on the library in editable mode.

```bash
uv run python src/demo/manage.py migrate
make serve   # → uv run python src/demo/manage.py runserver
```

Open `http://localhost:8000/django-cotton-gallery/`. You should see the gallery with the demo components from `src/demo/templates/cotton/`.

## Repository layout

```
django-cotton-gallery/
├── src/                            # Everything that is code lives here
│   ├── django_cotton_gallery/      # The library (only this ships in the wheel)
│   │   ├── core/                   # Pure-domain logic (see architecture.md)
│   │   │   ├── annotations.py      # @prop / @slot parser
│   │   │   ├── schemas.py          # Frozen dataclasses (the data contract)
│   │   │   ├── path_safety.py      # Centralized traversal validation
│   │   │   ├── source_reader.py    # File reading with encoding fallback
│   │   │   ├── dependencies.py     # CDN URL → library detection
│   │   │   ├── component_graph.py  cvars.py  insights.py
│   │   │   ├── catalog/            # cache, orderer, resolver, scanner
│   │   │   ├── preview/            # renderer, sanitizer, tag_builder, thumb_cache
│   │   │   └── linter/             # _rules, _scanners, _types
│   │   ├── management/commands/    # cotton_lint
│   │   ├── locale/                 # es / eu / fr translations (.po + .mo)
│   │   ├── static/                 # css/ + js/
│   │   ├── templates/              # base, index, detail, lint, insights, etc.
│   │   ├── templatetags/           # catalog_tags.py
│   │   ├── apps.py  conf.py  context_processors.py  factories.py
│   │   ├── setup_check.py  urls.py  views.py
│   │   └── __init__.py  py.typed   # PEP 561 marker
│   │
│   ├── demo/                       # Demo Django project (NOT published)
│   │   ├── config/                 # settings, urls, asgi, wsgi
│   │   ├── templates/cotton/       # Demo components for the gallery
│   │   └── manage.py               # Demo entry point
│   │
│   └── tests/                      # Test suite (NOT published)
│       ├── core/                   # Pure-domain unit tests (catalog/, preview/)
│       ├── integration/            # Django-aware tests
│       ├── e2e/                    # Playwright browser tests
│       ├── settings.py  conftest.py
│       └── test_architecture.py  test_smoke.py  urls*.py
│
├── docs/                           # All documentation (mkdocs Material site)
│   ├── index.md                    # Landing
│   ├── users/                      # Consumer-facing: getting-started, features,
│   │                               # configuration, annotations
│   ├── contributors/               # Maintainer-facing: development (this file),
│   │                               # testing, architecture, i18n, release
│   └── assets/                     # Screenshots
│
├── .github/                        # CI workflows + issue templates
│   ├── workflows/                  # test.yml, lint.yml, release.yml, docs.yml
│   ├── ISSUE_TEMPLATE/
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── dependabot.yml
│
├── dist/                           # Built wheel + sdist
├── pyproject.toml                  # Package metadata + tool configs
├── Makefile                        # serve, test, messages, compile-messages, …
├── tox.ini                         # Compatibility matrix
├── mkdocs.yml                      # Public docs site config
├── uv.lock                         # Locked dependency graph
├── README.md                       # Repo landing
├── CHANGELOG.md                    # Keep-a-Changelog
├── CONTRIBUTING.md                 # Contributor workflow
├── SECURITY.md                     # Security reporting
├── LICENSE                         # MIT
├── .env.example  .gitignore  .pre-commit-config.yaml  .python-version
└── db.sqlite3                      # Demo dev DB (gitignored), at repo root by choice
```

## Demo components

The components under `src/demo/templates/cotton/` are **only for the demo**. They're not part of the published wheel — consumers bring their own components.

The current set is a dozen-plus atoms/molecules plus a handful of organisms (and a `lint/` category that exercises the lint engine), under `src/demo/templates/cotton/`. They cover the basic prop/slot patterns: basic props, slots, named slots, `accepts_attrs`, and dynamic props.

To add more demo components, just drop new files under `src/demo/templates/cotton/`. The gallery picks them up automatically without restart.

## Editing the library

Because the library is installed with `pip install -e .`, edits to `src/django_cotton_gallery/` are reflected immediately. Restart the dev server only when you change Python files (templates and static files reload on the fly).

## Linting and formatting

```bash
ruff check src           # lint  (tests live under src/tests now)
ruff format src          # format
ruff check --fix src     # lint + auto-fix
```

Pre-commit runs both on every commit. CI (`lint.yml`) verifies on every push.

## Building the wheel locally

```bash
python -m build
ls dist/
# django_cotton_gallery-0.1.0-py3-none-any.whl
# django_cotton_gallery-0.1.0.tar.gz
```

Verify the wheel includes templates, static, and locale:

```bash
unzip -l dist/django_cotton_gallery-*.whl | grep -E '(templates|static|locale|py.typed)'
```

## Common gotchas

- **`ImproperlyConfigured: app_dirs must not be set when loaders is defined`**: when configuring TEMPLATES with explicit loaders (which Cotton requires), you must set `APP_DIRS: False`. Templates from installed apps still work because `app_directories.Loader` is in the loaders list.

- **The gallery shows zero components**: check that `templates/cotton/` exists at the path Django sees as `TEMPLATES[0]['DIRS'][0]`. Files directly under `templates/cotton/` are skipped on purpose — only files inside a category folder (e.g. `templates/cotton/atoms/button.html`) are scanned.

- **`{% url 'set_language' %}` raises `NoReverseMatch`**: include `path("i18n/", include("django.conf.urls.i18n"))` in your URL config. The gallery's base template uses Django's built-in language switcher view.

- **Translations don't apply when changing language**: make sure `LocaleMiddleware` is in `MIDDLEWARE`, positioned **after `SessionMiddleware`** and **before `CommonMiddleware`**.
