"""
Briques communes aux implémentations basées sur ``pypdf``.

Ouverture sécurisée d'un PDF (avec gestion des documents chiffrés) et
écriture atomique : partagées par le dépôt, l'optimiseur et le « tampon ».
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.errors import DependencyError, PdfReadError

from app.domain.exceptions import (
    EncryptedPdfError,
    EncryptionUnavailableError,
    InvalidPdfFileError,
    WrongPasswordError,
)
from app.domain.models import PdfSource
from app.infrastructure.atomic import atomic_write


def open_reader(source: PdfSource, password: str | None = None) -> PdfReader:
    """Ouvre ``source`` ; traduit les erreurs de ``pypdf`` en erreurs métier."""
    try:
        reader = PdfReader(str(source.path))
    except (PdfReadError, OSError) as exc:
        raise InvalidPdfFileError(f"Impossible de lire le PDF : {exc}") from exc

    if reader.is_encrypted:
        try:
            # Beaucoup de PDF « chiffrés » n'ont qu'un mot de passe
            # propriétaire (restrictions d'impression) : le mot de passe
            # vide suffit alors à les lire.
            outcome = reader.decrypt(password or "")
        except DependencyError as exc:
            raise EncryptionUnavailableError(
                "Le déchiffrement n'est pas disponible sur cette plateforme."
            ) from exc
        except Exception as exc:  # pypdf lève des types variés sur fichiers corrompus
            raise InvalidPdfFileError(f"Impossible de lire le PDF : {exc}") from exc

        if not outcome:
            if password:
                raise WrongPasswordError("Mot de passe incorrect.")
            raise EncryptedPdfError(
                "Ce PDF est protégé par un mot de passe. Déverrouillez-le "
                "d'abord avec l'outil « Mot de passe »."
            )
    return reader


def write_pdf(writer: PdfWriter, destination: Path) -> Path:
    """Écrit ``writer`` de façon atomique : jamais de PDF tronqué."""
    with atomic_write(destination) as temporary:
        with temporary.open("wb") as handle:
            writer.write(handle)
    return destination
