import logging

from flask import Blueprint, jsonify, Response
from services.riot_service import RiotService
from services.cache_service import MatchCache
from concurrent.futures import ThreadPoolExecutor
from utils.icons import tier_icon_url
from utils.svg_builder import build_matches_svg, build_composition_svg
from extensions import db
from models.user import User
import requests

log = logging.getLogger(__name__)

stats_bp = Blueprint('stats', __name__)
riot_service = RiotService()
cache_service = MatchCache()

MATCH_LIMIT = 5


@stats_bp.route('/tft-stats/<platform>/<game_name>/<tag_line>', methods=['GET'])
def get_stats(platform, game_name, tag_line):
    log.info("Request: GET /tft-stats/%s/%s/%s", platform, game_name, tag_line)
    try:
        account = riot_service.get_account_by_riot_id(platform, game_name, tag_line)
        puuid = account['puuid']

        # Fetch summoner info, league entries, and match IDs concurrently
        with ThreadPoolExecutor(max_workers=3) as executor:
            f_summoner  = executor.submit(riot_service.get_player_stats, platform, puuid)
            f_league    = executor.submit(riot_service.get_league_stats,  platform, puuid)
            f_match_ids = executor.submit(riot_service.get_last_games,    platform, puuid)
            summoner       = f_summoner.result()
            league_entries = f_league.result()
            match_ids      = f_match_ids.result()

        ranked = next((e for e in league_entries if e.get('queueType') == 'RANKED_TFT'), None)
        tier   = ranked.get('tier') if ranked else None
        log.info("Player: %s  tier=%s %s  LP=%s",
                 summoner.get('name'), tier,
                 ranked.get('rank') if ranked else '',
                 ranked.get('leaguePoints') if ranked else None)

        log.info("Total match IDs for player: %d", len(match_ids))

        # Cache ALL matches from Riot API so the DB stays complete
        missing_ids = cache_service.get_missing_ids(match_ids)
        if missing_ids:
            log.info("Fetching %d uncached match(es) from Riot API", len(missing_ids))
            # Fetch and store in batches of 10: fetch batch → write to DB → next batch
            batch_size = 10
            for i in range(0, len(missing_ids), batch_size):
                batch = missing_ids[i:i + batch_size]
                log.debug("Batch %d-%d: fetching %s", i + 1, i + len(batch), batch)
                fresh = riot_service.get_match_details_bulk(platform, batch)
                for match_data in fresh.values():
                    cache_service.store_match(match_data)
        else:
            log.info("All %d match(es) already cached — skipping Riot API fetch", len(match_ids))

        # Only return the last MATCH_LIMIT games in the response
        recent_match_ids = match_ids[:MATCH_LIMIT]
        log.info("Returning last %d match(es): %s", len(recent_match_ids), recent_match_ids)

        # Load participant rows from DB (units/traits eager-loaded)
        log.debug("Loading participant rows from DB for %d match(es)", len(recent_match_ids))
        participant_stats = cache_service.get_participant_stats(puuid, recent_match_ids)
        stats_by_id = {ums.match_id: ums for ums in participant_stats}

        matches = []
        for match_id in recent_match_ids:
            ums = stats_by_id.get(match_id)
            if not ums:
                continue
            matches.append({
                'match_id': match_id,
                'placement': ums.placement,
                'level': ums.level,
                'gold_left': ums.gold_left,
                'last_round': ums.last_round,
                'players_eliminated': ums.players_eliminated,
                'total_damage_to_players': ums.damage_to_players,
                'time_eliminated': ums.time_eliminated,
                'augments': ums.augments or [],
                'traits': [
                    {
                        'name': ts.trait_id,
                        'icon_url': ts.trait.icon_url if ts.trait else None,
                        'num_units': ts.num_units,
                        'style': ts.style,
                        'tier_current': ts.tier_current,
                        'tier_total': ts.tier_total,
                    }
                    for ts in ums.trait_stats if ts.tier_current > 0
                ],
                'units': [
                    {
                        'character_id': us.unit_id,
                        'icon_url': us.unit.icon_url if us.unit else None,
                        'rarity': us.unit.rarity if us.unit else None,
                        'stars': us.unit_tier,
                        'items': [
                            {
                                'item_id': usi.item_id,
                                'icon_url': usi.item.icon_url if usi.item else None,
                            }
                            for usi in us.unit_stat_items
                        ],
                    }
                    for us in ums.unit_stats
                ],
            })

        log.info("Built response: %d matches, placements=%s", len(matches), [m['placement'] for m in matches])
        placements = [m['placement'] for m in matches if m['placement'] is not None]
        average_placement = round(sum(placements) / len(placements), 2) if placements else None

        return jsonify({
            'summoner': {
                'name': summoner.get('name'),
                'level': summoner.get('summonerLevel'),
                'profile_icon_id': summoner.get('profileIconId'),
            },
            'ranked': {
                'tier': tier,
                'tier_icon_url': tier_icon_url(tier),
                'rank': ranked.get('rank') if ranked else None,
                'lp': ranked.get('leaguePoints') if ranked else None,
                'wins': ranked.get('wins') if ranked else None,
                'losses': ranked.get('losses') if ranked else None,
                'hot_streak': ranked.get('hotStreak') if ranked else None,
            },
            'average_placement': average_placement,
            'average_placement_sample': len(placements),
            'last_matches': matches,
        }), 200
    except ValueError as e:
        log.warning("ValueError: %s", e)
        return jsonify({'error': str(e)}), 400
    except requests.exceptions.HTTPError as e:
        log.error("HTTP error from Riot API: %s", e)
        return jsonify({'error': str(e)}), e.response.status_code
    except requests.exceptions.RequestException as e:
        log.error("Network error reaching Riot API: %s", e)
        return jsonify({'error': 'Failed to reach Riot API', 'details': str(e)}), 503
    except KeyError as e:
        log.error("Unexpected API response shape, missing key: %s", e)
        return jsonify({'error': f'Unexpected API response, missing field: {e}'}), 502


@stats_bp.route('/tft-stats/<platform>/<game_name>/<tag_line>/<match_id>/svg', methods=['GET'])
def get_match_svg(platform, game_name, tag_line, match_id):
    log.info("SVG request: %s/%s/%s  match=%s", platform, game_name, tag_line, match_id)

    # Resolve puuid from DB first to avoid an extra Riot API round-trip
    user = User.query.filter(
        db.func.lower(User.game_name) == game_name.lower(),
        db.func.lower(User.tag_line) == tag_line.lower(),
    ).first()

    if user:
        puuid = user.puuid
        log.debug("User found in DB: puuid=%.12s...", puuid)
    else:
        log.debug("User not in DB, resolving via Riot API")
        try:
            account = riot_service.get_account_by_riot_id(platform, game_name, tag_line)
            puuid = account['puuid']
        except requests.exceptions.HTTPError as e:
            return jsonify({'error': str(e)}), e.response.status_code
        except requests.exceptions.RequestException as e:
            return jsonify({'error': 'Failed to reach Riot API', 'details': str(e)}), 503

    stats = cache_service.get_participant_stats(puuid, [match_id])
    if not stats:
        return jsonify({
            'error': 'Match not found in cache. Call the player stats endpoint first to populate the cache.'
        }), 404

    ums = stats[0]
    match_dict = {
        'traits': [
            {
                'name': ts.trait_id,
                'num_units': ts.num_units,
                'style': ts.style,
                'tier_current': ts.tier_current,
            }
            for ts in ums.trait_stats
        ],
        'units': [
            {
                'character_id': us.unit_id,
                'rarity': us.unit.rarity if us.unit else 0,
                'stars': us.unit_tier,
                'items': [{'item_id': usi.item_id} for usi in us.unit_stat_items],
            }
            for us in ums.unit_stats
        ],
    }

    svg = build_composition_svg(match_dict)
    log.info("SVG built: %d units, %d active traits",
             len(match_dict['units']),
             sum(1 for t in match_dict['traits'] if t.get('tier_current', 0) > 0))
    return Response(svg, status=200, mimetype='image/svg+xml')


@stats_bp.route('/tft-stats/<platform>/<game_name>/<tag_line>/svg', methods=['GET'])
def get_player_svg(platform, game_name, tag_line):
    """Return one SVG containing the last 5 games for a player."""
    log.info("SVG (5-game) request: %s/%s/%s", platform, game_name, tag_line)

    user = User.query.filter(
        db.func.lower(User.game_name) == game_name.lower(),
        db.func.lower(User.tag_line) == tag_line.lower(),
    ).first()

    if user:
        puuid = user.puuid
        log.debug("User found in DB: puuid=%.12s...", puuid)
    else:
        log.debug("User not in DB, resolving via Riot API")
        try:
            account = riot_service.get_account_by_riot_id(platform, game_name, tag_line)
            puuid = account['puuid']
        except requests.exceptions.HTTPError as e:
            return jsonify({'error': str(e)}), e.response.status_code
        except requests.exceptions.RequestException as e:
            return jsonify({'error': 'Failed to reach Riot API', 'details': str(e)}), 503

    recent = cache_service.get_recent_participant_stats(puuid, limit=MATCH_LIMIT)
    if not recent:
        return jsonify({
            'error': 'No cached matches found. Call the player stats endpoint first to populate the cache.'
        }), 404

    # Fetch profile metadata for the banner header
    try:
        summoner       = riot_service.get_player_stats(platform, puuid)
        league_entries = riot_service.get_league_stats(platform, puuid)
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            return jsonify({
                'error': 'Unauthorized from Riot API. Verify RIOT_API_KEY is set, valid, and not expired.',
                'details': str(e),
            }), 401
        return jsonify({'error': str(e)}), e.response.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({'error': 'Failed to reach Riot API', 'details': str(e)}), 503

    ranked = next((e for e in league_entries if e.get('queueType') == 'RANKED_TFT'), None)

    player_profile = {
        'game_name':       game_name,
        'tag_line':        tag_line,
        'platform':        platform,
        'queue_label':     'Ranked',
        'profile_icon_id': summoner.get('profileIconId'),
        'tier':            ranked.get('tier')         if ranked else None,
        'rank':            ranked.get('rank')         if ranked else None,
        'lp':              ranked.get('leaguePoints') if ranked else None,
        'set_summary':     cache_service.get_set_summary(puuid),
    }

    matches = [
        {
            'placement': ums.placement,
            'traits': [
                {
                    'name': ts.trait_id,
                    'num_units': ts.num_units,
                    'style': ts.style,
                    'tier_current': ts.tier_current,
                }
                for ts in ums.trait_stats
            ],
            'units': [
                {
                    'character_id': us.unit_id,
                    'rarity': us.unit.rarity if us.unit else 0,
                    'stars': us.unit_tier,
                    'items': [{'item_id': usi.item_id} for usi in us.unit_stat_items],
                }
                for us in ums.unit_stats
            ],
        }
        for ums in recent
    ]

    svg = build_matches_svg(matches, player_profile=player_profile)
    log.info("5-game SVG built for %d matches", len(matches))
    return Response(svg, status=200, mimetype='image/svg+xml')
