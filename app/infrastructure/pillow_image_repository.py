"""
Implémentation concrète de la conversion image → PDF, basée sur Pillow.

C'est la seule couche du projet qui importe ``PIL``. Comme pour
``PyPdfRepository`` avec pypdf, cet isolement permet de changer de
bibliothèque de traitement d'image sans toucher aux cas d'usage ni à
l'interface graphique.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from PIL import Image, ImageChops, ImageFilter, ImageOps, UnidentifiedImageError

from app.domain.exceptions import EmptyImageSelectionError, InvalidImageError
from app.domain.image_repository import ImageToPdfConverter
from app.domain.models import ImageSource
from app.domain.options import ScanMode
from app.infrastructure.atomic import atomic_write

# A4 à 150 ppp : 1240 x 1754 pixels. Même résolution pour le mode « taille
# d'origine », afin qu'une photo de 12 Mpx ne donne pas une page géante.
RESOLUTION_DPI = 150.0
A4_PORTRAIT_PX = (1240, 1754)
A4_LANDSCAPE_PX = (1754, 1240)

# Amélioration « scan » : on travaille sur une image au plus de cette taille
# (A4 à 300 ppp) pour rester rapide sur un téléphone.
SCAN_MAX_SIDE_PX = 2480
SCAN_JPEG_QUALITY = 85
_BACKGROUND_DOWNSCALE = 8  # le fond de la page est estimé sur une image 8 fois plus petite
_MIN_PAPER = 150  # luminosité minimale supposée du papier (0-255)


class PillowImageRepository(ImageToPdfConverter):
    def _open(self, source: ImageSource, fit_a4: bool, mode: ScanMode) -> Image.Image:
        try:
            image = Image.open(source.path)
            image.load()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise InvalidImageError(
                f"Impossible de lire l'image : {source.name} ({exc})"
            ) from exc

        # Les photos de téléphone portent leur orientation dans les métadonnées
        # EXIF : sans cette correction, elles sortent couchées dans le PDF.
        image = ImageOps.exif_transpose(image)
        image = self._flatten(image)
        if mode is not ScanMode.ORIGINAL:
            image = self._enhance(image, mode)
        if fit_a4:
            image = self._fit_on_a4(image)
        if mode is ScanMode.BLACK_WHITE:
            image = image.convert("1", dither=Image.Dither.NONE)
        return image

    @staticmethod
    def _flatten(image: Image.Image) -> Image.Image:
        """RGB sur fond blanc (une simple conversion rendrait la transparence noire)."""
        has_alpha = image.mode in ("RGBA", "LA", "PA") or (
            image.mode == "P" and "transparency" in image.info
        )
        if has_alpha:
            rgba = image.convert("RGBA")
            background = Image.new("RGB", rgba.size, "white")
            background.paste(rgba, mask=rgba.getchannel("A"))
            return background
        return image.convert("RGB")

    @staticmethod
    def _fit_on_a4(image: Image.Image) -> Image.Image:
        size = A4_LANDSCAPE_PX if image.width > image.height else A4_PORTRAIT_PX
        scaled = ImageOps.contain(image, size, method=Image.Resampling.LANCZOS)
        canvas = Image.new(scaled.mode, size, "white")  # RGB ou L : le fond reste blanc
        canvas.paste(
            scaled, ((size[0] - scaled.width) // 2, (size[1] - scaled.height) // 2)
        )
        return canvas

    # ------------------------------------------------------------ amélioration
    @staticmethod
    def _page_background(channel: Image.Image) -> Image.Image:
        """
        Luminosité du papier en chaque point (ombres, éclairage inégal).

        Le texte est plus sombre que le papier : un filtre « maximum » sur une
        version réduite efface l'écriture et ne garde que le fond, ensuite
        lissé puis ramené à la taille d'origine. Le fond n'est jamais estimé
        plus sombre que ``_MIN_PAPER`` : une grande zone noire (photo, bandeau)
        n'est ainsi pas « éclaircie » comme si c'était du papier ombré.
        """
        width, height = channel.size
        small = channel.resize(
            (max(1, width // _BACKGROUND_DOWNSCALE), max(1, height // _BACKGROUND_DOWNSCALE)),
            Image.Resampling.BOX,
        )
        small = small.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(4))
        paper = small.resize((width, height), Image.Resampling.BILINEAR)
        return paper.point(lambda value: max(value, _MIN_PAPER))

    @classmethod
    def _flatten_light(cls, channel: Image.Image) -> Image.Image:
        """image - fond + 255 : le papier devient blanc, l'encre garde son écart."""
        return ImageChops.add(channel, ImageChops.invert(cls._page_background(channel)))

    @classmethod
    def _enhance(cls, image: Image.Image, mode: ScanMode) -> Image.Image:
        """Éclairage uniformisé, papier blanc, texte contrasté. Rend RGB ou L."""
        if max(image.size) > SCAN_MAX_SIDE_PX:
            image = ImageOps.contain(
                image, (SCAN_MAX_SIDE_PX, SCAN_MAX_SIDE_PX), method=Image.Resampling.LANCZOS
            )
        if mode is ScanMode.DOCUMENT:
            # Canal par canal : un papier crème ou bleuté devient vraiment blanc.
            flat = Image.merge("RGB", [cls._flatten_light(c) for c in image.split()])
            flat = ImageOps.autocontrast(flat, cutoff=1)
            return flat.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=3))

        gray = ImageOps.autocontrast(cls._flatten_light(image.convert("L")), cutoff=1)
        if mode is ScanMode.GRAYSCALE:
            return gray
        threshold = cls._otsu_threshold(gray)
        return gray.point(lambda value: 255 if value > threshold else 0)

    @staticmethod
    def _otsu_threshold(gray: Image.Image) -> int:
        """Seuil noir/blanc qui sépare au mieux l'encre du papier (méthode d'Otsu)."""
        histogram = gray.histogram()
        total = sum(histogram)
        sum_all = sum(level * count for level, count in enumerate(histogram))
        weight_back = sum_back = 0
        best, threshold = -1.0, 128
        for level in range(256):
            weight_back += histogram[level]
            if weight_back == 0:
                continue
            weight_front = total - weight_back
            if weight_front == 0:
                break
            sum_back += level * histogram[level]
            mean_back = sum_back / weight_back
            mean_front = (sum_all - sum_back) / weight_front
            between = weight_back * weight_front * (mean_back - mean_front) ** 2
            if between > best:
                best, threshold = between, level
        # Après uniformisation le papier est vers 255 : on borne le seuil pour
        # ne pas effacer un crayon léger ni noircir un fond légèrement gris.
        return max(120, min(threshold, 225))

    def convert(
        self,
        sources: Sequence[ImageSource],
        destination: Path,
        fit_a4: bool = True,
        mode: ScanMode = ScanMode.ORIGINAL,
    ) -> Path:
        if not sources:
            raise EmptyImageSelectionError("Sélectionnez au moins une image.")

        images = [self._open(source, fit_a4, mode) for source in sources]
        first, rest = images[0], images[1:]
        # La qualité JPEG ne s'applique pas au noir et blanc (compression CCITT).
        jpeg_modes = (ScanMode.DOCUMENT, ScanMode.GRAYSCALE)
        options = {"quality": SCAN_JPEG_QUALITY} if mode in jpeg_modes else {}

        with atomic_write(destination) as temporary:
            first.save(
                temporary,
                format="PDF",
                save_all=True,
                append_images=rest,
                resolution=RESOLUTION_DPI,
                **options,
            )
        return destination
