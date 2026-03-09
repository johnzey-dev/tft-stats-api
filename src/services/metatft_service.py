"""MetaTFTService — fetches profile data from api.metatft.com and transforms it
into the schemas expected by the SVG builder.
"""

from __future__ import annotations

import logging
import re

import requests

from schemas.match import ItemSchema, MatchSchema, TraitSchema, UnitSchema
from schemas.metatft import MetaTFTMatch, MetaTFTProfile
from schemas.player import PlayerProfileSchema, SetSummarySchema

log = logging.getLogger(__name__)

_METATFT_BASE = "https://api.metatft.com/public/profile/lookup_by_riotid"
# (connect_timeout, read_timeout) — MetaTFT can be slow for uncached profiles
_REQUEST_TIMEOUT = (10, 60)


def _parse_rating_text(rating_text: str) -> tuple[str, str, int]:
    """Parse 'GOLD II 14 LP' → ('GOLD', 'II', 14). Returns ('', '', 0) on failure."""
    m = re.match(r"([A-Z]+)\s+([IVX]+)\s+(\d+)\s+LP", rating_text or "")
    if m:
        return m.group(1), m.group(2), int(m.group(3))
    return "", "", 0


def _parse_trait_string(trait_str: str) -> tuple[str, int]:
    """Parse 'TFT16_Noxus_3' → ('TFT16_Noxus', 3). Returns (trait_str, 0) on failure."""
    m = re.match(r"^(.*?)_(\d+)$", trait_str)
    if m:
        return m.group(1), int(m.group(2))
    return trait_str, 0


class MetaTFTService:
    """Thin wrapper around the MetaTFT public API."""

    def fetch_profile(
        self, region: str, game_name: str, tag_line: str, tft_set: str
    ) -> MetaTFTProfile:
        """Fetch and validate a player profile from MetaTFT.

        Args:
            region:   Platform region slug, e.g. ``EUW1``.
            game_name: Riot game name, e.g. ``LeeSIUU``.
            tag_line:  Riot tag line, e.g. ``SIUU``.
            tft_set:   TFT set identifier, e.g. ``TFTSet16``.

        Returns:
            Validated :class:`MetaTFTProfile` instance.

        Raises:
            requests.HTTPError: If the upstream API returns a non-2xx status.
        """
        url = f"{_METATFT_BASE}/{region}/{game_name}/{tag_line}?source=full_profile&TFTSet={tft_set}&include_revival_matches=true"
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "en-GB,en;q=0.8",
            "origin": "https://www.metatft.com",
            "priority": "u=1, i",
            "referer": "https://www.metatft.com/",
            "sec-ch-ua": '"Not(A:Brand";v="8", "Chromium";v="144", "Brave";v="144"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "sec-gpc": "1",
            "user-agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Mobile Safari/537.36",
        }
        log.debug("Fetching MetaTFT profile: %s", url)
     
        resp = requests.get(url, headers=headers, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        return MetaTFTProfile.model_validate(resp.json())

    def to_match_schemas(self, matches: list[MetaTFTMatch]) -> list[MatchSchema]:
        """Convert MetaTFT match list into :class:`MatchSchema` list for the SVG builder."""
        result: list[MatchSchema] = []
        for m in matches:
            s = m.summary

            traits = [
                TraitSchema(
                    name=name,
                    num_units=count,
                    style=1,  # MetaTFT summary doesn't expose style tier
                    tier_current=1 if count > 0 else 0,
                )
                for trait_str in s.traits
                for name, count in [_parse_trait_string(trait_str)]
            ]

            units = [
                UnitSchema(
                    character_id=u.character_id,
                    rarity=0,  # not available in MetaTFT match summary
                    stars=u.tier,
                    items=[ItemSchema(item_id=item_name) for item_name in u.itemNames],
                )
                for u in s.units
            ]

            result.append(
                MatchSchema(
                    match_id=m.riot_match_id,
                    placement=m.placement,
                    level=s.level,
                    last_round=s.last_round,
                    players_eliminated=s.players_eliminated,
                    total_damage_to_players=s.total_damage_to_players,
                    time_eliminated=float(s.time_eliminated) if s.time_eliminated else None,
                    augments=s.augments,
                    traits=traits,
                    units=units,
                )
            )
        return result

    def to_player_profile(
        self,
        profile: MetaTFTProfile,
        game_name: str,
        tag_line: str,
        platform: str,
    ) -> PlayerProfileSchema:
        """Build a :class:`PlayerProfileSchema` from a MetaTFT profile for the SVG header."""
        ranked = profile.ranked
        tier = rank = ""
        lp: int | None = None
        if ranked and ranked.rating_text:
            tier, rank, lp = _parse_rating_text(ranked.rating_text)

        placements = [m.placement for m in profile.matches]
        total_returned = len(placements)
        avg = round(sum(placements) / total_returned, 2) if total_returned else None
        top4 = sum(1 for p in placements if p <= 4)
        wins = sum(1 for p in placements if p == 1)

        set_summary = SetSummarySchema(
            total_games=ranked.num_games if ranked else total_returned,
            avg_placement=avg,
            top4_count=top4,
            win_count=wins,
        )

        return PlayerProfileSchema(
            game_name=game_name,
            tag_line=tag_line,
            platform=platform,
            profile_icon_id=profile.summoner.profile_icon_id,
            tier=tier or None,
            rank=rank or None,
            lp=lp,
            set_summary=set_summary,
        )
