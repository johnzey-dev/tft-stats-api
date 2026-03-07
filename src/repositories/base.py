"""AbstractRepository — base class for all SQLAlchemy repositories.

Every concrete repository receives the SQLAlchemy *session* object at
construction time so that the Unit of Work can control transaction boundaries.
"""

from __future__ import annotations

from typing import Any, TypeVar

from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")


class AbstractRepository:
    """Lightweight base that exposes an INSERT-OR-IGNORE helper."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _upsert(self, model: type, values: dict[str, Any]) -> Any:
        """Execute ``INSERT OR IGNORE`` for *model* with the given column values.

        Returns the :class:`~sqlalchemy.engine.CursorResult` produced by the
        statement, which callers can inspect for ``rowcount`` when they need to
        know whether a new row was actually inserted.
        """
        stmt = insert(model).values(values).on_conflict_do_nothing()
        return self._session.execute(stmt)
