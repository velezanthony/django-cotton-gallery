"""E2E: syntax highlighting renders real tokens, not flat text.

The gallery vendors Prism plus a custom grammar layer. These checks assert the
grammar actually tokenises the surfaces that matter: the `{# @… #}` annotation
DSL on a component's Source tab, and the Python / Bash examples on the docs page
(which needed the vendored `prism-python` / `prism-bash` + custom tokens).
"""

from playwright.sync_api import Page, expect


def test_annotation_dsl_is_tokenised_on_the_source_tab(page: Page, live_gallery):
    """The `{# @prop … #}` annotations render as coloured DSL tokens (directive,
    type) instead of one flat comment."""
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/button/")
    page.click("[data-cg-tab='source']")

    src = page.locator("#cg-source-code")
    # the whole annotation comment is its own token…
    expect(src.locator(".token.annotation").first).to_be_attached()
    # …with the @prop / @description directive and the `select` type coloured.
    expect(src.locator(".token.annotation .token.annotation-directive").first).to_be_attached()
    expect(src.locator(".token.annotation .token.annotation-type").first).to_be_attached()


def test_docs_python_constants_are_highlighted(page: Page, live_gallery):
    """The docs Python examples highlight — and ALL_CAPS settings render as the
    custom `constant` token (Prism-python leaves them plain otherwise)."""
    page.goto(f"{live_gallery}/django-cotton-gallery/docs/")
    expect(page.locator("code.language-python .token.constant").first).to_be_attached()


def test_docs_bash_command_is_highlighted(page: Page, live_gallery):
    """The docs shell examples highlight the command word via the custom `command`
    token (Prism-bash only colours known builtins, and `python` is not one)."""
    page.goto(f"{live_gallery}/django-cotton-gallery/docs/")
    expect(page.locator("code.language-bash .token.command").first).to_be_attached()
