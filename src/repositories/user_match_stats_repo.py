"""UserMatchStatsRepository — per-player match results queries and persistence."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from config.settings import Config
from models.match import Match
from models.trait_stats import TraitStats
from models.unit_stats import UnitStats, UnitStatsItem
from models.user_match_stats import UserMatchStats
from repositories.base import AbstractRepository
from schemas.match import ItemSchema, MatchSchema, TraitSchema, UnitSchema
from schemas.player import SetSummarySchema

log = logging.getLogger(__name__)


class UserMatchStatsRepository(AbstractRepository):
    """Owns all read/write operations on :class:`~models.user_match_stats.UserMatchStats`.

    Read methods return fully mapped Pydantic schemas so that the service layer
    never has to touch ORM objects.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session)

    # ── ORM → Schema mapping ─────────────────────────────────────────────────

    @staticmethod
    def _map_to_schema(ums: UserMatchStats) -> MatchSchema:
        """Convert a :class:`~models.user_match_stats.UserMatchStats` ORM row
        (with its eagerly-loaded relationships) into a :class:`~schemas.match.MatchSchema`.
        """
        return MatchSchema(
            match_id=ums.match_id,
            placement=ums.placement,
            level=ums.level,
            gold_left=ums.gold_left,
            last_round=ums.last_round,
            players_eliminated=ums.players_eliminated,
            total_damage_to_players=ums.damage_to_players,
            time_eliminated=ums.time_eliminated,
            augments=ums.augments or [],
            traits=[
                TraitSchema(
                    name=ts.trait_id,
                    icon_url=ts.trait.icon_url if ts.trait else None,
                    num_units=ts.num_units or 0,
                    style=ts.style or 0,
                    tier_current=ts.tier_current or 0,
                    tier_total=ts.tier_total or 0,
                )
                for ts in ums.trait_stats
            ],
            units=[
                UnitSchema(
                    character_id=us.unit_id,
                    icon_url=us.unit.icon_url if us.unit else None,
                    rarity=us.unit.rarity if us.unit else 0,
                    stars=us.unit_tier or 0,
                    items=[
                        ItemSchema(
                            item_id=usi.item_id,
                            icon_url=usi.item.icon_url if usi.item else None,
                        )
                        for usi in us.unit_stat_items
                    ],
                )
                for us in ums.unit_stats
            ],
        )

    # ── Commands ──────────────────────────────────────────────────────────────

    def save(
        self,
        match_id: str,
        puuid: str,
        placement: int | None,
        damage_to_players: int | None,
        gold_left: int | None,
        last_round: int | None,
        level: int | None,
        players_eliminated: int | None,
        time_eliminated: float | None,
        win: bool,
        augments: list[str],
    ) -> bool:
        """Upsert a :class:`~models.user_match_stats.UserMatchStats` row.

        Returns ``True`` if a **new** row was inserted, ``False`` if it was
        already present (so callers can skip writing child entities).
        """
        result = self._upsert(
            UserMatchStats,
            {
                "match_id": match_id,
                "puuid": puuid,
                "placement": placement,
                "damage_to_players": damage_to_players,
                "gold_left": gold_left,
                "last_round": last_round,
                "level": level,
                "players_eliminated": players_eliminated,
                "time_eliminated": time_eliminated,
                "win": win,
                "augments": augments,
            },
        )
        return bool(result.rowcount)

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_by_puuid_and_ids(
        self, puuid: str, match_ids: list[str]
    ) -> list[MatchSchema]:
        """Return :class:`~schemas.match.MatchSchema` objects for the given
        *puuid* filtered to the specified *match_ids* within the current TFT set.
        """
        log.debug(
            "Loading participant stats  puuid=%.12s...  match_ids=%s",
            puuid,
            match_ids,
        )
        rows: list[UserMatchStats] = (
            self._session.query(UserMatchStats)
            .filter(
                UserMatchStats.puuid == puuid,
                UserMatchStats.match_id.in_(match_ids),
            )
            .join(Match, Match.match_id == UserMatchStats.match_id)
            .filter(Match.tft_set_number == Config.CURRENT_SET)
            .all()
        )
        log.info(
            "Participant stats loaded: %d/%d rows from DB (set=%d)",
            len(rows),
            len(match_ids),
            Config.CURRENT_SET,
        )
        return [self._map_to_schema(r) for r in rows]

    def get_recent(self, puuid: str, limit: int = 5) -> list[MatchSchema]:
        """Return the *limit* most-recent :class:`~schemas.match.MatchSchema` objects
        for *puuid* within the current TFT set, ordered newest-first.
        """
        log.debug(
            "Loading recent participant stats  puuid=%.12s...  limit=%d  set=%d",
            puuid,
            limit,
            Config.CURRENT_SET,
        )
        rows: list[UserMatchStats] = (
            self._session.query(UserMatchStats)
            .filter(UserMatchStats.puuid == puuid)
            .join(Match, Match.match_id == UserMatchStats.match_id)
            .filter(Match.tft_set_number == Config.CURRENT_SET)
            .order_by(Match.game_datetime.desc())
            .limit(limit)
            .all()
        )
        log.info(
            "Recent participant stats: %d rows (limit=%d, set=%d)",
            len(rows),
            limit,
            Config.CURRENT_SET,
        )
        return [self._map_to_schema(r) for r in rows]

    def get_set_summary(self, puuid: str) -> SetSummarySchema:
        """Compute aggregate stats (avg placement, top-4 rate, win rate) for
        *puuid* across all matches in the current TFT set.
        """
        rows = (
            self._session.query(UserMatchStats.placement, UserMatchStats.win)
            .join(Match, Match.match_id == UserMatchStats.match_id)
            .filter(
                UserMatchStats.puuid == puuid,
                Match.tft_set_number == Config.CURRENT_SET,
            )
            .all()
        )
        total: int = len(rows)
        placements: list[int] = [r.placement for r in rows if r.placement is not None]
        wins: int = sum(1 for r in rows if r.win)
        top4: int = sum(1 for p in placements if p <= 4)
        avg: float | None = (
            round(sum(placements) / len(placements), 2) if placements else None
        )
        log.info(
            "Set summary  puuid=%.12s...  total=%d  avg=%s  top4=%d  wins=%d",
            puuid,
            total,
            avg,
            top4,
            wins,
        )
        return SetSummarySchema(
            total_games=total,
            avg_placement=avg,
            top4_count=top4,
            win_count=wins,
        )
