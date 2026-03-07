"""TraitRepository — TFT trait reference-data persistence."""

from __future__ import annotations

from sqlalchemy.orm import Session

from models.trait import Trait
from repositories.base import AbstractRepository


class TraitRepository(AbstractRepository):
    """Handles the :class:`~models.trait.Trait` look-up table."""

    def __init__(self, session: Session) -> None:
        super().__init__(session)

    # ── Commands ──────────────────────────────────────────────────────────────

    def save(self, trait_id: str, icon_url: str) -> None:
        """Upsert a :class:`~models.trait.Trait` row (INSERT OR IGNORE)."""
        self._upsert(Trait, {"trait_id": trait_id, "icon_url": icon_url})
