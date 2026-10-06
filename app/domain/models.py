"""
Objets-valeur du domaine.

Les objets se valident eux-mêmes à la construction : impossible d'obtenir
une ``PageRange`` ou une ``PageSelection`` incohérente une fois l'objet
créé. Cela évite de dupliquer les mêmes contrôles dans chaque cas d'usage.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.domain.exceptions import InvalidImageError, InvalidPdfFileError, PageRangeError

SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".tif", ".webp"}

_SELECTION_PART = re.compile(r"(\d+)(?:-(\d+))?")


@dataclass(frozen=True, slots=True)
class PdfSource:
    """Un fichier PDF source, déjà vérifié comme existant."""

    path: Path

    def __post_init__(self) -> None:
        if not self.path.is_file():
            raise InvalidPdfFileError(f"Fichier introuvable : {self.path.name}")
        if self.path.suffix.lower() != ".pdf":
            raise InvalidPdfFileError("Le fichier sélectionné n'est pas un PDF.")

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def stem(self) -> str:
        return self.path.stem


@dataclass(frozen=True, slots=True)
class ImageSource:
    """Un fichier image source, déjà vérifié comme existant et supporté."""

    path: Path

    def __post_init__(self) -> None:
        if not self.path.is_file():
            raise InvalidImageError(f"Fichier introuvable : {self.path.name}")
        if self.path.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
            raise InvalidImageError(
                f"Format non pris en charge : {self.path.name}"
            )

    @property
    def name(self) -> str:
        return self.path.name


@dataclass(frozen=True, slots=True)
class PageRange:
    """Plage de pages 1-indexée, inclusive aux deux bornes."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 1 or self.end < self.start:
            raise PageRangeError(
                f"La plage {self.start}-{self.end} est invalide."
            )

    def validate_against(self, total_pages: int) -> None:
        if self.end > total_pages:
            raise PageRangeError(
                f"La page {self.end} n'existe pas : ce PDF contient "
                f"{total_pages} page(s)."
            )

    def numbers(self) -> range:
        return range(self.start, self.end + 1)


@dataclass(frozen=True, slots=True)
class PageSelection:
    """
    Sélection de pages saisie par l'utilisateur, ex. ``"1-3, 5, 8-10"``.

    L'ordre saisi est conservé (utile pour l'extraction) et les doublons
    sont ignorés.
    """

    ranges: tuple[PageRange, ...]

    @classmethod
    def parse(cls, text: str | None) -> "PageSelection":
        cleaned = (text or "").replace(" ", "").replace(";", ",")
        parts = [part for part in cleaned.split(",") if part]
        if not parts:
            raise PageRangeError("Indiquez au moins une page (ex. 1-3, 5, 8-10).")

        ranges: list[PageRange] = []
        for part in parts:
            match = _SELECTION_PART.fullmatch(part)
            if not match:
                raise PageRangeError(
                    f"Sélection invalide : « {part} ». Exemple : 1-3, 5, 8-10."
                )
            start = int(match.group(1))
            end = int(match.group(2) or start)
            ranges.append(PageRange(start, end))
        return cls(tuple(ranges))

    def pages(self, total_pages: int) -> list[int]:
        """Numéros de pages (1-indexés), validés contre le document."""
        seen: set[int] = set()
        ordered: list[int] = []
        for page_range in self.ranges:
            page_range.validate_against(total_pages)
            for number in page_range.numbers():
                if number not in seen:
                    seen.add(number)
                    ordered.append(number)
        return ordered
