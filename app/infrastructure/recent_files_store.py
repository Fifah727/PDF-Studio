"""Historique des derniers fichiers créés, dans un fichier JSON."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.domain.recents import RecentFile
from app.infrastructure.atomic import atomic_write

logger = logging.getLogger(__name__)

MAX_RECENT_FILES = 8


class JsonRecentFilesStore:
    """
    Garde les ``MAX_RECENT_FILES`` derniers fichiers, le plus récent d'abord.

    Un fichier absent, illisible ou aux entrées invalides donne simplement un
    historique vide ou partiel : cette fonction ne doit jamais gêner l'usage.
    """

    def __init__(self, path: Path, limit: int = MAX_RECENT_FILES):
        self._path = path
        self._limit = limit
        self._items = self._load()

    @property
    def items(self) -> list[RecentFile]:
        return list(self._items)

    def add(self, path: str | Path, label: str, when: datetime | None = None) -> None:
        resolved = str(path)
        when = when or datetime.now(timezone.utc)
        self._items = [item for item in self._items if item.path != resolved]
        self._items.insert(0, RecentFile(resolved, label, when))
        del self._items[self._limit :]
        self._save()

    def remove(self, path: str | Path) -> bool:
        """Retire un fichier de l'historique ; ``False`` s'il n'y figurait pas."""
        before = len(self._items)
        self._items = [item for item in self._items if item.path != str(path)]
        changed = len(self._items) != before
        if changed:
            self._save()
        return changed

    def clear(self) -> None:
        self._items = []
        self._save()

    # ------------------------------------------------------------ interne
    def _load(self) -> list[RecentFile]:
        try:
            raw = json.loads(self._path.read_text("utf-8"))
        except FileNotFoundError:
            return []
        except (OSError, ValueError):
            logger.warning("Historique illisible, ignoré : %s", self._path)
            return []
        items: list[RecentFile] = []
        for entry in raw if isinstance(raw, list) else []:
            try:
                when = datetime.fromisoformat(entry["created_at"])
                if when.tzinfo is None:
                    when = when.replace(tzinfo=timezone.utc)
                items.append(RecentFile(str(entry["path"]), str(entry["label"]), when))
            except (KeyError, TypeError, ValueError):
                continue
        return items[: self._limit]

    def _save(self) -> None:
        payload = [
            {"path": i.path, "label": i.label, "created_at": i.created_at.isoformat()}
            for i in self._items
        ]
        try:
            with atomic_write(self._path) as temporary:
                temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")
        except OSError:
            logger.exception("Impossible d'enregistrer l'historique")
