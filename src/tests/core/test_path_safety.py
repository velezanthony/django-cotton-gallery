"""Tests for path-traversal validation."""

from pathlib import Path

import pytest

from django_cotton_gallery.core.path_safety import (
    UnsafePath,
    resolve_within,
    validate_segments,
)


class TestValidateSegments:
    def test_valid_segments_pass(self):
        validate_segments(["atoms", "button"])
        validate_segments(["atoms", "ui", "input"])
        validate_segments(["a-b", "c_d"])

    @pytest.mark.parametrize("bad", ["", ".", ".."])
    def test_traversal_or_empty_rejected(self, bad):
        with pytest.raises(UnsafePath):
            validate_segments(["atoms", bad])

    def test_private_prefix_rejected(self):
        with pytest.raises(UnsafePath):
            validate_segments(["atoms", "_private"])

    def test_backslash_rejected(self):
        with pytest.raises(UnsafePath):
            validate_segments(["atoms", "bad\\name"])

    def test_colon_rejected(self):
        with pytest.raises(UnsafePath):
            validate_segments(["atoms", "bad:name"])

    def test_null_byte_rejected(self):
        with pytest.raises(UnsafePath):
            validate_segments(["atoms", "bad\x00"])

    def test_empty_list_passes(self):
        validate_segments([])


class TestResolveWithin:
    def test_candidate_inside_root(self, tmp_path: Path):
        candidate = tmp_path / "subdir" / "file.html"
        candidate.parent.mkdir()
        candidate.write_text("x")
        result = resolve_within(tmp_path, candidate)
        assert result == candidate.resolve()

    def test_candidate_equal_to_root(self, tmp_path: Path):
        result = resolve_within(tmp_path, tmp_path)
        assert result == tmp_path.resolve()

    def test_candidate_outside_root_rejects(self, tmp_path: Path):
        outside = tmp_path.parent / "outside"
        with pytest.raises(UnsafePath):
            resolve_within(tmp_path, outside)

    def test_traversal_via_dotdot_rejects(self, tmp_path: Path):
        candidate = tmp_path / ".." / "outside" / "file.html"
        with pytest.raises(UnsafePath):
            resolve_within(tmp_path, candidate)

    def test_nonexistent_paths_still_validated(self, tmp_path: Path):
        candidate = tmp_path / "does_not_exist.html"
        result = resolve_within(tmp_path, candidate)
        assert result == candidate.resolve()
