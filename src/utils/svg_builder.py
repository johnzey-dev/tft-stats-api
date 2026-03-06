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
PLACE_GAP    = 8    # gap between placement and traits

# Trait badges (vertical column, left of units)
BADGE_W      = 54   # badge total width
BADGE_H      = 22   # badge height   → matches metatft compact badge
BADGE_ICON   = 16   # icon inside badge
BADGE_GAP    = 3    # vertical gap between badges
BADGE_R_GAP  = 8    # gap between trait column and first unit

# Units
UNIT_PX      = 48   # portrait size (48×48 matches metatft CDN request)
UNIT_GAP     = 4    # horizontal gap between unit cells
PORT_BORDER  = 2    # rarity border thickness

# Stars (above portrait)  — metatft uses height="12", we use 13 for clarity
STARS_H      = 13
STARS_GAP    = 2    # gap between stars image and portrait top

# Items (below portrait)
ITEM_PX      = 18   # displayed size of each item icon
ITEM_GAP     = 2    # horizontal gap between items
ITEMS_V_GAP  = 3    # gap between portrait bottom and items row

# Full unit cell height  (stars area + gap + portrait + gap + items)
CELL_H = STARS_H + STARS_GAP + UNIT_PX + ITEMS_V_GAP + ITEM_PX

# Misc
BG            = "#0f1117"
ROW_BG_ALT    = "#12151f"
DIVIDER_COLOR = "#1e2130"


# ── Row renderer ──────────────────────────────────────────────────────────────

def _render_row(out: list, match_data: dict, y0: int, svg_w: int, row_index: int) -> None:
    """Append SVG elements for one match row into `out`."""
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

    # cursor starts after outer + row padding
    cx = OUTER_PAD + ROW_H_PAD

    # ── Placement ─────────────────────────────────────────────────────────────
    p_color = PLACEMENT_COLOR.get(placement, "#8a8fa8") if placement else "#8a8fa8"
    text_cy = y0 + ROW_V_PAD + CELL_H // 2 + 7
    out.append(
        f'<text x="{cx + PLACE_W // 2}" y="{text_cy}" '
        f'font-family="Arial,sans-serif" font-size="16" font-weight="bold" '
        f'text-anchor="middle" fill="{p_color}">#{placement or "?"}</text>'
    )
    cx += PLACE_W + PLACE_GAP

    # ── Trait badges ──────────────────────────────────────────────────────────
    traits_total_h = len(active_traits) * BADGE_H + max(0, len(active_traits) - 1) * BADGE_GAP
    ty0 = y0 + ROW_V_PAD + (CELL_H - traits_total_h) // 2

    for i, trait in enumerate(active_traits):
        by   = ty0 + i * (BADGE_H + BADGE_GAP)
        bx   = cx
        bg   = STYLE_BG.get(trait.get("style", 0), "#2a2a3a")
        icon = _trait_icon_src(trait.get("name", ""))
        cnt  = trait.get("num_units", "")

        out.append(f'<rect x="{bx}" y="{by}" width="{BADGE_W}" height="{BADGE_H}" fill="{bg}" rx="3"/>')
        # trait icon (white silhouette via mask-image on metatft; shown as-is here)
        icon_y = by + (BADGE_H - BADGE_ICON) // 2
        out.append(f'<image href="{icon}" x="{bx + 3}" y="{icon_y}" width="{BADGE_ICON}" height="{BADGE_ICON}"/>')
        # count number
        tx = bx + 3 + BADGE_ICON + 4
        ty = by + BADGE_H // 2 + 5
        out.append(
            f'<text x="{tx}" y="{ty}" '
            f'font-family="Arial,sans-serif" font-size="12" font-weight="bold" fill="white">{cnt}</text>'
        )

    cx += BADGE_W + BADGE_R_GAP

    # ── Unit cells ────────────────────────────────────────────────────────────
    cell_y = y0 + ROW_V_PAD   # top of cell area (where stars row begins)

    for idx, unit in enumerate(units):
        ux     = cx + idx * (UNIT_PX + UNIT_GAP)
        rarity = unit.get("rarity") or 0
        stars  = unit.get("stars") or 0
        cid    = (unit.get("character_id") or "").lower()
        items  = (unit.get("items") or [])[:3]
        border = RARITY_BORDER.get(rarity, "#b5b5b5")

        # Stars image (metatft: <img height="12" src=".../tiers/N.png">)
        if stars and stars > 0:
            out.append(
                f'<image href="{_stars_src(stars)}" '
                f'x="{ux}" y="{cell_y}" '
                f'width="{UNIT_PX}" height="{STARS_H}"/>'
            )

        # Portrait with rarity border
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

        # Items (centred below portrait)
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


def ROW_H() -> int:
    return ROW_V_PAD + CELL_H + ROW_V_PAD


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

    max_units  = max((len(m.get("units") or []) for m in matches), default=0)
    units_w    = max(0, max_units * (UNIT_PX + UNIT_GAP) - UNIT_GAP)
    inner_w    = PLACE_W + PLACE_GAP + BADGE_W + BADGE_R_GAP + units_w
    W          = OUTER_PAD + ROW_H_PAD + inner_w + ROW_H_PAD + OUTER_PAD
    row_h      = ROW_H()
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
