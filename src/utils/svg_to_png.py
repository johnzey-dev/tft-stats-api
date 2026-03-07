"""svg_to_png — convert an SVG string to PNG bytes using cairosvg.

cairosvg is a full SVG renderer built on Cairo/Pango. It correctly renders
<image> tags with data URI sources, text, rounded rects, clipPaths, and opacity.

Before rendering we replace all raw.githubusercontent.com hrefs with base64
data URIs read from the local src/assets/ copies so no HTTP requests are made.

Install: ``pip install cairosvg``
"""

from __future__ import annotations

import base64
import re
from pathlib import Path

import cairosvg

# Path to the local assets directory (same tree committed to GitHub)
_ASSETS_DIR = Path(__file__).parent.parent / "assets"

# The GitHub raw prefix used in the SVG hrefs
_GITHUB_RAW = "https://raw.githubusercontent.com/johnzey-dev/tft-stats-api/main/src/assets"

_HREF_RE = re.compile(r'href="(https://raw\.githubusercontent\.com/[^"]+)"')


def _github_url_to_local(url: str) -> Path | None:
    """Map a raw.githubusercontent.com asset URL to its local path."""
    if not url.startswith(_GITHUB_RAW):
        return None
    rel = url[len(_GITHUB_RAW):].lstrip("/")
    return _ASSETS_DIR / rel


# In-process cache: path → data URI string (populated on first render, reused forever)
_DATA_URI_CACHE: dict[str, str] = {}


def _to_data_uri(path: Path) -> str | None:
    """Read a local PNG and return a base64 data URI string.

    Results are cached in ``_DATA_URI_CACHE`` so each file is read from disk
    only once per server process — subsequent PNG renders are pure CPU work.
    """
    key = str(path)
    if key in _DATA_URI_CACHE:
        return _DATA_URI_CACHE[key]
    if not path.exists():
        return None
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    uri = f"data:image/png;base64,{data}"
    _DATA_URI_CACHE[key] = uri
    return uri


def _inline_images(svg: str) -> str:
    """Replace GitHub raw URLs in href= attributes with local data URIs."""
    def replacer(m: re.Match) -> str:
        url = m.group(1)
        local = _github_url_to_local(url)
        if local is None:
            return m.group(0)
        data_uri = _to_data_uri(local)
        if data_uri is None:
            return m.group(0)
        return f'href="{data_uri}"'

    return _HREF_RE.sub(replacer, svg)


def svg_to_png(svg: str, scale: float = 2.0) -> bytes:
    """Convert *svg* (a string) to PNG bytes using cairosvg.

    Args:
        svg:   The SVG markup to render.
        scale: Output resolution multiplier (default 2.0 = 2× / retina).

    Returns:
        Raw PNG bytes.
    """
    # Replace all GitHub raw URLs with local base64 data URIs so cairosvg
    # can render them without making HTTP requests.
    svg = _inline_images(svg)

    # cairosvg renders SVG to PNG directly, with scale support via dpi
    # Default browser DPI is 96; multiply by scale for retina output
    return cairosvg.svg2png(bytestring=svg.encode("utf-8"), scale=scale)
