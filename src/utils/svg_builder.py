"""SVG board renderer for TFT match compositions, matching metatft layout."""

import re

_CDN  = "https://cdn.metatft.com/cdn-cgi/image"
_FILE = "https://cdn.metatft.com/file/metatft"


# ── URL helpers ───────────────────────────────────────────────────────────────

def _cdn(category: str, name: str, px: int) -> str:
    return f"{_CDN}/width={px},height={px},format=auto/{_FILE}/{category}/{name.lower()}.png"


def _champion_url(character_id: str) -> str:
    return _cdn("champions", character_id, 48)


def _item_url(item_id: str) -> str:
    return _cdn("items", item_id, 24)


def _trait_icon_src(trait_id: str) -> str:
    m = re.match(r"tft\d+_(.*)", trait_id, re.IGNORECASE)
    name = m.group(1) if m else trait_id
    return f"{_FILE}/traits/{name.lower()}.png"


def _stars_src(tier: int) -> str:
    return f"{_FILE}/tiers/{max(1, min(int(tier), 3))}.png"


# ── Colour maps ───────────────────────────────────────────────────────────────

RARITY_BORDER = {
    0: "#b5b5b5",   # 1-cost  gray
    1: "#14cf11",   # 2-cost  green
    2: "#2c76e9",   # 3-cost  blue
    4: "#db1fe9",   # 4-cost  purple
    6: "#b8a31c",   # 5-cost  gold
}

STYLE_BG = {
    1: "#7e4c1f",   # bronze
    2: "#4d5a65",   # silver
    3: "#7a6010",   # gold
    4: "#5c2d8a",   # chromatic / prismatic
}

PLACEMENT_COLOR = {
    1: "#FFD700",
    2: "#C0C0C0",
    3: "#CD7F32",
}

# ── Layout constants ──────────────────────────────────────────────────────────

OUTER_PAD    = 8
ROW_V_PAD    = 8
ROW_H_PAD    = 10

# Placement column
PLACE_W      = 30
PLACE_GAP    = 8

# Trait badges — vertical column left of units
BADGE_W      = 54   # total badge width
BADGE_H      = 22   # badge height
BADGE_ICON   = 16   # icon size inside badge
BADGE_GAP    = 3    # vertical gap between badges
BADGE_R_GAP  = 8    # gap between trait column and first unit

# Units
UNIT_PX      = 48
UNIT_GAP     = 4
PORT_BORDER  = 2

# Stars
STARS_H      = 13
STARS_GAP    = 2

# Items
ITEM_PX      = 18
ITEM_GAP     = 2
ITEMS_V_GAP  = 3

# Unit cell height (stars + gap + portrait + gap + items)
CELL_H = STARS_H + STARS_GAP + UNIT_PX + ITEMS_V_GAP + ITEM_PX

BG            = "#0f1117"
ROW_BG_ALT    = "#12151f"
DIVIDER_COLOR = "#1e2130"


def _traits_h(n: int) -> int:
    """Total pixel height needed by n trait badges."""
    if n == 0:
        return 0
    return n * BADGE_H + (n - 1) * BADGE_GAP


def _row_inner_h(n_traits: int) -> int:
    """Inner content height for a row: tall enough for both traits and units."""
    return max(CELL_H, _traits_h(n_traits))


# ── Row renderer ──────────────────────────────────────────────────────────────

def _render_row(out: list, match_data: dict, y0: int, svg_w: int, row_index: int,
                inner_h: int) -> None:
    units     = match_data.get("units") or []
    traits    = match_data.get("traits") or []
    placement = match_data.get("placement")

    row_h  = ROW_V_PAD + inner_h + ROW_V_PAD
    row_bg = ROW_BG_ALT if row_index % 2 == 0 else BG
    out.append(f'<rect x="0" y="{y0}" width="{svg_w}" height="{row_h}" fill="{row_bg}"/>')

    active_traits = sorted(
        [t for t in traits if t.get("tier_current", 0) > 0],
        key=lambda t: (t.get("num_units", 0), t.get("tier_current", 0)),
        reverse=True,
    )

    # ── Placement (vertically centred) ────────────────────────────────────────
    p_color = PLACEMENT_COLOR.get(placement, "#8a8fa8") if placement else "#8a8fa8"
    p_cy    = y0 + ROW_V_PAD + inner_h // 2 + 6
    p_cx    = OUTER_PAD + ROW_H_PAD + PLACE_W // 2
    out.append(
        f'<text x="{p_cx}" y="{p_cy}" '
        f'font-family="Arial,sans-serif" font-size="16" font-weight="bold" '
        f'text-anchor="middle" fill="{p_color}">#{placement or "?"}</text>'
    )

    traits_x = OUTER_PAD + ROW_H_PAD + PLACE_W + PLACE_GAP

    # ── Trait badges — vertical column ────────────────────────────────────────
    th      = _traits_h(len(active_traits))
    ty0     = y0 + ROW_V_PAD + (inner_h - th) // 2   # vertically centre if shorter than units

    for i, trait in enumerate(active_traits):
        by   = ty0 + i * (BADGE_H + BADGE_GAP)
        bx   = traits_x
        bg   = STYLE_BG.get(trait.get("style", 0), "#2a2a3a")
        icon = _trait_icon_src(trait.get("name", ""))
        cnt  = trait.get("num_units", "")

        out.append(f'<rect x="{bx}" y="{by}" width="{BADGE_W}" height="{BADGE_H}" fill="{bg}" rx="3"/>')
        icon_y = by + (BADGE_H - BADGE_ICON) // 2
        out.append(
            f'<image href="{icon}" x="{bx + 3}" y="{icon_y}" '
            f'width="{BADGE_ICON}" height="{BADGE_ICON}"/>'
        )
        tx = bx + 3 + BADGE_ICON + 4
        ty_text = by + BADGE_H // 2 + 5
        out.append(
            f'<text x="{tx}" y="{ty_text}" '
            f'font-family="Arial,sans-serif" font-size="12" font-weight="bold" fill="white">{cnt}</text>'
        )

    # ── Unit cells ────────────────────────────────────────────────────────────
    units_x = traits_x + BADGE_W + BADGE_R_GAP
    # vertically centre unit cells within the row inner height
    cell_y  = y0 + ROW_V_PAD + (inner_h - CELL_H) // 2

    for idx, unit in enumerate(units):
        ux     = units_x + idx * (UNIT_PX + UNIT_GAP)
        rarity = unit.get("rarity") or 0
        stars  = unit.get("stars") or 0
        cid    = (unit.get("character_id") or "").lower()
        items  = (unit.get("items") or [])[:3]
        border = RARITY_BORDER.get(rarity, "#b5b5b5")

        if stars and stars > 0:
            out.append(
                f'<image href="{_stars_src(stars)}" '
                f'x="{ux}" y="{cell_y}" width="{UNIT_PX}" height="{STARS_H}"/>'
            )

        port_y  = cell_y + STARS_H + STARS_GAP
        b       = PORT_BORDER
        clip_id = f"clip{row_index}u{idx}"
        img_url = _champion_url(cid)

        out.append(
            f'<defs><clipPath id="{clip_id}">'
            f'<rect x="{ux + b}" y="{port_y + b}" '
            f'width="{UNIT_PX - b * 2}" height="{UNIT_PX - b * 2}" rx="2"/>'
            f'</clipPath></defs>'
        )
        out.append(
            f'<rect x="{ux}" y="{port_y}" '
            f'width="{UNIT_PX}" height="{UNIT_PX}" fill="{border}" rx="4"/>'
        )
        out.append(
            f'<image href="{img_url}" '
            f'x="{ux + b}" y="{port_y + b}" '
            f'width="{UNIT_PX - b * 2}" height="{UNIT_PX - b * 2}" '
            f'clip-path="url(#{clip_id})"/>'
        )

        item_y = port_y + UNIT_PX + ITEMS_V_GAP
        if items:
            total_items_w = len(items) * ITEM_PX + (len(items) - 1) * ITEM_GAP
            ix0 = ux + (UNIT_PX - total_items_w) // 2

            for j, it in enumerate(items):
                ix    = ix0 + j * (ITEM_PX + ITEM_GAP)
                iclip = f"clip{row_index}u{idx}i{j}"
                iurl  = _item_url(it.get("item_id") or "")

                out.append(
                    f'<defs><clipPath id="{iclip}">'
                    f'<rect x="{ix}" y="{item_y}" width="{ITEM_PX}" height="{ITEM_PX}" rx="2"/>'
                    f'</clipPath></defs>'
                )
                out.append(
                    f'<rect x="{ix}" y="{item_y}" width="{ITEM_PX}" height="{ITEM_PX}" fill="#111" rx="2"/>'
                )
                out.append(
                    f'<image href="{iurl}" x="{ix}" y="{item_y}" '
                    f'width="{ITEM_PX}" height="{ITEM_PX}" clip-path="url(#{iclip})"/>'
                )


# ── Public API ────────────────────────────────────────────────────────────────

def build_matches_svg(matches: list) -> str:
    """
    Render a list of match dicts as a single stacked SVG (one row per match).

    Each match dict must contain:
      - placement (int)
      - traits: [{name, num_units, style, tier_current}]
      - units:  [{character_id, rarity, stars, items: [{item_id}]}]
    """
    if not matches:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>'

    max_units = max((len(m.get("units") or []) for m in matches), default=0)

    # Each row may have a different number of traits → compute per-row inner heights
    row_inner_hs = [
        _row_inner_h(len([t for t in (m.get("traits") or []) if t.get("tier_current", 0) > 0]))
        for m in matches
    ]

    units_w  = max(0, max_units * (UNIT_PX + UNIT_GAP) - UNIT_GAP)
    inner_w  = PLACE_W + PLACE_GAP + BADGE_W + BADGE_R_GAP + units_w
    W        = OUTER_PAD + ROW_H_PAD + inner_w + ROW_H_PAD + OUTER_PAD

    row_hs   = [ROW_V_PAD + h + ROW_V_PAD for h in row_inner_hs]
    H        = sum(row_hs) + (len(matches) - 1)   # 1px dividers

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f'<rect width="{W}" height="{H}" fill="{BG}"/>',
    ]

    y = 0
    for i, match_data in enumerate(matches):
        _render_row(out, match_data, y, W, i, row_inner_hs[i])
        y += row_hs[i]
        if i < len(matches) - 1:
            out.append(f'<rect x="0" y="{y}" width="{W}" height="1" fill="{DIVIDER_COLOR}"/>')
            y += 1

    out.append("</svg>")
    return "\n".join(out)


def build_composition_svg(match_data: dict) -> str:
    """Render a single match as an SVG (convenience wrapper)."""
    return build_matches_svg([match_data])

_CDN  = "https://cdn.metatft.com/cdn-cgi/image"
_FILE = "https://cdn.metatft.com/file/metatft"


# ── URL helpers ───────────────────────────────────────────────────────────────

def _cdn(category: str, name: str, px: int) -> str:
    return f"{_CDN}/width={px},height={px},format=auto/{_FILE}/{category}/{name.lower()}.png"


def _champion_url(character_id: str) -> str:
    return _cdn("champions", character_id, 48)


def _item_url(item_id: str) -> str:
    return _cdn("items", item_id, 24)


def _trait_icon_src(trait_id: str) -> str:
    m = re.match(r"tft\d+_(.*)", trait_id, re.IGNORECASE)
    name = m.group(1) if m else trait_id
    return f"{_FILE}/traits/{name.lower()}.png"


def _stars_src(tier: int) -> str:
    return f"{_FILE}/tiers/{max(1, min(int(tier), 3))}.png"


# ── Colour maps ───────────────────────────────────────────────────────────────

RARITY_BORDER = {
    0: "#b5b5b5",   # 1-cost  gray
    1: "#14cf11",   # 2-cost  green
    2: "#2c76e9",   # 3-cost  blue
    4: "#db1fe9",   # 4-cost  purple
    6: "#b8a31c",   # 5-cost  gold
}

STYLE_BG = {
    1: "#7e4c1f",   # bronze
    2: "#4d5a65",   # silver
    3: "#7a6010",   # gold
    4: "#5c2d8a",   # chromatic / prismatic
}

PLACEMENT_COLOR = {
    1: "#FFD700",
    2: "#C0C0C0",
    3: "#CD7F32",
}

# ── Layout constants ──────────────────────────────────────────────────────────

OUTER_PAD    = 8    # SVG outer padding

# Row padding
ROW_V_PAD    = 8
ROW_H_PAD    = 10

# Placement column (left of everything)
PLACE_W      = 30
PLACE_GAP    = 10

# Trait badges — laid out HORIZONTALLY above the units
BADGE_H      = 22
BADGE_ICON   = 16
BADGE_H_PAD  = 4    # horizontal inner padding each side inside badge
BADGE_GAP    = 4    # horizontal gap between badges
TRAITS_V_GAP = 5    # vertical gap between trait row and unit row

# Units
UNIT_PX      = 48
UNIT_GAP     = 4
PORT_BORDER  = 2

# Stars
STARS_H      = 13
STARS_GAP    = 2

# Items
ITEM_PX      = 18
ITEM_GAP     = 2
ITEMS_V_GAP  = 3

# Full unit cell height
CELL_H = STARS_H + STARS_GAP + UNIT_PX + ITEMS_V_GAP + ITEM_PX

# Full row height (traits row + gap + units row)
ROW_INNER_H  = BADGE_H + TRAITS_V_GAP + CELL_H

# Misc
BG            = "#0f1117"
ROW_BG_ALT    = "#12151f"
DIVIDER_COLOR = "#1e2130"


def _badge_width(count_str: str) -> int:
    """Estimate badge width: icon + gap + count digits + padding."""
    digits = len(str(count_str))
    return BADGE_H_PAD + BADGE_ICON + 3 + max(10, digits * 8) + BADGE_H_PAD


# ── Row renderer ──────────────────────────────────────────────────────────────

def _render_row(out: list, match_data: dict, y0: int, svg_w: int, row_index: int) -> None:
    units     = match_data.get("units") or []
    traits    = match_data.get("traits") or []
    placement = match_data.get("placement")

    row_bg = ROW_BG_ALT if row_index % 2 == 0 else BG
    total_h = ROW_V_PAD + ROW_INNER_H + ROW_V_PAD
    out.append(f'<rect x="0" y="{y0}" width="{svg_w}" height="{total_h}" fill="{row_bg}"/>')

    active_traits = sorted(
        [t for t in traits if t.get("tier_current", 0) > 0],
        key=lambda t: (t.get("num_units", 0), t.get("tier_current", 0)),
        reverse=True,
    )

    # x cursor starts after outer + row padding + placement column
    content_x = OUTER_PAD + ROW_H_PAD + PLACE_W + PLACE_GAP

    # ── Placement (vertically centred on the left) ────────────────────────────
    p_color = PLACEMENT_COLOR.get(placement, "#8a8fa8") if placement else "#8a8fa8"
    p_cy    = y0 + ROW_V_PAD + ROW_INNER_H // 2 + 6
    out.append(
        f'<text x="{OUTER_PAD + ROW_H_PAD + PLACE_W // 2}" y="{p_cy}" '
        f'font-family="Arial,sans-serif" font-size="16" font-weight="bold" '
        f'text-anchor="middle" fill="{p_color}">#{placement or "?"}</text>'
    )

    # ── Trait badges — horizontal row ─────────────────────────────────────────
    trait_y = y0 + ROW_V_PAD
    bx      = content_x

    for trait in active_traits:
        cnt   = trait.get("num_units", "")
        bg    = STYLE_BG.get(trait.get("style", 0), "#2a2a3a")
        icon  = _trait_icon_src(trait.get("name", ""))
        bw    = _badge_width(cnt)

        out.append(f'<rect x="{bx}" y="{trait_y}" width="{bw}" height="{BADGE_H}" fill="{bg}" rx="3"/>')
        icon_y = trait_y + (BADGE_H - BADGE_ICON) // 2
        out.append(
            f'<image href="{icon}" x="{bx + BADGE_H_PAD}" y="{icon_y}" '
            f'width="{BADGE_ICON}" height="{BADGE_ICON}"/>'
        )
        tx = bx + BADGE_H_PAD + BADGE_ICON + 3
        ty = trait_y + BADGE_H // 2 + 5
        out.append(
            f'<text x="{tx}" y="{ty}" '
            f'font-family="Arial,sans-serif" font-size="12" font-weight="bold" fill="white">{cnt}</text>'
        )
        bx += bw + BADGE_GAP

    # ── Unit cells — row below traits ─────────────────────────────────────────
    cell_y = y0 + ROW_V_PAD + BADGE_H + TRAITS_V_GAP

    for idx, unit in enumerate(units):
        ux     = content_x + idx * (UNIT_PX + UNIT_GAP)
        rarity = unit.get("rarity") or 0
        stars  = unit.get("stars") or 0
        cid    = (unit.get("character_id") or "").lower()
        items  = (unit.get("items") or [])[:3]
        border = RARITY_BORDER.get(rarity, "#b5b5b5")

        if stars and stars > 0:
            out.append(
                f'<image href="{_stars_src(stars)}" '
                f'x="{ux}" y="{cell_y}" width="{UNIT_PX}" height="{STARS_H}"/>'
            )

        port_y  = cell_y + STARS_H + STARS_GAP
        b       = PORT_BORDER
        clip_id = f"clip{row_index}u{idx}"
        img_url = _champion_url(cid)

        out.append(
            f'<defs><clipPath id="{clip_id}">'
            f'<rect x="{ux + b}" y="{port_y + b}" '
            f'width="{UNIT_PX - b * 2}" height="{UNIT_PX - b * 2}" rx="2"/>'
            f'</clipPath></defs>'
        )
        out.append(
            f'<rect x="{ux}" y="{port_y}" '
            f'width="{UNIT_PX}" height="{UNIT_PX}" fill="{border}" rx="4"/>'
        )
        out.append(
            f'<image href="{img_url}" '
            f'x="{ux + b}" y="{port_y + b}" '
            f'width="{UNIT_PX - b * 2}" height="{UNIT_PX - b * 2}" '
            f'clip-path="url(#{clip_id})"/>'
        )

        item_y = port_y + UNIT_PX + ITEMS_V_GAP
        if items:
            total_items_w = len(items) * ITEM_PX + (len(items) - 1) * ITEM_GAP
            ix0 = ux + (UNIT_PX - total_items_w) // 2

            for j, it in enumerate(items):
                ix    = ix0 + j * (ITEM_PX + ITEM_GAP)
                iclip = f"clip{row_index}u{idx}i{j}"
                iurl  = _item_url(it.get("item_id") or "")

                out.append(
                    f'<defs><clipPath id="{iclip}">'
                    f'<rect x="{ix}" y="{item_y}" width="{ITEM_PX}" height="{ITEM_PX}" rx="2"/>'
                    f'</clipPath></defs>'
                )
                out.append(
                    f'<rect x="{ix}" y="{item_y}" width="{ITEM_PX}" height="{ITEM_PX}" fill="#111" rx="2"/>'
                )
                out.append(
                    f'<image href="{iurl}" x="{ix}" y="{item_y}" '
                    f'width="{ITEM_PX}" height="{ITEM_PX}" clip-path="url(#{iclip})"/>'
                )


def _row_h() -> int:
    return ROW_V_PAD + ROW_INNER_H + ROW_V_PAD


# ── Public API ────────────────────────────────────────────────────────────────

def build_matches_svg(matches: list) -> str:
    """
    Render a list of match dicts as a single stacked SVG (one row per match).

    Each match dict must contain:
      - placement (int)
      - traits: [{name, num_units, style, tier_current}]
      - units:  [{character_id, rarity, stars, items: [{item_id}]}]
    """
    if not matches:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>'

    max_units   = max((len(m.get("units") or []) for m in matches), default=0)
    max_traits  = max((len([t for t in (m.get("traits") or []) if t.get("tier_current", 0) > 0])
                       for m in matches), default=0)

    units_w    = max(0, max_units * (UNIT_PX + UNIT_GAP) - UNIT_GAP)
    # Worst-case trait row width (each badge ~36px wide)
    traits_w   = max(0, max_traits * (_badge_width(99) + BADGE_GAP) - BADGE_GAP)
    inner_w    = PLACE_W + PLACE_GAP + max(units_w, traits_w)
    W          = OUTER_PAD + ROW_H_PAD + inner_w + ROW_H_PAD + OUTER_PAD

    row_h      = _row_h()
    H          = len(matches) * row_h + (len(matches) - 1)  # 1px dividers

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f'<rect width="{W}" height="{H}" fill="{BG}"/>',
    ]

    for i, match_data in enumerate(matches):
        y0 = i * (row_h + 1)
        _render_row(out, match_data, y0, W, i)
        if i < len(matches) - 1:
            out.append(f'<rect x="0" y="{y0 + row_h}" width="{W}" height="1" fill="{DIVIDER_COLOR}"/>')

    out.append("</svg>")
    return "\n".join(out)


def build_composition_svg(match_data: dict) -> str:
    """Render a single match as an SVG (convenience wrapper)."""
    return build_matches_svg([match_data])

_CDN  = "https://cdn.metatft.com/cdn-cgi/image"
_FILE = "https://cdn.metatft.com/file/metatft"


# ── URL helpers (matching the exact metatft URL patterns from the site HTML) ──

def _cdn(category: str, name: str, px: int) -> str:
    return f"{_CDN}/width={px},height={px},format=auto/{_FILE}/{category}/{name.lower()}.png"


def _champion_url(character_id: str) -> str:
    return _cdn("champions", character_id, 48)


def _item_url(item_id: str) -> str:
    return _cdn("items", item_id, 24)


def _trait_icon_src(trait_id: str) -> str:
    """Return the raw (non-CDN) trait icon URL, same as metatft mask-image."""
    m = re.match(r"tft\d+_(.*)", trait_id, re.IGNORECASE)
    name = m.group(1) if m else trait_id
    return f"{_FILE}/traits/{name.lower()}.png"


def _stars_src(tier: int) -> str:
    """Stars row image — metatft hosts tiers/1.png, tiers/2.png, tiers/3.png."""
    return f"{_FILE}/tiers/{max(1, min(int(tier), 3))}.png"


# ── Colour maps (taken directly from metatft CSS / HTML border values) ────────

# Riot API rarity field → portrait border colour
RARITY_BORDER = {
    0: "#b5b5b5",   # 1-cost  gray
    1: "#14cf11",   # 2-cost  green
    2: "#2c76e9",   # 3-cost  blue
    4: "#db1fe9",   # 4-cost  purple
    6: "#b8a31c",   # 5-cost  gold
}

# Riot API trait style (int) → badge background
STYLE_BG = {
    1: "#7e4c1f",   # bronze
    2: "#4d5a65",   # silver
    3: "#7a6010",   # gold
    4: "#5c2d8a",   # chromatic / prismatic
}

PLACEMENT_COLOR = {
    1: "#FFD700",
    2: "#C0C0C0",
    3: "#CD7F32",
}

# ── Layout constants (mirroring metatft measurements) ─────────────────────────

OUTER_PAD    = 8    # SVG outer padding

# Row
ROW_V_PAD    = 8    # top/bottom padding inside each match row
ROW_H_PAD    = 10   # left/right padding inside each match row

# Placement badge (leftmost column)
PLACE_W      = 28   # width reserved for "#N" text
PLACE_GAP    = 8    # gap between placement and content

# Trait badges — horizontal row ABOVE units
BADGE_H      = 22   # badge height
BADGE_ICON   = 16   # icon size inside badge
BADGE_H_PAD  = 4    # horizontal inner padding each side
BADGE_GAP    = 4    # horizontal gap between badges
TRAITS_V_GAP = 4    # vertical gap between trait row and units row

# Units
UNIT_PX      = 48   # portrait size
UNIT_GAP     = 4    # horizontal gap between unit cells
PORT_BORDER  = 2    # rarity border thickness

# Stars (above portrait)
STARS_H      = 13
STARS_GAP    = 2

# Items (below portrait)
ITEM_PX      = 18
ITEM_GAP     = 2
ITEMS_V_GAP  = 3

# Full unit cell height  (stars area + gap + portrait + gap + items)
CELL_H = STARS_H + STARS_GAP + UNIT_PX + ITEMS_V_GAP + ITEM_PX

# Full inner row height = trait row + gap + unit cell
ROW_INNER_H = BADGE_H + TRAITS_V_GAP + CELL_H

# Misc
BG            = "#0f1117"
ROW_BG_ALT    = "#12151f"
DIVIDER_COLOR = "#1e2130"


def _badge_w(count_str) -> int:
    """Estimate badge width: icon + padding + count digits."""
    digits = len(str(count_str))
    return BADGE_H_PAD + BADGE_ICON + 3 + max(10, digits * 8) + BADGE_H_PAD


# ── Row renderer ──────────────────────────────────────────────────────────────

def _render_row(out: list, match_data: dict, y0: int, svg_w: int, row_index: int) -> None:
    """Append SVG elements for one match row: traits horizontally above units."""
    units     = match_data.get("units") or []
    traits    = match_data.get("traits") or []
    placement = match_data.get("placement")

    row_bg = ROW_BG_ALT if row_index % 2 == 0 else BG
    out.append(f'<rect x="0" y="{y0}" width="{svg_w}" height="{ROW_H()}" fill="{row_bg}"/>')

    active_traits = sorted(
        [t for t in traits if t.get("tier_current", 0) > 0],
        key=lambda t: (t.get("num_units", 0), t.get("tier_current", 0)),
        reverse=True,
    )

    content_x = OUTER_PAD + ROW_H_PAD + PLACE_W + PLACE_GAP

    # ── Placement (vertically centred on left) ────────────────────────────────
    p_color = PLACEMENT_COLOR.get(placement, "#8a8fa8") if placement else "#8a8fa8"
    p_cy    = y0 + ROW_V_PAD + ROW_INNER_H // 2 + 6
    out.append(
        f'<text x="{OUTER_PAD + ROW_H_PAD + PLACE_W // 2}" y="{p_cy}" '
        f'font-family="Arial,sans-serif" font-size="16" font-weight="bold" '
        f'text-anchor="middle" fill="{p_color}">#{placement or "?"}</text>'
    )

    # ── Trait badges — horizontal row ─────────────────────────────────────────
    bx      = content_x
    trait_y = y0 + ROW_V_PAD

    for trait in active_traits:
        cnt  = trait.get("num_units", "")
        bg   = STYLE_BG.get(trait.get("style", 0), "#2a2a3a")
        icon = _trait_icon_src(trait.get("name", ""))
        bw   = _badge_w(cnt)

        out.append(f'<rect x="{bx}" y="{trait_y}" width="{bw}" height="{BADGE_H}" fill="{bg}" rx="3"/>')
        icon_y = trait_y + (BADGE_H - BADGE_ICON) // 2
        out.append(
            f'<image href="{icon}" x="{bx + BADGE_H_PAD}" y="{icon_y}" '
            f'width="{BADGE_ICON}" height="{BADGE_ICON}"/>'
        )
        tx = bx + BADGE_H_PAD + BADGE_ICON + 3
        ty = trait_y + BADGE_H // 2 + 5
        out.append(
            f'<text x="{tx}" y="{ty}" '
            f'font-family="Arial,sans-serif" font-size="12" font-weight="bold" fill="white">{cnt}</text>'
        )
        bx += bw + BADGE_GAP

    # ── Unit cells — row below traits ─────────────────────────────────────────
    cell_y = y0 + ROW_V_PAD + BADGE_H + TRAITS_V_GAP

    for idx, unit in enumerate(units):
        ux     = content_x + idx * (UNIT_PX + UNIT_GAP)
        rarity = unit.get("rarity") or 0
        stars  = unit.get("stars") or 0
        cid    = (unit.get("character_id") or "").lower()
        items  = (unit.get("items") or [])[:3]
        border = RARITY_BORDER.get(rarity, "#b5b5b5")

        if stars and stars > 0:
            out.append(
                f'<image href="{_stars_src(stars)}" '
                f'x="{ux}" y="{cell_y}" width="{UNIT_PX}" height="{STARS_H}"/>'
            )

        port_y  = cell_y + STARS_H + STARS_GAP
        b       = PORT_BORDER
        clip_id = f"clip{row_index}u{idx}"
        img_url = _champion_url(cid)

        out.append(
            f'<defs><clipPath id="{clip_id}">'
            f'<rect x="{ux + b}" y="{port_y + b}" '
            f'width="{UNIT_PX - b * 2}" height="{UNIT_PX - b * 2}" rx="2"/>'
            f'</clipPath></defs>'
        )
        out.append(
            f'<rect x="{ux}" y="{port_y}" '
            f'width="{UNIT_PX}" height="{UNIT_PX}" fill="{border}" rx="4"/>'
        )
        out.append(
            f'<image href="{img_url}" '
            f'x="{ux + b}" y="{port_y + b}" '
            f'width="{UNIT_PX - b * 2}" height="{UNIT_PX - b * 2}" '
            f'clip-path="url(#{clip_id})"/>'
        )

        item_y = port_y + UNIT_PX + ITEMS_V_GAP
        if items:
            n     = len(items)
            # shrink item size so all items always fit within the unit portrait width
            ipx   = min(ITEM_PX, (UNIT_PX - (n - 1) * ITEM_GAP) // n)
            total_items_w = n * ipx + (n - 1) * ITEM_GAP
            ix0 = ux + (UNIT_PX - total_items_w) // 2

            for j, it in enumerate(items):
                ix    = ix0 + j * (ipx + ITEM_GAP)
                iclip = f"clip{row_index}u{idx}i{j}"
                iurl  = _item_url(it.get("item_id") or "")

                out.append(
                    f'<defs><clipPath id="{iclip}">'
                    f'<rect x="{ix}" y="{item_y}" width="{ipx}" height="{ipx}" rx="2"/>'
                    f'</clipPath></defs>'
                )
                out.append(
                    f'<rect x="{ix}" y="{item_y}" width="{ipx}" height="{ipx}" fill="#111" rx="2"/>'
                )
                out.append(
                    f'<image href="{iurl}" x="{ix}" y="{item_y}" '
                    f'width="{ipx}" height="{ipx}" clip-path="url(#{iclip})"/>'
                )


def ROW_H() -> int:
    return ROW_V_PAD + ROW_INNER_H + ROW_V_PAD


# ── Player profile banner ─────────────────────────────────────────────────────

TIER_TEXT_COLOR = {
    "iron":        "#8f8f8f",
    "bronze":      "#cd7f32",
    "silver":      "#c0c0c0",
    "gold":        "#f0b43a",
    "platinum":    "#4ac2aa",
    "emerald":     "#37b26d",
    "diamond":     "#61a8ff",
    "master":      "#b074ff",
    "grandmaster": "#ff6f6f",
    "challenger":  "#8cd1ff",
}

PROFILE_HEADER_H   = 170
PROFILE_HEADER_GAP = 10

SUMMARY_BAR_H      = 90   # height of the summary cards section
SUMMARY_BAR_GAP    = 0    # gap between profile header and summary bar


def _total_header_h(player_profile: dict | None) -> int:
    if not player_profile:
        return 0
    summary_h = (SUMMARY_BAR_H + SUMMARY_BAR_GAP) if player_profile.get('set_summary') else 0
    return PROFILE_HEADER_H + PROFILE_HEADER_GAP + summary_h


def _xml_escape(value) -> str:
    text = "" if value is None else str(value)
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


_PLATFORM_LABELS = {
    "euw1": "EUW", "eun1": "EUNE", "na1": "NA",
    "kr": "KR",   "jp1": "JP",   "br1": "BR",
    "la1": "LAN", "la2": "LAS",  "oc1": "OCE",
    "tr1": "TR",  "ru": "RU",
}


def _platform_badge(platform: str) -> str:
    p = (platform or "").lower()
    return _PLATFORM_LABELS.get(p, p.upper())


def _render_summary_bar(out: list, svg_w: int, y0: int, summary: dict) -> None:
    """Draw the three summary stat cards (Avg Place / Top 4 / Win) in a dark bar."""
    total  = summary.get('total_games') or 0
    avg    = summary.get('avg_placement')
    top4   = summary.get('top4_count', 0)
    wins   = summary.get('win_count', 0)

    top4_pct = round(top4 / total * 100, 1) if total else 0
    win_pct  = round(wins / total * 100, 1) if total else 0

    avg_text  = f"{avg:.2f}" if avg is not None else "—"
    top4_text = f"{top4_pct}%"
    win_text  = f"{win_pct}%"

    bar_bg = "#13161f"
    out.append(f'<rect x="0" y="{y0}" width="{svg_w}" height="{SUMMARY_BAR_H}" fill="{bar_bg}"/>')

    # "Summary" title left, "All Queues" right
    title_y = y0 + 20
    out.append(
        f'<text x="{OUTER_PAD + ROW_H_PAD}" y="{title_y}" '
        f'font-family="Arial,sans-serif" font-size="13" font-weight="700" fill="#e8ecf5">Summary</text>'
    )
    out.append(
        f'<text x="{svg_w - OUTER_PAD - ROW_H_PAD}" y="{title_y}" '
        f'font-family="Arial,sans-serif" font-size="11" font-weight="600" '
        f'text-anchor="end" fill="#7a82a0">All Queues</text>'
    )

    # Three stat cards equally spaced
    card_w   = (svg_w - 2 * (OUTER_PAD + ROW_H_PAD)) // 3
    card_x0  = OUTER_PAD + ROW_H_PAD
    card_y   = y0 + 28
    card_h   = SUMMARY_BAR_H - 30
    card_bg  = "#1b1f2e"
    card_r   = 6

    stats = [
        (avg_text,  "#fddf7f", "Avg Place", f"{total} Games"),
        (top4_text, "#d9f17f", "Top 4",     f"{top4} Games"),
        (win_text,  "#d0f57f", "Win",        f"{wins} Games"),
    ]

    for i, (value, color, label, games) in enumerate(stats):
        cx   = card_x0 + i * card_w + card_w // 2
        bx   = card_x0 + i * card_w + 2
        bw   = card_w - 4

        out.append(f'<rect x="{bx}" y="{card_y}" width="{bw}" height="{card_h}" rx="{card_r}" fill="{card_bg}"/>')
        out.append(
            f'<text x="{cx}" y="{card_y + 28}" '
            f'font-family="Arial,sans-serif" font-size="18" font-weight="700" '
            f'text-anchor="middle" fill="{color}">{_xml_escape(value)}</text>'
        )
        out.append(
            f'<text x="{cx}" y="{card_y + 44}" '
            f'font-family="Arial,sans-serif" font-size="11" font-weight="600" '
            f'text-anchor="middle" fill="#9aa4c5">{_xml_escape(label)}</text>'
        )
        out.append(
            f'<text x="{cx}" y="{card_y + 58}" '
            f'font-family="Arial,sans-serif" font-size="10" '
            f'text-anchor="middle" fill="#5a6078">{_xml_escape(games)}</text>'
        )


def _render_player_header(out: list, svg_w: int, player_profile: dict) -> None:
    center_x = svg_w // 2
    y0       = 8

    game_name   = _xml_escape(player_profile.get("game_name"))
    tag_line    = _xml_escape(player_profile.get("tag_line"))
    platform    = _xml_escape(_platform_badge(player_profile.get("platform") or ""))
    queue_label = _xml_escape(player_profile.get("queue_label") or "Ranked")

    tier       = (player_profile.get("tier") or "").strip()
    tier_lower = tier.lower()
    tier_title = tier.title() if tier else "Unranked"
    division   = _xml_escape(player_profile.get("rank") or "")
    lp         = player_profile.get("lp")
    lp_text    = f"{lp} LP" if lp is not None else ""
    tier_color = TIER_TEXT_COLOR.get(tier_lower, "#f2f2f2")

    profile_icon_id  = player_profile.get("profile_icon_id") or 1
    profile_icon_url = _xml_escape(
        player_profile.get("profile_icon_url")
        or f"{_FILE}/profileicons/profileicon{profile_icon_id}.png"
    )
    wings_url = _xml_escape(
        player_profile.get("wings_url")
        or (f"{_FILE}/ranks/wings_{tier_lower}.png" if tier_lower else "")
    )
    rank_icon_url = _xml_escape(
        player_profile.get("rank_icon_url")
        or (f"{_FILE}/ranks/{tier_lower}.png" if tier_lower else "")
    )

    # Background
    out.append(f'<rect x="0" y="0" width="{svg_w}" height="{PROFILE_HEADER_H}" fill="{BG}"/>')

    # Wings behind avatar
    if wings_url:
        out.append(
            f'<image href="{wings_url}" x="{center_x - 110}" y="{y0}" '
            f'width="220" height="110" opacity="0.95"/>'
        )

    # Circular avatar
    avatar_r    = 34
    avatar_cx   = center_x
    avatar_cy   = y0 + 48
    avatar_clip = "profileAvatarClip"
    out.append(
        f'<defs><clipPath id="{avatar_clip}">'
        f'<circle cx="{avatar_cx}" cy="{avatar_cy}" r="{avatar_r}"/>'
        f'</clipPath></defs>'
    )
    out.append(f'<circle cx="{avatar_cx}" cy="{avatar_cy}" r="{avatar_r + 3}" fill="#d49b39" opacity="0.85"/>')
    out.append(
        f'<image href="{profile_icon_url}" '
        f'x="{avatar_cx - avatar_r}" y="{avatar_cy - avatar_r}" '
        f'width="{avatar_r * 2}" height="{avatar_r * 2}" '
        f'clip-path="url(#{avatar_clip})"/>'
    )

    # Name line: GameName#TagLine
    out.append(
        f'<text x="{center_x}" y="{y0 + 103}" '
        f'font-family="Arial,sans-serif" font-size="20" font-weight="700" '
        f'text-anchor="middle" fill="#f5f7ff">{game_name}'
        f'<tspan fill="#a8afc6">#{tag_line}</tspan></text>'
    )

    # Rank line: [icon] Gold II | 14 LP
    rank_line_y = y0 + 128
    if rank_icon_url:
        out.append(
            f'<image href="{rank_icon_url}" '
            f'x="{center_x - 86}" y="{rank_line_y - 18}" width="20" height="20"/>'
        )
    out.append(
        f'<text x="{center_x}" y="{rank_line_y}" '
        f'font-family="Arial,sans-serif" font-size="16" font-weight="700" '
        f'text-anchor="middle" fill="{tier_color}">{_xml_escape(tier_title)} '
        f'<tspan fill="#e9edf9">{division}</tspan>'
        f'<tspan fill="#9aa4c5"> | {lp_text}</tspan></text>'
    )

    # Ranked label + region badge
    out.append(
        f'<text x="{center_x - 10}" y="{y0 + 150}" '
        f'font-family="Arial,sans-serif" font-size="13" font-weight="600" '
        f'text-anchor="end" fill="#b8bfd8">{queue_label}</text>'
    )
    out.append(
        f'<rect x="{center_x + 2}" y="{y0 + 135}" width="44" height="20" rx="6" fill="#575e74" opacity="0.9"/>'
    )
    out.append(
        f'<text x="{center_x + 24}" y="{y0 + 149}" '
        f'font-family="Arial,sans-serif" font-size="12" font-weight="700" '
        f'text-anchor="middle" fill="#f3f5ff">{platform}</text>'
    )


# ── Public API ────────────────────────────────────────────────────────────────

def build_matches_svg(matches: list, player_profile: dict | None = None) -> str:
    """
    Render a list of match dicts as a single stacked SVG (one row per match).

    Each match dict must contain:
      - placement (int)
      - traits: [{name, num_units, style, tier_current}]
      - units:  [{character_id, rarity, stars, items: [{item_id}]}]
    """
    if not matches:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>'

    max_units  = max((len(m.get("units") or []) for m in matches), default=0)
    max_traits = max((len([t for t in (m.get("traits") or []) if t.get("tier_current", 0) > 0])
                      for m in matches), default=0)
    units_w    = max(0, max_units * (UNIT_PX + UNIT_GAP) - UNIT_GAP)
    traits_w   = max(0, max_traits * (_badge_w(9) + BADGE_GAP) - BADGE_GAP)
    inner_w    = PLACE_W + PLACE_GAP + max(units_w, traits_w)
    W          = OUTER_PAD + ROW_H_PAD + inner_w + ROW_H_PAD + OUTER_PAD
    row_h      = ROW_H()
    profile_h  = _total_header_h(player_profile)
    H          = profile_h + len(matches) * row_h + (len(matches) - 1)  # 1px dividers

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f'<rect width="{W}" height="{H}" fill="{BG}"/>',
    ]

    if player_profile:
        _render_player_header(out, W, player_profile)
        summary = player_profile.get('set_summary')
        if summary:
            summary_y0 = PROFILE_HEADER_H + PROFILE_HEADER_GAP + SUMMARY_BAR_GAP
            _render_summary_bar(out, W, summary_y0, summary)

    for i, match_data in enumerate(matches):
        y0 = profile_h + i * (row_h + 1)
        _render_row(out, match_data, y0, W, i)
        if i < len(matches) - 1:
            out.append(f'<rect x="0" y="{y0 + row_h}" width="{W}" height="1" fill="{DIVIDER_COLOR}"/>')

    out.append("</svg>")
    return "\n".join(out)


def build_composition_svg(match_data: dict, player_profile: dict | None = None) -> str:
    """Render a single match as an SVG (convenience wrapper)."""
    return build_matches_svg([match_data], player_profile=player_profile)
