"""
StatsService — orchestrates Riot API calls, caching, and data assembly.

Route handlers should only call into this service and format HTTP responses.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from models.user import User
from extensions import db
from schemas.match import MatchSchema
from schemas.player import PlayerProfileSchema, SetSummarySchema, StatsResponseSchema
from schemas.riot import LeagueEntrySchema, SummonerSchema
from services.cache_service import MatchCache
from services.riot_service import RiotService
from utils.icons import tier_icon_url

log = logging.getLogger(__name__)

MATCH_LIMIT = 5
CACHE_BATCH_SIZE = 10


class StatsService:
    def __init__(self) -> None:
        self._riot  = RiotService()
        self._cache = MatchCache()

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _resolve_puuid(self, platform: str, game_name: str, tag_line: str) -> str:
        """Return puuid from DB if known, else resolve via Riot API."""
        user = User.query.filter(
            db.func.lower(User.game_name) == game_name.lower(),
            db.func.lower(User.tag_line)  == tag_line.lower(),
        ).first()
        if user:
            log.debug("User found in DB: puuid=%.12s...", user.puuid)
            return user.puuid

        log.debug("User not in DB, resolving via Riot API")
        account = self._riot.get_account_by_riot_id(platform, game_name, tag_line)
        return account.puuid

    def _ensure_cached(self, platform: str, match_ids: list[str]) -> None:
        """Fetch any missing match IDs from Riot and store them in the DB."""
        missing = self._cache.get_missing_ids(match_ids)
        if not missing:
            log.info("All %d match(es) already cached — skipping Riot API fetch", len(match_ids))
            return

        log.info("Fetching %d uncached match(es) from Riot API", len(missing))
        for i in range(0, len(missing), CACHE_BATCH_SIZE):
            batch = missing[i : i + CACHE_BATCH_SIZE]
            log.debug("Batch %d–%d: fetching %s", i + 1, i + len(batch), batch)
            fresh = self._riot.get_match_details_bulk(platform, batch)
            for match_data in fresh.values():
                self._cache.store_match(match_data)

    def _ranked_entry(self, entries: list[LeagueEntrySchema]) -> LeagueEntrySchema | None:
        return next((e for e in entries if e.queueType == "RANKED_TFT"), None)

    # ── Public API ────────────────────────────────────────────────────────────

    def get_stats(
        self, platform: str, game_name: str, tag_line: str
    ) -> StatsResponseSchema:
        """Fetch and assemble full stats for the JSON endpoint."""
        account = self._riot.get_account_by_riot_id(platform, game_name, tag_line)
        puuid   = account.puuid

        # Fetch summoner, league, and match IDs concurrently
        with ThreadPoolExecutor(max_workers=3) as executor:
            f_summoner  = executor.submit(self._riot.get_summoner,       platform, puuid)
            f_league    = executor.submit(self._riot.get_league_entries, platform, puuid)
            f_match_ids = executor.submit(self._riot.get_all_match_ids,  platform, puuid)
            summoner:    SummonerSchema        = f_summoner.result()
            league:      list[LeagueEntrySchema] = f_league.result()
            match_ids:   list[str]             = f_match_ids.result()

        ranked = self._ranked_entry(league)
        log.info(
            "Player: %s  tier=%s %s  LP=%s",
            summoner.name,
            ranked.tier if ranked else None,
            ranked.rank if ranked else "",
            ranked.leaguePoints if ranked else None,
        )
        log.info("Total match IDs for player: %d", len(match_ids))

        self._ensure_cached(platform, match_ids)

        recent_ids = match_ids[:MATCH_LIMIT]
        log.info("Returning last %d match(es): %s", len(recent_ids), recent_ids)

        matches = self._cache.get_participant_stats(puuid, recent_ids)
        # Preserve Riot order (cache query can return in any order)
        id_order = {mid: i for i, mid in enumerate(recent_ids)}
        matches.sort(key=lambda m: id_order.get(m.match_id, 999))

        placements = [m.placement for m in matches if m.placement is not None]
        avg        = round(sum(placements) / len(placements), 2) if placements else None
        log.info(
            "Built response: %d matches, placements=%s", len(matches), placements
        )

        return StatsResponseSchema(
            summoner={
                "name":           summoner.name,
                "level":          summoner.summonerLevel,
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
        self, platform: str, game_name: str, tag_line: str, puuid: str
    ) -> PlayerProfileSchema:
        """Fetch summoner + league data and return a PlayerProfileSchema."""
        with ThreadPoolExecutor(max_workers=2) as executor:
            f_summoner = executor.submit(self._riot.get_summoner,       platform, puuid)
            f_league   = executor.submit(self._riot.get_league_entries, platform, puuid)
            summoner: SummonerSchema          = f_summoner.result()
            league:   list[LeagueEntrySchema] = f_league.result()

        ranked = self._ranked_entry(league)
        summary = self._cache.get_set_summary(puuid)

        return PlayerProfileSchema(
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

    def get_recent_matches(self, puuid: str) -> list[MatchSchema]:
        """Return the last MATCH_LIMIT cached matches for a player."""
        return self._cache.get_recent_participant_stats(puuid, limit=MATCH_LIMIT)

    def get_match(self, puuid: str, match_id: str) -> MatchSchema | None:
        """Return a single cached match for a player, or None if not found."""
        results = self._cache.get_participant_stats(puuid, [match_id])
        return results[0] if results else None

    def resolve_puuid(self, platform: str, game_name: str, tag_line: str) -> str:
        """Public wrapper around _resolve_puuid for use in route handlers."""
        return self._resolve_puuid(platform, game_name, tag_line)
