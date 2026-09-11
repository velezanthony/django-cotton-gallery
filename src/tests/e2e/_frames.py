"""Reaching into the preview from E2E tests.

The component renders in its own document (js/isolated-stage.js), so
`page.locator(...)` stops at the frame boundary: everything inside the preview
has to be addressed through a `FrameLocator`. Centralised here so the selector
lives in one place if the stage markup ever moves.
"""

from __future__ import annotations

from playwright.sync_api import FrameLocator, Page

STAGE_FRAME = "[data-cg-preview-stage] iframe"


def stage_frame(page: Page) -> FrameLocator:
    """The document the component renders in, for the single-preview surfaces."""
    return page.frame_locator(STAGE_FRAME)
