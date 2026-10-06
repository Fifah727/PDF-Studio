"""Cas d'usage de personnalisation : filigrane, signature, numérotation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from app.application.common import ensure_distinct, pages_or_default
from app.domain.models import ImageSource, PdfSource
from app.domain.options import ImageStamp, PageNumbering, StampKind, TextWatermark
from app.domain.repositories import PdfRepository
from app.domain.stamping import PdfStamper


@dataclass(frozen=True, slots=True)
class WatermarkTextUseCase:
    """Filigrane texte ; une sélection vide vise toutes les pages."""

    repository: PdfRepository
    stamper: PdfStamper

    def validate(self, source_path: str, selection: str) -> list[int]:
        pages, _ = pages_or_default(
            self.repository, PdfSource(Path(source_path)), selection, "all"
        )
        return pages

    def execute(
        self,
        source_path: str,
        watermark: TextWatermark,
        selection: str,
        destination: str,
    ) -> Path:
        ensure_distinct([source_path], destination)
        pages = self.validate(source_path, selection)
        return self.stamper.watermark_text(
            PdfSource(Path(source_path)), watermark, pages, Path(destination)
        )


@dataclass(frozen=True, slots=True)
class StampImageUseCase:
    """
    Pose une image sur des pages : filigrane image ou signature.

    ``default_pages`` règle ce que signifie une sélection vide :
    ``"all"`` (filigrane) ou ``"last"`` (signature en fin de document).
    """

    repository: PdfRepository
    stamper: PdfStamper
    default_pages: str = "all"
    kind: StampKind = StampKind.IMAGE

    def validate(self, source_path: str, image_path: str, selection: str) -> list[int]:
        ImageSource(Path(image_path))  # l'image existe et son format est géré
        pages, _ = pages_or_default(
            self.repository, PdfSource(Path(source_path)), selection, self.default_pages
        )
        return pages

    def execute(
        self,
        source_path: str,
        image_path: str,
        stamp: ImageStamp,
        selection: str,
        destination: str,
    ) -> Path:
        ensure_distinct([source_path, image_path], destination)
        pages = self.validate(source_path, image_path, selection)
        return self.stamper.stamp_image(
            PdfSource(Path(source_path)),
            ImageSource(Path(image_path)),
            replace(stamp, kind=self.kind),  # la nature (filigrane / signature) vient du cas d'usage
            pages,
            Path(destination),
        )


@dataclass(frozen=True, slots=True)
class NumberPagesUseCase:
    """Numérote les pages ; la première page visée reçoit le numéro de départ."""

    repository: PdfRepository
    stamper: PdfStamper

    def validate(self, source_path: str, selection: str) -> list[int]:
        pages, _ = pages_or_default(
            self.repository, PdfSource(Path(source_path)), selection, "all"
        )
        return pages

    def execute(
        self,
        source_path: str,
        numbering: PageNumbering,
        selection: str,
        destination: str,
    ) -> Path:
        ensure_distinct([source_path], destination)
        pages = self.validate(source_path, selection)
        return self.stamper.number_pages(
            PdfSource(Path(source_path)), numbering, pages, Path(destination)
        )
