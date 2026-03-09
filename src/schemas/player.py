"""Pydantic schemas for player profile."""

from __future__ import annotations
from pydantic import BaseModel


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
