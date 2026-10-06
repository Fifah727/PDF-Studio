"""
Traitement par lot : une chaîne d'actions appliquée à plusieurs PDF.

Chaque PDF suit les mêmes étapes, dans un ordre fixe (numérotation, filigrane,
compression, effacement des métadonnées, mot de passe) ; le mot de passe vient
en dernier pour que les étapes précédentes puissent lire le document. Les
résultats sont regroupés dans une archive ZIP.

Un fichier en échec (illisible, déjà protégé…) n'arrête pas le lot : il est
listé dans le résultat et les autres continuent.
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from app.application.common import ensure_distinct
from app.domain.archive import ArchiveWriter
from app.domain.exceptions import InsufficientFilesError, PdfError
from app.domain.models import PdfSource
from app.domain.optimization import PdfOptimizer
from app.domain.options import BatchPlan, BatchResult, PdfMetadata
from app.domain.repositories import PdfRepository
from app.domain.stamping import PdfStamper

logger = logging.getLogger(__name__)

OUTPUT_SUFFIX = "_traite"


@dataclass(frozen=True, slots=True)
class BatchProcessUseCase:
    repository: PdfRepository
    stamper: PdfStamper
    optimizer: PdfOptimizer
    archive: ArchiveWriter

    def execute(
        self, source_paths: Sequence[str], plan: BatchPlan, destination: str
    ) -> BatchResult:
        if not source_paths:
            raise InsufficientFilesError("Sélectionnez au moins un PDF.")
        ensure_distinct(source_paths, destination)

        entries: list[tuple[str, Path]] = []
        failures: list[tuple[str, str]] = []
        used_names: set[str] = set()

        with tempfile.TemporaryDirectory(prefix="pdf_studio_") as folder:
            work = Path(folder)
            for index, path in enumerate(source_paths):
                name = Path(path).name
                try:
                    result = self._process(path, plan, work / str(index))
                except PdfError as exc:
                    failures.append((name, str(exc)))
                    continue
                except Exception as exc:  # un fichier cassé ne doit pas tuer le lot
                    logger.exception("Échec du traitement de %s", name)
                    failures.append((name, f"Erreur inattendue : {exc}"))
                    continue
                entries.append((_unique_name(Path(name).stem, used_names), result))

            if not entries:
                reason = failures[0][1] if failures else "aucun fichier"
                raise PdfError(f"Aucun fichier n'a pu être traité ({reason}).")
            self.archive.write(entries, Path(destination))

        return BatchResult(Path(destination), len(entries), tuple(failures))

    # ------------------------------------------------------------ une chaîne
    def _process(self, path: str, plan: BatchPlan, folder: Path) -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        current = PdfSource(Path(path))
        step = 0

        def next_file() -> Path:
            nonlocal step
            step += 1
            return folder / f"etape_{step}.pdf"

        def everything() -> list[int]:
            return list(range(1, self.repository.count_pages(current) + 1))

        if plan.numbering is not None:
            output = self.stamper.number_pages(current, plan.numbering, everything(), next_file())
            current = PdfSource(output)
        if plan.watermark is not None:
            output = self.stamper.watermark_text(current, plan.watermark, everything(), next_file())
            current = PdfSource(output)
        if plan.compression is not None:
            output = self.optimizer.compress(current, plan.compression, next_file()).path
            current = PdfSource(output)
        if plan.clear_metadata:
            output = self.repository.write_metadata(
                current, PdfMetadata(), next_file(), clear_all=True
            )
            current = PdfSource(output)
        if plan.password:
            output = self.repository.protect(current, plan.password, next_file())
            current = PdfSource(output)
        return current.path


def _unique_name(stem: str, used: set[str]) -> str:
    """``rapport_traite.pdf``, puis ``rapport_traite_2.pdf``… si le nom existe déjà."""
    candidate = f"{stem}{OUTPUT_SUFFIX}.pdf"
    counter = 2
    while candidate.lower() in used:
        candidate = f"{stem}{OUTPUT_SUFFIX}_{counter}.pdf"
        counter += 1
    used.add(candidate.lower())
    return candidate
