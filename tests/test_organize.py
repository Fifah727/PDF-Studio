"""Réorganiser, insérer, recto-verso, rogner."""

import pytest
from pypdf import PdfReader

from app.domain.exceptions import (
    InvalidCropError,
    InvalidOptionError,
    OutputOverwritesSourceError,
    PageCountMismatchError,
    PageRangeError,
)
from app.domain.options import CropMargins
from app.presentation.di import build_use_cases
from tests.helpers import make_pdf, widths

uc = build_use_cases()


@pytest.fixture
def pdf4(tmp_path):
    return make_pdf(tmp_path / "a.pdf", 4)  # largeurs 110,120,130,140


# ------------------------------------------------------------------ réorganiser
def test_reorder_listed_pages_first_rest_follows(pdf4, tmp_path):
    out = uc.reorder_pages.execute(pdf4, "3, 1", str(tmp_path / "o.pdf"))
    assert widths(out) == [130, 110, 120, 140]


def test_reorder_reverse_whole_document(pdf4, tmp_path):
    out = uc.reorder_pages.execute(pdf4, "", str(tmp_path / "o.pdf"), reverse=True)
    assert widths(out) == [140, 130, 120, 110]


def test_reorder_identity_is_refused(pdf4, tmp_path):
    with pytest.raises(InvalidOptionError, match="identique"):
        uc.reorder_pages.execute(pdf4, "1, 2, 3, 4", str(tmp_path / "o.pdf"))
    assert not (tmp_path / "o.pdf").exists()


def test_reorder_out_of_range_and_overwrite(pdf4, tmp_path):
    with pytest.raises(PageRangeError):
        uc.reorder_pages.validate(pdf4, "9")
    with pytest.raises(OutputOverwritesSourceError):
        uc.reorder_pages.execute(pdf4, "2", pdf4)


# ------------------------------------------------------------------ insérer
def test_insert_blank_pages_match_neighbour_size(pdf4, tmp_path):
    out = uc.insert_pages.execute(pdf4, 2, str(tmp_path / "o.pdf"), blank_count=2)
    assert widths(out) == [110, 120, 120, 120, 130, 140]


def test_insert_blank_at_start_and_end(pdf4, tmp_path):
    start = uc.insert_pages.execute(pdf4, 0, str(tmp_path / "s.pdf"), blank_count=1)
    assert widths(start) == [110, 110, 120, 130, 140]
    end = uc.insert_pages.execute(pdf4, 4, str(tmp_path / "e.pdf"), blank_count=1)
    assert widths(end) == [110, 120, 130, 140, 140]


def test_insert_blank_page_respects_rotation(tmp_path):
    from pypdf import PdfWriter

    writer = PdfWriter()
    page = writer.add_blank_page(width=100, height=300)
    page.rotate(90)
    path = tmp_path / "r.pdf"
    writer.write(path)
    out = uc.insert_pages.execute(str(path), 1, str(tmp_path / "o.pdf"), blank_count=1)
    blank = PdfReader(str(out)).pages[1]
    # Page vue en paysage (300 x 100) : la page blanche l'est aussi.
    assert (round(float(blank.mediabox.width)), round(float(blank.mediabox.height))) == (300, 100)


def test_insert_another_pdf(pdf4, tmp_path):
    other = make_pdf(tmp_path / "b.pdf", 2, base_width=500)
    out = uc.insert_pages.execute(pdf4, 1, str(tmp_path / "o.pdf"), insert_path=other)
    assert widths(out) == [110, 510, 520, 120, 130, 140]
    at_start = uc.insert_pages.execute(pdf4, 0, str(tmp_path / "s.pdf"), insert_path=other)
    assert widths(at_start) == [510, 520, 110, 120, 130, 140]


@pytest.mark.parametrize("after,blanks", [(9, 1), (-1, 1), (1, 0), (1, 500)])
def test_insert_validation(pdf4, tmp_path, after, blanks):
    with pytest.raises((PageRangeError, InvalidOptionError)):
        uc.insert_pages.execute(pdf4, after, str(tmp_path / "o.pdf"), blank_count=blanks)


def test_insert_refuses_overwriting_either_input(pdf4, tmp_path):
    other = make_pdf(tmp_path / "b.pdf", 1)
    with pytest.raises(OutputOverwritesSourceError):
        uc.insert_pages.execute(pdf4, 1, other, insert_path=other)


# ------------------------------------------------------------------ recto-verso
def test_interleave_reversed_backs(tmp_path):
    fronts = make_pdf(tmp_path / "f.pdf", 3, base_width=100)  # 110,120,130
    backs = make_pdf(tmp_path / "b.pdf", 3, base_width=500)  # 510,520,530 (lus à l'envers)
    out = uc.interleave_pdfs.execute(fronts, backs, str(tmp_path / "o.pdf"), backs_reversed=True)
    assert widths(out) == [110, 530, 120, 520, 130, 510]


def test_interleave_straight_backs_and_missing_last_back(tmp_path):
    fronts = make_pdf(tmp_path / "f.pdf", 3, base_width=100)
    backs = make_pdf(tmp_path / "b.pdf", 2, base_width=500)  # dernier verso vierge non scanné
    out = uc.interleave_pdfs.execute(fronts, backs, str(tmp_path / "o.pdf"), backs_reversed=False)
    assert widths(out) == [110, 510, 120, 520, 130]


def test_interleave_rejects_mismatched_counts_and_same_file(tmp_path):
    fronts = make_pdf(tmp_path / "f.pdf", 5)
    backs = make_pdf(tmp_path / "b.pdf", 2)
    with pytest.raises(PageCountMismatchError, match="5 page"):
        uc.interleave_pdfs.validate(fronts, backs)
    with pytest.raises(InvalidOptionError):
        uc.interleave_pdfs.validate(fronts, fronts)


# ------------------------------------------------------------------ rogner
def box(path, index=0):
    page = PdfReader(str(path)).pages[index]
    return [round(float(v), 1) for v in (page.cropbox.left, page.cropbox.bottom, page.cropbox.right, page.cropbox.top)]


def test_crop_selected_pages_only(pdf4, tmp_path):
    out = uc.crop_pages.execute(pdf4, "2", CropMargins(top=10, left=10), str(tmp_path / "o.pdf"))
    assert box(out, 0) == [0, 0, 110, 300]  # intacte
    # 10 mm = 28,35 pt
    assert box(out, 1) == [28.3, 0, 120, 271.7]


def test_crop_all_pages_by_default(pdf4, tmp_path):
    out = uc.crop_pages.execute(pdf4, "", CropMargins(bottom=10), str(tmp_path / "o.pdf"))
    assert all(box(out, i)[1] == 28.3 for i in range(4))


def test_crop_follows_screen_orientation_on_rotated_pages(tmp_path):
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=400).rotate(90)
    path = tmp_path / "r.pdf"
    writer.write(path)
    # Page tournée de 90° (sens horaire) : le « haut » vu à l'écran est le côté GAUCHE du plan PDF.
    out = uc.crop_pages.execute(str(path), "", CropMargins(top=25.4), str(tmp_path / "o.pdf"))
    assert box(out) == [72.0, 0, 200, 400]


def test_crop_that_empties_a_page_is_refused_without_output(pdf4, tmp_path):
    with pytest.raises(InvalidCropError):
        uc.crop_pages.execute(pdf4, "", CropMargins(left=30, right=30), str(tmp_path / "o.pdf"))
    assert not (tmp_path / "o.pdf").exists()
