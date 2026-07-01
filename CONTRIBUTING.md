# Contributing

Thanks for considering a contribution. This guide covers the day-to-day workflow.

## Development setup

```bash
git clone https://github.com/velezanthony/django-cotton-gallery.git
cd django-cotton-gallery
uv pip install -e ".[dev]"
pre-commit install
```

Run the demo project locally to see your changes:

```bash
uv run python src/demo/manage.py migrate
make serve   # → uv run python src/demo/manage.py runserver
```

Visit `http://localhost:8000/django-cotton-gallery/` to browse the gallery.

## Running tests

```bash
uv run --extra test python -m pytest            # full suite (bare `pytest` is not on PATH)
uv run --extra test python -m pytest -k schemas # a specific module/pattern
uv run tox                                       # full Python × Django matrix (slow)
uv run tox -e py312-django52                     # one specific combo
```

The full matrix (`uv run tox`) builds a venv per Python × Django combo and takes a few minutes. For everyday work, the single `uv run --extra test python -m pytest` against your active Django is enough.

## Code style

Ruff is the single source of truth for both linting and formatting.

```bash
uv run ruff check src         # lint  (tests live under src/tests now)
uv run ruff format src        # apply formatting
uv run ruff check --fix src   # auto-fix what ruff can
```

Pre-commit runs both on every commit. If you skipped `pre-commit install`, the lint job in CI will catch you.

## Architecture

The library is organised by feature, not by layer. The pure domain lives under `src/django_cotton_gallery/core/` — `catalog/` (discover, resolve, order, cache), `preview/` (tag-build, render, sanitize, thumb-cache), `linter/`, plus single-responsibility modules (`annotations.py`, `schemas.py`, `path_safety.py`, `source_reader.py`, …). The Django glue (`views.py`, `factories.py`, `templatetags/`) sits at the package root. For the full map and the rationale, see [docs/contributors/architecture.md](docs/contributors/architecture.md).

When adding a new feature, ask: *which existing module owns this responsibility?* Prefer extending an existing module over creating a new one. Only split when a module crosses ~150 lines or starts mixing concerns.

## Adding a test

Tests live in `src/tests/` and mirror the source structure:

- Pure unit tests that don't need Django → `src/tests/core/test_*.py`
- Tests for a subpackage → `src/tests/<subpackage>/test_*.py`
- Tests that exercise Django (templates, views, ORM) → mark with `pytest.mark.django_db` or use the `client`/`gallery_setup` fixtures

Every new module should land **with** its tests in the same PR.

## Submitting a change

1. Fork and create a feature branch off `main`: `feat/short-description` or `fix/short-description`.
2. Write the change AND its tests.
3. Add an entry to `CHANGELOG.md` under `[Unreleased]`.
4. Update `docs/` if the change affects user-facing behaviour.
5. Run `make test` locally — must pass.
6. Push, open a PR against `main`. The PR template will guide you.
7. CI runs the full matrix. Address any failures.

## Reporting a security issue

Please do **not** open a public issue. See [SECURITY.md](SECURITY.md).

## Code of Conduct

Be respectful. We follow the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
