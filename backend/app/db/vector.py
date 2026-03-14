from __future__ import annotations

from typing import Any

from sqlalchemy.types import JSON, TypeDecorator

try:
    from pgvector.sqlalchemy import Vector as PGVector
except Exception:  # pragma: no cover - optional dependency at runtime
    PGVector = None


def pgvector_available() -> bool:
    return PGVector is not None


class FlexibleVector(TypeDecorator[list[float]]):
    impl = JSON
    cache_ok = True

    def __init__(self, dim: int) -> None:
        super().__init__()
        self.dim = dim

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql" and PGVector is not None:
            return dialect.type_descriptor(PGVector(self.dim))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: Any, dialect):
        if value is None:
            return []
        if isinstance(value, tuple):
            value = list(value)
        if dialect.name == "postgresql" and PGVector is not None:
            return list(value)
        return list(value)

    def process_result_value(self, value: Any, dialect):
        if value is None:
            return []
        if isinstance(value, tuple):
            return list(value)
        if isinstance(value, list):
            return value
        try:
            return list(value)
        except TypeError:
            return []
