"""Compression, métadonnées, signets."""

import pytest
from pypdf import PdfReader, PdfWriter

from app.domain.exceptions import InvalidBookmarksError, OutputOverwritesSourceError
from app.domain.models import PdfSource
from app.domain.options import CompressionLevel, PdfMetadata
from app.infrastructure.pypdf_repository import PyPdfRepository
from app.presentation.di import build_use_cases
from app.presentation.screens.optimize_screens import compression_message
from tests.helpers import make_pdf, make_photo_pdf, widths

uc = build_use_cases()
repo = PyPdfRepository()


# ------------------------------------------------------------------ compression
def test_strong_compression_shrinks_a_photo_pdf(tmp_path):
    src = make_photo_pdf(tmp_path / "photo.pdf")
    result = uc.compress_pdf.execute(src, CompressionLevel.STRONG, str(tmp_path / "o.pdf"))
    assert result.improved and result.final_size < 0.7 * result.original_size
    assert result.path.stat().st_size == result.final_size
    assert len(PdfReader(str(result.path)).pages) == 1


def test_compression_never_makes_a_file_bigger(tmp_path):
    src = make_pdf(tmp_path / "plain.pdf", 3)  # déjà minimal
    result = uc.compress_pdf.execute(src, CompressionLevel.LIGHT, str(tmp_path / "o.pdf"))
    assert result.final_size <= result.original_size
    assert widths(result.path) == [110, 120, 130]
    assert not any(p.name.endswith(".part") for p in tmp_path.iterdir())


def test_compression_keeps_the_original_untouched(tmp_path):
    src = make_photo_pdf(tmp_path / "photo.pdf")
    before = (tmp_path / "photo.pdf").read_bytes()
    uc.compress_pdf.execute(src, "medium", str(tmp_path / "o.pdf"))
    assert (tmp_path / "photo.pdf").read_bytes() == before


def test_compress_refuses_overwriting_source(tmp_path):
    src = make_photo_pdf(tmp_path / "photo.pdf")
    with pytest.raises(OutputOverwritesSourceError):
        uc.compress_pdf.execute(src, CompressionLevel.MEDIUM, src)


def test_compression_message_reports_gain_or_absence_of_gain(tmp_path):
    from pathlib import Path

    from app.domain.options import CompressionResult

    saved = Path("x_compresse.pdf")
    better = compression_message(CompressionResult(saved, 5 * 1024 * 1024, 1024 * 1024), saved)
    assert "5,0 Mo → 1,0 Mo" in better and "−80 %" in better
    assert "déjà optimisé" in compression_message(CompressionResult(saved, 100, 100), saved)
    assert "déjà optimisé" in compression_message(None, saved)


# ------------------------------------------------------------------ métadonnées
def pdf_with_metadata(path):
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_metadata({"/Title": "Rapport", "/Author": "Jean", "/Subject": "Secret"})
    writer.write(path)
    return str(path)


def test_read_then_write_metadata(tmp_path):
    src = pdf_with_metadata(tmp_path / "m.pdf")
    current = uc.read_metadata.execute(src)
    assert (current.title, current.author, current.subject) == ("Rapport", "Jean", "Secret")

    out = uc.write_metadata.execute(
        src, PdfMetadata(title="Nouveau titre", author="  Fifa  "), str(tmp_path / "o.pdf")
    )
    info = PdfReader(str(out)).metadata
    assert info.title == "Nouveau titre" and info.author == "Fifa"
    assert info.get("/Subject") is None  # champ laissé vide = retiré


def test_clear_all_metadata_removes_info_and_xmp(tmp_path):
    src = pdf_with_metadata(tmp_path / "m.pdf")
    out = uc.write_metadata.execute(src, PdfMetadata(), str(tmp_path / "o.pdf"), clear_all=True)
    reader = PdfReader(str(out))
    assert not reader.metadata or not reader.metadata.get("/Title")
    assert not reader.metadata or not reader.metadata.get("/Author")
    assert reader.xmp_metadata is None
    assert len(reader.pages) == 1


def test_read_metadata_of_pdf_without_info_is_empty(tmp_path):
    writer = PdfWriter()
    writer.add_blank_page(width=10, height=10)
    writer.metadata = None
    writer.write(tmp_path / "n.pdf")
    assert uc.read_metadata.execute(str(tmp_path / "n.pdf")).title == ""


# ------------------------------------------------------------------ signets
def test_write_bookmarks_builds_nested_outline(tmp_path):
    src = make_pdf(tmp_path / "a.pdf", 6)
    text = "1: Introduction\n- 2: Contexte\n- 3: Objectifs\n4: Corps\n- 5: Détail\n6: Conclusion"
    out = uc.write_bookmarks.execute(src, text, str(tmp_path / "o.pdf"))
    assert [(b.title, b.page, b.level) for b in uc.read_bookmarks.execute(str(out))] == [
        ("Introduction", 1, 0), ("Contexte", 2, 1), ("Objectifs", 3, 1),
        ("Corps", 4, 0), ("Détail", 5, 1), ("Conclusion", 6, 0),
    ]
    assert widths(out) == [110, 120, 130, 140, 150, 160]  # les pages sont intactes


def test_bookmark_levels_are_preserved_when_reread(tmp_path):
    src = make_pdf(tmp_path / "a.pdf", 4)
    out = uc.write_bookmarks.execute(src, "1: A\n- 2: B\n-- 3: C\n4: D", str(tmp_path / "o.pdf"))
    assert [(b.title, b.level) for b in uc.read_bookmarks.execute(str(out))] == [
        ("A", 0), ("B", 1), ("C", 2), ("D", 0),
    ]


def test_empty_bookmark_text_removes_existing_bookmarks(tmp_path):
    src = make_pdf(tmp_path / "a.pdf", 3)
    with_marks = uc.write_bookmarks.execute(src, "1: A\n2: B", str(tmp_path / "w.pdf"))
    assert len(uc.read_bookmarks.execute(str(with_marks))) == 2
    cleaned = uc.write_bookmarks.execute(str(with_marks), "", str(tmp_path / "c.pdf"))
    assert uc.read_bookmarks.execute(str(cleaned)) == []
    assert len(PdfReader(str(cleaned)).pages) == 3


def test_bookmark_pages_are_checked_against_the_document(tmp_path):
    src = make_pdf(tmp_path / "a.pdf", 3)
    with pytest.raises(InvalidBookmarksError, match="page 7"):
        uc.write_bookmarks.execute(src, "1: A\n7: B", str(tmp_path / "o.pdf"))
    assert not (tmp_path / "o.pdf").exists()


def test_bookmarks_replace_previous_ones(tmp_path):
    src = make_pdf(tmp_path / "a.pdf", 3)
    first = uc.write_bookmarks.execute(src, "1: Vieux\n2: Ancien", str(tmp_path / "f.pdf"))
    second = uc.write_bookmarks.execute(str(first), "3: Nouveau", str(tmp_path / "s.pdf"))
    assert [(b.title, b.page) for b in repo.read_bookmarks(PdfSource(second))] == [("Nouveau", 3)]
