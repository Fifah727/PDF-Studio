import pytest

from app.domain.exceptions import (
    EncryptedPdfError,
    InsufficientFilesError,
    LastPageDeletionError,
    OutputOverwritesSourceError,
    PageRangeError,
    PdfError,
    WrongPasswordError,
)
from app.presentation.di import build_use_cases
from tests.helpers import make_pdf, widths

uc = build_use_cases()


@pytest.fixture
def pdf4(tmp_path):
    return make_pdf(tmp_path / "a.pdf", 4)  # largeurs 110,120,130,140


def test_extract_multi_ranges_in_order(pdf4, tmp_path):
    out = uc.extract_pages.execute(pdf4, "3, 1-2", str(tmp_path / "o.pdf"))
    assert widths(out) == [130, 110, 120]


def test_extract_validates_before_saving(pdf4):
    assert uc.extract_pages.validate(pdf4, "1-2") == [1, 2]
    with pytest.raises(PageRangeError):
        uc.extract_pages.validate(pdf4, "1-9")


def test_delete_multiple(pdf4, tmp_path):
    out = uc.delete_pages.execute(pdf4, "1, 3-4", str(tmp_path / "o.pdf"))
    assert widths(out) == [120]


def test_delete_all_refused(pdf4, tmp_path):
    with pytest.raises(LastPageDeletionError):
        uc.delete_pages.execute(pdf4, "1-4", str(tmp_path / "o.pdf"))
    assert not (tmp_path / "o.pdf").exists()


def test_merge(pdf4, tmp_path):
    b = make_pdf(tmp_path / "b.pdf", 2, base_width=500)
    out = uc.merge_pdfs.execute([pdf4, b], str(tmp_path / "m.pdf"))
    assert widths(out) == [110, 120, 130, 140, 510, 520]
    with pytest.raises(InsufficientFilesError):
        uc.merge_pdfs.execute([pdf4], str(tmp_path / "x.pdf"))


def test_rotate_selected_and_all(pdf4, tmp_path):
    from pypdf import PdfReader

    out = uc.rotate_pages.execute(pdf4, "2", 90, str(tmp_path / "r.pdf"))
    assert [p.get("/Rotate", 0) for p in PdfReader(str(out)).pages] == [0, 90, 0, 0]
    out = uc.rotate_pages.execute(pdf4, "", 180, str(tmp_path / "r2.pdf"))
    assert [p.get("/Rotate", 0) for p in PdfReader(str(out)).pages] == [180] * 4
    with pytest.raises(PageRangeError):
        uc.rotate_pages.validate(pdf4, "1", 45)


def test_landscape(pdf4, tmp_path):
    from pypdf import PdfReader

    out = uc.landscape_pair.execute(pdf4, str(tmp_path / "l.pdf"))
    pages = PdfReader(str(out)).pages
    assert len(pages) == 2 and float(pages[0].mediabox.width) > float(pages[0].mediabox.height)


def test_split_archive_names_sorted_and_no_leftovers(tmp_path):
    import zipfile

    src = make_pdf(tmp_path / "doc.pdf", 12)
    out = uc.split_pdf.execute(src, str(tmp_path / "pages.zip"))
    names = zipfile.ZipFile(out).namelist()
    assert names[0] == "doc_page_01.pdf" and names[-1] == "doc_page_12.pdf"
    assert sorted(names) == names
    assert sorted(p.name for p in tmp_path.iterdir()) == ["doc.pdf", "pages.zip"]


@pytest.mark.parametrize("name", ["a.pdf"])
def test_never_overwrites_source(pdf4, tmp_path, name):
    for call in (
        lambda: uc.extract_pages.execute(pdf4, "1", pdf4),
        lambda: uc.delete_pages.execute(pdf4, "1", pdf4),
        lambda: uc.rotate_pages.execute(pdf4, "1", 90, pdf4),
        lambda: uc.landscape_pair.execute(pdf4, pdf4),
        lambda: uc.protect_pdf.execute(pdf4, "x", pdf4),
        lambda: uc.unlock_pdf.execute(pdf4, "x", pdf4),
        lambda: uc.split_pdf.execute(pdf4, pdf4),
    ):
        with pytest.raises(OutputOverwritesSourceError):
            call()
    assert widths(pdf4) == [110, 120, 130, 140]  # source intacte


def test_failed_write_leaves_no_partial_file(pdf4, tmp_path):
    bad = tmp_path / "ghost" / "o.pdf"
    out = uc.extract_pages.execute(pdf4, "1", str(bad))  # dossier créé à la volée
    assert out.exists()
    assert not [p for p in tmp_path.rglob("*.part")]


def test_protect_then_unlock(pdf4, tmp_path):
    protected = uc.protect_pdf.execute(pdf4, "s3cret", str(tmp_path / "p.pdf"))

    # Les autres outils refusent proprement un PDF protégé
    with pytest.raises(EncryptedPdfError):
        uc.extract_pages.execute(str(protected), "1", str(tmp_path / "x.pdf"))
    with pytest.raises(WrongPasswordError):
        uc.unlock_pdf.execute(str(protected), "nope", str(tmp_path / "u.pdf"))

    unlocked = uc.unlock_pdf.execute(str(protected), "s3cret", str(tmp_path / "u.pdf"))
    assert widths(unlocked) == [110, 120, 130, 140]
    assert uc.count_pages.execute(str(unlocked)) == 4  # lisible sans mot de passe


def test_unlock_plain_pdf_is_an_error(pdf4, tmp_path):
    with pytest.raises(PdfError, match="pas protégé"):
        uc.unlock_pdf.execute(pdf4, "", str(tmp_path / "u.pdf"))


def test_protect_requires_password(pdf4, tmp_path):
    with pytest.raises(PdfError):
        uc.protect_pdf.execute(pdf4, "", str(tmp_path / "p.pdf"))
