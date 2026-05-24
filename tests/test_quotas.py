"""Tests for core.quotas — model→ModelQuota substring lookup.

Why this matters:
- The substring-match-first-wins ordering is fragile. New entries
  must be added in MORE-SPECIFIC → LESS-SPECIFIC order so e.g.
  `3.1-flash-lite-preview` doesn't get shadowed by `3.1-flash-lite`.
- get_quota() is called from running.py / settings.py / stats.py
  every UI tick; wrong values silently mislead the user (the very
  bug Nick caught in v2.4.9 → v2.5.0).
"""
from core.quotas import (
    DEFAULT_QUOTA,
    ModelQuota,
    get_quota,
    quota_summary,
)


class TestGetQuota:
    def test_unknown_model_returns_default(self):
        q = get_quota("totally-made-up-model-name-9000")
        assert q == DEFAULT_QUOTA

    def test_empty_string_returns_default(self):
        assert get_quota("") == DEFAULT_QUOTA

    def test_none_safe(self):
        # get_quota guards on falsy input; passing None must not crash.
        assert get_quota(None) == DEFAULT_QUOTA

    def test_case_insensitive(self):
        a = get_quota("Gemini-3.1-Flash-Lite")
        b = get_quota("gemini-3.1-flash-lite")
        assert a == b

    def test_substring_match_more_specific_wins(self):
        """3.1-flash-lite-preview must NOT be shadowed by 3.1-flash-lite.
        This is the ordering-fragility test — if someone reorders the
        table and puts the less-specific key first, this fails."""
        preview = get_quota("gemini-3.1-flash-lite-preview")
        plain   = get_quota("gemini-3.1-flash-lite")
        # Preview has stricter RPD than the non-preview tier.
        assert preview.rpd < plain.rpd, (
            f"preview RPD ({preview.rpd}) should be < non-preview "
            f"RPD ({plain.rpd}) — substring ordering is broken"
        )

    def test_preview_with_date_suffix_still_matches_preview(self):
        """Real API returns names like `gemini-3.1-flash-lite-preview-09-2025`.
        Substring match must still resolve to the preview entry."""
        q = get_quota("gemini-3.1-flash-lite-preview-09-2025")
        # Should match the preview row (not the plain row).
        assert q == get_quota("gemini-3.1-flash-lite-preview")

    def test_known_models_have_sane_limits(self):
        for name in (
            "gemini-3.1-flash-lite",
            "gemini-2.5-flash-lite",
            "gemini-2.0-flash",
            "gemini-1.5-flash",
        ):
            q = get_quota(name)
            assert isinstance(q, ModelQuota)
            assert q.rpm > 0 and q.tpm > 0 and q.rpd > 0

    def test_pro_models_have_lower_rpd_than_lite(self):
        """Sanity: pro tiers should always have lower RPD than lite tiers."""
        pro  = get_quota("gemini-2.5-pro")
        lite = get_quota("gemini-2.5-flash-lite")
        assert pro.rpd < lite.rpd


class TestQuotaSummary:
    def test_format_contains_all_three_limits(self):
        s = quota_summary("gemini-3.1-flash-lite-preview")
        assert "RPM" in s
        assert "TPM" in s
        assert "RPD" in s

    def test_format_compacts_large_numbers(self):
        # 1_000_000 should be rendered as 1M, not 1000000
        s = quota_summary("gemini-2.0-flash")
        assert "1M" in s or "K" in s  # one of the compactions fired
