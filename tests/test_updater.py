"""Tests for updater.py pure logic — version compare + installer integrity.

These exercise the fragile, network-free corners flagged by the v2.8.2
Tester audit (H-A3#7): the version-precedence math (numeric, different
lengths, and the new pre-release handling from C-A2#2) and the SHA-256
integrity gate (H-A3#1). No live GitHub calls — everything here is pure
functions over strings + a tmp file.
"""
from __future__ import annotations

import hashlib

from updater import (
    _parse_version,
    _is_prerelease,
    is_newer,
    parse_expected_sha256,
    verify_sha256,
    _file_sha256,
    _resume_sidecar_path,
    _write_resume_sidecar,
    _validate_partial_for_url,
)


class TestParseVersion:
    def test_basic(self):
        assert _parse_version("2.8.1") == (2, 8, 1)

    def test_v_prefix_stripped(self):
        assert _parse_version("v2.8.1") == (2, 8, 1)
        assert _parse_version("V2.8.1") == (2, 8, 1)

    def test_prerelease_suffix_ignored_in_numeric(self):
        # The numeric tuple stops at the release; suffix handled separately.
        assert _parse_version("2.8.1-beta") == (2, 8, 1)
        assert _parse_version("2.8.1rc1") == (2, 8, 1)

    def test_two_segment(self):
        assert _parse_version("2.8") == (2, 8)

    def test_garbage_returns_zero(self):
        assert _parse_version("not-a-version") == (0,)


class TestIsPrerelease:
    def test_plain_release_is_not_prerelease(self):
        assert _is_prerelease("2.8.1") is False
        assert _is_prerelease("v2.8.1") is False

    def test_suffix_is_prerelease(self):
        assert _is_prerelease("2.8.1-beta") is True
        assert _is_prerelease("2.8.1rc1") is True
        assert _is_prerelease("2.8.1+build7") is True


class TestIsNewer:
    def test_newer_patch(self):
        assert is_newer("2.8.1", "2.8.2") is True

    def test_newer_minor(self):
        assert is_newer("2.8.1", "2.9.0") is True

    def test_newer_major(self):
        assert is_newer("2.8.1", "3.0.0") is True

    def test_equal_is_not_newer(self):
        assert is_newer("2.8.1", "2.8.1") is False

    def test_older_is_not_newer(self):
        assert is_newer("2.8.2", "2.8.1") is False

    def test_numeric_not_lexical(self):
        # 10 > 9 numerically (lexical string compare would get this wrong).
        assert is_newer("2.9.0", "2.10.0") is True
        assert is_newer("2.10.0", "2.9.0") is False

    def test_different_lengths(self):
        assert is_newer("2.8", "2.8.1") is True
        assert is_newer("2.8.1", "2.8") is False

    def test_v_prefix_either_side(self):
        assert is_newer("v2.8.1", "v2.8.2") is True

    def test_prerelease_below_final(self):
        # A user on -beta SHOULD be offered the final of the same version.
        assert is_newer("2.8.1-beta", "2.8.1") is True

    def test_final_not_offered_prerelease(self):
        # A user on the final should NOT be "updated" back to a pre-release.
        assert is_newer("2.8.1", "2.8.1-beta") is False

    def test_same_prerelease_not_newer(self):
        assert is_newer("2.8.1-beta", "2.8.1-beta") is False


class TestParseExpectedSha256:
    HASH = "a" * 64

    def test_colon_form(self):
        assert parse_expected_sha256(f"Release notes\nSHA256: {self.HASH}\n") == self.HASH

    def test_dash_and_equals_form(self):
        assert parse_expected_sha256(f"sha-256 = {self.HASH}") == self.HASH

    def test_case_insensitive_and_lowered(self):
        body = f"SHA256: {'A' * 64}"
        assert parse_expected_sha256(body) == "a" * 64

    def test_none_when_absent(self):
        assert parse_expected_sha256("just some notes, no hash here") == ""

    def test_empty_body(self):
        assert parse_expected_sha256("") == ""

    def test_ignores_wrong_length_hex(self):
        # 63 hex chars is not a valid sha256 — must not match.
        assert parse_expected_sha256(f"SHA256: {'a' * 63}") == ""


class TestVerifySha256:
    def test_matches(self, tmp_path):
        p = tmp_path / "f.zip"
        p.write_bytes(b"hello world")
        digest = hashlib.sha256(b"hello world").hexdigest()
        assert verify_sha256(p, digest) is True

    def test_mismatch(self, tmp_path):
        p = tmp_path / "f.zip"
        p.write_bytes(b"hello world")
        assert verify_sha256(p, "b" * 64) is False

    def test_empty_expected_skips_and_passes(self, tmp_path):
        p = tmp_path / "f.zip"
        p.write_bytes(b"anything")
        assert verify_sha256(p, "") is True

    def test_case_insensitive(self, tmp_path):
        p = tmp_path / "f.zip"
        p.write_bytes(b"data")
        digest = hashlib.sha256(b"data").hexdigest().upper()
        assert verify_sha256(p, digest) is True

    def test_missing_file_fails(self, tmp_path):
        p = tmp_path / "nope.zip"
        assert verify_sha256(p, "a" * 64) is False

    def test_file_sha256_roundtrip(self, tmp_path):
        p = tmp_path / "f.bin"
        p.write_bytes(b"\x00\x01\x02\x03")
        assert _file_sha256(p) == hashlib.sha256(b"\x00\x01\x02\x03").hexdigest()


class TestValidatePartialForUrl:
    """Range-resume safety guard — resume only when the sidecar URL matches."""

    def test_no_dest_returns_zero(self, tmp_path):
        dest = tmp_path / "part.zip"
        assert _validate_partial_for_url(dest, "https://x/a.zip") == 0

    def test_matching_url_resumes_from_size(self, tmp_path):
        dest = tmp_path / "part.zip"
        dest.write_bytes(b"0123456789")  # 10 bytes
        _write_resume_sidecar(dest, "https://x/a.zip")
        assert _validate_partial_for_url(dest, "https://x/a.zip") == 10
        assert dest.exists()  # not discarded

    def test_mismatched_url_discards(self, tmp_path):
        dest = tmp_path / "part.zip"
        dest.write_bytes(b"0123456789")
        _write_resume_sidecar(dest, "https://x/OLD.zip")
        assert _validate_partial_for_url(dest, "https://x/NEW.zip") == 0
        assert not dest.exists()  # wiped for a clean fresh download
        assert not _resume_sidecar_path(dest).exists()

    def test_missing_sidecar_discards(self, tmp_path):
        dest = tmp_path / "part.zip"
        dest.write_bytes(b"0123456789")  # partial but no sidecar
        assert _validate_partial_for_url(dest, "https://x/a.zip") == 0
        assert not dest.exists()
