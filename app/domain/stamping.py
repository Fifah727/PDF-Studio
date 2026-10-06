"""Port pour poser du texte ou des images sur les pages d'un PDF."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Collection

from app.domain.models import ImageSource, PdfSource
from app.domain.options import ImageStamp, PageNumbering, TextWatermark


class PdfStamper(ABC):
    """Les numéros de pages (1-indexés) sont déjà validés par la couche application."""

    @abstractmethod
    def watermark_text(
        self,
        source: PdfSource,
        watermark: TextWatermark,
        pages: Collection[int],
        destination: Path,
    ) -> Path:
        """Écrit un texte semi-transparent, centré et incliné, sur les pages."""

    @abstractmethod
    def stamp_image(
        self,
        source: PdfSource,
        image: ImageSource,
        stamp: ImageStamp,
        pages: Collection[int],
        destination: Path,
    ) -> Path:
        """Pose une image (transparence PNG conservée) sur les pages."""

    @abstractmethod
    def number_pages(
        self,
        source: PdfSource,
        numbering: PageNumbering,
        pages: Collection[int],
        destination: Path,
    ) -> Path:
        """
        Numérote les pages indiquées ; la première page de ``pages`` reçoit
        ``numbering.start``.
        """
