"""
Cas d'usage (couche application).

Chaque cas d'usage est une classe avec une méthode ``execute``. Il reçoit
un ``PdfRepository`` par injection de dépendance (voir
``app.presentation.di``) : il ne sait pas s'il parle à ``pypdf``, à une
autre bibliothèque, ou à un faux dépôt de test.

C'est ici, et nulle part ailleurs, que les entrées brutes de l'interface
(chemins ``str``, sélection de pages saisie en texte) deviennent des objets
du domaine validés.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from app.application.common import ensure_distinct, resolve_pages
from app.domain.exceptions import (
    InsufficientFilesError,
    LastPageDeletionError,
    PageRangeError,
)
from app.domain.image_repository import ImageToPdfConverter
from app.domain.models import ImageSource, PdfSource
from app.domain.options import ScanMode
from app.domain.repositories import PdfRepository

MIN_FILES_TO_MERGE = 2
ALLOWED_ROTATIONS = (90, 180, 270)


# Noms historiques conservés pour ce module ; le code vit dans ``common``.
_ensure_distinct = ensure_distinct
_resolve_pages = resolve_pages


@dataclass(frozen=True, slots=True)
class CountPagesUseCase:
    repository: PdfRepository

    def execute(self, source_path: str) -> int:
        return self.repository.count_pages(PdfSource(Path(source_path)))


@dataclass(frozen=True, slots=True)
class SplitPdfUseCase:
    repository: PdfRepository

    def execute(self, source_path: str, destination: str) -> Path:
        _ensure_distinct([source_path], destination)
        source = PdfSource(Path(source_path))
        return self.repository.split_to_archive(source, Path(destination))


@dataclass(frozen=True, slots=True)
class ExtractPagesUseCase:
    repository: PdfRepository

    def validate(self, source_path: str, selection: str) -> list[int]:
        """Vérifie la sélection avant même d'ouvrir la boîte « Enregistrer »."""
        source = PdfSource(Path(source_path))
        pages, _ = _resolve_pages(self.repository, source, selection)
        return pages

    def execute(self, source_path: str, selection: str, destination: str) -> Path:
        _ensure_distinct([source_path], destination)
        source = PdfSource(Path(source_path))
        pages, _ = _resolve_pages(self.repository, source, selection)
        return self.repository.extract_pages(source, pages, Path(destination))


@dataclass(frozen=True, slots=True)
class MergePdfsUseCase:
    repository: PdfRepository

    def execute(self, source_paths: Sequence[str], destination: str) -> Path:
        if len(source_paths) < MIN_FILES_TO_MERGE:
            raise InsufficientFilesError(
                f"Sélectionnez au moins {MIN_FILES_TO_MERGE} fichiers PDF."
            )
        _ensure_distinct(source_paths, destination)
        sources = [PdfSource(Path(path)) for path in source_paths]
        return self.repository.merge(sources, Path(destination))


@dataclass(frozen=True, slots=True)
class DeletePagesUseCase:
    repository: PdfRepository

    def validate(self, source_path: str, selection: str) -> list[int]:
        source = PdfSource(Path(source_path))
        pages, total = _resolve_pages(self.repository, source, selection)
        if len(pages) >= total:
            raise LastPageDeletionError(
                "Impossible de supprimer toutes les pages du PDF."
            )
        return pages

    def execute(self, source_path: str, selection: str, destination: str) -> Path:
        _ensure_distinct([source_path], destination)
        pages = self.validate(source_path, selection)
        source = PdfSource(Path(source_path))
        return self.repository.delete_pages(source, pages, Path(destination))


@dataclass(frozen=True, slots=True)
class RotatePagesUseCase:
    repository: PdfRepository

    def validate(self, source_path: str, selection: str, angle: int) -> list[int]:
        """Une sélection vide signifie « toutes les pages »."""
        if angle not in ALLOWED_ROTATIONS:
            raise PageRangeError("L'angle doit être 90°, 180° ou 270°.")
        source = PdfSource(Path(source_path))
        if not (selection or "").strip():
            return list(range(1, self.repository.count_pages(source) + 1))
        pages, _ = _resolve_pages(self.repository, source, selection)
        return pages

    def execute(
        self, source_path: str, selection: str, angle: int, destination: str
    ) -> Path:
        _ensure_distinct([source_path], destination)
        pages = self.validate(source_path, selection, angle)
        source = PdfSource(Path(source_path))
        return self.repository.rotate_pages(source, pages, angle, Path(destination))


@dataclass(frozen=True, slots=True)
class LandscapePairUseCase:
    repository: PdfRepository

    def execute(self, source_path: str, destination: str) -> Path:
        _ensure_distinct([source_path], destination)
        source = PdfSource(Path(source_path))
        return self.repository.to_landscape_pairs(source, Path(destination))


@dataclass(frozen=True, slots=True)
class ProtectPdfUseCase:
    repository: PdfRepository

    def execute(self, source_path: str, password: str, destination: str) -> Path:
        if not password:
            raise PageRangeError("Saisissez un mot de passe.")
        _ensure_distinct([source_path], destination)
        source = PdfSource(Path(source_path))
        return self.repository.protect(source, password, Path(destination))


@dataclass(frozen=True, slots=True)
class UnlockPdfUseCase:
    repository: PdfRepository

    def execute(self, source_path: str, password: str, destination: str) -> Path:
        _ensure_distinct([source_path], destination)
        source = PdfSource(Path(source_path))
        return self.repository.unlock(source, password, Path(destination))


@dataclass(frozen=True, slots=True)
class ImagesToPdfUseCase:
    converter: ImageToPdfConverter

    def execute(
        self,
        source_paths: Sequence[str],
        destination: str,
        fit_a4: bool = True,
        mode: ScanMode = ScanMode.ORIGINAL,
    ) -> Path:
        _ensure_distinct(source_paths, destination)
        sources = [ImageSource(Path(path)) for path in source_paths]
        return self.converter.convert(
            sources, Path(destination), fit_a4=fit_a4, mode=mode
        )
