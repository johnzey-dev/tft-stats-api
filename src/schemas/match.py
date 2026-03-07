"""Pydantic schemas for match data flowing between cache → service → SVG builder."""

from __future__ import annotations
from pydantic import BaseModel, Field


class ItemSchema(BaseModel):
    item_id:  str
    icon_url: str | None = None


class TraitSchema(BaseModel):
    name:         str
    icon_url:     str | None = None
    num_units:    int = 0
    style:        int = 0
    tier_current: int = 0
    tier_total:   int = 0


class UnitSchema(BaseModel):
    character_id: str
    icon_url:     str | None = None
    rarity:       int = 0
    stars:        int = 0
    items:        list[ItemSchema] = Field(default_factory=list)


class MatchSchema(BaseModel):
    match_id:               str | None = None
    placement:              int | None = None
    level:                  int | None = None
    gold_left:              int | None = None
    last_round:             int | None = None
    players_eliminated:     int | None = None
    total_damage_to_players: int | None = None
    time_eliminated:        float | None = None
    augments:               list[str] = Field(default_factory=list)
    traits:                 list[TraitSchema] = Field(default_factory=list)
    units:                  list[UnitSchema] = Field(default_factory=list)
