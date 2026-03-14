from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return a UTC timestamp compatible with the current SQLite schema."""
    return datetime.now(UTC).replace(tzinfo=None)
