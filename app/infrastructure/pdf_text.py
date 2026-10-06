"""
Texte pour les polices PDF standard (Helvetica, jeu WinAnsi).

Les 14 polices standard sont connues de tout lecteur PDF : rien à
incorporer, le fichier reste léger. En contrepartie, il faut connaître la
largeur des caractères pour centrer ou aligner un texte.
"""

from __future__ import annotations

import unicodedata

# Largeurs Helvetica (AFM) des caractères ASCII 32 à 126, en 1/1000 d'em.
_ASCII_WIDTHS = (
    278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,  # espace … /
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556,                                # 0 … 9
    278, 278, 584, 584, 584, 556, 1015,                                              # : … @
    667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833,                 # A … M
    722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611,                 # N … Z
    278, 278, 278, 469, 556, 333,                                                    # [ … `
    556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833,                 # a … m
    556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500,                 # n … z
    334, 260, 334, 584,                                                              # { … ~
)
assert len(_ASCII_WIDTHS) == 95

_SPECIAL_WIDTHS = {
    "ß": 611, "æ": 889, "œ": 944, "Æ": 1000, "Œ": 1000, "ø": 611, "Ø": 778,
    "ð": 556, "þ": 556, "Þ": 667, "Ð": 722, "€": 556, "£": 556, "¥": 556,
    "§": 556, "©": 737, "®": 737, "°": 400, "«": 556, "»": 556, "–": 556,
    "—": 1000, "…": 1000, "‘": 222, "’": 222, "“": 333, "”": 333, "•": 350,
    "×": 584, "÷": 584, "¿": 611, "¡": 333, "\u00a0": 278,
}
_DEFAULT_WIDTH = 556
ASCENT = 0.72  # hauteur approximative des majuscules / taille de police


def char_width(char: str) -> int:
    if char in _SPECIAL_WIDTHS:
        return _SPECIAL_WIDTHS[char]
    code = ord(char)
    if 32 <= code <= 126:
        return _ASCII_WIDTHS[code - 32]
    # Lettres accentuées : même chasse que la lettre de base (é -> e).
    base = unicodedata.normalize("NFD", char)[0]
    if 32 <= ord(base) <= 126:
        return _ASCII_WIDTHS[ord(base) - 32]
    return _DEFAULT_WIDTH


def text_width(text: str, size: float) -> float:
    """Largeur du texte, en points, à la taille ``size``."""
    return sum(char_width(char) for char in text) * size / 1000.0


def pdf_literal(text: str) -> bytes:
    """Chaîne PDF ``(…)`` encodée en WinAnsi, caractères spéciaux échappés."""
    out = bytearray(b"(")
    for byte in text.encode("cp1252", errors="replace"):
        if byte in b"()\\":
            out += b"\\" + bytes([byte])
        elif 32 <= byte < 127:
            out.append(byte)
        else:
            out += b"\\%03o" % byte
    out += b")"
    return bytes(out)
