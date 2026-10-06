"""
Port (interface abstraite) pour l'accès aux fichiers PDF.

Le domaine et l'application ne connaissent que cette abstraction. La
couche infrastructure fournit une implémentation concrète (aujourd'hui
``PyPdfRepository``, basée sur ``pypdf``). Ce découplage permet de changer
de bibliothèque PDF, ou d'écrire un faux dépôt pour les tests, sans toucher
aux cas d'usage ni à l'interface.

Les numéros de pages échangés avec ce port sont 1-indexés et déjà validés
par la couche application.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Collection, Sequence

from app.domain.models import PdfSource
from app.domain.options import Bookmark, CropMargins, ExportResult, PdfMetadata


class PdfRepository(ABC):
    @abstractmethod
    def count_pages(self, source: PdfSource) -> int:
        """Retourne le nombre de pages du document."""

    @abstractmethod
    def split_to_archive(self, source: PdfSource, destination: Path) -> Path:
        """Crée un PDF par page et les regroupe dans une archive ZIP."""

    @abstractmethod
    def extract_pages(
        self, source: PdfSource, pages: Sequence[int], destination: Path
    ) -> Path:
        """Copie les pages demandées, dans l'ordre fourni, vers un nouveau PDF."""

    @abstractmethod
    def merge(self, sources: Sequence[PdfSource], destination: Path) -> Path:
        """Fusionne plusieurs PDF, dans l'ordre fourni, en un seul fichier."""

    @abstractmethod
    def delete_pages(
        self, source: PdfSource, pages: Collection[int], destination: Path
    ) -> Path:
        """Retourne une copie du document privée des pages indiquées."""

    @abstractmethod
    def rotate_pages(
        self,
        source: PdfSource,
        pages: Collection[int],
        angle: int,
        destination: Path,
    ) -> Path:
        """Fait pivoter les pages indiquées de ``angle`` degrés (sens horaire)."""

    @abstractmethod
    def to_landscape_pairs(self, source: PdfSource, destination: Path) -> Path:
        """Regroupe les pages deux par deux sur des feuilles paysage (A4+A4)."""

    @abstractmethod
    def protect(self, source: PdfSource, password: str, destination: Path) -> Path:
        """Chiffre le document : le mot de passe sera exigé à l'ouverture."""

    @abstractmethod
    def unlock(self, source: PdfSource, password: str, destination: Path) -> Path:
        """Retourne une copie sans protection par mot de passe."""

    # ------------------------------------------------------------ organisation
    @abstractmethod
    def insert_blank_pages(
        self, source: PdfSource, after_page: int, count: int, destination: Path
    ) -> Path:
        """Insère ``count`` pages blanches après ``after_page`` (0 = au début)."""

    @abstractmethod
    def insert_pdf(
        self, source: PdfSource, after_page: int, inserted: PdfSource, destination: Path
    ) -> Path:
        """Insère toutes les pages de ``inserted`` après ``after_page`` (0 = au début)."""

    @abstractmethod
    def interleave(
        self,
        fronts: PdfSource,
        backs: PdfSource,
        backs_reversed: bool,
        destination: Path,
    ) -> Path:
        """
        Alterne les pages de ``fronts`` (rectos) et de ``backs`` (versos).

        Avec ``backs_reversed``, les versos sont dans l'ordre inverse (cas d'un
        scanner qui lit d'abord les rectos, puis la pile retournée).
        """

    @abstractmethod
    def crop(
        self,
        source: PdfSource,
        pages: Collection[int],
        margins: CropMargins,
        destination: Path,
    ) -> Path:
        """Rogne les marges (vues à l'écran) des pages indiquées."""

    # ------------------------------------------------------------ métadonnées / signets
    @abstractmethod
    def read_metadata(self, source: PdfSource) -> PdfMetadata:
        """Lit les métadonnées descriptives du document."""

    @abstractmethod
    def write_metadata(
        self,
        source: PdfSource,
        metadata: PdfMetadata,
        destination: Path,
        clear_all: bool = False,
    ) -> Path:
        """
        Remplace les métadonnées par ``metadata`` (un champ vide est retiré).
        Avec ``clear_all``, toutes les métadonnées (y compris XMP) sont supprimées.
        """

    @abstractmethod
    def read_bookmarks(self, source: PdfSource) -> list[Bookmark]:
        """Signets existants, à plat, avec leur niveau d'imbrication."""

    @abstractmethod
    def write_bookmarks(
        self, source: PdfSource, bookmarks: Sequence[Bookmark], destination: Path
    ) -> Path:
        """Remplace tous les signets par ``bookmarks`` (liste vide = aucun signet)."""

    # ------------------------------------------------------------ extraction
    @abstractmethod
    def extract_images(self, source: PdfSource, destination: Path) -> ExportResult:
        """Écrit les images incorporées dans une archive ZIP."""

    @abstractmethod
    def extract_text(
        self, source: PdfSource, destination: Path, page_markers: bool = True
    ) -> ExportResult:
        """Écrit le texte de la couche texte du PDF dans un fichier ``.txt``."""
