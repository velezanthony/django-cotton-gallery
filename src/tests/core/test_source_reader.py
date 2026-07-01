"""Tests for the source reader's encoding fallback."""

from pathlib import Path

from django_cotton_gallery.core.source_reader import read_text


def test_reads_utf8(tmp_path: Path):
    file = tmp_path / "ok.html"
    file.write_text("Hola — mundo", encoding="utf-8")
    assert read_text(file) == "Hola — mundo"


def test_falls_back_to_cp1252(tmp_path: Path):
    file = tmp_path / "legacy.html"
    file.write_bytes(b"\xe9\xe8\xea")  # é è ê in cp1252; invalid utf-8 standalone
    assert read_text(file) == "éèê"


def test_empty_file(tmp_path: Path):
    file = tmp_path / "empty.html"
    file.write_text("")
    assert read_text(file) == ""
