"""
Réduction de taille d'un PDF (``pypdf`` + ``Pillow``).

Deux leviers, sans aucun service externe :

- les flux de contenu (texte, tracés) sont recompressés ;
- les grosses images sont réencodées en JPEG, et réduites si elles dépassent
  la définition utile du niveau choisi.

Une image n'est remplacée que si le gain est réel, et un document dont la
taille ne diminue pas est restitué à l'identique : l'outil ne grossit jamais
un fichier.
"""

from __future__ import annotations

import io
import logging
import shutil
from pathlib import Path

from pypdf import PdfWriter
from PIL import Image

from app.domain.models import PdfSource
from app.domain.optimization import PdfOptimizer
from app.domain.options import CompressionLevel, CompressionResult
from app.infrastructure.atomic import atomic_write
from app.infrastructure.pypdf_common import open_reader

logger = logging.getLogger(__name__)

# niveau -> (qualité JPEG, plus grand côté en pixels)
_SETTINGS: dict[CompressionLevel, tuple[int, int]] = {
    CompressionLevel.LIGHT: (85, 3000),
    CompressionLevel.MEDIUM: (70, 2000),
    CompressionLevel.STRONG: (50, 1400),
}
_MIN_PIXELS = 40_000  # sous ce seuil (≈ 200 x 200), le gain ne vaut pas le calcul
_MIN_GAIN = 0.05  # on ignore un gain inférieur à 5 % sur une image


class PyPdfOptimizer(PdfOptimizer):
    def compress(
        self, source: PdfSource, level: CompressionLevel, destination: Path
    ) -> CompressionResult:
        quality, max_side = _SETTINGS[level]
        reader = open_reader(source)
        writer = PdfWriter(clone_from=reader)

        seen: set[int] = set()
        for page in writer.pages:
            self._shrink_images(page, quality, max_side, seen)
            try:
                page.compress_content_streams(level=9)
            except Exception:  # flux atypique : la page reste telle quelle
                logger.debug("Flux non recompressé", exc_info=True)
        writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)

        original_size = source.path.stat().st_size
        with atomic_write(destination) as temporary:
            with temporary.open("wb") as handle:
                writer.write(handle)
            final_size = temporary.stat().st_size
            if final_size >= original_size:
                shutil.copyfile(source.path, temporary)  # jamais plus gros
                final_size = original_size
        return CompressionResult(destination, original_size, final_size)

    # ------------------------------------------------------------ images
    def _shrink_images(self, page, quality: int, max_side: int, seen: set[int]) -> None:
        try:
            images = page.images
            total = len(images)
        except Exception:
            logger.debug("Images illisibles", exc_info=True)
            return
        for position in range(total):
            try:
                image = images[position]
                reference = image.indirect_reference
                if reference is None or reference.idnum in seen:
                    continue
                seen.add(reference.idnum)
                self._shrink(image, quality, max_side)
            except Exception:  # image atypique : on la laisse intacte
                logger.debug("Image conservée telle quelle", exc_info=True)

    @staticmethod
    def _shrink(image, quality: int, max_side: int) -> None:
        xobject = image.indirect_reference.get_object()
        # Masques et transparence : le remplacement les perdrait.
        if any(key in xobject for key in ("/SMask", "/Mask", "/ImageMask")):
            return
        if xobject.get("/BitsPerComponent") == 1:
            return
        decoded = image.image
        if decoded is None or decoded.mode == "CMYK":
            return
        width, height = decoded.size
        if width * height < _MIN_PIXELS:
            return

        candidate = decoded if decoded.mode in ("RGB", "L") else decoded.convert("RGB")
        if max(width, height) > max_side:
            candidate = candidate.copy()
            candidate.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

        try:
            original_size = int(xobject["/Length"])
        except (KeyError, TypeError, ValueError):
            original_size = len(image.data)
        probe = io.BytesIO()
        candidate.save(probe, format="JPEG", quality=quality, optimize=True)
        if probe.tell() > original_size * (1 - _MIN_GAIN):
            return
        image.replace(candidate, quality=quality)
