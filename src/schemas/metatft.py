"""Pydantic models for the MetaTFT public profile API response.

Endpoint: https://api.metatft.com/public/profile/lookup_by_riotid/{region}/{game_name}/{tag_line}
Params: source=full_profile, tft_set=TFTSetXX, include_revival_matches=true
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class MetaTFTAccount(BaseModel):
    summoner_id: str = ""
    account_id: str = ""


class MetaTFTSummoner(BaseModel):
    id: int
    puuid: str
    summoner_region: str
    profile_icon_id: int
    summoner_level: int
    revision_date: int
    riot_id: str
    account: MetaTFTAccount = Field(default_factory=MetaTFTAccount)
    last_refreshed: int | None = None
    last_name_fetch: str | None = None
    is_profile_hidden: bool = False


class MetaTFTRanked(BaseModel):
    num_games: int
    rating_text: str
    rating_numeric: int
    peak_rating: str
    peak_rating_numeric: int
    timestamp: str


class MetaTFTRatingEntry(BaseModel):
    num_games: int
    rating_text: str
    rating_numeric: int
    peak_rating: str
    peak_rating_numeric: int
    timestamp: str


class MetaTFTRatingChange(BaseModel):
    num_games: int
    rating_text: str
    rating_numeric: int
    created_timestamp: str
    tft_set_name: str
    queue_id: int


class MetaTFTUnit(BaseModel):
    character_id: str
    tier: int  # 1/2/3 = stars
    itemNames: list[str] = Field(default_factory=list)


class MetaTFTMatchSummary(BaseModel):
    level: int
    little_legend: str | None = None
    time_eliminated: int | None = None
    last_round: int | None = None
    total_damage_to_players: int | None = None
    players_eliminated: int | None = None
    units: list[MetaTFTUnit] = Field(default_factory=list)
    augments: list[str] = Field(default_factory=list)
    traits: list[str] = Field(default_factory=list)  # e.g. "TFT16_Noxus_3"
    player_rating: str | None = None
    player_rating_numeric: int | None = None
    headliner_traits: list[str] | None = None


class MetaTFTMatch(BaseModel):
    placement: int
    riot_match_id: str
    match_timestamp: int
    queue_id: int
    rating_queue_id: int
    tft_set: str
    avg_rating: str | None = None
    avg_rating_numeric: int | None = None
    match_data_url: str
    summary: MetaTFTMatchSummary


class MetaTFTSeasonStats(BaseModel):
    total: int
    placements: list[int] = Field(default_factory=list)


class MetaTFTServerRank(BaseModel):
    rank: int
    total: int


class MetaTFTProfile(BaseModel):
    summoner: MetaTFTSummoner
    ranked: MetaTFTRanked | None = None
    rating_history: dict[str, dict[str, MetaTFTRatingEntry]] = Field(default_factory=dict)
    ranked_rating_changes: list[MetaTFTRatingChange] = Field(default_factory=list)
    matches: list[MetaTFTMatch] = Field(default_factory=list)
    app_matches: list = Field(default_factory=list)
    replays: list = Field(default_factory=list)
    ranked_season_stats: dict[str, MetaTFTSeasonStats] = Field(default_factory=dict)
    server_rank: MetaTFTServerRank | None = None
