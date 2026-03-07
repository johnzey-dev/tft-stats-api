"""Pydantic schemas for player profile and stats response."""

from __future__ import annotations
from pydantic import BaseModel, Field

from schemas.match import MatchSchema


class SetSummarySchema(BaseModel):
    total_games:    int = 0
    avg_placement:  float | None = None
    top4_count:     int = 0
    win_count:      int = 0


class PlayerProfileSchema(BaseModel):
    game_name:        str
    tag_line:         str
    platform:         str
    queue_label:      str = "Ranked"
    profile_icon_id:  int = 1
    tier:             str | None = None
    rank:             str | None = None
    lp:               int | None = None
    set_summary:      SetSummarySchema | None = None


class StatsResponseSchema(BaseModel):
    """Full JSON response returned by GET /tft-stats/<platform>/<game_name>/<tag_line>."""

    summoner: dict = Field(default_factory=dict)
    ranked:   dict = Field(default_factory=dict)
    average_placement:        float | None = None
    average_placement_sample: int = 0
    last_matches:             list[MatchSchema] = Field(default_factory=list)
