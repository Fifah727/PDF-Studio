from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader, PdfWriter


def make_pdf(path: Path, pages: int, base_width: int = 100) -> str:
    """PDF dont chaque page a une largeur distincte (base + 10*n) : pages identifiables."""
    writer = PdfWriter()
    for n in range(1, pages + 1):
        writer.add_blank_page(width=base_width + 10 * n, height=300)
    with path.open("wb") as handle:
        writer.write(handle)
    return str(path)


def widths(path) -> list[int]:
    return [round(float(p.mediabox.width)) for p in PdfReader(str(path)).pages]


def make_photo_pdf(path: Path, size: tuple[int, int] = (1600, 1200)) -> str:
    """PDF d'une page portant une grosse image bruitée (compressible)."""
    from PIL import Image

    Image.effect_noise(size, 60).convert("RGB").save(path, "PDF", resolution=150)
    return str(path)


def make_text_pdf(path: Path, lines: list[str]) -> str:
    """PDF dont chaque page contient une ligne de texte réellement extractible."""
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    for line in lines:
        page = writer.add_blank_page(width=300, height=300)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 14 Tf 20 150 Td ({line}) Tj ET".encode("latin-1"))
        page.replace_contents(stream)
    with path.open("wb") as handle:
        writer.write(handle)
    return str(path)
