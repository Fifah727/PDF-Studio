"""
Repérage et retrait des filigranes (``pypdf``).

Seuls les filigranes **identifiables comme tels** sont retirés :

- ceux de PDF Studio (balisage ``/Artifact /Subtype /Watermark`` + ``/PSKind``) ;
- ceux que d'autres outils déclarent comme filigranes avec ce même balisage
  standard (ISO 32000), ou dans un calque facultatif nommé « watermark » /
  « filigrane ».

Un filigrane « aplati » dans l'image d'une page (scan, impression en PDF,
filigrane fondu dans le fond) ne se distingue pas du contenu : il ne peut pas
être retiré automatiquement, et l'outil ne tente pas de le deviner.

On ne touche qu'au flux de contenu des pages : le texte et les images du
document ne sont jamais modifiés, seuls les blocs marqués disparaissent.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Collection

from pypdf import PageObject, PdfWriter
from pypdf.generic import ContentStream, DictionaryObject, NameObject

from app.domain.exceptions import NoWatermarkError
from app.domain.models import PdfSource
from app.domain.options import RemovalResult, StampKind, WatermarkReport
from app.domain.unmarking import WatermarkRemover
from app.infrastructure.pypdf_common import open_reader, write_pdf

logger = logging.getLogger(__name__)

_TEXT_OPERATORS = {b"Tj", b"TJ", b"'", b'"'}
_LAYER_WORDS = ("watermark", "filigrane")
_MAX_FORM_DEPTH = 3
# (opérateur, catégorie de /Resources, position de l'opérande qui porte le nom)
_NAME_USES = ((b"Do", "/XObject", 0), (b"Tf", "/Font", 0), (b"gs", "/ExtGState", 0))


@dataclass(frozen=True, slots=True)
class _Block:
    start: int  # index du BDC
    end: int  # index du EMC correspondant
    kind: StampKind


class PyPdfWatermarkRemover(WatermarkRemover):
    # ------------------------------------------------------------ analyse
    def scan(self, source: PdfSource) -> WatermarkReport:
        reader = open_reader(source)
        tally: Counter[StampKind] = Counter()
        pages = 0
        for page in reader.pages:
            blocks = self._blocks(page)
            tally.update(block.kind for block in blocks)
            pages += bool(blocks)
        return _report(tally, pages)

    # ------------------------------------------------------------ retrait
    def remove(
        self, source: PdfSource, kinds: Collection[StampKind], destination: Path
    ) -> RemovalResult:
        wanted = set(kinds)
        writer = PdfWriter(clone_from=open_reader(source))
        removed: Counter[StampKind] = Counter()
        found: Counter[StampKind] = Counter()
        pages = 0

        for page in writer.pages:
            operations = _operations(page)
            if operations is None:
                continue
            blocks = self._blocks(page, operations)
            found.update(block.kind for block in blocks)
            chosen = [block for block in blocks if block.kind in wanted]
            if not chosen:
                continue
            self._strip(writer, page, operations, chosen)
            removed.update(block.kind for block in chosen)
            pages += 1

        if not removed:
            if not found:
                raise NoWatermarkError(
                    "Aucun filigrane identifiable dans ce PDF. Un filigrane intégré à "
                    "l'image des pages (scan, impression en PDF) ne peut pas être retiré "
                    "automatiquement."
                )
            raise NoWatermarkError("Aucun filigrane du type choisi dans ce PDF.")

        write_pdf(writer, destination)
        return RemovalResult(destination, _report(removed, pages))

    # ------------------------------------------------------------ blocs marqués
    def _blocks(self, page: PageObject, operations=None) -> list[_Block]:
        try:
            operations = operations if operations is not None else _operations(page)
            if not operations:
                return []
            resources = _resources(page)
            found: list[_Block] = []
            stack: list[tuple[int, list | None]] = []
            for index, (operands, operator) in enumerate(operations):
                if operator == b"BDC":
                    stack.append((index, operands))
                elif operator == b"BMC":
                    stack.append((index, None))
                elif operator == b"EMC" and stack:
                    start, opened = stack.pop()
                    kind = (
                        self._kind_of(opened, resources, operations[start + 1 : index], page)
                        if opened
                        else None
                    )
                    if kind is not None:
                        found.append(_Block(start, index, kind))
            # Un filigrane contenu dans un autre n'est compté (et retiré) qu'une fois.
            return [
                b
                for b in found
                if not any(o.start < b.start and o.end > b.end for o in found)
            ]
        except Exception:  # flux illisible : cette page est laissée telle quelle
            logger.debug("Page non analysée", exc_info=True)
            return []

    def _kind_of(self, operands, resources, inner, page) -> StampKind | None:
        if len(operands) < 2:
            return None
        tag = str(operands[0])
        properties = _properties(operands[1], resources)
        if properties is None:
            return None
        if tag == "/Artifact" and properties.get("/Subtype") == "/Watermark":
            declared = str(properties.get("/PSKind", ""))
            if declared in {kind.value for kind in StampKind}:
                return StampKind(declared)
            return _classify(inner, resources, page.pdf)
        if tag == "/OC":
            name = str(properties.get("/Name", "")).lower()
            if any(word in name for word in _LAYER_WORDS):
                return _classify(inner, resources, page.pdf)
        return None

    # ------------------------------------------------------------ suppression
    def _strip(self, writer, page, operations, chosen: list[_Block]) -> None:
        dropped = {i for block in chosen for i in range(block.start, block.end + 1)}
        kept = [op for i, op in enumerate(operations) if i not in dropped]
        removed_ops = [op for i, op in enumerate(operations) if i in dropped]

        content = ContentStream(None, writer)
        content.operations = kept
        page.replace_contents(content)
        _prune_resources(page, removed_ops, kept)


# ====================================================================== aides
def _report(tally: Counter, pages: int) -> WatermarkReport:
    ordered = tuple((kind, tally[kind]) for kind in StampKind if tally[kind])
    return WatermarkReport(ordered, pages)


def _operations(page: PageObject):
    contents = page.get_contents()
    return None if contents is None else contents.operations


def _resources(page: PageObject) -> DictionaryObject:
    """Ressources de la page, héritées des pages parentes si besoin."""
    node = page
    while node is not None:
        found = node.get("/Resources")
        if found is not None:
            return found.get_object()
        parent = node.get("/Parent")
        node = parent.get_object() if parent is not None else None
    return DictionaryObject()


def _properties(operand, resources) -> DictionaryObject | None:
    """Liste de propriétés d'un BDC : dictionnaire en ligne, ou nom défini dans /Properties."""
    if isinstance(operand, NameObject):
        entry = resources.get("/Properties", {}).get(operand)
        operand = entry.get_object() if entry is not None else None
    elif hasattr(operand, "get_object"):
        operand = operand.get_object()
    return operand if isinstance(operand, DictionaryObject) else None


def _classify(inner, resources, pdf, depth: int = 0) -> StampKind:
    """Texte ou image ? Les objets formulaire (Do) sont ouverts sur quelques niveaux."""
    has_text = has_image = False
    for operands, operator in inner:
        if operator in _TEXT_OPERATORS:
            has_text = True
        elif operator == b"BI":
            has_image = True
        elif operator == b"Do" and operands:
            target = resources.get("/XObject", {}).get(operands[0])
            target = target.get_object() if target is not None else None
            if target is None:
                continue
            if target.get("/Subtype") == "/Form" and depth < _MAX_FORM_DEPTH:
                form = ContentStream(target, pdf)
                nested = _classify(
                    form.operations, target.get("/Resources", resources).get_object(), pdf, depth + 1
                )
                has_text |= nested is StampKind.TEXT
                has_image |= nested is not StampKind.TEXT
            else:
                has_image = True
    if has_text:
        return StampKind.TEXT
    return StampKind.IMAGE


def _prune_resources(page: PageObject, removed_ops, kept_ops) -> None:
    """
    Retire des ressources de la page les polices, images et états graphiques
    que seuls les blocs supprimés utilisaient : le fichier s'allège d'autant.

    Prudent par construction : on ne touche qu'à un dictionnaire de ressources
    propre à la page (pas à un dictionnaire partagé entre pages) et qu'aux
    noms réellement utilisés par ce qui a été supprimé.
    """
    raw = page.get("/Resources")
    if raw is None or hasattr(raw, "idnum"):  # héritées ou partagées : on ne modifie pas
        return
    resources = raw.get_object() if hasattr(raw, "get_object") else raw
    for operator, category, position in _NAME_USES:
        table = resources.get(category)
        if table is None:
            continue
        table = table.get_object()
        still_used = {str(ops[0][position]) for ops in kept_ops if ops[1] == operator and ops[0]}
        for operands, op in removed_ops:
            if op != operator or not operands:
                continue
            name = str(operands[position])
            if name not in still_used and name in table:
                del table[NameObject(name)]
