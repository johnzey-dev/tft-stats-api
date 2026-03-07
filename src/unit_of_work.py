"""Unit of Work — coordinates transactions across all repositories.

Usage (inside a Flask application context)::

    from unit_of_work import SqlAlchemyUnitOfWork

    with SqlAlchemyUnitOfWork() as uow:
        uow.matches.save(match_id, ...)
        uow.users.save(puuid, ...)
        uow.commit()   # explicit commit; auto-rollback on exception

The UoW owns **one** :pyobj:`~sqlalchemy.orm.Session` per context-manager
invocation and wires all repositories to that session, guaranteeing that every
write within a ``with`` block lands in a single atomic transaction.
"""

from __future__ import annotations

import logging
from types import TracebackType
from typing import Self

from extensions import db
from repositories.item_repo import ItemRepository
from repositories.match_repo import MatchRepository
from repositories.trait_repo import TraitRepository
from repositories.unit_repo import UnitRepository
from repositories.user_match_stats_repo import UserMatchStatsRepository
from repositories.user_repo import UserRepository

log = logging.getLogger(__name__)


class SqlAlchemyUnitOfWork:
    """Context manager that scopes a set of repository operations to one
    SQLAlchemy session transaction.

    All repositories share the same :attr:`session` so that SQLAlchemy's
    identity map deduplicates objects and flushes happen in a predictable order.
    """

    def __init__(self) -> None:
        self._session = db.session

    # ── Repository accessors ─────────────────────────────────────────────────

    @property
    def matches(self) -> MatchRepository:
        return MatchRepository(self._session)

    @property
    def users(self) -> UserRepository:
        return UserRepository(self._session)

    @property
    def items(self) -> ItemRepository:
        return ItemRepository(self._session)

    @property
    def traits(self) -> TraitRepository:
        return TraitRepository(self._session)

    @property
    def units(self) -> UnitRepository:
        return UnitRepository(self._session)

    @property
    def stats(self) -> UserMatchStatsRepository:
        return UserMatchStatsRepository(self._session)

    # ── Transaction control ───────────────────────────────────────────────────

    def commit(self) -> None:
        """Flush pending changes and commit the transaction."""
        self._session.commit()
        log.debug("UoW: transaction committed")

    def rollback(self) -> None:
        """Roll back any uncommitted changes."""
        self._session.rollback()
        log.debug("UoW: transaction rolled back")

    # ── Context manager protocol ──────────────────────────────────────────────

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            log.warning("UoW: exception in block (%s), rolling back", exc_type.__name__)
            self.rollback()
        # Flask-SQLAlchemy manages the session lifecycle (scoped session);
        # we do NOT call session.close() here — Flask tears it down at
        # request teardown automatically.
