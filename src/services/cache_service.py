import logging

from sqlalchemy.dialects.sqlite import insert

from extensions import db
from models.item import Item
from models.match import Match
from models.trait import Trait
from models.trait_stats import TraitStats
from models.unit import Unit
from models.unit_stats import UnitStats, UnitStatsItem
from models.user import User
from models.user_match_stats import UserMatchStats
from utils.icons import item_icon_url, trait_icon_url, unit_icon_url

log = logging.getLogger(__name__)


class MatchCache:
    def get_missing_ids(self, match_ids):
        if not match_ids:
            return []

        cached = {
            row.match_id
            for row in db.session.query(Match.match_id)
            .filter(Match.match_id.in_(match_ids))
            .all()
        }
        missing = [match_id for match_id in match_ids if match_id not in cached]
        log.info("Cache check: %d requested, %d cached, %d missing", len(match_ids), len(cached), len(missing))
        return missing

    def _ignore_insert(self, model, values):
        return db.session.execute(
            insert(model).values(values).on_conflict_do_nothing()
        )

    def store_match(self, match_data):
        match_id = match_data['metadata']['match_id']
        info = match_data['info']
        participants = [p for p in info.get('participants', []) if p.get('puuid') and p['puuid'] != 'BOT']
        log.info("Storing match %s  [%d participants, set=%s, version=%s]",
                 match_id, len(participants), info.get('tft_set_number'), info.get('game_version'))

        self._ignore_insert(
            Match,
            {
                'match_id': match_id,
                'game_datetime': info.get('game_datetime'),
                'game_length': info.get('game_length'),
                'game_version': info.get('game_version'),
                'tft_set_number': info.get('tft_set_number'),
            },
        )

        for participant in info.get('participants', []):
            puuid = participant.get('puuid')
            if not puuid or puuid == 'BOT':
                continue
            log.debug("  Participant puuid=%.12s...  placement=%s  units=%d  traits=%d",
                      puuid, participant.get('placement'),
                      len(participant.get('units', [])),
                      len(participant.get('traits', [])))

            self._ignore_insert(
                User,
                {
                    'puuid': puuid,
                    'game_name': participant.get('riotIdGameName', ''),
                    'tag_line': participant.get('riotIdTagline', ''),
                },
            )

            user_match_result = self._ignore_insert(
                UserMatchStats,
                {
                    'match_id': match_id,
                    'puuid': puuid,
                    'placement': participant.get('placement'),
                    'damage_to_players': participant.get('total_damage_to_players'),
                    'gold_left': participant.get('gold_left'),
                    'last_round': participant.get('last_round'),
                    'level': participant.get('level'),
                    'players_eliminated': participant.get('players_eliminated'),
                    'time_eliminated': participant.get('time_eliminated'),
                    'win': participant.get('win', False),
                    'augments': participant.get('augments', []),
                },
            )

            if user_match_result.rowcount == 0:
                log.debug("  Skipping puuid=%.12s... — already stored for %s", puuid, match_id)
                continue

            unit_cache = set()
            item_cache = set()
            trait_cache = set()

            for unit_data in participant.get('units', []):
                unit_id = unit_data.get('character_id')
                if not unit_id:
                    continue

                if unit_id not in unit_cache:
                    self._ignore_insert(
                        Unit,
                        {
                            'unit_id': unit_id,
                            'rarity': unit_data.get('rarity'),
                            'icon_url': unit_icon_url(unit_id),
                        },
                    )
                    unit_cache.add(unit_id)

                unit_stats = UnitStats(
                    match_id=match_id,
                    puuid=puuid,
                    unit_id=unit_id,
                    unit_tier=unit_data.get('tier'),
                )
                db.session.add(unit_stats)
                db.session.flush()

                for item_id in unit_data.get('itemNames', []):
                    if not item_id:
                        continue

                    if item_id not in item_cache:
                        self._ignore_insert(
                            Item,
                            {
                                'item_id': item_id,
                                'icon_url': item_icon_url(item_id),
                            },
                        )
                        item_cache.add(item_id)

                    db.session.add(
                        UnitStatsItem(
                            unit_stats_id=unit_stats.id,
                            item_id=item_id,
                        )
                    )

            for trait_data in participant.get('traits', []):
                trait_id = trait_data.get('name')
                if not trait_id:
                    continue

                if trait_id not in trait_cache:
                    self._ignore_insert(
                        Trait,
                        {
                            'trait_id': trait_id,
                            'icon_url': trait_icon_url(trait_id),
                        },
                    )
                    trait_cache.add(trait_id)

                self._ignore_insert(
                    TraitStats,
                    {
                        'match_id': match_id,
                        'puuid': puuid,
                        'trait_id': trait_id,
                        'num_units': trait_data.get('num_units'),
                        'style': trait_data.get('style'),
                        'tier_current': trait_data.get('tier_current'),
                        'tier_total': trait_data.get('tier_total'),
                    },
                )

        log.debug("Match %s committed to DB", match_id)
        db.session.commit()

    def get_participant_stats(self, puuid, match_ids):
        log.debug("Loading participant stats  puuid=%.12s...  match_ids=%s", puuid, match_ids)
        rows = (
            UserMatchStats.query
            .filter(
                UserMatchStats.puuid == puuid,
                UserMatchStats.match_id.in_(match_ids),
            )
            .all()
        )
        log.info("Participant stats loaded: %d/%d rows from DB", len(rows), len(match_ids))
        return rows

    def get_recent_participant_stats(self, puuid, limit=5):
        """Return the N most recent participant stats for a player ordered by game time."""
        log.debug("Loading recent participant stats  puuid=%.12s...  limit=%d", puuid, limit)
        rows = (
            UserMatchStats.query
            .filter(UserMatchStats.puuid == puuid)
            .join(Match, Match.match_id == UserMatchStats.match_id)
            .order_by(Match.game_datetime.desc())
            .limit(limit)
            .all()
        )
        log.info("Recent participant stats: %d rows (limit=%d)", len(rows), limit)
        return rows

