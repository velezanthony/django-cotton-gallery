# django-cotton-gallery — Makefile
# `make` (no args) prints a help grouped by section.
#
# Philosophy:
#   - Python commands use `uv run` → work from any venv-aware shell.
#   - i18n targets require GNU gettext on the system (apt install gettext).
#   - `make smoke` reinstalls the wheel into a consumer project whose path
#     is SMOKE_CONSUMER_DIR. Set it in a local `.env` (gitignored) so the
#     path never reaches the repo, override it per-call (make smoke
#     SMOKE_CONSUMER_DIR=...), or fall back to the ../pruebas/ default.
#
# Things NOT in this Makefile (use them by hand when needed):
#   uv run pytest src/tests/path::test    # Run a single test
#   uv run pytest -k "expr"           # Run tests by name expression
#   uv run pytest -x                  # Stop at first failure
#   twine upload dist/*               # Publish to PyPI (release-only, intentional)
#   uv tree                           # Inspect dependency tree
#
# `##@` markers define sections in `make help` output.

.DEFAULT_GOAL := help

# Local overrides (gitignored). Define SMOKE_CONSUMER_DIR here, one per line,
# KEY=value, no quotes. The leading `-` means "don't fail if .env is absent".
-include .env

# Where `make smoke` rebuilds the wheel into. `.env` or the environment win;
# this is only the fallback so the target works out of the box.
SMOKE_CONSUMER_DIR ?= ../pruebas

.PHONY: help \
        dev serve smoke \
        test coverage lint format fix typecheck matrix pre-commit \
        messages compile-messages \
        lock upgrade sync \
        build clean

help:  ## List all available commands
	@printf "\n  \033[1mdjango-cotton-gallery\033[0m — project operations\n\n"
	@printf "  Usage: \033[36mmake <command>\033[0m\n"
	@awk 'BEGIN {FS = ":.*?## "} \
		/^##@/ { printf "\n  \033[1;33m%s\033[0m\n", substr($$0, 5) } \
		/^[a-zA-Z_-]+:.*?##/ { printf "    \033[36m%-20s\033[0m %s\n", $$1, $$2 }' \
		$(MAKEFILE_LIST)
	@printf "\n"

##@ Development

dev:  ## Install Pythons (3.10-3.13) and dev dependencies
	uv python install 3.10 3.11 3.12 3.13
	uv sync --extra dev

serve:  ## Run the in-repo demo (uses src/demo/templates/cotton/* — safe for screenshots)
	uv run python src/demo/manage.py runserver

smoke:  ## Rebuild wheel + reinstall in SMOKE_CONSUMER_DIR for a consumer smoke-test
	@test -d "$(SMOKE_CONSUMER_DIR)" || { \
		printf "\033[31mSMOKE_CONSUMER_DIR='%s' does not exist.\033[0m\n" "$(SMOKE_CONSUMER_DIR)"; \
		printf "Set it in a local .env (KEY=value, no quotes) or pass it inline:\n"; \
		printf "  make smoke SMOKE_CONSUMER_DIR=/path/to/consumer\n"; \
		exit 1; }
	$(MAKE) build
	cd "$(SMOKE_CONSUMER_DIR)" && uv lock --upgrade-package django-cotton-gallery && uv sync --reinstall-package django-cotton-gallery

##@ Tests & Quality

test:  ## Run pytest on the current Python
	uv run --extra test python -m pytest

coverage:  ## Run pytest with coverage report (terminal + htmlcov/)
	uv run --extra test python -m pytest --cov --cov-report=term-missing --cov-report=html

lint:  ## Run ruff check on src (tests live under src/tests)
	uv run ruff check src

format:  ## Auto-format code with ruff
	uv run ruff format src

fix:  ## Auto-fix lint issues with ruff (safe fixes only)
	uv run ruff check --fix src

typecheck:  ## Run mypy on the package source
	uv run --extra typecheck mypy src/django_cotton_gallery

matrix:  ## Run tox across all Python x Django combinations
	uv run tox -p auto

pre-commit:  ## Run pre-commit hooks across the whole tree
	uv run pre-commit run --all-files

##@ Translations (i18n)

# Requires GNU gettext: `sudo apt install gettext` (xgettext, msguniq, msgmerge, msgfmt).
# We `cd src/django_cotton_gallery` so makemessages/compilemessages only scan
# our package locale dirs, not .tox / .venv / pip-installed packages elsewhere.

messages:  ## Extract translatable strings into .po (es, eu, fr)
	cd src/django_cotton_gallery && uv run --project ../.. python -m django makemessages -l es -l eu -l fr --extension=html,py,txt

compile-messages:  ## Compile .po -> .mo for our package locales
	cd src/django_cotton_gallery && uv run --project ../.. python -m django compilemessages -l es -l eu -l fr

##@ Dependencies (uv)

# uv trio:
#   lock    → you edited pyproject.toml by hand → regenerate uv.lock
#   upgrade → bump deps to latest versions within pyproject.toml ranges
#   sync    → align your venv with uv.lock (after a git pull if lock changed)

lock:  ## Regenerate uv.lock after editing pyproject.toml by hand
	uv lock

upgrade:  ## Bump deps to latest versions within pyproject.toml ranges
	uv lock --upgrade

sync:  ## Align your venv with uv.lock
	uv sync

##@ Build & Release

build:  ## Build wheel and sdist into dist/
	rm -rf dist/ build/ *.egg-info
	uv run python -m build

clean:  ## Remove build artifacts and caches
	rm -rf dist/ build/ *.egg-info .tox/ .pytest_cache/ .coverage htmlcov/ coverage.xml
