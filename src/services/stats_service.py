"""StatsService — application-layer orchestrator.

This service owns all TFT stats business logic.  It coordinates Riot API calls
and the match-ingestion pipeline, then assembles the typed Pydantic schemas
returned to route handlers.

Dependencies are **injected** at construction time through the
:class:`~services.riot_service.RiotService` and
:class:`~services.match_ingestion_service.MatchIngestionService` parameters,
making both easy to swap or mock in tests.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor

from unit_of_work import SqlAlchemyUnitOfWork
from schemas.match import MatchSchema
from schemas.player import PlayerProfileSchema, SetSummarySchema, StatsResponseSchema
from schemas.riot import LeagueEntrySchema, SummonerSchema
from services.match_ingestion_service import MatchIngestionService
from services.riot_service import RiotService
from utils.icons import tier_icon_url

log = logging.getLogger(__name__)

MATCH_LIMIT: int = 5
CACHE_BATCH_SIZE: int = 10

# ── In-memory TTL caches (survive across requests, reset on server restart) ──
# Key: (game_name.lower(), tag_line.lower())  →  (puuid, expires_at)
_PUUID_CACHE: dict[tuple[str, str], tuple[str, float]] = {}
# Key: (platform, game_name.lower(), tag_line.lower())  →  (PlayerProfileSchema, expires_at)
_PROFILE_CACHE: dict[tuple[str, str, str], tuple[object, float]] = {}

_PUUID_TTL:   int = 3600   # 1 hour  — puuid never changes
_PROFILE_TTL: int = 300    # 5 min   — rank/LP can change


class StatsService:
    """Thin orchestrator — routes must only call this class.

    Args:
        riot:      Riot API gateway (injected; defaults to :class:`~services.riot_service.RiotService`).
        ingestion: Match-cache façade (injected; defaults to :class:`~services.match_ingestion_service.MatchIngestionService`).
    """

    def __init__(
        self,
        riot: RiotService | None = None,
        ingestion: MatchIngestionService | None = None,
    ) -> None:
        self._riot: RiotService = riot or RiotService()
        self._ingestion: MatchIngestionService = ingestion or MatchIngestionService()

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _resolve_puuid(
        self, platform: str, game_name: str, tag_line: str
    ) -> str:
        """Return the player's *puuid* from memory cache, DB cache, or Riot API.

        Priority: in-memory TTL cache → SQLite users table → Riot API.
        """
        key = (game_name.lower(), tag_line.lower())
        cached = _PUUID_CACHE.get(key)
        if cached and time.time() < cached[1]:
            log.debug("puuid memory-cache hit for %s#%s", game_name, tag_line)
            return cached[0]

        with SqlAlchemyUnitOfWork() as uow:
            user = uow.users.find_by_riot_id(game_name, tag_line)

        if user:
            log.debug("User DB cache hit: puuid=%.12s...", user.puuid)
            _PUUID_CACHE[key] = (user.puuid, time.time() + _PUUID_TTL)
            return user.puuid

        log.debug("User not in DB, resolving via Riot API")
        account = self._riot.get_account_by_riot_id(platform, game_name, tag_line)
        _PUUID_CACHE[key] = (account.puuid, time.time() + _PUUID_TTL)
        return account.puuid

    def _ensure_cached(self, platform: str, match_ids: list[str]) -> None:
        """Fetch and store any *match_ids* that are not yet in the local cache."""
        missing: list[str] = self._ingestion.get_missing_ids(match_ids)
        if not missing:
            log.info(
                "All %d match(es) already cached — skipping Riot API fetch",
                len(match_ids),
            )
            return

        log.info("Fetching %d uncached match(es) from Riot API", len(missing))
        for i in range(0, len(missing), CACHE_BATCH_SIZE):
            batch: list[str] = missing[i : i + CACHE_BATCH_SIZE]
            log.debug("Batch %d–%d: fetching %s", i + 1, i + len(batch), batch)
            fresh: dict[str, dict] = self._riot.get_match_details_bulk(platform, batch)
            for match_data in fresh.values():
                self._ingestion.store_match(match_data)

    @staticmethod
    def _ranked_entry(
        entries: list[LeagueEntrySchema],
    ) -> LeagueEntrySchema | None:
        """Return the RANKED_TFT league entry, if present."""
        return next(
            (e for e in entries if e.queueType == "RANKED_TFT"), None
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def get_stats(
        self, platform: str, game_name: str, tag_line: str
    ) -> StatsResponseSchema:
        """Fetch and assemble the full JSON stats payload for a player.

        Concurrently resolves summoner, league entries, and all match IDs, then
        ensures every match is cached before building the response.
        """
        account = self._riot.get_account_by_riot_id(platform, game_name, tag_line)
        puuid: str = account.puuid

        with ThreadPoolExecutor(max_workers=3) as executor:
            f_summoner  = executor.submit(self._riot.get_summoner,       platform, puuid)
            f_league    = executor.submit(self._riot.get_league_entries, platform, puuid)
            f_match_ids = executor.submit(self._riot.get_all_match_ids,  platform, puuid)
            summoner:  SummonerSchema          = f_summoner.result()
            league:    list[LeagueEntrySchema] = f_league.result()
            match_ids: list[str]               = f_match_ids.result()

        ranked: LeagueEntrySchema | None = self._ranked_entry(league)
        log.info(
            "Player: %s  tier=%s %s  LP=%s",
            summoner.name,
            ranked.tier if ranked else None,
            ranked.rank if ranked else "",
            ranked.leaguePoints if ranked else None,
        )
        log.info("Total match IDs for player: %d", len(match_ids))

        self._ensure_cached(platform, match_ids)

        recent_ids: list[str] = match_ids[:MATCH_LIMIT]
        log.info("Returning last %d match(es): %s", len(recent_ids), recent_ids)

        matches: list[MatchSchema] = self._ingestion.get_participant_stats(
            puuid, recent_ids
        )
        # Preserve Riot ordering (the DB query can return rows in any order)
        id_order: dict[str, int] = {mid: i for i, mid in enumerate(recent_ids)}
        matches.sort(key=lambda m: id_order.get(m.match_id, 999))

        placements: list[int] = [
            m.placement for m in matches if m.placement is not None
        ]
        avg: float | None = (
            round(sum(placements) / len(placements), 2) if placements else None
        )
        log.info("Built response: %d matches, placements=%s", len(matches), placements)

        return StatsResponseSchema(
            summoner={
                "name": summoner.name,
                "level": summoner.summonerLevel,
                "profile_icon_id": summoner.profileIconId,
            },
            ranked={
                "tier":          ranked.tier          if ranked else None,
                "tier_icon_url": tier_icon_url(ranked.tier if ranked else None),
                "rank":          ranked.rank          if ranked else None,
                "lp":            ranked.leaguePoints  if ranked else None,
                "wins":          ranked.wins           if ranked else None,
                "losses":        ranked.losses         if ranked else None,
                "hot_streak":    ranked.hotStreak      if ranked else None,
            },
            average_placement=avg,
            average_placement_sample=len(placements),
            last_matches=matches,
        )

    def get_player_profile(
        self,
        platform: str,
        game_name: str,
        tag_line: str,
        puuid: str,
    ) -> PlayerProfileSchema:
        """Fetch summoner + league data and return a :class:`~schemas.player.PlayerProfileSchema`.

        Results are cached in memory for :data:`_PROFILE_TTL` seconds to avoid
        hammering the Riot API on every GitHub README load.
        """
        pkey = (platform, game_name.lower(), tag_line.lower())
        pcached = _PROFILE_CACHE.get(pkey)
        if pcached and time.time() < pcached[1]:
            log.debug("Profile memory-cache hit for %s#%s", game_name, tag_line)
            return pcached[0]  # type: ignore[return-value]

        with ThreadPoolExecutor(max_workers=2) as executor:
            f_summoner = executor.submit(self._riot.get_summoner,       platform, puuid)
            f_league   = executor.submit(self._riot.get_league_entries, platform, puuid)
            summoner: SummonerSchema          = f_summoner.result()
            league:   list[LeagueEntrySchema] = f_league.result()

        ranked: LeagueEntrySchema | None = self._ranked_entry(league)
        summary: SetSummarySchema = self._ingestion.get_set_summary(puuid)

        profile = PlayerProfileSchema(
            game_name=game_name,
            tag_line=tag_line,
            platform=platform,
            queue_label="Ranked",
            profile_icon_id=summoner.profileIconId,
            tier=ranked.tier          if ranked else None,
            rank=ranked.rank          if ranked else None,
            lp=ranked.leaguePoints    if ranked else None,
            set_summary=summary,
        )
        _PROFILE_CACHE[pkey] = (profile, time.time() + _PROFILE_TTL)
        return profile

    def get_recent_matches(self, puuid: str) -> list[MatchSchema]:
        """Return the last :data:`MATCH_LIMIT` cached matches for *puuid*."""
        return self._ingestion.get_recent_participant_stats(puuid, limit=MATCH_LIMIT)

    def get_match(self, puuid: str, match_id: str) -> MatchSchema | None:
        """Return a single cached match for *puuid*, or ``None`` if not found."""
        results: list[MatchSchema] = self._ingestion.get_participant_stats(
            puuid, [match_id]
        )
        return results[0] if results else None

    def resolve_puuid(self, platform: str, game_name: str, tag_line: str) -> str:
        """Public façade over :py:meth:`_resolve_puuid` for route handlers."""
        return self._resolve_puuid(platform, game_name, tag_line)
