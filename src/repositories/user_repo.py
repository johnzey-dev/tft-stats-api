"""UserRepository — player identity persistence."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from models.user import User
from repositories.base import AbstractRepository

log = logging.getLogger(__name__)


class UserRepository(AbstractRepository):
    """Handles the :class:`~models.user.User` aggregate."""

    def __init__(self, session: Session) -> None:
        super().__init__(session)

    # ── Queries ───────────────────────────────────────────────────────────────

    def find_by_riot_id(self, game_name: str, tag_line: str) -> User | None:
        """Look up a :class:`~models.user.User` by their Riot game name + tag.

        The comparison is **case-insensitive** so that ``John#EUW`` and
        ``john#euw`` resolve to the same player.
        """
        user: User | None = (
            self._session.query(User)
            .filter(
                User.game_name.ilike(game_name),
                User.tag_line.ilike(tag_line),
            )
            .first()
        )
        if user:
            log.debug("User cache hit: puuid=%.12s...", user.puuid)
        return user

    # ── Commands ──────────────────────────────────────────────────────────────

    def save(self, puuid: str, game_name: str, tag_line: str) -> None:
        """Upsert a :class:`~models.user.User` row (INSERT OR IGNORE)."""
        self._upsert(
            User,
            {
                "puuid": puuid,
                "game_name": game_name,
                "tag_line": tag_line,
            },
        )
