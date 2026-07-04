"""E2E tests for the annotation builder.

The builder composes a component's *whole* annotation block — the
`@description`, the `@strict` / `@ignore-unused` flags, `@prop`s, `@slot`s and
`@trigger` — in canonical order, plus the matching `<c-vars>` line. These tests
drive the form and assert the live-generated output.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect


def _annotations(page: Page) -> str:
    """The composed annotation block's text (Prism markup stripped)."""
    return page.locator("[data-cg-bld-annotations]").text_content() or ""


def _cvars(page: Page) -> str:
    return page.locator("[data-cg-bld-cvars]").text_content() or ""


def test_builder_composes_full_annotation_block(page: Page, live_gallery: str) -> None:
    page.goto(f"{live_gallery}/django-cotton-gallery/builder/")
    page.wait_for_selector("[data-cg-bld-name]")  # first prop entry spawned on init

    # Component-level fields.
    page.fill("[data-cg-bld-comp-description]", "Compact status label")
    page.check("[data-cg-bld-strict]")
    page.check("[data-cg-bld-ignore-unused]")
    page.fill("[data-cg-bld-trigger]", "<button>Open</button>")
    page.fill("[data-cg-bld-trigger-desc]", "Opens the dialog")

    # One prop.
    page.fill("[data-cg-bld-name]", "tone")
    page.fill("[data-cg-bld-description]", "Semantic tone")
    page.fill("[data-cg-bld-default]", "info")

    # One named slot (description-only).
    page.click("[data-cg-builder-slot-add]")
    page.fill("[data-cg-bld-slot-name]", "actions")
    page.fill("[data-cg-bld-slot-desc]", "Top-right buttons")

    out = _annotations(page)
    assert "{# @strict #}" in out
    assert "{# @ignore-unused #}" in out
    assert "{# @description Compact status label #}" in out
    assert '{# @prop tone:text | default:"info" | description:"Semantic tone" #}' in out
    assert "{# @slot:actions — Top-right buttons #}" in out
    assert "{# @trigger <button>Open</button> — Opens the dialog #}" in out

    # Canonical order: strict < ignore-unused < description < prop < slot < trigger.
    order = [
        out.index("@strict"),
        out.index("@ignore-unused"),
        out.index("@description"),
        out.index("@prop"),
        out.index("@slot"),
        out.index("@trigger"),
    ]
    assert order == sorted(order), f"annotations out of canonical order: {out!r}"

    # The <c-vars> line reflects the prop's default.
    assert 'tone="info"' in _cvars(page)


def test_builder_flag_toggles_off(page: Page, live_gallery: str) -> None:
    """Unchecking a flag removes its line — the flag is not sticky."""
    page.goto(f"{live_gallery}/django-cotton-gallery/builder/")
    page.wait_for_selector("[data-cg-bld-strict]")

    page.check("[data-cg-bld-strict]")
    assert "{# @strict #}" in _annotations(page)

    page.uncheck("[data-cg-bld-strict]")
    assert "{# @strict #}" not in _annotations(page)


def test_builder_add_and_remove_slot(page: Page, live_gallery: str) -> None:
    """Slots are 0..n: adding one emits a `@slot` line, removing it drops it."""
    page.goto(f"{live_gallery}/django-cotton-gallery/builder/")
    page.wait_for_selector("[data-cg-builder-slot-add]")

    page.click("[data-cg-builder-slot-add]")
    page.fill("[data-cg-bld-slot-name]", "footer")
    assert "{# @slot:footer #}" in _annotations(page)

    page.click("[data-cg-bld-slot-remove]")
    assert "@slot:footer" not in _annotations(page)


def test_builder_warns_on_comment_terminator(page: Page, live_gallery: str) -> None:
    """A `#}` in any field closes the Django comment early and cannot be
    escaped inside `{# … #}` — the builder must warn, not emit broken output.
    """
    page.goto(f"{live_gallery}/django-cotton-gallery/builder/")
    page.wait_for_selector("[data-cg-bld-comp-description]")

    validation = page.locator("[data-cg-bld-validation]")
    page.fill("[data-cg-bld-comp-description]", "clean summary")
    expect(validation).to_be_hidden()

    page.fill("[data-cg-bld-comp-description]", "oops #} broken")
    expect(validation).to_be_visible()
    expect(validation).to_contain_text("#}")


def test_builder_prop_only_regression(page: Page, live_gallery: str) -> None:
    """The original @prop-only flow still works — no stray component lines."""
    page.goto(f"{live_gallery}/django-cotton-gallery/builder/")
    page.wait_for_selector("[data-cg-bld-name]")

    page.fill("[data-cg-bld-name]", "size")
    page.fill("[data-cg-bld-default]", "md")

    out = _annotations(page)
    assert '{# @prop size:text | default:"md" #}' in out
    assert "@strict" not in out
    assert "@slot" not in out
    assert "@trigger" not in out
    assert 'size="md"' in _cvars(page)
    # The empty-state placeholder must be gone once a real prop exists.
    expect(page.locator("[data-cg-bld-cvars]")).to_contain_text("c-vars")
