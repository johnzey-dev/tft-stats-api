"""MatchIngestionService — orchestrates persisting a raw Riot match payload.

This service is the *only* place that knows how to decompose a Riot API
``match_detail`` dict and fan it out into the normalised DB schema.  All actual
DB writes are delegated to repositories through a :class:`~unit_of_work.SqlAlchemyUnitOfWork`
so that the entire match lands in a single atomic transaction.
"""

from __future__ import annotations

import logging

from models.trait_stats import TraitStats
from schemas.match import MatchSchema
from schemas.player import SetSummarySchema
from unit_of_work import SqlAlchemyUnitOfWork
from utils.icons import item_icon_url, trait_icon_url, unit_icon_url

log = logging.getLogger(__name__)


class MatchIngestionService:
    """Coordinates reading/writing match data via the repository layer.

    Replaces the old ``MatchCache`` God class:

    - **Cache checks** → :py:meth:`get_missing_ids`
    - **Ingestion**    → :py:meth:`store_match`  (atomic UoW transaction)
    - **Queries**      → delegated to :class:`~repositories.user_match_stats_repo.UserMatchStatsRepository`
      via a read-only UoW
    """

    # ── Cache management ─────────────────────────────────────────────────────

    def get_missing_ids(self, match_ids: list[str]) -> list[str]:
        """Return the subset of *match_ids* not yet persisted in the DB."""
        with SqlAlchemyUnitOfWork() as uow:
            return uow.matches.get_missing_ids(match_ids)

    def store_match(self, match_data: dict) -> None:  # noqa: C901 (complexity acceptable for an ingestion pipeline)
        """Decompose a raw Riot ``match_detail`` payload and persist every entity.

        The entire operation is wrapped in a single Unit of Work transaction:
        if anything fails, the whole match is rolled back and not partially
        saved.
        """
        match_id: str = match_data["metadata"]["match_id"]
        info: dict = match_data["info"]

        participants: list[dict] = [
            p
            for p in info.get("participants", [])
            if p.get("puuid") and p["puuid"] != "BOT"
        ]
        log.info(
            "Storing match %s  [%d participants, set=%s, version=%s]",
            match_id,
            len(participants),
            info.get("tft_set_number"),
            info.get("game_version"),
        )

        with SqlAlchemyUnitOfWork() as uow:
            # ── Match header ─────────────────────────────────────────────────
            uow.matches.save(
                match_id=match_id,
                game_datetime=info.get("game_datetime"),
                game_length=info.get("game_length"),
                game_version=info.get("game_version"),
                tft_set_number=info.get("tft_set_number"),
            )

            for participant in participants:
                puuid: str = participant["puuid"]
                log.debug(
                    "  Participant puuid=%.12s...  placement=%s  units=%d  traits=%d",
                    puuid,
                    participant.get("placement"),
                    len(participant.get("units", [])),
                    len(participant.get("traits", [])),
                )

                # ── User ─────────────────────────────────────────────────────
                uow.users.save(
                    puuid=puuid,
                    game_name=participant.get("riotIdGameName", ""),
                    tag_line=participant.get("riotIdTagline", ""),
                )

                # ── UserMatchStats ────────────────────────────────────────────
                inserted: bool = uow.stats.save(
                    match_id=match_id,
                    puuid=puuid,
                    placement=participant.get("placement"),
                    damage_to_players=participant.get("total_damage_to_players"),
                    gold_left=participant.get("gold_left"),
                    last_round=participant.get("last_round"),
                    level=participant.get("level"),
                    players_eliminated=participant.get("players_eliminated"),
                    time_eliminated=participant.get("time_eliminated"),
                    win=participant.get("win", False),
                    augments=participant.get("augments", []),
                )

                if not inserted:
                    log.debug(
                        "  Skipping puuid=%.12s... — already stored for %s",
                        puuid,
                        match_id,
                    )
                    continue

                # ── Units, items, traits (only for newly inserted rows) ──────
                seen_units: set[str] = set()
                seen_items: set[str] = set()
                seen_traits: set[str] = set()

                for unit_data in participant.get("units", []):
                    unit_id: str | None = unit_data.get("character_id")
                    if not unit_id:
                        continue

                    if unit_id not in seen_units:
                        uow.units.save_reference(
                            unit_id=unit_id,
                            rarity=unit_data.get("rarity"),
                            icon_url=unit_icon_url(unit_id),
                        )
                        seen_units.add(unit_id)

                    item_ids: list[str] = [
                        iid
                        for iid in unit_data.get("itemNames", [])
                        if iid
                    ]
                    for item_id in item_ids:
                        if item_id not in seen_items:
                            uow.items.save(
                                item_id=item_id,
                                icon_url=item_icon_url(item_id),
                            )
                            seen_items.add(item_id)

                    uow.units.save_unit_stats(
                        match_id=match_id,
                        puuid=puuid,
                        unit_id=unit_id,
                        unit_tier=unit_data.get("tier"),
                        item_ids=item_ids,
                    )

                for trait_data in participant.get("traits", []):
                    trait_id: str | None = trait_data.get("name")
                    if not trait_id:
                        continue

                    if trait_id not in seen_traits:
                        uow.traits.save(
                            trait_id=trait_id,
                            icon_url=trait_icon_url(trait_id),
                        )
                        seen_traits.add(trait_id)

                    uow.stats._upsert(  # TraitStats has a composite PK — upsert is safe
                        TraitStats,
                        {
                            "match_id": match_id,
                            "puuid": puuid,
                            "trait_id": trait_id,
                            "num_units": trait_data.get("num_units"),
                            "style": trait_data.get("style"),
                            "tier_current": trait_data.get("tier_current"),
                            "tier_total": trait_data.get("tier_total"),
                        },
                    )

            uow.commit()
            log.debug("Match %s committed to DB", match_id)

    # ── Read-through queries ──────────────────────────────────────────────────

    def get_participant_stats(
        self, puuid: str, match_ids: list[str]
    ) -> list[MatchSchema]:
        """Return cached match schemas for *puuid* filtered to *match_ids*."""
        with SqlAlchemyUnitOfWork() as uow:
            return uow.stats.get_by_puuid_and_ids(puuid, match_ids)

    def get_recent_participant_stats(
        self, puuid: str, limit: int = 5
    ) -> list[MatchSchema]:
        """Return the *limit* most-recent cached matches for *puuid*."""
        with SqlAlchemyUnitOfWork() as uow:
            return uow.stats.get_recent(puuid, limit=limit)

    def get_set_summary(self, puuid: str) -> SetSummarySchema:
        """Return aggregate stats for *puuid* across the current TFT set."""
        with SqlAlchemyUnitOfWork() as uow:
            return uow.stats.get_set_summary(puuid)
