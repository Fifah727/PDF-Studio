"""
Implémentation concrète du dépôt PDF, basée sur ``pypdf``.

C'est la seule couche du projet qui importe ``pypdf``. Si cette
bibliothèque devait être remplacée un jour (par ``pikepdf`` par exemple),
seul ce fichier serait à réécrire : le domaine, les cas d'usage et
l'interface graphique n'en dépendent pas.
"""

from __future__ import annotations

import io
import logging
import zipfile
from pathlib import Path
from typing import Collection, Sequence

from pypdf import PageObject, PdfReader, PdfWriter, Transformation
from pypdf.errors import DependencyError
from pypdf.generic import RectangleObject

from app.domain.exceptions import (
    EncryptionUnavailableError,
    InvalidCropError,
    NoContentError,
    PdfError,
)
from app.domain.models import PdfSource
from app.domain.options import Bookmark, CropMargins, ExportResult, PdfMetadata
from app.domain.repositories import PdfRepository
from app.infrastructure.atomic import atomic_write
from app.infrastructure.pypdf_common import open_reader, write_pdf

logger = logging.getLogger(__name__)

# Dimensions A4 en points (1/72 pouce), utilisées comme taille de cellule
# cible : chaque page source est mise à l'échelle pour tenir dans une
# cellule A4, quelle que soit sa taille d'origine, puis deux cellules sont
# posées côte à côte sur une feuille paysage deux fois plus large.
A4_WIDTH_PT = 595.28
A4_HEIGHT_PT = 841.89


class PyPdfRepository(PdfRepository):
    # ------------------------------------------------------------ lecture / écriture
    def _reader(self, source: PdfSource, password: str | None = None) -> PdfReader:
        return open_reader(source, password)

    def _write(self, writer: PdfWriter, destination: Path) -> Path:
        return write_pdf(writer, destination)

    # ------------------------------------------------------------ opérations
    def count_pages(self, source: PdfSource) -> int:
        return len(self._reader(source).pages)

    def split_to_archive(self, source: PdfSource, destination: Path) -> Path:
        reader = self._reader(source)
        total = len(reader.pages)
        width = len(str(total))  # page_01 … page_12 : tri naturel dans l'archive

        with atomic_write(destination) as temporary:
            with zipfile.ZipFile(
                temporary, "w", compression=zipfile.ZIP_DEFLATED
            ) as archive:
                for index, page in enumerate(reader.pages, start=1):
                    writer = PdfWriter()
                    writer.add_page(page)
                    buffer = io.BytesIO()
                    writer.write(buffer)
                    archive.writestr(
                        f"{source.stem}_page_{index:0{width}d}.pdf", buffer.getvalue()
                    )
        return destination

    def extract_pages(
        self, source: PdfSource, pages: Sequence[int], destination: Path
    ) -> Path:
        reader = self._reader(source)
        writer = PdfWriter()
        for number in pages:
            writer.add_page(reader.pages[number - 1])
        return self._write(writer, destination)

    def merge(self, sources: Sequence[PdfSource], destination: Path) -> Path:
        writer = PdfWriter()
        for source in sources:
            reader = self._reader(source)
            for page in reader.pages:
                writer.add_page(page)
        return self._write(writer, destination)

    def delete_pages(
        self, source: PdfSource, pages: Collection[int], destination: Path
    ) -> Path:
        reader = self._reader(source)
        removed = set(pages)
        writer = PdfWriter()
        for index, page in enumerate(reader.pages, start=1):
            if index not in removed:
                writer.add_page(page)
        return self._write(writer, destination)

    def rotate_pages(
        self,
        source: PdfSource,
        pages: Collection[int],
        angle: int,
        destination: Path,
    ) -> Path:
        reader = self._reader(source)
        targets = set(pages)
        writer = PdfWriter()
        for index, page in enumerate(reader.pages, start=1):
            added = writer.add_page(page)
            if index in targets:
                added.rotate(angle)
        return self._write(writer, destination)

    def to_landscape_pairs(self, source: PdfSource, destination: Path) -> Path:
        reader = self._reader(source)
        pages = list(reader.pages)

        sheet_width = 2 * A4_WIDTH_PT
        writer = PdfWriter()

        def place(sheet: PageObject, page: PageObject, cell_x: float) -> None:
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)
            scale = min(A4_WIDTH_PT / page_width, A4_HEIGHT_PT / page_height)
            offset_x = cell_x + (A4_WIDTH_PT - page_width * scale) / 2
            offset_y = (A4_HEIGHT_PT - page_height * scale) / 2
            transformation = Transformation().scale(scale).translate(offset_x, offset_y)
            sheet.merge_transformed_page(page, transformation)

        index = 0
        while index < len(pages):
            sheet = writer.add_blank_page(width=sheet_width, height=A4_HEIGHT_PT)
            place(sheet, pages[index], 0)
            if index + 1 < len(pages):
                place(sheet, pages[index + 1], A4_WIDTH_PT)
            index += 2

        return self._write(writer, destination)

    def protect(self, source: PdfSource, password: str, destination: Path) -> Path:
        reader = self._reader(source)
        writer = PdfWriter(clone_from=reader)
        try:
            writer.encrypt(user_password=password, algorithm="AES-256")
        except DependencyError as exc:
            raise EncryptionUnavailableError(
                "Le chiffrement n'est pas disponible sur cette plateforme."
            ) from exc
        return self._write(writer, destination)

    def unlock(self, source: PdfSource, password: str, destination: Path) -> Path:
        reader = self._reader(source, password)
        if not reader.is_encrypted:
            raise PdfError("Ce PDF n'est pas protégé par un mot de passe.")
        writer = PdfWriter(clone_from=reader)
        return self._write(writer, destination)

    # ------------------------------------------------------------ organisation
    def insert_blank_pages(
        self, source: PdfSource, after_page: int, count: int, destination: Path
    ) -> Path:
        reader = self._reader(source)
        pages = list(reader.pages)
        reference = pages[max(after_page, 1) - 1]
        width, height = _visual_size(reference)

        writer = PdfWriter()

        def add_blanks() -> None:
            for _ in range(count):
                writer.add_blank_page(width=width, height=height)

        if after_page == 0:
            add_blanks()
        for index, page in enumerate(pages, start=1):
            writer.add_page(page)
            if index == after_page:
                add_blanks()
        return self._write(writer, destination)

    def insert_pdf(
        self, source: PdfSource, after_page: int, inserted: PdfSource, destination: Path
    ) -> Path:
        reader = self._reader(source)
        extra = list(self._reader(inserted).pages)

        writer = PdfWriter()
        if after_page == 0:
            for page in extra:
                writer.add_page(page)
        for index, page in enumerate(reader.pages, start=1):
            writer.add_page(page)
            if index == after_page:
                for added in extra:
                    writer.add_page(added)
        return self._write(writer, destination)

    def interleave(
        self,
        fronts: PdfSource,
        backs: PdfSource,
        backs_reversed: bool,
        destination: Path,
    ) -> Path:
        front_pages = list(self._reader(fronts).pages)
        back_pages = list(self._reader(backs).pages)
        if backs_reversed:
            back_pages.reverse()

        writer = PdfWriter()
        for index, front in enumerate(front_pages):
            writer.add_page(front)
            if index < len(back_pages):
                writer.add_page(back_pages[index])
        return self._write(writer, destination)

    def crop(
        self,
        source: PdfSource,
        pages: Collection[int],
        margins: CropMargins,
        destination: Path,
    ) -> Path:
        reader = self._reader(source)
        targets = set(pages)
        top, bottom, left, right = margins.in_points()

        writer = PdfWriter()
        for index, page in enumerate(reader.pages, start=1):
            added = writer.add_page(page)
            if index in targets:
                box = _cropped_box(added, top, bottom, left, right)
                if box is None:
                    raise InvalidCropError(
                        f"Ces marges ne laissent presque rien de la page {index}."
                    )
                added.cropbox = box
        return self._write(writer, destination)

    # ------------------------------------------------------------ métadonnées
    def read_metadata(self, source: PdfSource) -> PdfMetadata:
        info = self._reader(source).metadata
        if info is None:
            return PdfMetadata()

        def text(key: str) -> str:
            value = info.get(key)
            return str(value).strip() if value is not None else ""

        return PdfMetadata(
            title=text("/Title"),
            author=text("/Author"),
            subject=text("/Subject"),
            keywords=text("/Keywords"),
            creator=text("/Creator"),
            producer=text("/Producer"),
        )

    def write_metadata(
        self,
        source: PdfSource,
        metadata: PdfMetadata,
        destination: Path,
        clear_all: bool = False,
    ) -> Path:
        reader = self._reader(source)
        writer = PdfWriter(clone_from=reader)

        if clear_all:
            writer.metadata = None
            writer.xmp_metadata = None  # copie XMP : porte les mêmes informations
            return self._write(writer, destination)

        merged = {key: value for key, value in dict(writer.metadata or {}).items()}
        wanted = metadata.cleaned()
        for key, value in (
            ("/Title", wanted.title),
            ("/Author", wanted.author),
            ("/Subject", wanted.subject),
            ("/Keywords", wanted.keywords),
            ("/Creator", wanted.creator),
            ("/Producer", wanted.producer),
        ):
            if value:
                merged[key] = value
            else:
                merged.pop(key, None)
        writer.metadata = merged
        return self._write(writer, destination)

    # ------------------------------------------------------------ signets
    def read_bookmarks(self, source: PdfSource) -> list[Bookmark]:
        reader = self._reader(source)
        found: list[Bookmark] = []

        def walk(nodes, level: int) -> None:
            for node in nodes:
                if isinstance(node, list):
                    walk(node, level + 1)
                    continue
                try:
                    page = reader.get_destination_page_number(node)
                    title = str(node.title).strip()
                except Exception:  # signet cassé ou cible introuvable : on l'ignore
                    logger.debug("Signet ignoré", exc_info=True)
                    continue
                if page is None or page < 0 or not title:
                    continue
                # Niveau toujours cohérent : jamais plus d'un cran sous le précédent.
                allowed = found[-1].level + 1 if found else 0
                found.append(Bookmark(title, page + 1, min(level, allowed)))

        try:
            walk(reader.outline, 0)
        except Exception:
            logger.warning("Lecture des signets interrompue", exc_info=True)
        return found

    def write_bookmarks(
        self, source: PdfSource, bookmarks: Sequence[Bookmark], destination: Path
    ) -> Path:
        reader = self._reader(source)
        writer = PdfWriter(clone_from=reader)
        root = writer.root_object
        if "/Outlines" in root:
            del root["/Outlines"]

        parents: list = []  # parents[n] = dernier signet rencontré au niveau n
        for bookmark in bookmarks:
            parent = parents[bookmark.level - 1] if bookmark.level else None
            reference = writer.add_outline_item(
                bookmark.title, bookmark.page - 1, parent=parent
            )
            del parents[bookmark.level :]
            parents.append(reference)
        writer.compress_identical_objects(remove_identicals=False, remove_orphans=True)
        return self._write(writer, destination)

    # ------------------------------------------------------------ extraction
    def extract_images(self, source: PdfSource, destination: Path) -> ExportResult:
        reader = self._reader(source)
        digits = len(str(len(reader.pages)))
        seen: set[int] = set()
        count = 0

        with atomic_write(destination) as temporary:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
                for number, page in enumerate(reader.pages, start=1):
                    try:
                        images = page.images
                        total = len(images)
                    except Exception:
                        logger.debug("Images illisibles, page %s", number, exc_info=True)
                        continue
                    kept_on_page = 0
                    for position in range(total):
                        try:
                            image = images[position]
                        except Exception:  # filtre non pris en charge (JBIG2…)
                            logger.debug("Image ignorée, page %s", number, exc_info=True)
                            continue
                        reference = image.indirect_reference
                        if reference is not None:
                            if reference.idnum in seen:  # logo répété sur chaque page
                                continue
                            seen.add(reference.idnum)
                        decoded = image.image
                        if decoded is not None and min(decoded.size) < _MIN_IMAGE_SIDE:
                            continue  # filets, puces : pas de vraies images
                        kept_on_page += 1
                        count += 1
                        extension = Path(image.name).suffix or ".png"
                        archive.writestr(
                            f"page_{number:0{digits}d}_image_{kept_on_page:02d}{extension}",
                            image.data,
                        )
            if count == 0:
                raise NoContentError("Aucune image trouvée dans ce PDF.")
        return ExportResult(destination, count)

    def extract_text(
        self, source: PdfSource, destination: Path, page_markers: bool = True
    ) -> ExportResult:
        reader = self._reader(source)
        blocks: list[str] = []
        pages_with_text = 0
        for number, page in enumerate(reader.pages, start=1):
            try:
                text = (page.extract_text() or "").strip()
            except Exception:  # police ou flux non lisible : page laissée vide
                logger.debug("Texte illisible, page %s", number, exc_info=True)
                text = ""
            pages_with_text += bool(text)
            blocks.append(f"--- Page {number} ---\n{text}" if page_markers else text)

        if pages_with_text == 0:
            raise NoContentError(
                "Aucun texte trouvé : ce PDF est probablement un scan (une image), "
                "sans texte sélectionnable."
            )
        with atomic_write(destination) as temporary:
            temporary.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
        return ExportResult(destination, pages_with_text)


# Images plus petites que cela (en pixels, côté le plus court) : décorations.
_MIN_IMAGE_SIDE = 24
# Une page rognée doit garder au moins 10 points de côté.
_MIN_CROPPED_SIDE = 10.0


def _visual_size(page: PageObject) -> tuple[float, float]:
    """Largeur et hauteur de la page telle qu'on la voit (rotation comprise)."""
    box = page.cropbox
    width, height = float(box.width), float(box.height)
    return (height, width) if (page.rotation or 0) % 180 else (width, height)


def _cropped_box(
    page: PageObject, top: float, bottom: float, left: float, right: float
) -> RectangleObject | None:
    """
    Nouvelle zone visible, ou ``None`` si elle serait (presque) vide.

    Les marges sont exprimées comme à l'écran ; sur une page pivotée, le
    « haut » visuel n'est pas le haut du plan PDF, d'où la permutation.
    """
    rotation = (page.rotation or 0) % 360
    if rotation == 90:
        left, top, right, bottom = top, right, bottom, left
    elif rotation == 180:
        left, top, right, bottom = right, bottom, left, top
    elif rotation == 270:
        left, top, right, bottom = bottom, left, top, right

    box = page.cropbox
    x0, y0 = float(box.left) + left, float(box.bottom) + bottom
    x1, y1 = float(box.right) - right, float(box.top) - top
    if x1 - x0 < _MIN_CROPPED_SIDE or y1 - y0 < _MIN_CROPPED_SIDE:
        return None
    return RectangleObject((x0, y0, x1, y1))
