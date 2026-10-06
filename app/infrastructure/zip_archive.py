"""Archive ZIP écrite de façon atomique."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Sequence

from app.domain.archive import ArchiveWriter
from app.infrastructure.atomic import atomic_write


class ZipArchiveWriter(ArchiveWriter):
    def write(self, entries: Sequence[tuple[str, Path]], destination: Path) -> Path:
        with atomic_write(destination) as temporary:
            # Les PDF sont déjà compressés : STORED évite de perdre du temps pour rien.
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
                for name, path in entries:
                    archive.write(path, arcname=name)
        return destination
