import logging

from sqlalchemy.dialects.sqlite import insert

from config.settings import Config
from extensions import db
from models.item import Item
from models.match import Match
from models.trait import Trait
from models.trait_stats import TraitStats
from models.unit import Unit
from models.unit_stats import UnitStats, UnitStatsItem
from models.user import User
from models.user_match_stats import UserMatchStats
from schemas.match import ItemSchema, MatchSchema, TraitSchema, UnitSchema
from schemas.player import SetSummarySchema
from utils.icons import item_icon_url, trait_icon_url, unit_icon_url

log = logging.getLogger(__name__)

BATCH_SIZE = 10


class MatchCache:
    # ── Internal helpers ─────────────────────────────────────────────────────

    def _upsert(self, model, values: dict) -> object:
        """INSERT OR IGNORE into `model`."""
        return db.session.execute(
            insert(model).values(values).on_conflict_do_nothing()
        )

    # ── Cache management ─────────────────────────────────────────────────────

    def get_missing_ids(self, match_ids: list[str]) -> list[str]:
        if not match_ids:
            return []
        cached = {
            row.match_id
            for row in db.session.query(Match.match_id)
            .filter(Match.match_id.in_(match_ids))
            .all()
        }
        missing = [mid for mid in match_ids if mid not in cached]
        log.info(
            "Cache check: %d requested, %d cached, %d missing",
            len(match_ids), len(cached), len(missing),
        )
        return missing

    def store_match(self, match_data: dict) -> None:
        match_id = match_data["metadata"]["match_id"]
        info = match_data["info"]
        participants = [
            p for p in info.get("participants", [])
            if p.get("puuid") and p["puuid"] != "BOT"
        ]
        log.info(
            "Storing match %s  [%d participants, set=%s, version=%s]",
            match_id, len(participants),
            info.get("tft_set_number"), info.get("game_version"),
        )

        self._upsert(Match, {
            "match_id":       match_id,
            "game_datetime":  info.get("game_datetime"),
            "game_length":    info.get("game_length"),
            "game_version":   info.get("game_version"),
            "tft_set_number": info.get("tft_set_number"),
        })

        for participant in info.get("participants", []):
            puuid = participant.get("puuid")
            if not puuid or puuid == "BOT":
                continue
            log.debug(
                "  Participant puuid=%.12s...  placement=%s  units=%d  traits=%d",
                puuid, participant.get("placement"),
                len(participant.get("units", [])),
                len(participant.get("traits", [])),
            )

            self._upsert(User, {
                "puuid":     puuid,
                "game_name": participant.get("riotIdGameName", ""),
                "tag_line":  participant.get("riotIdTagline", ""),
            })

            result = self._upsert(UserMatchStats, {
                "match_id":           match_id,
                "puuid":              puuid,
                "placement":          participant.get("placement"),
                "damage_to_players":  participant.get("total_damage_to_players"),
                "gold_left":          participant.get("gold_left"),
                "last_round":         participant.get("last_round"),
                "level":              participant.get("level"),
                "players_eliminated": participant.get("players_eliminated"),
                "time_eliminated":    participant.get("time_eliminated"),
                "win":                participant.get("win", False),
                "augments":           participant.get("augments", []),
            })

            if result.rowcount == 0:
                log.debug(
                    "  Skipping puuid=%.12s... — already stored for %s", puuid, match_id
                )
                continue

            unit_cache: set[str] = set()
            item_cache: set[str] = set()
            trait_cache: set[str] = set()

            for unit_data in participant.get("units", []):
                unit_id = unit_data.get("character_id")
                if not unit_id:
                    continue
                if unit_id not in unit_cache:
                    self._upsert(Unit, {
                        "unit_id":  unit_id,
                        "rarity":   unit_data.get("rarity"),
                        "icon_url": unit_icon_url(unit_id),
                    })
                    unit_cache.add(unit_id)

                unit_stats = UnitStats(
                    match_id=match_id,
                    puuid=puuid,
                    unit_id=unit_id,
                    unit_tier=unit_data.get("tier"),
                )
                db.session.add(unit_stats)
                db.session.flush()

                for item_id in unit_data.get("itemNames", []):
                    if not item_id:
                        continue
                    if item_id not in item_cache:
                        self._upsert(Item, {
                            "item_id":  item_id,
                            "icon_url": item_icon_url(item_id),
                        })
                        item_cache.add(item_id)
                    db.session.add(
                        UnitStatsItem(unit_stats_id=unit_stats.id, item_id=item_id)
                    )

            for trait_data in participant.get("traits", []):
                trait_id = trait_data.get("name")
                if not trait_id:
                    continue
                if trait_id not in trait_cache:
                    self._upsert(Trait, {
                        "trait_id": trait_id,
                        "icon_url": trait_icon_url(trait_id),
                    })
                    trait_cache.add(trait_id)
                self._upsert(TraitStats, {
                    "match_id":     match_id,
                    "puuid":        puuid,
                    "trait_id":     trait_id,
                    "num_units":    trait_data.get("num_units"),
                    "style":        trait_data.get("style"),
                    "tier_current": trait_data.get("tier_current"),
                    "tier_total":   trait_data.get("tier_total"),
                })

        log.debug("Match %s committed to DB", match_id)
        db.session.commit()

    # ── Queries ───────────────────────────────────────────────────────────────

    def _ums_to_match_schema(self, ums: UserMatchStats) -> MatchSchema:
        """Map an ORM UserMatchStats row → MatchSchema."""
        return MatchSchema(
            match_id=ums.match_id,
            placement=ums.placement,
            level=ums.level,
            gold_left=ums.gold_left,
            last_round=ums.last_round,
            players_eliminated=ums.players_eliminated,
            total_damage_to_players=ums.damage_to_players,
            time_eliminated=ums.time_eliminated,
            augments=ums.augments or [],
            traits=[
                TraitSchema(
                    name=ts.trait_id,
                    icon_url=ts.trait.icon_url if ts.trait else None,
                    num_units=ts.num_units or 0,
                    style=ts.style or 0,
                    tier_current=ts.tier_current or 0,
                    tier_total=ts.tier_total or 0,
                )
                for ts in ums.trait_stats
            ],
            units=[
                UnitSchema(
                    character_id=us.unit_id,
                    icon_url=us.unit.icon_url if us.unit else None,
                    rarity=us.unit.rarity if us.unit else 0,
                    stars=us.unit_tier or 0,
                    items=[
                        ItemSchema(
                            item_id=usi.item_id,
                            icon_url=usi.item.icon_url if usi.item else None,
                        )
                        for usi in us.unit_stat_items
                    ],
                )
                for us in ums.unit_stats
            ],
        )

    def get_participant_stats(
        self, puuid: str, match_ids: list[str]
    ) -> list[MatchSchema]:
        log.debug(
            "Loading participant stats  puuid=%.12s...  match_ids=%s", puuid, match_ids
        )
        rows = (
            UserMatchStats.query
            .filter(
                UserMatchStats.puuid == puuid,
                UserMatchStats.match_id.in_(match_ids),
            )
            .join(Match, Match.match_id == UserMatchStats.match_id)
            .filter(Match.tft_set_number == Config.CURRENT_SET)
            .all()
        )
        log.info(
            "Participant stats loaded: %d/%d rows from DB (set=%d)",
            len(rows), len(match_ids), Config.CURRENT_SET,
        )
        return [self._ums_to_match_schema(r) for r in rows]

    def get_recent_participant_stats(
        self, puuid: str, limit: int = 5
    ) -> list[MatchSchema]:
        """Return the N most recent matches for a player from the current TFT set."""
        log.debug(
            "Loading recent participant stats  puuid=%.12s...  limit=%d  set=%d",
            puuid, limit, Config.CURRENT_SET,
        )
        rows = (
            UserMatchStats.query
            .filter(UserMatchStats.puuid == puuid)
            .join(Match, Match.match_id == UserMatchStats.match_id)
            .filter(Match.tft_set_number == Config.CURRENT_SET)
            .order_by(Match.game_datetime.desc())
            .limit(limit)
            .all()
        )
        log.info(
            "Recent participant stats: %d rows (limit=%d, set=%d)",
            len(rows), limit, Config.CURRENT_SET,
        )
        return [self._ums_to_match_schema(r) for r in rows]

    def get_set_summary(self, puuid: str) -> SetSummarySchema:
        """Return aggregate stats for the current set."""
        rows = (
            UserMatchStats.query
            .filter(UserMatchStats.puuid == puuid)
            .join(Match, Match.match_id == UserMatchStats.match_id)
            .filter(Match.tft_set_number == Config.CURRENT_SET)
            .with_entities(UserMatchStats.placement, UserMatchStats.win)
            .all()
        )
        total      = len(rows)
        placements = [r.placement for r in rows if r.placement is not None]
        wins       = sum(1 for r in rows if r.win)
        top4       = sum(1 for p in placements if p <= 4)
        avg        = round(sum(placements) / len(placements), 2) if placements else None
        log.info(
            "Set summary  puuid=%.12s...  total=%d  avg=%s  top4=%d  wins=%d",
            puuid, total, avg, top4, wins,
        )
        return SetSummarySchema(
            total_games=total,
            avg_placement=avg,
            top4_count=top4,
            win_count=wins,
        )
