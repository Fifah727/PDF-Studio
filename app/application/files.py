"""Utilitaires de noms de fichiers, indépendants de toute interface."""

from __future__ import annotations

from pathlib import Path


def with_extension(path: str, extension: str) -> str:
    """
    Garantit que ``path`` se termine par ``extension`` (insensible à la casse).

    Un nom renommé par l'utilisateur ("mon rapport", "scan.v2", "Bilan.PDF"
    ou même "bilan.") est normalisé : espaces et points finaux retirés
    (Windows les ignore de toute façon), extension ajoutée si besoin.
    """
    cleaned = path.strip().rstrip(". ")
    if Path(cleaned).suffix.lower() == extension.lower():
        return cleaned
    return cleaned + extension


def suggest_name(source_path: str, suffix: str, extension: str = ".pdf") -> str:
    """Nom proposé par défaut : ``rapport.pdf`` + ``_extrait`` -> ``rapport_extrait.pdf``."""
    return f"{Path(source_path).stem}{suffix}{extension}"
