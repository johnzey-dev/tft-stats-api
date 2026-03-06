import re

CDRAGON  = "https://raw.communitydragon.org/latest"
METATFT  = "https://cdn.metatft.com/cdn-cgi/image"
_FILE    = "https://cdn.metatft.com/file/metatft"


def _metatft(category: str, name: str, size: int = 64) -> str:
    return f"{METATFT}/width={size},height={size},format=auto/{_FILE}/{category}/{name.lower()}.png"


def tier_icon_url(tier):
    if not tier:
        return None
    # Riot rank crests stay on CDragon (metatft doesn't host these)
    return f"{CDRAGON}/plugins/rcp-fe-lol-shared-components/global/default/images/ranked-mini-crests/{tier.lower()}.png"


def trait_icon_url(trait_id):
    if not trait_id:
        return None
    m = re.match(r"tft\d+_(.*)", trait_id, re.IGNORECASE)
    name = m.group(1) if m else trait_id
    return _metatft("traits", name)


def unit_icon_url(character_id):
    if not character_id:
        return None
    return _metatft("champions", character_id)


def item_icon_url(item_id):
    if not item_id:
        return None
    return _metatft("items", item_id)
