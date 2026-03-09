"""svg_to_png — convert an SVG string to PNG bytes using cairosvg.

Before rendering we replace all raw.githubusercontent.com hrefs with base64
data URIs read from the local src/assets/ copies so no HTTP requests are made.

Install: ``pip install cairosvg``
System:  ``brew install cairo`` (macOS) / ``apt install libcairo2`` (Linux)
"""

from __future__ import annotations

import base64
import os
import re
from pathlib import Path

# Ensure Homebrew's lib dir is in the dynamic linker path before cairocffi loads.
_homebrew_lib = "/opt/homebrew/lib"
if Path(_homebrew_lib).is_dir():
    _existing = os.environ.get("DYLD_LIBRARY_PATH", "")
    if _homebrew_lib not in _existing:
        os.environ["DYLD_LIBRARY_PATH"] = f"{_homebrew_lib}:{_existing}".strip(":")

import cairosvg

_ASSETS_DIR = Path(__file__).parent.parent / "assets"
_GITHUB_RAW = "https://raw.githubusercontent.com/johnzey-dev/tft-stats-api/main/src/assets"
_HREF_RE = re.compile(r'href="(https://raw\.githubusercontent\.com/[^"]+)"')

_DATA_URI_CACHE: dict[str, str] = {}


def _github_url_to_local(url: str) -> Path | None:
    if not url.startswith(_GITHUB_RAW):
        return None
    rel = url[len(_GITHUB_RAW):].lstrip("/")
    return _ASSETS_DIR / rel


def _to_data_uri(path: Path) -> str | None:
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
    svg = _inline_images(svg)
    return cairosvg.svg2png(bytestring=svg.encode("utf-8"), scale=scale)
