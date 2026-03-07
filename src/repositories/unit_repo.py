"""UnitRepository — TFT champion reference-data and per-match unit persistence."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from models.unit import Unit
from models.unit_stats import UnitStats, UnitStatsItem
from repositories.base import AbstractRepository

log = logging.getLogger(__name__)


class UnitRepository(AbstractRepository):
    """Handles :class:`~models.unit.Unit`, :class:`~models.unit_stats.UnitStats`
    and :class:`~models.unit_stats.UnitStatsItem` persistence.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session)

    # ── Commands ──────────────────────────────────────────────────────────────

    def save_reference(self, unit_id: str, rarity: int | None, icon_url: str) -> None:
        """Upsert a :class:`~models.unit.Unit` reference row (INSERT OR IGNORE)."""
        self._upsert(Unit, {"unit_id": unit_id, "rarity": rarity, "icon_url": icon_url})

    def save_unit_stats(
        self,
        match_id: str,
        puuid: str,
        unit_id: str,
        unit_tier: int | None,
        item_ids: list[str],
    ) -> None:
        """Persist a :class:`~models.unit_stats.UnitStats` row and its items.

        This intentionally uses ``session.add`` + ``session.flush`` so that the
        auto-generated primary key is available for the child
        :class:`~models.unit_stats.UnitStatsItem` rows immediately.
        """
        unit_stats = UnitStats(
            match_id=match_id,
            puuid=puuid,
            unit_id=unit_id,
            unit_tier=unit_tier,
        )
        self._session.add(unit_stats)
        self._session.flush()

        for item_id in item_ids:
            if item_id:
                self._session.add(
                    UnitStatsItem(unit_stats_id=unit_stats.id, item_id=item_id)
                )
        log.debug(
            "Saved UnitStats: match=%s puuid=%.12s... unit=%s tier=%s items=%s",
            match_id,
            puuid,
            unit_id,
            unit_tier,
            item_ids,
        )
