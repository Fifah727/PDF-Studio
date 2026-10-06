"""Port pour repérer et retirer des filigranes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Collection

from app.domain.models import PdfSource
from app.domain.options import RemovalResult, StampKind, WatermarkReport


class WatermarkRemover(ABC):
    @abstractmethod
    def scan(self, source: PdfSource) -> WatermarkReport:
        """Liste les filigranes identifiables, sans rien modifier."""

    @abstractmethod
    def remove(
        self, source: PdfSource, kinds: Collection[StampKind], destination: Path
    ) -> RemovalResult:
        """
        Retire les filigranes des natures demandées et écrit le résultat.
        Lève ``NoWatermarkError`` s'il n'y en a aucun (rien n'est écrit).
        """
