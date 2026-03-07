"""Download all TFT asset images from the CDN to src/assets/.

Run from the project root:
    PYTHONPATH=src venv/bin/python scripts/download_assets.py

Images are stored at:
    src/assets/champions/tft16_shen.png
    src/assets/items/tft_item_warmogs.png
    src/assets/traits/brawler.png
    src/assets/ranks/gold.png
    src/assets/profileicons/profileicon29.png
    etc.

Only missing files are downloaded (safe to re-run).
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

# ── Bootstrap Flask app to access the DB ──────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
app_module = __import__("main")
app = app_module.app

ASSETS_DIR = Path(__file__).parent.parent / "src" / "assets"
SESSION = requests.Session()
SESSION.headers["User-Agent"] = "tft-stats-api-downloader/1.0"


def extract_direct_url(cdn_url: str) -> str:
    """Strip the cdn-cgi resizer wrapper, return the inner /file/ URL."""
    m = re.search(r"(https://cdn\.metatft\.com/file/.+)", cdn_url or "")
    return m.group(1) if m else cdn_url


def url_to_local_path(url: str) -> Path:
    """Map a CDN URL to a local assets/ path.

    https://cdn.metatft.com/file/metatft/champions/tft16_shen.png
      → src/assets/champions/tft16_shen.png
    """
    parsed = urlparse(url)
    # path looks like /file/metatft/champions/tft16_shen.png
    # strip the /file/metatft/ prefix
    parts = Path(parsed.path).parts  # ('/', 'file', 'metatft', 'champions', 'x.png')
    relative = Path(*parts[3:])  # ('champions', 'x.png')
    return ASSETS_DIR / relative


def download_all() -> None:
    with app.app_context():
        from extensions import db
        from models.item import Item
        from models.trait import Trait
        from models.unit import Unit

        rows: list[tuple[str, str]] = []
        rows += db.session.execute(db.select(Unit.unit_id, Unit.icon_url)).all()
        rows += db.session.execute(db.select(Item.item_id, Item.icon_url)).all()
        rows += db.session.execute(db.select(Trait.trait_id, Trait.icon_url)).all()

    # Deduplicate by direct URL
    seen: dict[str, str] = {}  # direct_url → local_path
    for _id, raw_url in rows:
        if not raw_url:
            continue
        direct = extract_direct_url(raw_url)
        local = url_to_local_path(direct)
        seen[direct] = str(local)

    total = len(seen)
    print(f"Found {total} unique assets in DB")

    downloaded = skipped = failed = 0

    for i, (url, local_str) in enumerate(seen.items(), 1):
        local = Path(local_str)
        if local.exists():
            skipped += 1
            continue

        local.parent.mkdir(parents=True, exist_ok=True)

        try:
            resp = SESSION.get(url, timeout=15)
            resp.raise_for_status()
            if not resp.content[:4] in (b"\x89PNG", b"GIF8", b"\xff\xd8\xff", b"RIFF"):
                # not a real image
                print(f"  [WARN] non-image response for {url} ({len(resp.content)} bytes)")
                failed += 1
                continue
            local.write_bytes(resp.content)
            downloaded += 1
            if downloaded % 50 == 0:
                print(f"  [{i}/{total}] downloaded {downloaded} so far…")
            time.sleep(0.05)  # be polite
        except Exception as exc:
            print(f"  [FAIL] {url}: {exc}")
            failed += 1

    print(f"\nDone. Downloaded: {downloaded}  Skipped: {skipped}  Failed: {failed}")


if __name__ == "__main__":
    download_all()
