"""Free-tier rate limit lookup per Gemini model.

Source: Google AI Studio public free-tier limits as of 2026 Q1. Limits
shift over time — Google updates them without bumping any API version
or release tag. Treat values here as best-effort defaults; paid-tier
users should ignore the quota bars entirely.

The lookup uses **partial substring matching** (more specific first)
so a model name like `gemini-3.1-flash-lite-preview-09-2025` still
resolves to the 3.1-flash-lite-preview entry. Unknown models fall
back to a conservative DEFAULT_QUOTA.

Caller pattern:
    from core.quotas import get_quota
    q = get_quota(app_state.model)
    # q.rpm, q.tpm, q.rpd are the limits for that model
"""
from __future__ import annotations

from typing import NamedTuple


class ModelQuota(NamedTuple):
    rpm: int  # requests per minute
    tpm: int  # tokens per minute (combined input + output)
    rpd: int  # requests per day


# Conservative fallback for unrecognized models. Lower than any
# known production tier so we don't accidentally claim a higher
# ceiling than the API actually grants.
DEFAULT_QUOTA = ModelQuota(rpm=10, tpm=250_000, rpd=250)


# Partial-match table — first match wins, so list MORE-SPECIFIC keys
# BEFORE their less-specific siblings (e.g. "3.1-flash-lite-preview"
# must come before "3.1-flash-lite", and "3.1-flash" must come AFTER
# "3.1-flash-lite" so it doesn't shadow it).
_MODEL_QUOTAS: list[tuple[str, ModelQuota]] = [
    # ─── Gemini 3.1 ───
    ("3.1-flash-lite-preview", ModelQuota(15, 250_000, 500)),
    ("3.1-flash-lite",         ModelQuota(15, 250_000, 1000)),
    ("3.1-flash-preview",      ModelQuota(10, 250_000, 250)),
    ("3.1-flash",              ModelQuota(10, 250_000, 250)),
    ("3.1-pro-preview",        ModelQuota(5,  125_000, 25)),
    ("3.1-pro",                ModelQuota(5,  125_000, 25)),
    # ─── Gemini 3 (no .1) ───
    ("3-flash-preview",        ModelQuota(10, 250_000, 250)),
    ("3-flash",                ModelQuota(10, 250_000, 250)),
    # ─── Gemini 2.5 ───
    ("2.5-flash-lite-preview", ModelQuota(15, 250_000, 1000)),
    ("2.5-flash-lite",         ModelQuota(15, 250_000, 1000)),
    ("2.5-flash-preview",      ModelQuota(10, 250_000, 250)),
    ("2.5-flash",              ModelQuota(10, 250_000, 250)),
    ("2.5-pro",                ModelQuota(5,  250_000, 100)),
    # ─── Gemini 2.0 ───
    ("2.0-flash-lite",         ModelQuota(30, 1_000_000, 1500)),
    ("2.0-flash",              ModelQuota(15, 1_000_000, 1500)),
    # ─── Gemini 1.5 (deprecated but users may still pick) ───
    ("1.5-flash-8b",           ModelQuota(15, 1_000_000, 1500)),
    ("1.5-flash",              ModelQuota(15, 1_000_000, 1500)),
    ("1.5-pro",                ModelQuota(2,   32_000,  50)),
]


def get_quota(model_name: str) -> ModelQuota:
    """Return free-tier quota for `model_name`, or DEFAULT_QUOTA if
    we don't recognize it. Case-insensitive substring match."""
    if not model_name:
        return DEFAULT_QUOTA
    name = model_name.lower()
    for key, quota in _MODEL_QUOTAS:
        if key in name:
            return quota
    return DEFAULT_QUOTA


def quota_summary(model_name: str) -> str:
    """Short, UI-friendly summary string for the chosen model.
    Example: 'RPM 15  ·  TPM 250K  ·  RPD 500'."""
    q = get_quota(model_name)
    def _fmt(n: int) -> str:
        if n >= 1_000_000:
            return f"{n // 1_000_000}M"
        if n >= 1_000:
            return f"{n // 1_000}K"
        return str(n)
    return f"RPM {q.rpm}   TPM {_fmt(q.tpm)}   RPD {q.rpd}"
