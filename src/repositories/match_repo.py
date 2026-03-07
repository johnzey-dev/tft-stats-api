"""MatchRepository — cache-existence checks and match persistence."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from models.match import Match
from repositories.base import AbstractRepository

log = logging.getLogger(__name__)


class MatchRepository(AbstractRepository):
    """Handles the :class:`~models.match.Match` aggregate."""

    def __init__(self, session: Session) -> None:
        super().__init__(session)

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_cached_ids(self, match_ids: list[str]) -> set[str]:
        """Return the subset of *match_ids* that are already persisted."""
        if not match_ids:
            return set()
        rows = (
            self._session.query(Match.match_id)
            .filter(Match.match_id.in_(match_ids))
            .all()
        )
        return {row.match_id for row in rows}

    def get_missing_ids(self, match_ids: list[str]) -> list[str]:
        """Return only the IDs from *match_ids* that are **not** yet cached.

        Preserves the original ordering so callers can use the first N entries
        as the most-recent matches.
        """
        cached = self.get_cached_ids(match_ids)
        missing = [mid for mid in match_ids if mid not in cached]
        log.info(
            "Cache check: %d requested, %d cached, %d missing",
            len(match_ids),
            len(cached),
            len(missing),
        )
        return missing

    # ── Commands ──────────────────────────────────────────────────────────────

    def save(
        self,
        match_id: str,
        game_datetime: float | None,
        game_length: float | None,
        game_version: str | None,
        tft_set_number: int | None,
    ) -> None:
        """Upsert a :class:`~models.match.Match` row (INSERT OR IGNORE)."""
        self._upsert(
            Match,
            {
                "match_id": match_id,
                "game_datetime": game_datetime,
                "game_length": game_length,
                "game_version": game_version,
                "tft_set_number": tft_set_number,
            },
        )
