import logging
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from config.settings import Config

log = logging.getLogger(__name__)


class RiotService:
    def __init__(self):
        self.api_key = Config.RIOT_API_KEY
        self.headers = {"X-Riot-Token": self.api_key}

    def _platform_url(self, platform):
        return f"https://{platform}.api.riotgames.com"

    def _regional_url(self, platform):
        region = Config.PLATFORM_TO_REGION.get(platform.lower())
        if not region:
            raise ValueError(f"Unknown platform: {platform}")
        return f"https://{region}.api.riotgames.com"

    def get_account_by_riot_id(self, platform, game_name, tag_line):
        url = f"{self._regional_url(platform)}/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
        log.debug("GET account  %s#%s  platform=%s", game_name, tag_line, platform)
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        data = response.json()
        log.info("Account resolved: puuid=%.12s...", data.get('puuid', ''))
        return data

    def get_player_stats(self, platform, puuid):
        url = f"{self._platform_url(platform)}/tft/summoner/v1/summoners/by-puuid/{puuid}"
        log.debug("GET summoner  puuid=%.12s...  platform=%s", puuid, platform)
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        data = response.json()
        log.info("Summoner: %s  level=%s", data.get('name'), data.get('summonerLevel'))
        return data

    def get_league_stats(self, platform, puuid):
        url = f"{self._platform_url(platform)}/tft/league/v1/by-puuid/{puuid}"
        log.debug("GET league entries  puuid=%.12s...  platform=%s", puuid, platform)
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        data = response.json()
        log.info("League entries received: %d entries", len(data))
        return data

    def get_last_games(self, platform, puuid):
        base_url = f"{self._regional_url(platform)}/tft/match/v1/matches/by-puuid/{puuid}/ids"
        all_ids = []
        start = 0
        count = 200
        log.debug("GET match IDs  puuid=%.12s...  platform=%s", puuid, platform)
        while True:
            response = requests.get(
                base_url,
                headers=self.headers,
                params={'start': start, 'count': count, 'type': 'ranked'},
                timeout=Config.TIMEOUT,
            )
            response.raise_for_status()
            batch = response.json()
            all_ids.extend(batch)
            log.debug("  page start=%d  got=%d  total so far=%d", start, len(batch), len(all_ids))
            if len(batch) < count:
                break
            start += count
        log.info("Match IDs fetched: %d total", len(all_ids))
        return all_ids

    def get_match_detail(self, platform, match_id, max_retries=5):
        url = f"{self._regional_url(platform)}/tft/match/v1/matches/{match_id}"
        log.debug("GET match detail  match_id=%s  platform=%s", match_id, platform)
        for attempt in range(max_retries):
            response = requests.get(url, headers=self.headers, timeout=Config.TIMEOUT)
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 2 ** attempt))
                log.warning("Rate limited on %s (attempt %d/%d) — sleeping %ds", match_id, attempt + 1, max_retries, retry_after)
                time.sleep(retry_after)
                continue
            response.raise_for_status()
            log.debug("Match detail OK  match_id=%s  status=%d", match_id, response.status_code)
            return response.json()
        response.raise_for_status()  # raise after exhausting retries

    def get_match_details_bulk(self, platform, match_ids, max_workers=5):
        """Fetch multiple match details concurrently from Riot API."""
        log.info("Fetching %d match(es) from Riot API  platform=%s  workers=%d", len(match_ids), platform, max_workers)
        results = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_id = {executor.submit(self.get_match_detail, platform, mid): mid for mid in match_ids}
            for future in as_completed(future_to_id):
                mid = future_to_id[future]
                results[mid] = future.result()
                log.debug("  Fetched %s [%d/%d]", mid, len(results), len(match_ids))
        log.info("Bulk fetch complete: %d/%d matches retrieved", len(results), len(match_ids))
        return results