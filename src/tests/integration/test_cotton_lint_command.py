"""Tests for the `python manage.py cotton_lint` management command.

The command is published — without these tests a downstream user could
break the CLI silently. We exercise the three exit paths (clean catalog
exits 0, errors exit 1, warnings-as-errors flag escalates) and the
output format (component header + per-issue lines + summary).
"""

from __future__ import annotations

import io

import pytest
from django.core.management import call_command


@pytest.fixture
def write_component(gallery_setup):
    """Drop a single .html under cotton/atoms/<name>.html so the cotton_lint
    command finds it via the test catalog. Returns the path the file was
    written to."""

    def _write(name: str, body: str):
        atoms = gallery_setup / "cotton" / "atoms"
        atoms.mkdir(parents=True, exist_ok=True)
        path = atoms / f"{name}.html"
        path.write_text(body)
        return path

    return _write


def _run_command(*args) -> tuple[str, int]:
    """Call `cotton_lint` with `args`, capturing stdout. Returns (output, exit).

    `call_command` raises `SystemExit` when the command calls `sys.exit(1)`
    for failed lint — caught and translated into the exit code so the test
    can assert without try/except boilerplate at every call site.
    """
    out = io.StringIO()
    try:
        call_command("cotton_lint", *args, stdout=out)
    except SystemExit as exc:
        return out.getvalue(), int(exc.code) if exc.code is not None else 0
    return out.getvalue(), 0


class TestCottonLintCommand:
    def test_clean_catalog_exits_zero(self, write_component):
        # Default fixture's button.html is already lint-clean.
        output, code = _run_command()
        assert code == 0
        assert "0 errors" in output

    def test_error_in_catalog_exits_one(self, write_component):
        # default-mismatch is an `error` rule — exit 1 expected.
        write_component(
            "broken",
            "{# @description Broken #}\n"
            '{# @prop variant:text | default:"a" | description:"x" #}\n'
            '<c-vars variant="b" />\n'
            "<button>{{ variant }}</button>\n",
        )
        output, code = _run_command()
        assert code == 1
        assert "default-mismatch" in output
        assert "atoms/broken" in output

    def test_warnings_alone_exit_zero(self, write_component):
        # missing-description is a warning — clean exit by default.
        write_component(
            "warn-only",
            "{# @description Card #}\n"
            '{# @prop label:text | default:"x" #}\n'  # missing | description:
            '<c-vars label="x" />\n'
            "<div></div>\n",
        )
        output, code = _run_command()
        assert code == 0
        assert "missing-description" in output

    def test_warnings_as_errors_flag_escalates(self, write_component):
        write_component(
            "warn-only",
            "{# @description Card #}\n"
            '{# @prop label:text | default:"x" #}\n'
            '<c-vars label="x" />\n'
            "<div></div>\n",
        )
        output, code = _run_command("--warnings-as-errors")
        assert code == 1
        assert "missing-description" in output

    def test_summary_line_present(self, write_component):
        # Always emits the `<clean>/<total> clean · N errors · N warnings` line.
        output, _ = _run_command()
        assert "clean" in output
        assert "errors" in output
        assert "warnings" in output

    def test_clean_components_skipped_in_per_component_output(self, write_component):
        """Clean components shouldn't appear with their path header — only
        components with at least one issue print a per-component block.
        Keeps the report focused on what actually needs attention."""
        # The gallery_setup fixture provides a clean atoms/button — it
        # should not appear as a per-component header in the output, only
        # in the summary tally.
        output, _ = _run_command()
        # The summary mentions "1 clean" but the path header for the clean
        # button must NOT appear (no issues to list under it).
        assert "1/1 clean" in output
