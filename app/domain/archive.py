"""Port pour regrouper des fichiers dans une archive."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Sequence


class ArchiveWriter(ABC):
    @abstractmethod
    def write(self, entries: Sequence[tuple[str, Path]], destination: Path) -> Path:
        """Crée une archive ZIP : chaque entrée est (nom dans l'archive, fichier source)."""
