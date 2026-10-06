"""
Informations techniques de l'application (écran « À propos »).

Les versions sont lues sur les paquets réellement installés : sur un appareil
où une bibliothèque manque (par exemple ``cryptography`` sur un mobile), on
l'affiche comme indisponible plutôt que d'inventer un numéro.
"""

from __future__ import annotations

import platform
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Callable


@dataclass(frozen=True, slots=True)
class Library:
    package: str  # nom de distribution (pip)
    label: str  # nom affiché
    role: str  # ce qu'elle fait dans l'application
    license: str


LIBRARIES: tuple[Library, ...] = (
    Library("flet", "Flet", "L'interface, identique sur Android et Windows", "Apache-2.0"),
    Library("pypdf", "pypdf", "Lecture et écriture des pages PDF", "BSD-3-Clause"),
    Library("pillow", "Pillow", "Images, scans et compression", "HPND"),
    Library("cryptography", "cryptography", "Mots de passe AES-256", "Apache-2.0 / BSD"),
)


def installed_version(package: str) -> str | None:
    """Version installée du paquet, ou ``None`` s'il est absent."""
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return None


def library_versions(
    lookup: Callable[[str], str | None] = installed_version,
) -> list[tuple[Library, str | None]]:
    return [(library, lookup(library.package)) for library in LIBRARIES]


def build_report(
    app_name: str,
    app_version: str,
    lookup: Callable[[str], str | None] = installed_version,
) -> str:
    """
    Texte à joindre à un message de support.

    Ne contient aucune donnée personnelle : ni nom de fichier, ni nom
    d'utilisateur, ni chemin du dossier personnel.
    """
    lines = [
        f"{app_name} {app_version}",
        f"Système : {platform.system() or '?'} {platform.release()}".rstrip(),
        f"Python : {platform.python_version()}",
    ]
    for library, version in library_versions(lookup):
        lines.append(f"{library.label} : {version or 'indisponible'}")
    return "\n".join(lines)


def existing_data_file(data_dir: Path) -> Path | None:
    """Un fichier de données réellement présent (pour ouvrir le dossier en le sélectionnant)."""
    for name in ("settings.json", "recents.json"):
        candidate = data_dir / name
        if candidate.is_file():
            return candidate
    return None
