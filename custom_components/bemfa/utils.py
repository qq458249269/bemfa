"""Support for bemfa service."""

from typing import Any


def has_key(data: Any, key: str) -> bool:
    """Whether data has specific valid key."""
    return key in data and data[key] is not None
