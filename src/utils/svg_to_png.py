"""svg_to_png — convert an SVG string to PNG bytes using svglib + Pillow.

``svglib`` renders the SVG (including ``<image>`` tags with data-URI sources)
via ReportLab, then Pillow is used to scale the result to the desired
resolution.  Both are pure-Python wheels with no native system dependencies.

Install: ``pip install svglib reportlab Pillow``
"""

from __future__ import annotations

import io
import tempfile
import os

from PIL import Image
from reportlab.graphics import renderPM
from svglib.svglib import svg2rlg


def svg_to_png(svg: str, scale: float = 2.0) -> bytes:
    """Convert *svg* (a string) to PNG bytes.

    Args:
        svg:   The SVG markup to render.
        scale: Output resolution multiplier (default 2.0 = 2× / retina).

    Returns:
        Raw PNG bytes.
    """
    # svglib requires a file path, so write to a named temp file
    with tempfile.NamedTemporaryFile(
        suffix=".svg", delete=False, mode="w", encoding="utf-8"
    ) as f:
        f.write(svg)
        tmp_path = f.name

    try:
        drawing = svg2rlg(tmp_path)
    finally:
        os.unlink(tmp_path)

    if drawing is None:
        raise ValueError("svglib could not parse the SVG document")

    # Render at 1× first into a buffer
    buf = io.BytesIO()
    renderPM.drawToFile(drawing, buf, fmt="PNG", dpi=96)
    buf.seek(0)

    if scale == 1.0:
        return buf.read()

    # Upscale with Pillow using high-quality resampling
    img = Image.open(buf)
    new_w = round(img.width * scale)
    new_h = round(img.height * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()
