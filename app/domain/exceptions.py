"""
Exceptions métier du domaine.

Ces exceptions ne dépendent d'aucune bibliothèque tierce (ni pypdf, ni
Flet). Les couches infrastructure traduisent leurs erreurs techniques vers
ces types ; les couches presentation les affichent sans connaître leur
origine technique.
"""

from __future__ import annotations


class PdfError(Exception):
    """Racine de toutes les erreurs métier liées aux PDF."""


class InvalidPdfFileError(PdfError):
    """Le fichier n'existe pas, n'est pas lisible ou n'est pas un PDF valide."""


class PageRangeError(PdfError):
    """Plage ou numéro de page invalide pour le document concerné."""


class InsufficientFilesError(PdfError):
    """Une opération nécessitant plusieurs fichiers n'en a pas reçu assez."""


class LastPageDeletionError(PdfError):
    """Tentative de supprimer toutes les pages d'un document."""


class InvalidImageError(PdfError):
    """Le fichier n'existe pas, n'est pas lisible ou n'est pas une image valide."""


class EmptyImageSelectionError(PdfError):
    """Une conversion image → PDF a été lancée sans aucune image sélectionnée."""


class OutputOverwritesSourceError(PdfError):
    """Le fichier de sortie est le même que l'un des fichiers sources."""


class EncryptedPdfError(PdfError):
    """Le PDF est protégé par un mot de passe que l'on ne connaît pas."""


class WrongPasswordError(PdfError):
    """Le mot de passe fourni ne permet pas d'ouvrir le PDF."""


class EncryptionUnavailableError(PdfError):
    """La bibliothèque de chiffrement n'est pas disponible sur cette plateforme."""


class InvalidOptionError(PdfError):
    """Une option saisie (opacité, taille, marge…) est hors des valeurs permises."""


class UnsupportedTextError(InvalidOptionError):
    """Le texte contient des caractères que la police PDF standard ne sait pas écrire."""


class InvalidCropError(InvalidOptionError):
    """Les marges de rognage ne laissent aucune surface visible sur une page."""


class InvalidBookmarksError(InvalidOptionError):
    """La liste de signets saisie est mal formée ou hors du document."""


class PageCountMismatchError(PdfError):
    """Les deux PDF (recto/verso) n'ont pas des nombres de pages compatibles."""


class NoContentError(PdfError):
    """Le PDF ne contient rien à extraire (aucune image, aucun texte)."""


class NoWatermarkError(PdfError):
    """Aucun filigrane identifiable (du type demandé) dans le PDF."""
