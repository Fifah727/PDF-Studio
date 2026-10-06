"""
Objets-valeur des options des outils avancés.

Comme ``PageSelection``, ces objets se valident à la construction : un
``TextWatermark`` ou un ``CropMargins`` existant est forcément cohérent, ce
qui évite de répéter les contrôles dans les cas d'usage et dans l'interface.
Aucune dépendance à pypdf, Pillow ou Flet.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path

from app.domain.exceptions import (
    InvalidBookmarksError,
    InvalidOptionError,
    UnsupportedTextError,
)

MM_TO_POINTS = 72.0 / 25.4
MAX_CROP_MM = 200.0
MAX_STAMP_TEXT = 60
MAX_BOOKMARK_TITLE = 200


# ------------------------------------------------------------------ textes
def ensure_stampable(text: str) -> str:
    """
    Vérifie que ``text`` peut s'écrire avec une police PDF standard.

    Les polices standard (Helvetica…) couvrent l'alphabet latin d'Europe
    occidentale (jeu WinAnsi / cp1252) : le français et le malgache passent,
    pas l'arabe ni le cyrillique. Renvoie le texte nettoyé.
    """
    cleaned = " ".join(text.split())
    unsupported = sorted({char for char in cleaned if not _is_winansi(char)})
    if unsupported:
        raise UnsupportedTextError(
            "Caractères non pris en charge : " + " ".join(unsupported)
            + ". Utilisez des lettres latines (accents français et malgaches inclus)."
        )
    return cleaned


def _is_winansi(char: str) -> bool:
    try:
        char.encode("cp1252")
    except UnicodeEncodeError:
        return False
    return char.isprintable()


def _ranged(value: float, low: float, high: float, label: str) -> float:
    if not (low <= value <= high):
        raise InvalidOptionError(f"{label} doit être compris entre {low:g} et {high:g}.")
    return float(value)


# ------------------------------------------------------------------ nature d'un tampon
class StampKind(str, Enum):
    """Ce qu'un tampon représente : sert à le retrouver pour le retirer."""

    TEXT = "text"
    IMAGE = "image"
    SIGNATURE = "signature"


# ------------------------------------------------------------------ positions
class Position(str, Enum):
    """Neuf emplacements sur une page, vus à l'écran (pages pivotées comprises)."""

    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    MIDDLE_LEFT = "middle_left"
    CENTER = "center"
    MIDDLE_RIGHT = "middle_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"

    @property
    def horizontal(self) -> str:
        return {"left": "left", "right": "right"}.get(self.value.split("_")[-1], "center")

    @property
    def vertical(self) -> str:
        head = self.value.split("_")[0]
        return {"top": "top", "bottom": "bottom"}.get(head, "middle")


class StampColor(str, Enum):
    BLACK = "black"
    GRAY = "gray"
    RED = "red"
    BLUE = "blue"
    GREEN = "green"

    @property
    def rgb(self) -> tuple[float, float, float]:
        return _COLORS[self]


_COLORS = {
    StampColor.BLACK: (0.0, 0.0, 0.0),
    StampColor.GRAY: (0.45, 0.45, 0.45),
    StampColor.RED: (0.78, 0.10, 0.10),
    StampColor.BLUE: (0.10, 0.25, 0.75),
    StampColor.GREEN: (0.10, 0.50, 0.22),
}


# ------------------------------------------------------------------ compression
class CompressionLevel(str, Enum):
    LIGHT = "light"
    MEDIUM = "medium"
    STRONG = "strong"


@dataclass(frozen=True, slots=True)
class CompressionResult:
    path: Path
    original_size: int
    final_size: int

    @property
    def improved(self) -> bool:
        return self.final_size < self.original_size

    @property
    def saved_ratio(self) -> float:
        """Part économisée, entre 0 et 1."""
        if not self.improved or self.original_size <= 0:
            return 0.0
        return 1.0 - self.final_size / self.original_size


# ------------------------------------------------------------------ métadonnées
@dataclass(frozen=True, slots=True)
class PdfMetadata:
    title: str = ""
    author: str = ""
    subject: str = ""
    keywords: str = ""
    creator: str = ""
    producer: str = ""

    def cleaned(self) -> "PdfMetadata":
        return replace(self, **{name: getattr(self, name).strip() for name in _META_FIELDS})

    @property
    def is_empty(self) -> bool:
        return not any(getattr(self, name) for name in _META_FIELDS)


_META_FIELDS = ("title", "author", "subject", "keywords", "creator", "producer")


# ------------------------------------------------------------------ rognage
@dataclass(frozen=True, slots=True)
class CropMargins:
    """Marges à retirer, en millimètres, telles qu'on voit la page à l'écran."""

    top: float = 0.0
    bottom: float = 0.0
    left: float = 0.0
    right: float = 0.0

    def __post_init__(self) -> None:
        for label, value in (
            ("Marge haute", self.top),
            ("Marge basse", self.bottom),
            ("Marge gauche", self.left),
            ("Marge droite", self.right),
        ):
            _ranged(value, 0.0, MAX_CROP_MM, label)
        if not (self.top or self.bottom or self.left or self.right):
            raise InvalidOptionError("Indiquez au moins une marge à rogner.")

    def in_points(self) -> tuple[float, float, float, float]:
        """(haut, bas, gauche, droite) en points PDF."""
        return (
            self.top * MM_TO_POINTS,
            self.bottom * MM_TO_POINTS,
            self.left * MM_TO_POINTS,
            self.right * MM_TO_POINTS,
        )


# ------------------------------------------------------------------ signets
@dataclass(frozen=True, slots=True)
class Bookmark:
    title: str
    page: int  # 1-indexée
    level: int = 0

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise InvalidBookmarksError("Un signet doit avoir un titre.")
        if len(self.title) > MAX_BOOKMARK_TITLE:
            raise InvalidBookmarksError("Titre de signet trop long (200 caractères max).")
        if self.page < 1:
            raise InvalidBookmarksError("Le numéro de page d'un signet commence à 1.")
        if self.level < 0:
            raise InvalidBookmarksError("Niveau de signet invalide.")


_BOOKMARK_LINE = re.compile(r"(-*)\s*(\d+)\s*:\s*(.+)")


def parse_bookmarks(text: str | None, total_pages: int | None = None) -> list[Bookmark]:
    """
    Lit la saisie « une ligne par signet » : ``page: titre``.

    Chaque tiret en début de ligne descend d'un niveau ::

        1: Introduction
        - 3: Contexte
        5: Conclusion
    """
    bookmarks: list[Bookmark] = []
    previous_level = -1
    for number, raw in enumerate((text or "").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        match = _BOOKMARK_LINE.fullmatch(line)
        if not match:
            raise InvalidBookmarksError(
                f"Ligne {number} invalide : « {line} ». Format attendu : « 3: Titre »."
            )
        level = len(match.group(1))
        bookmark = Bookmark(match.group(3).strip(), int(match.group(2)), level)
        if level > previous_level + 1:
            raise InvalidBookmarksError(
                f"Ligne {number} : un sous-signet doit suivre un signet du niveau au-dessus."
            )
        if total_pages is not None and bookmark.page > total_pages:
            raise InvalidBookmarksError(
                f"Ligne {number} : la page {bookmark.page} n'existe pas "
                f"({total_pages} page(s))."
            )
        bookmarks.append(bookmark)
        previous_level = level
    return bookmarks


def format_bookmarks(bookmarks: list[Bookmark]) -> str:
    """Opération inverse de ``parse_bookmarks`` (pour préremplir le champ)."""
    return "\n".join(f"{'-' * b.level}{' ' if b.level else ''}{b.page}: {b.title}" for b in bookmarks)


# ------------------------------------------------------------------ tampons
@dataclass(frozen=True, slots=True)
class TextWatermark:
    text: str
    color: StampColor = StampColor.GRAY
    opacity: float = 0.25
    angle: int = 45
    scale: float = 0.7  # part de la longueur disponible occupée par le texte

    def __post_init__(self) -> None:
        text = ensure_stampable(self.text)
        if not text:
            raise InvalidOptionError("Saisissez le texte du filigrane.")
        if len(text) > MAX_STAMP_TEXT:
            raise InvalidOptionError(f"Texte trop long ({MAX_STAMP_TEXT} caractères max).")
        object.__setattr__(self, "text", text)
        _ranged(self.opacity, 0.05, 1.0, "L'opacité")
        _ranged(self.angle, -90, 90, "L'angle")
        _ranged(self.scale, 0.2, 1.0, "La taille")


@dataclass(frozen=True, slots=True)
class ImageStamp:
    """Image posée sur la page (filigrane image ou signature)."""

    position: Position = Position.CENTER
    width_fraction: float = 0.3  # largeur de l'image / largeur de la page
    opacity: float = 1.0
    margin: float = 36.0  # points, par rapport au bord de page
    remove_white_background: bool = False
    kind: StampKind = StampKind.IMAGE  # IMAGE (filigrane) ou SIGNATURE

    def __post_init__(self) -> None:
        if self.kind is StampKind.TEXT:
            raise InvalidOptionError("Un tampon image ne peut pas être de type texte.")
        _ranged(self.width_fraction, 0.05, 1.0, "La largeur")
        _ranged(self.opacity, 0.05, 1.0, "L'opacité")
        _ranged(self.margin, 0.0, 200.0, "La marge")


@dataclass(frozen=True, slots=True)
class PageNumbering:
    template: str = "{n}"
    position: Position = Position.BOTTOM_CENTER
    start: int = 1
    font_size: float = 10.0
    margin: float = 28.0
    color: StampColor = StampColor.BLACK

    def __post_init__(self) -> None:
        template = ensure_stampable(self.template)
        if "{n}" not in template:
            raise InvalidOptionError("Le format doit contenir {n} (numéro de la page).")
        if len(template) > 40:
            raise InvalidOptionError("Format trop long (40 caractères max).")
        object.__setattr__(self, "template", template)
        _ranged(self.start, 0, 99999, "Le numéro de départ")
        _ranged(self.font_size, 6, 48, "La taille du texte")
        _ranged(self.margin, 0.0, 200.0, "La marge")

    def render(self, number: int, total: int) -> str:
        return self.template.replace("{n}", str(number)).replace("{total}", str(total))


# ------------------------------------------------------------------ scan
class ScanMode(str, Enum):
    ORIGINAL = "original"
    DOCUMENT = "document"  # couleurs conservées, fond éclairci, contraste renforcé
    GRAYSCALE = "grayscale"
    BLACK_WHITE = "black_white"


# ------------------------------------------------------------------ résultats
@dataclass(frozen=True, slots=True)
class ExportResult:
    path: Path
    items: int  # images ou pages écrites


@dataclass(frozen=True, slots=True)
class BatchResult:
    path: Path
    processed: int
    failures: tuple[tuple[str, str], ...] = ()  # (nom de fichier, raison)


@dataclass(frozen=True, slots=True)
class BatchPlan:
    """Chaîne d'actions appliquée à chaque PDF, dans cet ordre fixe."""

    numbering: PageNumbering | None = None
    watermark: TextWatermark | None = None
    compression: CompressionLevel | None = None
    clear_metadata: bool = False
    password: str | None = None

    def __post_init__(self) -> None:
        if not self.steps:
            raise InvalidOptionError("Choisissez au moins une action à appliquer.")

    @property
    def steps(self) -> tuple[str, ...]:
        return tuple(
            name
            for name, active in (
                ("numbering", self.numbering is not None),
                ("watermark", self.watermark is not None),
                ("compression", self.compression is not None),
                ("metadata", self.clear_metadata),
                ("password", bool(self.password)),
            )
            if active
        )


# ------------------------------------------------------------------ retrait de filigranes
@dataclass(frozen=True, slots=True)
class WatermarkReport:
    """Filigranes identifiés dans un PDF : nombre d'occurrences par nature."""

    counts: tuple[tuple[StampKind, int], ...] = ()
    pages: int = 0  # pages concernées

    def count(self, kind: StampKind) -> int:
        return dict(self.counts).get(kind, 0)

    @property
    def total(self) -> int:
        return sum(number for _, number in self.counts)

    @property
    def kinds(self) -> tuple[StampKind, ...]:
        return tuple(kind for kind, number in self.counts if number)


@dataclass(frozen=True, slots=True)
class RemovalResult:
    path: Path
    removed: WatermarkReport
