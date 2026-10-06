"""Stockage des préférences dans un fichier JSON."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.domain.settings import Settings
from app.infrastructure.atomic import atomic_write

logger = logging.getLogger(__name__)


class JsonSettingsStore:
    """
    Garde les préférences en mémoire et les écrit à chaque changement.

    Un fichier absent, illisible ou corrompu ne fait jamais planter
    l'application : on repart des valeurs par défaut.
    """

    def __init__(self, path: Path):
        self._path = path
        self._current = self._load()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def current(self) -> Settings:
        return self._current

    def update(self, **changes: Any) -> Settings:
        self._current = self._current.with_changes(**changes)
        self._save()
        return self._current

    def reset(self) -> Settings:
        self._current = Settings()
        self._save()
        return self._current

    # ------------------------------------------------------------ interne
    def _load(self) -> Settings:
        try:
            return Settings.from_mapping(json.loads(self._path.read_text("utf-8")))
        except FileNotFoundError:
            return Settings()
        except (OSError, ValueError):
            logger.warning("Préférences illisibles, valeurs par défaut : %s", self._path)
            return Settings()

    def _save(self) -> None:
        payload = {
            name: getattr(self._current, name)
            for name in Settings.__dataclass_fields__  # type: ignore[attr-defined]
        }
        try:
            with atomic_write(self._path) as temporary:
                temporary.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2), "utf-8"
                )
        except OSError:
            # Préférences non persistées (disque en lecture seule…) :
            # l'application continue avec la valeur en mémoire.
            logger.exception("Impossible d'enregistrer les préférences")
