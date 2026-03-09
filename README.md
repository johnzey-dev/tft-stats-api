# TFT Stats API

A Flask API that renders a **PNG stats card** for a Teamfight Tactics player — designed to be embedded directly in a GitHub profile README. It shows the player's last 5 games: placement, augments, traits, units, and items, alongside a rank/LP header.

The project has gone through two major versions with different data sources.

---

## Version History

### v2 — MetaTFT backend *(current)*

Data is fetched from the **MetaTFT public API** (`api.metatft.com`). This means:

- **No Riot developer API key required** — no 24-hour expiry, no rate-limit headaches.
- Set-scoped: the URL includes a TFT set identifier (e.g. `TFTSet16`).
- Match data includes augments, traits, units, items, placement, level, and damage stats.
- The PNG card is rendered server-side with **cairosvg**.

**Endpoint:**
```
GET /tft-stats/<region>/<game_name>/<tag_line>/<tft_set>/png
```

Example:
```
GET /tft-stats/EUW1/LeeSIUU/SIUU/TFTSet16/png
```

---

### v1 — Riot API backend *(legacy)*

Data was fetched directly from the **official Riot Games API**. This version required:

- A Riot developer API key (expires every 24 hours on dev tier).
- A local **SQLite database** (`cache.db`) to store match data between requests.
- An **Alembic** migration setup to manage the schema.
- A background `watchdog.sh` script to restart the server, refresh the cloudflared tunnel URL, and push the new URL to the GitHub profile README via SSH.

The Riot API flow was:
1. Resolve `game_name#tag_line` → `puuid` via the Account API.
2. Fetch summoner info + league entries (rank/LP) concurrently.
3. Fetch recent match IDs and cache any unseen matches into SQLite.
4. Build the SVG/PNG from the cached match data.

This version is preserved in git history but is no longer the active backend.

---

## Features (v2)

- PNG stats card with the last 5 games (placement, augments, traits, units, items).
- Player header with rank, LP, average placement, top-4 rate, and win rate.
- No API key required — data sourced from MetaTFT.
- In-memory asset cache (base64 data URIs) for fast repeated renders.
- `/health` endpoint reporting server uptime.

---

## Project Structure

```
tft-stats-api/
├── src/
│   ├── main.py                        # Flask entry point (port 5001)
│   ├── api/
│   │   └── routes/
│   │       └── stats.py               # /health and /png endpoints
│   ├── services/
│   │   └── metatft_service.py         # MetaTFT API client + schema transformation
│   ├── utils/
│   │   ├── svg_builder.py             # SVG card layout builder
│   │   └── svg_to_png.py              # cairosvg renderer + base64 asset inlining
│   ├── schemas/                        # Pydantic v2 schemas (match, player, metatft)
│   ├── assets/                         # Local TFT icons (items, traits, units, augments)
│   └── config/
│       └── settings.py                # MetaTFT request timeout config
├── scripts/
│   └── watchdog.sh                    # Cron-safe: restart Flask, refresh cloudflared tunnel, push README
├── migrations/                         # Alembic migrations (v1 legacy — SQLite schema)
├── logs/                               # Server + tunnel logs (git-ignored)
├── requirements.txt
├── .env                                # Environment variables (not committed)
└── README.md
```

---

## Setup

### Requirements

- Python 3.11+
- `brew install cloudflared` (for GitHub profile tunnel)
- Cairo system library (required by cairosvg): `brew install cairo`

### Install

```zsh
git clone git@github.com:johnzey-dev/tft-stats-api.git
cd tft-stats-api
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Run

```zsh
source venv/bin/activate
PYTHONPATH=src python src/main.py
```

Server starts on `http://localhost:5001`.

---

## API Reference

### `GET /health`

Returns server status and uptime.

```json
{ "status": "ok", "uptime_seconds": 3421 }
```

---

### `GET /tft-stats/<region>/<game_name>/<tag_line>/<tft_set>/png`

Returns a PNG stats card for the player's last 5 games in the given TFT set.

| Parameter   | Description             | Example    |
|-------------|-------------------------|------------|
| `region`    | Platform region         | `EUW1`     |
| `game_name` | Riot game name          | `LeeSIUU`  |
| `tag_line`  | Riot tag line           | `SIUU`     |
| `tft_set`   | TFT set identifier      | `TFTSet16` |

**Example:**
```
curl -o stats.png "http://localhost:5001/tft-stats/EUW1/LeeSIUU/SIUU/TFTSet16/png"
```

**Embed in a GitHub README:**
```markdown
![TFT Stats](https://<your-tunnel>.trycloudflare.com/tft-stats/EUW1/LeeSIUU/SIUU/TFTSet16/png)
```

---

## Watchdog / Automation

`scripts/watchdog.sh` automates the full deployment cycle for GitHub profile hosting:

1. Checks `localhost:5001` health — restarts Flask if down.
2. Kills the old cloudflared tunnel and starts a fresh one.
3. Extracts the new `trycloudflare.com` URL.
4. Clones the `johnzey-dev/johnzey-dev` profile repo via SSH.
5. Replaces the old tunnel URL in `README.md` with `sed`.
6. Commits and pushes via SSH (key passed directly — no passphrase agent needed).

**Install as a cron job (every 30 minutes):**
```
crontab -e
*/30 * * * * /Users/john/fun-apps/tft-stats-api/scripts/watchdog.sh >> /Users/john/fun-apps/tft-stats-api/logs/watchdog.log 2>&1
```

---

## License

MIT
