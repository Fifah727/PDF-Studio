"""
Pose de texte et d'images sur les pages (``pypdf`` + ``Pillow``).

Principe : pour chaque page on fabrique une petite page « calque » qui
contient seulement le tampon, puis on la fusionne par-dessus la page
d'origine (``merge_page``). Le contenu existant n'est jamais modifié.

Les coordonnées sont exprimées *telles qu'on voit la page* (origine en bas à
gauche de la page affichée). ``_frame`` calcule la matrice qui ramène ces
coordonnées visuelles dans le plan PDF, en tenant compte de la rotation de la
page et de l'origine de sa zone visible : un tampon « en bas à droite » reste
en bas à droite, même sur un scan pivoté.
"""

from __future__ import annotations

import io
import math
import zlib
from pathlib import Path
from typing import Collection

from pypdf import PageObject, PdfReader, PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    NumberObject,
    RectangleObject,
)
from PIL import Image, ImageChops, ImageOps, UnidentifiedImageError

from app.domain.exceptions import InvalidImageError
from app.domain.models import ImageSource, PdfSource
from app.domain.options import ImageStamp, PageNumbering, StampKind, TextWatermark
from app.domain.stamping import PdfStamper
from app.infrastructure.pdf_text import ASCENT, pdf_literal, text_width
from app.infrastructure.pypdf_common import open_reader, write_pdf

_MAX_STAMP_PIXELS = 1000  # largeur max de l'image incorporée (suffit à 300 ppp sur 8 cm)
_WHITE_CUTOFF = 235  # au-dessus, un gris est traité comme du fond
_WHITE_RANGE = 120  # plage de gris sur laquelle l'opacité monte de 0 à 100 %


class PyPdfStamper(PdfStamper):
    # ------------------------------------------------------------ texte
    def watermark_text(
        self,
        source: PdfSource,
        watermark: TextWatermark,
        pages: Collection[int],
        destination: Path,
    ) -> Path:
        writer = PdfWriter(clone_from=open_reader(source))
        targets = set(pages)
        cos, sin = (
            math.cos(math.radians(watermark.angle)),
            math.sin(math.radians(watermark.angle)),
        )
        unit_width = text_width(watermark.text, 1.0) or 1.0
        red, green, blue = watermark.color.rgb

        for index, page in enumerate(writer.pages, start=1):
            if index not in targets:
                continue
            width, height, matrix = _frame(page)
            # Longueur de la droite inclinée qui traverse la page par son centre.
            room = min(
                width / abs(cos) if abs(cos) > 1e-6 else math.inf,
                height / abs(sin) if abs(sin) > 1e-6 else math.inf,
            )
            size = max(6.0, min(400.0, watermark.scale * room / unit_width))
            drawn = text_width(watermark.text, size)
            content = (
                b"q %s cm /GS1 gs %s rg\n"
                b"q 1 0 0 1 %s %s cm %s %s %s %s 0 0 cm\n"
                b"BT /F1 %s Tf %s %s Td %s Tj ET\nQ\nQ\n"
            ) % (
                matrix,
                _nums(red, green, blue),
                _num(width / 2),
                _num(height / 2),
                _num(cos),
                _num(sin),
                _num(-sin),
                _num(cos),
                _num(size),
                _num(-drawn / 2),
                _num(-size * ASCENT / 2),
                pdf_literal(watermark.text),
            )
            content = _tagged(content, StampKind.TEXT)
            _merge(page, _overlay(content, page.mediabox, opacity=watermark.opacity, font=True))
        return write_pdf(writer, destination)

    def number_pages(
        self,
        source: PdfSource,
        numbering: PageNumbering,
        pages: Collection[int],
        destination: Path,
    ) -> Path:
        writer = PdfWriter(clone_from=open_reader(source))
        ordered = sorted(set(pages))
        rank = {page_number: offset for offset, page_number in enumerate(ordered)}
        last = numbering.start + len(ordered) - 1
        red, green, blue = numbering.color.rgb

        for index, page in enumerate(writer.pages, start=1):
            if index not in rank:
                continue
            width, height, matrix = _frame(page)
            label = numbering.render(numbering.start + rank[index], last)
            size = numbering.font_size
            drawn = text_width(label, size)
            x = _anchor(numbering.position.horizontal, width, drawn, numbering.margin)
            y = _anchor_vertical(numbering.position.vertical, height, size, numbering.margin)
            content = b"q %s cm %s rg BT /F1 %s Tf %s %s Td %s Tj ET Q\n" % (
                matrix,
                _nums(red, green, blue),
                _num(size),
                _num(x),
                _num(y),
                pdf_literal(label),
            )
            content = b"/Artifact <</Type /Pagination>> BDC\n" + content + b"EMC\n"
            _merge(page, _overlay(content, page.mediabox, font=True))
        return write_pdf(writer, destination)

    # ------------------------------------------------------------ image
    def stamp_image(
        self,
        source: PdfSource,
        image: ImageSource,
        stamp: ImageStamp,
        pages: Collection[int],
        destination: Path,
    ) -> Path:
        pixels = _load_stamp_image(image, stamp)
        writer = PdfWriter(clone_from=open_reader(source))
        targets = set(pages)
        aspect = pixels.height / pixels.width

        for index, page in enumerate(writer.pages, start=1):
            if index not in targets:
                continue
            width, height, matrix = _frame(page)
            drawn_width = stamp.width_fraction * width
            drawn_height = drawn_width * aspect
            if drawn_height > height:  # image très haute : on la ramène dans la page
                drawn_height = height
                drawn_width = drawn_height / aspect
            x = _anchor(stamp.position.horizontal, width, drawn_width, stamp.margin)
            y = _anchor_box(stamp.position.vertical, height, drawn_height, stamp.margin)
            content = b"q %s cm /GS1 gs %s 0 0 %s %s %s cm /Im1 Do Q\n" % (
                matrix,
                _num(drawn_width),
                _num(drawn_height),
                _num(x),
                _num(y),
            )
            _merge(
                page,
                _overlay(
                    _tagged(content, stamp.kind),
                    page.mediabox,
                    opacity=stamp.opacity,
                    image=pixels,
                ),
            )
        return write_pdf(writer, destination)


# ====================================================================== géométrie
def _frame(page: PageObject) -> tuple[float, float, bytes]:
    """
    (largeur, hauteur, matrice) de la page *telle qu'on la voit*.

    La matrice ``a b c d e f`` transforme les coordonnées visuelles (origine
    en bas à gauche de la page affichée) en coordonnées du plan PDF.
    """
    box = page.cropbox
    x0, y0 = float(box.left), float(box.bottom)
    w, h = float(box.width), float(box.height)
    rotation = (page.rotation or 0) % 360
    if rotation == 90:
        return h, w, _nums(0, 1, -1, 0, x0 + w, y0)
    if rotation == 180:
        return w, h, _nums(-1, 0, 0, -1, x0 + w, y0 + h)
    if rotation == 270:
        return h, w, _nums(0, -1, 1, 0, x0, y0 + h)
    return w, h, _nums(1, 0, 0, 1, x0, y0)


def _anchor(horizontal: str, page: float, drawn: float, margin: float) -> float:
    if horizontal == "left":
        return margin
    if horizontal == "right":
        return max(0.0, page - margin - drawn)
    return max(0.0, (page - drawn) / 2)


def _anchor_box(vertical: str, page: float, drawn: float, margin: float) -> float:
    """Ordonnée du bas d'un cadre de hauteur ``drawn``."""
    if vertical == "bottom":
        return margin
    if vertical == "top":
        return max(0.0, page - margin - drawn)
    return max(0.0, (page - drawn) / 2)


def _anchor_vertical(vertical: str, page: float, size: float, margin: float) -> float:
    """Ordonnée de la ligne de base d'un texte de corps ``size``."""
    if vertical == "bottom":
        return margin
    if vertical == "top":
        return max(0.0, page - margin - size * ASCENT)
    return max(0.0, page / 2 - size * ASCENT / 2)


def _tagged(content: bytes, kind: StampKind) -> bytes:
    """
    Entoure ``content`` d'un bloc de contenu marqué « filigrane ».

    ``/Artifact`` + ``/Subtype /Watermark`` est le balisage standard (ISO 32000) :
    les autres lecteurs et éditeurs reconnaissent ce tampon comme un filigrane
    et ``PyPdfWatermarkRemover`` peut le retrouver. ``/PSKind`` précise s'il
    s'agit d'un texte, d'une image ou d'une signature.
    """
    header = b"/Artifact <</Type /Pagination /Subtype /Watermark /PSKind (%s)>> BDC\n" % kind.value.encode()
    if kind is not StampKind.TEXT:  # image / signature : ce n'est pas de la pagination
        header = b"/Artifact <</Subtype /Watermark /PSKind (%s)>> BDC\n" % kind.value.encode()
    return header + content + b"EMC\n"


def _num(value: float) -> bytes:
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return (text if text not in ("", "-0") else "0").encode("ascii")


def _nums(*values: float) -> bytes:
    return b" ".join(_num(v) for v in values)


# ====================================================================== calques
def _overlay(
    content: bytes,
    area: RectangleObject,
    opacity: float | None = None,
    font: bool = False,
    image: Image.Image | None = None,
) -> PageObject:
    """
    Page « calque » portant ``content`` et les ressources qu'il utilise.

    ``area`` est la zone de la page cible dans le plan PDF. ``merge_page``
    découpe le calque selon son propre cadre : il doit donc recouvrir toute la
    page cible, sinon un tampon sur une page pivotée serait tronqué.
    """
    writer = PdfWriter()
    page = writer.add_blank_page(width=1, height=1)
    page.mediabox = RectangleObject([float(v) for v in area])

    resources = DictionaryObject()
    if opacity is not None:
        alpha = FloatObject(f"{opacity:.3f}")
        state = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/ExtGState"),
                NameObject("/ca"): alpha,  # remplissage (texte, images)
                NameObject("/CA"): alpha,
            }
        )
        resources[NameObject("/ExtGState")] = DictionaryObject({NameObject("/GS1"): state})
    if font:
        helvetica = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
                NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
            }
        )
        resources[NameObject("/Font")] = DictionaryObject({NameObject("/F1"): helvetica})
    if image is not None:
        resources[NameObject("/XObject")] = DictionaryObject(
            {NameObject("/Im1"): _image_xobject(writer, image)}
        )
    page[NameObject("/Resources")] = resources

    stream = DecodedStreamObject()
    stream.set_data(content)
    page.replace_contents(stream)

    buffer = io.BytesIO()
    writer.write(buffer)
    buffer.seek(0)
    return PdfReader(buffer).pages[0]


def _merge(page: PageObject, overlay: PageObject) -> None:
    page.merge_page(overlay, over=True)


def _image_xobject(writer: PdfWriter, image: Image.Image):
    """Image RGBA -> objet image PDF (RVB Flate) + masque doux (canal alpha)."""
    rgba = image.convert("RGBA")

    def stream(data: bytes, colorspace: str, width: int, height: int) -> DecodedStreamObject:
        obj = DecodedStreamObject()
        obj.set_data(zlib.compress(data, 6))
        obj[NameObject("/Type")] = NameObject("/XObject")
        obj[NameObject("/Subtype")] = NameObject("/Image")
        obj[NameObject("/Width")] = NumberObject(width)
        obj[NameObject("/Height")] = NumberObject(height)
        obj[NameObject("/ColorSpace")] = NameObject(colorspace)
        obj[NameObject("/BitsPerComponent")] = NumberObject(8)
        obj[NameObject("/Filter")] = NameObject("/FlateDecode")
        return obj

    mask = stream(rgba.getchannel("A").tobytes(), "/DeviceGray", *rgba.size)
    picture = stream(rgba.convert("RGB").tobytes(), "/DeviceRGB", *rgba.size)
    picture[NameObject("/SMask")] = writer._add_object(mask)  # noqa: SLF001
    return writer._add_object(picture)  # noqa: SLF001


# ====================================================================== image source
def _load_stamp_image(source: ImageSource, stamp: ImageStamp) -> Image.Image:
    try:
        image = Image.open(source.path)
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise InvalidImageError(
            f"Impossible de lire l'image : {source.name} ({exc})"
        ) from exc

    image = ImageOps.exif_transpose(image).convert("RGBA")
    if stamp.remove_white_background:
        image = _white_to_transparent(image)

    # Recadrage serré : la marge demandée est celle du dessin, pas du cadre.
    visible = image.getchannel("A").point(lambda value: 255 if value > 8 else 0)
    box = visible.getbbox()
    if box is None:
        raise InvalidImageError("Cette image est entièrement transparente.")
    image = image.crop(box)

    if image.width > _MAX_STAMP_PIXELS:
        ratio = _MAX_STAMP_PIXELS / image.width
        image = image.resize(
            (_MAX_STAMP_PIXELS, max(1, round(image.height * ratio))), Image.Resampling.LANCZOS
        )
    return image


def _white_to_transparent(image: Image.Image) -> Image.Image:
    """Fond blanc (scan, photo de signature) -> transparent, avec bords adoucis."""
    gray = image.convert("L")
    soft = gray.point(
        lambda v: 0
        if v >= _WHITE_CUTOFF
        else min(255, int((_WHITE_CUTOFF - v) * 255 / _WHITE_RANGE))
    )
    alpha = ImageChops.multiply(image.getchannel("A"), soft)
    result = image.copy()
    result.putalpha(alpha)
    return result
