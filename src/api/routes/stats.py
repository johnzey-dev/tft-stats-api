from __future__ import annotations

import logging
from typing import Any

import requests
from flask import Blueprint, Response, jsonify

from services.stats_service import StatsService
from utils.svg_builder import build_composition_svg, build_matches_svg

log = logging.getLogger(__name__)

stats_bp: Blueprint      = Blueprint("stats", __name__)
stats_service: StatsService = StatsService()


# ── Error handler helper ─────────────────────────────────────────────────────

def _handle_riot_error(exc: Exception) -> tuple[Any, int]:
    """Convert common Riot API exceptions into Flask JSON error responses."""
    if isinstance(exc, requests.exceptions.HTTPError):
        status: int = exc.response.status_code if exc.response is not None else 500
        if status == 401:
            return jsonify({
                "error": (
                    "Unauthorized from Riot API. "
                    "Verify RIOT_API_KEY is set, valid, and not expired."
                ),
                "details": str(exc),
            }), 401
        return jsonify({"error": str(exc)}), status
    if isinstance(exc, requests.exceptions.RequestException):
        return jsonify({"error": "Failed to reach Riot API", "details": str(exc)}), 503
    raise exc  # unexpected — let Flask's default error handler deal with it


# ── Routes ───────────────────────────────────────────────────────────────────

@stats_bp.route("/tft-stats/<platform>/<game_name>/<tag_line>", methods=["GET"])
def get_stats(platform: str, game_name: str, tag_line: str) -> tuple[Any, int]:
    log.info("Request: GET /tft-stats/%s/%s/%s", platform, game_name, tag_line)
    try:
        result = stats_service.get_stats(platform, game_name, tag_line)
        return jsonify(result.model_dump()), 200
    except ValueError as exc:
        log.warning("ValueError: %s", exc)
        return jsonify({"error": str(exc)}), 400
    except (requests.exceptions.HTTPError, requests.exceptions.RequestException) as exc:
        log.error("Riot API error: %s", exc)
        return _handle_riot_error(exc)
    except KeyError as exc:
        log.error("Unexpected API response shape, missing key: %s", exc)
        return jsonify({"error": f"Unexpected API response, missing field: {exc}"}), 502


@stats_bp.route(
    "/tft-stats/<platform>/<game_name>/<tag_line>/<match_id>/svg", methods=["GET"]
)
def get_match_svg(
    platform: str, game_name: str, tag_line: str, match_id: str
) -> Response | tuple[Any, int]:
    log.info("SVG request: %s/%s/%s  match=%s", platform, game_name, tag_line, match_id)
    try:
        puuid = stats_service.resolve_puuid(platform, game_name, tag_line)
    except (requests.exceptions.HTTPError, requests.exceptions.RequestException) as exc:
        log.error("Riot API error resolving puuid: %s", exc)
        return _handle_riot_error(exc)

    match = stats_service.get_match(puuid, match_id)
    if not match:
        return jsonify({
            "error": "Match not found in cache. Call the player stats endpoint first to populate the cache."
        }), 404

    svg = build_composition_svg(match.model_dump())
    log.info(
        "SVG built: %d units, %d active traits",
        len(match.units),
        sum(1 for t in match.traits if t.tier_current > 0),
    )
    return Response(svg, status=200, mimetype="image/svg+xml")


@stats_bp.route(
    "/tft-stats/<platform>/<game_name>/<tag_line>/svg", methods=["GET"]
)
def get_player_svg(
    platform: str, game_name: str, tag_line: str
) -> Response | tuple[Any, int]:
    """Return one SVG containing the last 5 games for a player."""
    log.info("SVG (5-game) request: %s/%s/%s", platform, game_name, tag_line)
    try:
        puuid = stats_service.resolve_puuid(platform, game_name, tag_line)
    except (requests.exceptions.HTTPError, requests.exceptions.RequestException) as exc:
        log.error("Riot API error resolving puuid: %s", exc)
        return _handle_riot_error(exc)

    recent = stats_service.get_recent_matches(puuid)
    if not recent:
        return jsonify({
            "error": "No cached matches found. Call the player stats endpoint first to populate the cache."
        }), 404

    try:
        profile = stats_service.get_player_profile(platform, game_name, tag_line, puuid)
    except (requests.exceptions.HTTPError, requests.exceptions.RequestException) as exc:
        log.error("Riot API error fetching profile: %s", exc)
        return _handle_riot_error(exc)

    svg = build_matches_svg(
        [m.model_dump() for m in recent],
        player_profile=profile.model_dump(),
    )
    log.info("5-game SVG built for %d matches", len(recent))
    return Response(svg, status=200, mimetype="image/svg+xml")
