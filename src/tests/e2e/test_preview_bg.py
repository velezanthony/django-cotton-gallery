"""E2E: the preview background switcher.

Covers the presets, the editable swatches (white/dark/brand recoloured via a
native color picker), and the draft/commit persistence rule — a picked color
previews live but only reaches localStorage when the user hits "Done".
"""

from playwright.sync_api import Page, expect

BUTTON = "/django-cotton-gallery/atoms/button/"
COLORS_KEY = "cg-preview-bg-colors"


def test_preset_background_persists_across_reload(page: Page, live_gallery):
    """Selecting a preset backdrop applies it to the stage and survives reload."""
    page.goto(f"{live_gallery}{BUTTON}")
    page.locator('.cg-bg-btn[data-cg-bg="dark"]').click()
    expect(page.locator("[data-cg-preview-stage]").first).to_have_attribute("data-cg-bg", "dark")

    page.reload()
    expect(page.locator("[data-cg-preview-stage]").first).to_have_attribute("data-cg-bg", "dark")


def test_edit_mode_toggles_the_command_buttons(page: Page, live_gallery):
    """Edit reveals Done + Reset (and hides Edit); the switcher enters edit mode."""
    page.goto(f"{live_gallery}{BUTTON}")
    edit = page.locator('[data-cg-bg-editcmd="edit"]')
    done = page.locator('[data-cg-bg-editcmd="done"]')
    reset = page.locator('[data-cg-bg-editcmd="reset"]')

    expect(edit).to_be_visible()
    expect(done).to_be_hidden()
    expect(reset).to_be_hidden()

    edit.click()
    expect(edit).to_be_hidden()
    expect(done).to_be_visible()
    expect(reset).to_be_visible()
    assert page.evaluate(
        "document.querySelector('.cg-preview__bg-switcher').classList.contains('cg-editing')"
    )


def test_custom_color_only_persists_on_done(page: Page, live_gallery):
    """A picked swatch color previews live but is NOT written to localStorage
    until the user commits with Done."""
    page.goto(f"{live_gallery}{BUTTON}")
    page.locator('[data-cg-bg-editcmd="edit"]').click()

    # Native color inputs can't be `.fill()`ed reliably; drive the value + event.
    page.evaluate(
        """() => {
            const inp = document.querySelector('[data-cg-bg-edit="dark"]');
            inp.value = '#7c3aed';
            inp.dispatchEvent(new Event('input', { bubbles: true }));
        }"""
    )

    # Live preview is applied…
    assert (
        page.evaluate(
            "getComputedStyle(document.documentElement).getPropertyValue('--cg-bg-dark').trim()"
        )
        == "#7c3aed"
    )
    # …but nothing is persisted yet.
    assert page.evaluate(f"localStorage.getItem('{COLORS_KEY}')") is None

    # Done commits the draft.
    page.locator('[data-cg-bg-editcmd="done"]').click()
    saved = page.evaluate(f"JSON.parse(localStorage.getItem('{COLORS_KEY}') || '{{}}')")
    assert saved.get("dark") == "#7c3aed"


def test_reset_returns_swatches_to_defaults(page: Page, live_gallery):
    """Reset (committed with Done) clears customised colors back to the CSS defaults."""
    page.goto(f"{live_gallery}{BUTTON}")
    page.evaluate(f"localStorage.setItem('{COLORS_KEY}', JSON.stringify({{ dark: '#7c3aed' }}))")
    page.reload()
    assert (
        page.evaluate(
            "getComputedStyle(document.documentElement).getPropertyValue('--cg-bg-dark').trim()"
        )
        == "#7c3aed"
    )

    page.locator('[data-cg-bg-editcmd="edit"]').click()
    page.locator('[data-cg-bg-editcmd="reset"]').click()
    # var cleared live (falls back to the CSS default)
    assert (
        page.evaluate(
            "getComputedStyle(document.documentElement).getPropertyValue('--cg-bg-dark').trim()"
        )
        == ""
    )

    page.locator('[data-cg-bg-editcmd="done"]').click()
    saved = page.evaluate(f"JSON.parse(localStorage.getItem('{COLORS_KEY}') || '{{}}')")
    assert "dark" not in saved
