"""Cas d'usage d'organisation : réordonner, insérer, recto-verso, rogner."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.application.common import ensure_distinct, pages_or_default, resolve_pages
from app.domain.exceptions import InvalidOptionError, PageCountMismatchError, PageRangeError
from app.domain.models import PdfSource
from app.domain.options import CropMargins
from app.domain.repositories import PdfRepository

MAX_BLANK_PAGES = 200


@dataclass(frozen=True, slots=True)
class ReorderPagesUseCase:
    """
    Nouvel ordre des pages.

    Les pages saisies viennent en premier, dans l'ordre saisi ; les autres
    suivent dans leur ordre d'origine. ``reverse`` inverse tout le document.
    """

    repository: PdfRepository

    def validate(self, source_path: str, selection: str, reverse: bool = False) -> list[int]:
        source = PdfSource(Path(source_path))
        total = self.repository.count_pages(source)
        if reverse:
            order = list(range(total, 0, -1))
        else:
            listed, _ = resolve_pages(self.repository, source, selection)
            order = listed + [n for n in range(1, total + 1) if n not in set(listed)]
        if order == list(range(1, total + 1)):
            raise InvalidOptionError("Cet ordre est identique à l'ordre actuel.")
        return order

    def execute(
        self, source_path: str, selection: str, destination: str, reverse: bool = False
    ) -> Path:
        ensure_distinct([source_path], destination)
        order = self.validate(source_path, selection, reverse)
        # Écrire les pages dans un autre ordre = extraire toutes les pages dans cet ordre.
        return self.repository.extract_pages(
            PdfSource(Path(source_path)), order, Path(destination)
        )


@dataclass(frozen=True, slots=True)
class InsertPagesUseCase:
    """Insère des pages blanches ou les pages d'un autre PDF après la page N."""

    repository: PdfRepository

    def validate(
        self,
        source_path: str,
        after_page: int,
        insert_path: str | None = None,
        blank_count: int = 0,
    ) -> int:
        source = PdfSource(Path(source_path))
        total = self.repository.count_pages(source)
        if not 0 <= after_page <= total:
            raise PageRangeError(
                f"Position invalide : indiquez un nombre de 0 (au début) à {total}."
            )
        if insert_path:
            PdfSource(Path(insert_path))
        elif not 1 <= blank_count <= MAX_BLANK_PAGES:
            raise InvalidOptionError(
                f"Choisissez un PDF à insérer ou de 1 à {MAX_BLANK_PAGES} pages blanches."
            )
        return total

    def execute(
        self,
        source_path: str,
        after_page: int,
        destination: str,
        insert_path: str | None = None,
        blank_count: int = 0,
    ) -> Path:
        ensure_distinct([source_path, *([insert_path] if insert_path else [])], destination)
        self.validate(source_path, after_page, insert_path, blank_count)
        source = PdfSource(Path(source_path))
        if insert_path:
            return self.repository.insert_pdf(
                source, after_page, PdfSource(Path(insert_path)), Path(destination)
            )
        return self.repository.insert_blank_pages(
            source, after_page, blank_count, Path(destination)
        )


@dataclass(frozen=True, slots=True)
class InterleavePdfsUseCase:
    """Recto-verso : fusionne un scan des rectos et un scan des versos."""

    repository: PdfRepository

    def validate(self, fronts_path: str, backs_path: str) -> tuple[int, int]:
        if Path(fronts_path).resolve() == Path(backs_path).resolve():
            raise InvalidOptionError("Choisissez deux fichiers différents.")
        fronts = self.repository.count_pages(PdfSource(Path(fronts_path)))
        backs = self.repository.count_pages(PdfSource(Path(backs_path)))
        # Il peut manquer le dernier verso (feuille blanche non scannée), pas davantage.
        if fronts - backs not in (0, 1):
            raise PageCountMismatchError(
                f"Les rectos ont {fronts} page(s) et les versos {backs} : il en faut "
                "autant (ou une de plus pour les rectos si le dernier verso est vierge)."
            )
        return fronts, backs

    def execute(
        self,
        fronts_path: str,
        backs_path: str,
        destination: str,
        backs_reversed: bool = True,
    ) -> Path:
        ensure_distinct([fronts_path, backs_path], destination)
        self.validate(fronts_path, backs_path)
        return self.repository.interleave(
            PdfSource(Path(fronts_path)),
            PdfSource(Path(backs_path)),
            backs_reversed,
            Path(destination),
        )


@dataclass(frozen=True, slots=True)
class CropPagesUseCase:
    """Rogne les marges ; une sélection vide vise toutes les pages."""

    repository: PdfRepository

    def validate(self, source_path: str, selection: str, margins: CropMargins) -> list[int]:
        source = PdfSource(Path(source_path))
        pages, _ = pages_or_default(self.repository, source, selection, "all")
        return pages

    def execute(
        self, source_path: str, selection: str, margins: CropMargins, destination: str
    ) -> Path:
        ensure_distinct([source_path], destination)
        pages = self.validate(source_path, selection, margins)
        return self.repository.crop(
            PdfSource(Path(source_path)), pages, margins, Path(destination)
        )
