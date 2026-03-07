"""image_proxy — resolve TFT asset image paths for SVG rendering.

``local_image_href`` returns a ``file://`` URI for a pre-downloaded asset so
svglib can load it directly from disk when converting SVG → PNG.

For dynamic per-player images (profile icons) that may not be pre-downloaded,
it fetches the image from the CDN, saves it to ``src/assets/`` for future use,
and returns the local ``file://`` URI.

Missing/unfetchable images return an empty string — svglib skips blank hrefs.
"""

from __future__ import annotations

import logging
from pathlib import Path

import requests

log = logging.getLogger(__name__)

# Root of the local asset store (src/assets/)
ASSETS_DIR = Path(__file__).parent.parent / "assets"

_SESSION = requests.Session()
_SESSION.headers["User-Agent"] = "tft-stats-api/1.0"
_TIMEOUT = 8


def local_image_href(path: Path, fallback_cdn_url: str = "") -> str:
    """Return a ``file://`` URI for *path* if it exists locally.

    If the file is missing and *fallback_cdn_url* is provided, fetches from
    the CDN, saves it to *path*, then returns the ``file://`` URI.
    Returns ``""`` if the file cannot be resolved.
    """
    if path.exists():
        return path.resolve().as_uri()

    if not fallback_cdn_url:
        log.debug("Local asset missing, no fallback: %s", path)
        return ""

    # Strip cdn-cgi resizer wrapper if present
    import re
    m = re.search(r"(https://cdn\.metatft\.com/file/metatft/.+)", fallback_cdn_url)
    fetch_url = m.group(1) if m else fallback_cdn_url

    try:
        resp = _SESSION.get(fetch_url, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.content
        if data[:4] not in (b"\x89PNG", b"GIF8", b"\xff\xd8\xff", b"RIFF"):
            log.warning("Non-image response from %s", fetch_url)
            return ""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        log.debug("Downloaded and cached %d bytes → %s", len(data), path)
        return path.resolve().as_uri()
    except Exception as exc:
        log.warning("Image fetch failed (%s): %s", fetch_url, exc)
        return ""
