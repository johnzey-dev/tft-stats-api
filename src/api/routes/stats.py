from __future__ import annotations

import logging
import time
from typing import Any

import requests
from flask import Blueprint, Response, jsonify

from services.metatft_service import MetaTFTService
from utils.svg_builder import build_matches_svg
from utils.svg_to_png import svg_to_png

log = logging.getLogger(__name__)

stats_bp: Blueprint = Blueprint("stats", __name__)
_service = MetaTFTService()

_START_TIME = time.time()


# ── Health ───────────────────────────────────────────────────────────────────

@stats_bp.route("/health", methods=["GET"])
def health() -> tuple[Any, int]:
    return jsonify({
        "status": "ok",
        "uptime_seconds": round(time.time() - _START_TIME),
    }), 200


# ── PNG endpoint ──────────────────────────────────────────────────────────────

@stats_bp.route(
    "/tft-stats/<region>/<game_name>/<tag_line>/<tft_set>/png", methods=["GET"]
)
def get_player_png(
    region: str, game_name: str, tag_line: str, tft_set: str
) -> Response | tuple[Any, int]:
    """Return a PNG card of recent matches for a player in a given TFT set.

    URL params:
        region:   Platform region, e.g. EUW1
        game_name: Riot game name, e.g. LeeSIUU
        tag_line:  Riot tag line, e.g. SIUU
        tft_set:   TFT set identifier, e.g. TFTSet16
    """
    log.info("PNG request: %s/%s/%s set=%s", region, game_name, tag_line, tft_set)
    t0 = time.time()
    try:
        profile = _service.fetch_profile(region, game_name, tag_line, tft_set)
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 502
        log.error("MetaTFT API error %s: %s", status, exc)
        return jsonify({"error": "Failed to fetch profile from MetaTFT", "details": str(exc)}), status
    except requests.exceptions.RequestException as exc:
        log.error("MetaTFT request failed: %s", exc)
        return jsonify({"error": "Could not reach MetaTFT API", "details": str(exc)}), 503
    log.info("  fetch_profile:   %.3fs", time.time() - t0); t1 = time.time()

    if not profile.matches:
        return jsonify({"error": "No matches found for this player and set."}), 404

    all_matches = _service.to_match_schemas(profile.matches)
    player_profile = _service.to_player_profile(profile, game_name, tag_line, region)
    log.info("  transform:       %.3fs", time.time() - t1); t2 = time.time()

    svg = build_matches_svg(
        [m.model_dump() for m in all_matches[:5]],
        player_profile=player_profile.model_dump(),
    )
    log.info("  build_svg:       %.3fs", time.time() - t2); t3 = time.time()

    png = svg_to_png(svg, scale=1.5)
    log.info("  svg_to_png:      %.3fs", time.time() - t3)
    log.info("  TOTAL:           %.3fs — %d matches for %s#%s", time.time() - t0, len(all_matches), game_name, tag_line)
    return Response(png, status=200, mimetype="image/png")
