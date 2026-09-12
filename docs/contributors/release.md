# Releasing

How to cut a new version of `django-cotton-gallery` and publish it to PyPI.

## One-time setup (required before the first release)

### 1. Reserve the project name on PyPI

Either upload an initial version manually, or reserve via the PyPI UI. The project at <https://pypi.org/project/django-cotton-gallery/> must exist before Trusted Publishing can be configured.

### 2. Configure Trusted Publishing on PyPI

Visit <https://pypi.org/manage/project/django-cotton-gallery/settings/publishing/> and add a publisher with:

- **PyPI Project Name**: `django-cotton-gallery`
- **Owner**: `velezanthony`
- **Repository name**: `django-cotton-gallery`
- **Workflow name**: `release.yml`
- **Environment name**: `pypi`

This replaces API tokens entirely. PyPI verifies via OIDC that the workflow comes from the legitimate repo.

### 3. Create the `pypi` GitHub Environment

Repo → **Settings** → **Environments** → **New environment** → name it `pypi`.

Optional: add **required reviewers** here to gate every release behind a manual approval.

### 4. Configure GitHub Pages source

Repo → **Settings** → **Pages** → **Source**: select **GitHub Actions** (NOT "Deploy from branch"). The `docs.yml` workflow does the rest.

## Release checklist

When you're ready to cut version `X.Y.Z`:

```bash
# 1. Make sure main is clean and up to date
git checkout main
git pull --ff-only

# 2. Verify the suite is green
uv run --extra test python -m pytest -v

# 3. Verify the matrix (optional, CI will catch this anyway)
uv run tox -p auto

# 4. Bump the version in pyproject.toml
# (manual edit — no automation yet)
# A literal old version would stop matching after the first release and sed
# would exit 0 without touching anything. Match any version instead.
sed -i -E 's/^version = "[^"]+"$/version = "X.Y.Z"/' pyproject.toml
grep -q '^version = "X.Y.Z"$' pyproject.toml || { echo "bump failed"; exit 1; }

# 5. Move [Unreleased] → [X.Y.Z] in CHANGELOG.md
# Update the date and the link footnotes:
#   [Unreleased]: ...compare/vX.Y.Z...HEAD
#   [X.Y.Z]: ...releases/tag/vX.Y.Z

# 6. Commit and push
git add pyproject.toml CHANGELOG.md
git commit -m "chore: release vX.Y.Z"
git push

# 7. Tag (the workflow triggers on tags matching v*.*.*)
git tag vX.Y.Z
git push --tags
```

The `release.yml` workflow now runs and:

1. Builds `dist/django_cotton_gallery-X.Y.Z.tar.gz` and the wheel
2. Runs `twine check dist/*` to validate metadata
3. Verifies the tag version matches `pyproject.toml`
4. Uploads to PyPI via Trusted Publishing (no token)

## Verifying the release

```bash
# Wait ~1 minute for PyPI's CDN to serve the new version, then:
pip index versions django-cotton-gallery

# Install from a clean venv to confirm it works
python -m venv /tmp/test-release
/tmp/test-release/bin/pip install django-cotton-gallery==X.Y.Z
/tmp/test-release/bin/python -c "import django_cotton_gallery; print(django_cotton_gallery.__version__)"
```

## Versioning rules

We follow [SemVer](https://semver.org/):

- **Patch** (X.Y.**Z**): bug fixes, doc fixes, internal refactors. No API surface change.
- **Minor** (X.**Y**.0): new features, new annotations, new settings, new translations. Existing API still works.
- **Major** (**X**.0.0): breaking changes. Removed settings, renamed annotations, removed CSS classes consumers might have hooked into.

`@prop` annotation grammar is part of the public API. Renaming `default` to `defaultValue` would be a major version bump.

## Hotfix workflow

For a critical bug in production:

```bash
# Branch off the tag
git checkout -b hotfix/X.Y.(Z+1) vX.Y.Z

# Fix the bug, add a test that fails on the bug, ship it
git commit -m "fix: <description of the bug>"

# Bump version and CHANGELOG
# Tag and push (the workflow does the rest)
git tag vX.Y.(Z+1)
git push origin hotfix/X.Y.(Z+1) vX.Y.(Z+1)

# Merge back into main
git checkout main
git merge --no-ff hotfix/X.Y.(Z+1)
git push
```

## Post-release

- Verify the GitHub Actions run succeeded (Actions tab).
- Verify the release exists on PyPI (https://pypi.org/project/django-cotton-gallery/X.Y.Z/).
- Verify the docs site updated (https://velezanthony.github.io/django-cotton-gallery/).
- Open the GitHub Release entry, paste the `[X.Y.Z]` section from `CHANGELOG.md` as the body.

## Yanking a bad release

If a release ships with a critical bug, yank it (PyPI's "soft delete"). There is no
`twine` command for this — yank from the PyPI web UI:

1. Go to <https://pypi.org/manage/project/django-cotton-gallery/releases/>.
2. Open the affected version → **Options → Yank** → enter a reason.

`pip install django-cotton-gallery` will skip yanked versions for new installs but won't break existing pins. Cut a fix release as soon as possible.
