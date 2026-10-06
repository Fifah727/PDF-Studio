"""Cas d'usage : repérer et retirer des filigranes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Collection

from app.application.common import ensure_distinct
from app.domain.exceptions import InvalidOptionError
from app.domain.models import PdfSource
from app.domain.options import RemovalResult, StampKind, WatermarkReport
from app.domain.unmarking import WatermarkRemover


@dataclass(frozen=True, slots=True)
class ScanWatermarksUseCase:
    remover: WatermarkRemover

    def execute(self, source_path: str) -> WatermarkReport:
        return self.remover.scan(PdfSource(Path(source_path)))


@dataclass(frozen=True, slots=True)
class RemoveWatermarksUseCase:
    remover: WatermarkRemover

    def execute(
        self, source_path: str, kinds: Collection[StampKind], destination: str
    ) -> RemovalResult:
        ensure_distinct([source_path], destination)
        wanted = {StampKind(kind) for kind in kinds}
        if not wanted:
            raise InvalidOptionError("Choisissez au moins un type de filigrane à retirer.")
        return self.remover.remove(PdfSource(Path(source_path)), wanted, Path(destination))
