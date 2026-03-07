"""Pydantic schemas that mirror the Riot API raw response shapes."""

from __future__ import annotations
from pydantic import BaseModel, Field


class AccountSchema(BaseModel):
    """GET /riot/account/v1/accounts/by-riot-id/{gameName}/{tagLine}"""

    puuid:        str
    gameName:     str = ""
    tagLine:      str = ""


class SummonerSchema(BaseModel):
    """GET /tft/summoner/v1/summoners/by-puuid/{puuid}"""

    id:              str = ""
    accountId:       str = ""
    puuid:           str = ""
    name:            str = ""
    profileIconId:   int = 1
    summonerLevel:   int = 0
    revisionDate:    int = 0


class LeagueEntrySchema(BaseModel):
    """One entry from GET /tft/league/v1/by-puuid/{puuid}"""

    leagueId:     str = ""
    summonerId:   str = ""
    queueType:    str = ""
    tier:         str | None = None
    rank:         str | None = None
    leaguePoints: int = 0
    wins:         int = 0
    losses:       int = 0
    hotStreak:    bool = False
    veteran:      bool = False
    freshBlood:   bool = False
    inactive:     bool = False
