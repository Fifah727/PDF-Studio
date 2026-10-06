"""Écriture atomique : le fichier final n'apparaît que s'il est complet."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def atomic_write(destination: Path) -> Iterator[Path]:
    """
    Fournit un chemin temporaire voisin de ``destination``.

    Si le bloc réussit, le temporaire remplace la destination en une
    opération ; s'il échoue, il est supprimé et la destination (éventuel
    fichier existant) reste intacte. Une opération interrompue ne laisse
    donc jamais de PDF tronqué.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.part")
    try:
        yield temporary
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
