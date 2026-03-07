"""ItemRepository — TFT item reference-data persistence."""

from __future__ import annotations

from sqlalchemy.orm import Session

from models.item import Item
from repositories.base import AbstractRepository


class ItemRepository(AbstractRepository):
    """Handles the :class:`~models.item.Item` look-up table."""

    def __init__(self, session: Session) -> None:
        super().__init__(session)

    # ── Commands ──────────────────────────────────────────────────────────────

    def save(self, item_id: str, icon_url: str) -> None:
        """Upsert an :class:`~models.item.Item` row (INSERT OR IGNORE)."""
        self._upsert(Item, {"item_id": item_id, "icon_url": icon_url})
