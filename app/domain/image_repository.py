"""Port pour la conversion d'images en PDF."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Sequence

from app.domain.models import ImageSource
from app.domain.options import ScanMode


class ImageToPdfConverter(ABC):
    @abstractmethod
    def convert(
        self,
        sources: Sequence[ImageSource],
        destination: Path,
        fit_a4: bool = True,
        mode: ScanMode = ScanMode.ORIGINAL,
    ) -> Path:
        """
        Assemble les images (une par page, dans l'ordre fourni) en un PDF.

        Avec ``fit_a4``, chaque image est centrée et ajustée sur une page A4
        (portrait ou paysage selon l'image) ; sinon la page épouse l'image.
        ``mode`` applique une amélioration « scan » (voir ``ScanMode``).
        """
