"""Dossier de données de l'application (préférences, journal)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def app_data_dir() -> Path:
    """
    Dossier persistant de l'application.

    Sur mobile, Flet fournit ``FLET_APP_STORAGE_DATA`` (stockage privé de
    l'app). Sur bureau on utilise ``~/.pdf_studio`` ; en dernier recours le
    dossier temporaire (rien n'est alors conservé entre deux sessions).
    """
    candidates: list[Path] = []
    flet_storage = os.environ.get("FLET_APP_STORAGE_DATA")
    if flet_storage:
        candidates.append(Path(flet_storage))
    candidates.append(Path.home() / ".pdf_studio")
    candidates.append(Path(tempfile.gettempdir()) / "pdf_studio")

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write_test"
            probe.write_text("ok")
            probe.unlink()
            return candidate
        except OSError:
            continue
    return Path(tempfile.gettempdir())
