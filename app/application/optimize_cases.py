"""Cas d'usage d'optimisation : compression, métadonnées, signets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.application.common import ensure_distinct
from app.domain.models import PdfSource
from app.domain.optimization import PdfOptimizer
from app.domain.options import (
    Bookmark,
    CompressionLevel,
    CompressionResult,
    PdfMetadata,
    parse_bookmarks,
)
from app.domain.repositories import PdfRepository


@dataclass(frozen=True, slots=True)
class CompressPdfUseCase:
    optimizer: PdfOptimizer

    def execute(
        self, source_path: str, level: CompressionLevel, destination: str
    ) -> CompressionResult:
        ensure_distinct([source_path], destination)
        return self.optimizer.compress(
            PdfSource(Path(source_path)), CompressionLevel(level), Path(destination)
        )


@dataclass(frozen=True, slots=True)
class ReadMetadataUseCase:
    repository: PdfRepository

    def execute(self, source_path: str) -> PdfMetadata:
        return self.repository.read_metadata(PdfSource(Path(source_path)))


@dataclass(frozen=True, slots=True)
class WriteMetadataUseCase:
    repository: PdfRepository

    def execute(
        self,
        source_path: str,
        metadata: PdfMetadata,
        destination: str,
        clear_all: bool = False,
    ) -> Path:
        ensure_distinct([source_path], destination)
        return self.repository.write_metadata(
            PdfSource(Path(source_path)), metadata, Path(destination), clear_all
        )


@dataclass(frozen=True, slots=True)
class ReadBookmarksUseCase:
    repository: PdfRepository

    def execute(self, source_path: str) -> list[Bookmark]:
        return self.repository.read_bookmarks(PdfSource(Path(source_path)))


@dataclass(frozen=True, slots=True)
class WriteBookmarksUseCase:
    """Remplace les signets par la liste saisie (vide = supprimer tous les signets)."""

    repository: PdfRepository

    def validate(self, source_path: str, text: str) -> list[Bookmark]:
        total = self.repository.count_pages(PdfSource(Path(source_path)))
        return parse_bookmarks(text, total)

    def execute(self, source_path: str, text: str, destination: str) -> Path:
        ensure_distinct([source_path], destination)
        bookmarks = self.validate(source_path, text)
        return self.repository.write_bookmarks(
            PdfSource(Path(source_path)), bookmarks, Path(destination)
        )
