"""Validations partagées par tous les cas d'usage."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from app.domain.exceptions import OutputOverwritesSourceError
from app.domain.models import PageSelection, PdfSource
from app.domain.repositories import PdfRepository


def ensure_distinct(sources: Sequence[str], destination: str) -> None:
    """
    Refuse d'écrire par-dessus un fichier source.

    Écrire dans le fichier que l'on est en train de lire produirait un
    résultat corrompu (typiquement quand on renomme la sortie comme
    l'entrée).
    """
    target = Path(destination).resolve()
    for source in sources:
        if Path(source).resolve() == target:
            raise OutputOverwritesSourceError(
                "Le fichier de sortie ne peut pas écraser le fichier source. "
                "Choisissez un autre nom."
            )


def resolve_pages(
    repository: PdfRepository, source: PdfSource, selection: str
) -> tuple[list[int], int]:
    total = repository.count_pages(source)
    return PageSelection.parse(selection).pages(total), total


def pages_or_default(
    repository: PdfRepository, source: PdfSource, selection: str | None, default: str
) -> tuple[list[int], int]:
    """
    Pages visées par un outil à sélection facultative.

    Sélection vide : ``default`` = ``"all"`` (toutes les pages) ou ``"last"``
    (dernière page seulement).
    """
    total = repository.count_pages(source)
    if (selection or "").strip():
        return PageSelection.parse(selection).pages(total), total
    return ([total] if default == "last" else list(range(1, total + 1))), total
