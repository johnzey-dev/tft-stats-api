import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from config.settings import Config
from schemas.riot import AccountSchema, LeagueEntrySchema, SummonerSchema

log = logging.getLogger(__name__)


class RiotService:
    def __init__(self) -> None:
        self._headers = {"X-Riot-Token": Config.RIOT_API_KEY}

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _platform_url(self, platform: str) -> str:
        return f"https://{platform}.api.riotgames.com"

    def _regional_url(self, platform: str) -> str:
        region = Config.PLATFORM_TO_REGION.get(platform.lower())
        if not region:
            raise ValueError(f"Unknown platform: {platform}")
        return f"https://{region}.api.riotgames.com"

    def _get(self, url: str, **kwargs) -> dict | list:
        """Perform a GET request and return parsed JSON, raising on HTTP errors."""
        response = requests.get(url, headers=self._headers, **kwargs)
        response.raise_for_status()
        return response.json()

    # ── Public API ────────────────────────────────────────────────────────────

    def get_account_by_riot_id(
        self, platform: str, game_name: str, tag_line: str
    ) -> AccountSchema:
        url = (
            f"{self._regional_url(platform)}"
            f"/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
        )
        log.debug("GET account  %s#%s  platform=%s", game_name, tag_line, platform)
        data = self._get(url)
        account = AccountSchema.model_validate(data)
        log.info("Account resolved: puuid=%.12s...", account.puuid)
        return account

    def get_summoner(self, platform: str, puuid: str) -> SummonerSchema:
        url = f"{self._platform_url(platform)}/tft/summoner/v1/summoners/by-puuid/{puuid}"
        log.debug("GET summoner  puuid=%.12s...  platform=%s", puuid, platform)
        data = self._get(url)
        summoner = SummonerSchema.model_validate(data)
        log.info("Summoner: %s  level=%s", summoner.name, summoner.summonerLevel)
        return summoner

    def get_league_entries(
        self, platform: str, puuid: str
    ) -> list[LeagueEntrySchema]:
        url = f"{self._platform_url(platform)}/tft/league/v1/by-puuid/{puuid}"
        log.debug("GET league entries  puuid=%.12s...  platform=%s", puuid, platform)
        data = self._get(url)
        entries = [LeagueEntrySchema.model_validate(e) for e in data]
        log.info("League entries received: %d entries", len(entries))
        return entries

    def get_all_match_ids(self, platform: str, puuid: str) -> list[str]:
        """Page through the Riot match-IDs endpoint and return ALL ranked match IDs."""
        base_url = (
            f"{self._regional_url(platform)}"
            f"/tft/match/v1/matches/by-puuid/{puuid}/ids"
        )
        all_ids: list[str] = []
        start, count = 0, 200
        log.debug("GET match IDs  puuid=%.12s...  platform=%s", puuid, platform)
        while True:
            batch: list = self._get(
                base_url,
                params={"start": start, "count": count, "type": "ranked"},
                timeout=Config.TIMEOUT,
            )
            all_ids.extend(batch)
            log.debug(
                "  page start=%d  got=%d  total so far=%d",
                start, len(batch), len(all_ids),
            )
            if len(batch) < count:
                break
            start += count
        log.info("Match IDs fetched: %d total", len(all_ids))
        return all_ids

    def get_match_detail(
        self, platform: str, match_id: str, max_retries: int = 5
    ) -> dict:
        url = f"{self._regional_url(platform)}/tft/match/v1/matches/{match_id}"
        log.debug("GET match detail  match_id=%s  platform=%s", match_id, platform)
        for attempt in range(max_retries):
            response = requests.get(url, headers=self._headers, timeout=Config.TIMEOUT)
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 2**attempt))
                log.warning(
                    "Rate limited on %s (attempt %d/%d) — sleeping %ds",
                    match_id, attempt + 1, max_retries, retry_after,
                )
                time.sleep(retry_after)
                continue
            response.raise_for_status()
            log.debug("Match detail OK  match_id=%s", match_id)
            return response.json()
        response.raise_for_status()  # exhausted retries

    def get_match_details_bulk(
        self, platform: str, match_ids: list[str], max_workers: int = 5
    ) -> dict[str, dict]:
        """Fetch multiple match details concurrently."""
        log.info(
            "Fetching %d match(es) from Riot API  platform=%s  workers=%d",
            len(match_ids), platform, max_workers,
        )
        results: dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_id = {
                executor.submit(self.get_match_detail, platform, mid): mid
                for mid in match_ids
            }
            for future in as_completed(future_to_id):
                mid = future_to_id[future]
                results[mid] = future.result()
                log.debug("  Fetched %s [%d/%d]", mid, len(results), len(match_ids))
        log.info(
            "Bulk fetch complete: %d/%d matches retrieved",
            len(results), len(match_ids),
        )
        return results
