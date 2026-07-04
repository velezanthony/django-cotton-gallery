"""E2E: lint issues surface inline on the Source tab.

The gallery already computes per-component lint issues (with a source line);
this checks that opening the Source tab renders a gutter marker on the
offending line and a hover tooltip carrying the (reused, translated) message.
"""

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect


@pytest.fixture
def cotton_tree(tmp_path: Path) -> Path:
    """A cotton/ tree whose one component trips a line-bearing lint issue.

    `undocumented` is declared in `<c-vars>` with no matching `@prop`, so the
    linter raises `missing-annotation` anchored to the `<c-vars>` line (line 2).
    Overrides the shared fixture for this module only.
    """
    templates_dir = tmp_path / "templates"
    cotton_dir = templates_dir / "cotton" / "atoms"
    cotton_dir.mkdir(parents=True)
    (cotton_dir / "broken.html").write_text(
        "{# @description Undocumented prop trips missing-annotation #}\n"
        '<c-vars undocumented="x" />\n'
        "<div {{ attrs }}>{{ slot }}</div>\n"
    )
    return templates_dir


def test_source_tab_marks_lint_issue_inline(page: Page, live_gallery):
    page.goto(f"{live_gallery}/django-cotton-gallery/atoms/broken/")

    # The lint panel carries the issue tagged with its source line (2).
    issue = page.locator("[data-cg-lint-panel] .cg-lint__issue[data-cg-issue-line='2']")
    expect(issue.first).to_be_attached()

    # Opening the Source tab renders an inline gutter marker on that line.
    page.click("[data-cg-tab='source']")
    expect(page.locator(".cg-source pre.cg-source--linted")).to_be_attached()
    marker = page.locator(".cg-src-gutter-icon").first
    expect(marker).to_be_visible()

    # Hovering the marker reveals the tooltip, reusing the translated message
    # (which names the offending prop).
    marker.hover()
    tip = page.locator(".cg-src-tip")
    expect(tip).to_be_visible()
    expect(tip).to_contain_text("undocumented")
