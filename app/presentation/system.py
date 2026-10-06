"""Intégrations avec le système d'exploitation (bureau uniquement)."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def reveal_in_folder(path: Path) -> None:
    """Ouvre le dossier contenant ``path`` en sélectionnant le fichier si possible."""
    try:
        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer", f"/select,{path}"])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])
    except OSError:
        logger.exception("Impossible d'ouvrir le dossier de %s", path)
