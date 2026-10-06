"""Filigrane, numérotation, image/signature : on lit le contenu réellement écrit."""

import pytest
from PIL import Image, ImageDraw
from pypdf import PdfReader, PdfWriter

from app.domain.exceptions import (
    InvalidImageError,
    InvalidOptionError,
    OutputOverwritesSourceError,
    PageRangeError,
)
from app.domain.options import ImageStamp, PageNumbering, Position, StampColor, TextWatermark
from app.presentation.di import build_use_cases
from tests.helpers import make_pdf

uc = build_use_cases()


def page_text(path, index=0) -> str:
    return PdfReader(str(path)).pages[index].extract_text()


def raw_content(path, index=0) -> bytes:
    page = PdfReader(str(path)).pages[index]
    return page.get_contents().get_data()


def rotated_pdf(tmp_path, angle=90, width=300, height=400):
    writer = PdfWriter()
    writer.add_blank_page(width=width, height=height).rotate(angle)
    path = tmp_path / f"rot{angle}.pdf"
    writer.write(path)
    return str(path)


@pytest.fixture
def pdf3(tmp_path):
    return make_pdf(tmp_path / "a.pdf", 3)


# ------------------------------------------------------------------ filigrane texte
def test_watermark_text_is_written_on_every_page_by_default(pdf3, tmp_path):
    out = uc.watermark_text.execute(pdf3, TextWatermark("CONFIDENTIEL"), "", str(tmp_path / "o.pdf"))
    assert [page_text(out, i).strip() for i in range(3)] == ["CONFIDENTIEL"] * 3


def test_watermark_only_on_selected_pages(pdf3, tmp_path):
    out = uc.watermark_text.execute(pdf3, TextWatermark("COPIE"), "2", str(tmp_path / "o.pdf"))
    assert [bool(page_text(out, i).strip()) for i in range(3)] == [False, True, False]


def test_watermark_keeps_page_size_and_original_content(tmp_path):
    from tests.helpers import make_text_pdf

    src = make_text_pdf(tmp_path / "t.pdf", ["Bonjour"])
    out = uc.watermark_text.execute(src, TextWatermark("BROUILLON"), "", str(tmp_path / "o.pdf"))
    text = page_text(out)
    assert "Bonjour" in text and "BROUILLON" in text
    box = PdfReader(str(out)).pages[0].mediabox
    assert (float(box.width), float(box.height)) == (300.0, 300.0)


def test_watermark_has_transparency_and_color(pdf3, tmp_path):
    out = uc.watermark_text.execute(
        pdf3, TextWatermark("X", color=StampColor.RED, opacity=0.4), "1", str(tmp_path / "o.pdf")
    )
    page = PdfReader(str(out)).pages[0]
    state = page["/Resources"]["/ExtGState"]
    assert any(abs(float(gs["/ca"]) - 0.4) < 1e-6 for gs in (v.get_object() for v in state.values()))
    assert b"0.78 0.1 0.1 rg" in raw_content(out)


def test_watermark_accents_survive_winansi_encoding(pdf3, tmp_path):
    out = uc.watermark_text.execute(pdf3, TextWatermark("Très secret – ñô"), "1", str(tmp_path / "o.pdf"))
    assert "Très secret" in page_text(out)


def test_watermark_rejects_overwrite_and_bad_pages(pdf3, tmp_path):
    with pytest.raises(OutputOverwritesSourceError):
        uc.watermark_text.execute(pdf3, TextWatermark("X"), "", pdf3)
    with pytest.raises(PageRangeError):
        uc.watermark_text.execute(pdf3, TextWatermark("X"), "9", str(tmp_path / "o.pdf"))


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_watermark_on_rotated_pages_is_not_clipped(tmp_path, rotation):
    src = rotated_pdf(tmp_path, rotation)
    out = uc.watermark_text.execute(src, TextWatermark("CONFIDENTIEL"), "", str(tmp_path / "o.pdf"))
    assert page_text(out).strip()
    page = PdfReader(str(out)).pages[0]
    assert (page.rotation or 0) == rotation  # la rotation d'origine est conservée


# ------------------------------------------------------------------ numérotation
def test_numbering_all_pages_with_total(pdf3, tmp_path):
    out = uc.number_pages.execute(pdf3, PageNumbering("Page {n} sur {total}"), "", str(tmp_path / "o.pdf"))
    assert [page_text(out, i).strip() for i in range(3)] == [
        "Page 1 sur 3", "Page 2 sur 3", "Page 3 sur 3",
    ]


def test_numbering_custom_start(pdf3, tmp_path):
    out = uc.number_pages.execute(pdf3, PageNumbering("{n}", start=10), "", str(tmp_path / "o.pdf"))
    assert [page_text(out, i).strip() for i in range(3)] == ["10", "11", "12"]


def test_numbering_selected_pages_start_counting_at_first_selected(pdf3, tmp_path):
    out = uc.number_pages.execute(pdf3, PageNumbering("{n}"), "2-3", str(tmp_path / "o.pdf"))
    assert [page_text(out, i).strip() for i in range(3)] == ["", "1", "2"]


def test_numbering_special_characters_are_escaped(pdf3, tmp_path):
    out = uc.number_pages.execute(pdf3, PageNumbering("(p. {n})"), "1", str(tmp_path / "o.pdf"))
    assert page_text(out).strip() == "(p. 1)"


@pytest.mark.parametrize("position", list(Position))
def test_numbering_every_position_is_inside_the_page(tmp_path, position):
    src = rotated_pdf(tmp_path, 0, 300, 400)
    out = uc.number_pages.execute(src, PageNumbering("{n}", position=position), "", str(tmp_path / "o.pdf"))
    assert page_text(out).strip() == "1"


def test_numbering_placement_matches_screen_orientation(tmp_path):
    def positions(path):
        found = []
        PdfReader(str(path)).pages[0].extract_text(
            visitor_text=lambda t, cm, tm, fd, fs: found.append((tm[4], tm[5])) if t.strip() else None
        )
        return found

    flat = rotated_pdf(tmp_path, 0, 300, 400)
    out = uc.number_pages.execute(flat, PageNumbering("{n}", position=Position.BOTTOM_RIGHT), "", str(tmp_path / "o.pdf"))
    (x, y), = positions(out)
    assert x > 250 and y < 60  # en bas à droite d'une page 300 x 400


# ------------------------------------------------------------------ image / signature
@pytest.fixture
def signature(tmp_path):
    image = Image.new("RGB", (600, 200), "white")  # photo de signature : fond blanc opaque
    ImageDraw.Draw(image).line([(20, 150), (300, 30), (580, 120)], fill=(20, 40, 160), width=10)
    path = tmp_path / "sig.png"
    image.save(path)
    return str(path)


def xobject_images(path, index=0):
    page = PdfReader(str(path)).pages[index]
    xobjects = page["/Resources"].get("/XObject", {})
    return [x.get_object() for x in xobjects.values() if x.get_object().get("/Subtype") == "/Image"]


def test_signature_defaults_to_last_page_only(pdf3, signature, tmp_path):
    out = uc.sign_pdf.execute(pdf3, signature, ImageStamp(remove_white_background=True), "", str(tmp_path / "o.pdf"))
    assert [len(xobject_images(out, i)) for i in range(3)] == [0, 0, 1]


def test_image_watermark_defaults_to_all_pages(pdf3, signature, tmp_path):
    out = uc.stamp_image.execute(pdf3, signature, ImageStamp(opacity=0.3), "", str(tmp_path / "o.pdf"))
    assert [len(xobject_images(out, i)) for i in range(3)] == [1, 1, 1]


def test_signature_white_background_becomes_transparent(pdf3, signature, tmp_path):
    out = uc.sign_pdf.execute(pdf3, signature, ImageStamp(remove_white_background=True), "3", str(tmp_path / "o.pdf"))
    (image,) = xobject_images(out, 2)
    assert "/SMask" in image
    alpha = image["/SMask"].get_object().get_data()
    assert min(alpha) == 0 and max(alpha) == 255  # fond transparent ET trait opaque


def test_png_transparency_is_preserved_without_white_removal(pdf3, tmp_path):
    logo = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    ImageDraw.Draw(logo).ellipse((20, 20, 180, 180), fill=(200, 30, 30, 255))
    logo.save(tmp_path / "logo.png")
    out = uc.stamp_image.execute(pdf3, str(tmp_path / "logo.png"), ImageStamp(), "1", str(tmp_path / "o.pdf"))
    alpha = xobject_images(out)[0]["/SMask"].get_object().get_data()
    assert min(alpha) == 0 and max(alpha) == 255


def test_stamp_image_errors(pdf3, signature, tmp_path):
    with pytest.raises(InvalidOptionError):
        ImageStamp(width_fraction=0)
    blank = tmp_path / "blank.png"
    Image.new("RGBA", (50, 50), (0, 0, 0, 0)).save(blank)
    with pytest.raises(InvalidImageError, match="transparente"):
        uc.stamp_image.execute(pdf3, str(blank), ImageStamp(), "", str(tmp_path / "o.pdf"))
    with pytest.raises(InvalidImageError):
        uc.stamp_image.execute(pdf3, str(tmp_path / "absent.png"), ImageStamp(), "", str(tmp_path / "o.pdf"))
    with pytest.raises(OutputOverwritesSourceError):
        uc.stamp_image.execute(pdf3, signature, ImageStamp(), "", signature)


def test_tall_image_is_fitted_inside_the_page(tmp_path, pdf3):
    tall = tmp_path / "tall.png"
    Image.new("RGB", (100, 3000), (10, 10, 10)).save(tall)
    out = uc.stamp_image.execute(pdf3, str(tall), ImageStamp(width_fraction=1.0, margin=0), "1", str(tmp_path / "o.pdf"))
    assert len(xobject_images(out, 0)) == 1
