"""Tests for auth.is_valid_key_format — pre-flight Gemini key check.

The check is intentionally permissive (don't reject valid keys), but
should still catch obvious garbage so the user gets a useful error
instead of a Gemini 400 deep in the pipeline.
"""
from auth import is_valid_key_format, save_api_key, load_api_key, clear_api_key


class TestIsValidKeyFormat:
    def test_valid_key_format(self):
        # Synthetic key shaped like the real format (39 chars, starts AIza)
        fake = "AIza" + "A" * 35
        assert is_valid_key_format(fake) is True

    def test_too_short_rejected(self):
        assert is_valid_key_format("AIzaShort") is False

    def test_wrong_prefix_rejected(self):
        assert is_valid_key_format("XYza" + "A" * 35) is False

    def test_empty_string_rejected(self):
        assert is_valid_key_format("") is False

    def test_none_safe(self):
        assert is_valid_key_format(None) is False

    def test_whitespace_only_rejected(self):
        # Leading/trailing whitespace gets stripped THEN checked
        assert is_valid_key_format("   ") is False

    def test_whitespace_around_valid_key_accepted(self):
        fake = "AIza" + "A" * 35
        assert is_valid_key_format(f"  {fake}  ") is True


class TestKeyPersistence:
    """Round-trip save → load → clear, with the safe_user_data fixture
    redirecting writes to a tmp dir (NEVER touch ~/.happy/auth.json)."""

    def test_save_and_load(self, safe_user_data):
        fake = "AIza" + "B" * 35
        ok, _msg = save_api_key(fake)
        assert ok
        assert load_api_key() == fake

    def test_load_returns_none_when_missing(self, safe_user_data):
        assert load_api_key() is None

    def test_clear_removes_file(self, safe_user_data):
        fake = "AIza" + "C" * 35
        save_api_key(fake)
        assert load_api_key() == fake
        clear_api_key()
        assert load_api_key() is None

    def test_save_overwrites_previous(self, safe_user_data):
        first = "AIza" + "1" * 35
        second = "AIza" + "2" * 35
        save_api_key(first)
        save_api_key(second)
        assert load_api_key() == second
