"""Port pour la réduction de taille d'un PDF."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.domain.models import PdfSource
from app.domain.options import CompressionLevel, CompressionResult


class PdfOptimizer(ABC):
    @abstractmethod
    def compress(
        self, source: PdfSource, level: CompressionLevel, destination: Path
    ) -> CompressionResult:
        """
        Réduit la taille du PDF. Si le résultat n'est pas plus petit que
        l'original, une copie fidèle de l'original est écrite à la place
        (``CompressionResult.improved`` vaut alors ``False``).
        """
