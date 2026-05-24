"""Tests for core.config — python_executable + QUOTA_* deprecation.

v2.5.1 fixed `python_executable()` to NOT return `sys.executable`
in frozen mode (where it points to HappyAIAgent.exe, not Python).
Source-mode behaviour must keep working — these tests pin it.

v2.5.1 also added DeprecationWarning to QUOTA_RPM/TPM/RPD via
module __getattr__. The warning must fire on first access and the
back-compat values must still resolve so external callers don't
break suddenly.
"""
import sys
import warnings

import pytest

from core import config


class TestPythonExecutable:
    def test_source_mode_returns_real_python(self):
        """Running under pytest = source mode (not frozen). Should
        return sys.executable directly."""
        # Pytest itself is launched via python.exe, so sys.frozen is unset.
        assert not getattr(sys, "frozen", False)
        result = config.python_executable()
        assert result is not None
        assert "python" in str(result).lower()

    def test_returns_string_or_none(self):
        """API contract: str or None — never raises."""
        result = config.python_executable()
        assert result is None or isinstance(result, str)


class TestQuotaDeprecation:
    def test_quota_rpm_emits_deprecation_warning(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _ = config.QUOTA_RPM
        assert any(
            issubclass(w.category, DeprecationWarning) for w in caught
        ), "QUOTA_RPM access should emit DeprecationWarning"

    def test_quota_tpm_emits_deprecation_warning(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _ = config.QUOTA_TPM
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)

    def test_quota_rpd_emits_deprecation_warning(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _ = config.QUOTA_RPD
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)

    def test_quota_values_still_resolve_for_backcompat(self):
        # Suppress warnings — we just want to check the values exist.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assert config.QUOTA_RPM == 15
            assert config.QUOTA_TPM == 250_000
            assert config.QUOTA_RPD == 500

    def test_unknown_attribute_still_raises(self):
        """__getattr__ should only intercept the deprecated names; any
        other unknown attribute must still raise AttributeError."""
        with pytest.raises(AttributeError):
            _ = config.SOMETHING_THAT_DOES_NOT_EXIST


class TestConstants:
    def test_version_is_nonempty(self):
        assert config.VERSION
        assert config.VERSION != "0.0.0"  # We always ship with a real version

    def test_app_root_exists(self):
        assert config.APP_ROOT.exists()

    def test_user_data_exists(self):
        # config.py creates USER_DATA on import.
        assert config.USER_DATA.exists()

    def test_default_settings_has_required_keys(self):
        for key in ("model", "delay", "judge_threshold",
                    "max_judge_loops", "pipeline_mode"):
            assert key in config.DEFAULT_SETTINGS
