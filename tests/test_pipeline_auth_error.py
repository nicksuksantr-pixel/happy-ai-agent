"""Tests for v2.6.0 AuthError detection in _call_with_retry.

Why this matters:
- Auth failures (401, PERMISSION_DENIED, API_KEY_INVALID) are NOT
  transient — retrying just burns quota and leaves the user staring
  at a hanging "Working on Coder…" status for minutes.
- _is_auth_error() must catch the strings Gemini actually emits.
- _call_with_retry must raise AuthError (not the underlying generic
  exception) so app.py can route it to the re-auth modal instead of
  the generic "Pipeline error" box.
"""
import pytest

from pipeline import (
    AuthError,
    _call_with_retry,
    _is_auth_error,
    _is_transient,
)


class TestIsAuthError:
    @pytest.mark.parametrize("msg", [
        "401 unauthenticated",
        "401 UNAUTHORIZED",
        "PERMISSION_DENIED: API_KEY_INVALID",
        "permission denied",
        "API key not valid. Please pass a valid API key.",
        "API_KEY_INVALID",
        "Invalid API key",
    ])
    def test_detects_auth_error(self, msg):
        assert _is_auth_error(Exception(msg)) is True

    @pytest.mark.parametrize("msg", [
        "503 unavailable",
        "rate limit exceeded",
        "internal error",
        "empty response",
        "connection refused",
    ])
    def test_non_auth_errors_not_flagged(self, msg):
        assert _is_auth_error(Exception(msg)) is False

    def test_auth_errors_NOT_marked_transient(self):
        """Belt-and-braces: an auth error must not also be in the
        transient set, otherwise _call_with_retry's auth check could
        race with the retry check."""
        for msg in ("401 unauthenticated", "API_KEY_INVALID"):
            err = Exception(msg)
            # _is_auth_error always wins in _call_with_retry, but we
            # also don't want it accidentally in the transient list.
            assert not _is_transient(err)


class TestCallWithRetryAuth:
    def test_auth_error_raises_immediately_no_retry(self):
        """First call raises 401 → _call_with_retry should NOT retry,
        should raise AuthError immediately."""
        call_count = {"n": 0}

        def fn():
            call_count["n"] += 1
            raise Exception("401 UNAUTHENTICATED: API_KEY_INVALID")

        with pytest.raises(AuthError) as exc_info:
            _call_with_retry(fn)
        assert call_count["n"] == 1, "auth errors must not be retried"
        # AuthError wraps the original message
        assert "401" in str(exc_info.value) or "AUTH" in str(exc_info.value).upper()

    def test_transient_error_still_retries(self):
        """Sanity: non-auth transient errors should still go through
        the retry loop (we didn't break the existing behaviour)."""
        # We'll patch RETRY_DELAYS to all zeros so the test runs fast.
        import pipeline
        from unittest.mock import patch

        call_count = {"n": 0}

        def fn():
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise Exception("internal error")
            return "ok"

        with patch.object(pipeline, "RETRY_DELAYS", [0, 0, 0, 0, 0]):
            result = _call_with_retry(fn)

        assert result == "ok"
        assert call_count["n"] == 3

    def test_auth_error_preserves_original_message(self):
        """AuthError(str(e)[:300]) must keep the message readable so
        the UI modal can show it to the user."""
        def fn():
            raise Exception(
                "google.api_core.exceptions.PermissionDenied: "
                "403 API key not valid. Please pass a valid API key."
            )

        with pytest.raises(AuthError) as exc_info:
            _call_with_retry(fn)
        # The "permission" or "API key not valid" substring must be in
        # the re-raised AuthError so the modal text helps the user.
        msg = str(exc_info.value).lower()
        assert "api key" in msg or "permission" in msg
