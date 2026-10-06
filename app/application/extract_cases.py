"""Cas d'usage d'extraction : images et texte d'un PDF."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.application.common import ensure_distinct
from app.domain.models import PdfSource
from app.domain.options import ExportResult
from app.domain.repositories import PdfRepository


@dataclass(frozen=True, slots=True)
class ExtractImagesUseCase:
    repository: PdfRepository

    def execute(self, source_path: str, destination: str) -> ExportResult:
        ensure_distinct([source_path], destination)
        return self.repository.extract_images(PdfSource(Path(source_path)), Path(destination))


@dataclass(frozen=True, slots=True)
class ExtractTextUseCase:
    repository: PdfRepository

    def execute(
        self, source_path: str, destination: str, page_markers: bool = True
    ) -> ExportResult:
        ensure_distinct([source_path], destination)
        return self.repository.extract_text(
            PdfSource(Path(source_path)), Path(destination), page_markers
        )
