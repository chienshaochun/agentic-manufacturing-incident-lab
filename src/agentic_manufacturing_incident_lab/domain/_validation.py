"""Validation helpers shared by immutable domain records."""

from datetime import datetime


def require_text(value: str | None, field_name: str) -> None:
    """Require a non-empty string after surrounding whitespace is ignored."""
    if value is None or not value.strip():
        raise ValueError(f"{field_name} must not be blank")


def require_timezone(value: datetime, field_name: str) -> None:
    """Require an aware timestamp so records can be ordered reliably."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include timezone information")
