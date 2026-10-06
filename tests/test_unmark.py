"""Repérage et retrait des filigranes (texte, image, signature)."""

import pytest
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, TextStringObject

from app.domain.exceptions import (
    InvalidOptionError,
    NoWatermarkError,
    OutputOverwritesSourceError,
)
from app.domain.options import ImageStamp, PageNumbering, StampKind, TextWatermark
from app.presentation.di import build_use_cases
from tests.helpers import make_pdf, make_text_pdf

uc = build_use_cases()
ALL = list(StampKind)


@pytest.fixture
def logo(tmp_path):
    Image.new("RGB", (300, 100), (20, 40, 160)).save(tmp_path / "logo.png")
    return str(tmp_path / "logo.png")


@pytest.fixture
def stamped(tmp_path, logo):
    """2 pages de texte + filigrane texte, filigrane image, signature (dernière page), numéros."""
    src = make_text_pdf(tmp_path / "t.pdf", ["Bonjour", "Salama"])
    a = uc.watermark_text.execute(src, TextWatermark("CONFIDENTIEL"), "", str(tmp_path / "a.pdf"))
    b = uc.stamp_image.execute(str(a), logo, ImageStamp(), "", str(tmp_path / "b.pdf"))
    c = uc.sign_pdf.execute(str(b), logo, ImageStamp(), "", str(tmp_path / "c.pdf"))
    d = uc.number_pages.execute(str(c), PageNumbering("{n}"), "", str(tmp_path / "d.pdf"))
    return str(d)


def page_words(path, index=0):
    return PdfReader(str(path)).pages[index].extract_text().split()


def image_count(path, index=0):
    page = PdfReader(str(path)).pages[index]
    xobjects = page["/Resources"].get("/XObject", {})
    return sum(1 for x in xobjects.values() if x.get_object().get("/Subtype") == "/Image")


# ------------------------------------------------------------------ repérage
def test_scan_counts_each_kind_and_pages(stamped):
    report = uc.scan_watermarks.execute(stamped)
    assert report.count(StampKind.TEXT) == 2  # une fois par page
    assert report.count(StampKind.IMAGE) == 2
    assert report.count(StampKind.SIGNATURE) == 1  # dernière page seulement
    assert report.pages == 2 and report.total == 5
    assert report.kinds == (StampKind.TEXT, StampKind.IMAGE, StampKind.SIGNATURE)


def test_scan_of_clean_pdf_is_empty(tmp_path):
    report = uc.scan_watermarks.execute(make_pdf(tmp_path / "a.pdf", 2))
    assert report.total == 0 and report.kinds == () and report.pages == 0


def test_page_numbers_are_not_mistaken_for_watermarks(tmp_path):
    numbered = uc.number_pages.execute(make_pdf(tmp_path / "a.pdf", 2), PageNumbering("{n}"), "", str(tmp_path / "n.pdf"))
    assert uc.scan_watermarks.execute(str(numbered)).total == 0


# ------------------------------------------------------------------ retrait sélectif
def test_remove_only_the_text_watermark(stamped, tmp_path):
    result = uc.remove_watermarks.execute(stamped, [StampKind.TEXT], str(tmp_path / "o.pdf"))
    assert result.removed.count(StampKind.TEXT) == 2 and result.removed.total == 2
    assert "CONFIDENTIEL" not in PdfReader(str(result.path)).pages[0].extract_text()
    assert page_words(result.path) == ["Bonjour", "1"]
    after = uc.scan_watermarks.execute(str(result.path))
    assert after.count(StampKind.TEXT) == 0
    assert after.count(StampKind.IMAGE) == 2 and after.count(StampKind.SIGNATURE) == 1


def test_remove_only_the_signature_keeps_image_watermark(stamped, tmp_path):
    result = uc.remove_watermarks.execute(stamped, [StampKind.SIGNATURE], str(tmp_path / "o.pdf"))
    assert result.removed.total == 1
    assert image_count(result.path, 0) == 1 and image_count(result.path, 1) == 1  # filigrane image seul


def test_remove_everything_restores_the_original_content(stamped, tmp_path):
    result = uc.remove_watermarks.execute(stamped, ALL, str(tmp_path / "o.pdf"))
    assert result.removed.total == 5 and result.removed.pages == 2
    assert page_words(result.path, 0) == ["Bonjour", "1"] and page_words(result.path, 1) == ["Salama", "2"]
    assert image_count(result.path, 0) == 0 and image_count(result.path, 1) == 0
    assert uc.scan_watermarks.execute(str(result.path)).total == 0


def test_removal_shrinks_the_file_by_dropping_unused_resources(stamped, tmp_path):
    from pathlib import Path

    result = uc.remove_watermarks.execute(stamped, ALL, str(tmp_path / "o.pdf"))
    assert result.path.stat().st_size < Path(stamped).stat().st_size


def test_removal_keeps_rotation_and_page_size(tmp_path, logo):
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=300).rotate(90)
    writer.write(tmp_path / "r.pdf")
    stamped = uc.watermark_text.execute(str(tmp_path / "r.pdf"), TextWatermark("COPIE"), "", str(tmp_path / "s.pdf"))
    result = uc.remove_watermarks.execute(str(stamped), [StampKind.TEXT], str(tmp_path / "o.pdf"))
    page = PdfReader(str(result.path)).pages[0]
    assert (page.rotation, float(page.mediabox.width), float(page.mediabox.height)) == (90, 200.0, 300.0)


# ------------------------------------------------------------------ erreurs
def test_nothing_to_remove_is_explained_and_writes_nothing(tmp_path):
    src = make_pdf(tmp_path / "a.pdf", 2)
    with pytest.raises(NoWatermarkError, match="aplati|scan"):
        uc.remove_watermarks.execute(src, ALL, str(tmp_path / "o.pdf"))
    assert not (tmp_path / "o.pdf").exists()


def test_requested_kind_absent_is_reported_differently(stamped, tmp_path, logo):
    only_text = uc.watermark_text.execute(make_pdf(tmp_path / "p.pdf", 1), TextWatermark("X"), "", str(tmp_path / "x.pdf"))
    with pytest.raises(NoWatermarkError, match="type choisi"):
        uc.remove_watermarks.execute(str(only_text), [StampKind.SIGNATURE], str(tmp_path / "o.pdf"))


def test_no_kind_selected_and_overwrite_are_refused(stamped, tmp_path):
    with pytest.raises(InvalidOptionError):
        uc.remove_watermarks.execute(stamped, [], str(tmp_path / "o.pdf"))
    with pytest.raises(OutputOverwritesSourceError):
        uc.remove_watermarks.execute(stamped, ALL, stamped)


def test_image_stamp_cannot_claim_to_be_text():
    with pytest.raises(InvalidOptionError):
        ImageStamp(kind=StampKind.TEXT)


# ------------------------------------------------------------------ filigranes d'autres outils
def third_party_pdf(path, body: bytes, properties=None, layer_name=None):
    """PDF à une page de texte réel + un bloc marqué, comme le ferait un autre éditeur."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    resources = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
    if layer_name:
        layer = DictionaryObject({NameObject("/Type"): NameObject("/OCG"), NameObject("/Name"): TextStringObject(layer_name)})
        resources[NameObject("/Properties")] = DictionaryObject({NameObject("/MC0"): writer._add_object(layer)})
    page[NameObject("/Resources")] = resources
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 14 Tf 20 150 Td (Contenu reel) Tj ET\n" + body)
    page.replace_contents(stream)
    writer.write(path)
    return str(path)


MARK = b"BT /F1 40 Tf 50 50 Td (DRAFT) Tj ET\n"


def test_standard_artifact_watermark_from_another_tool(tmp_path):
    body = b"/Artifact <</Type /Pagination /Subtype /Watermark /Desc (Watermark)>> BDC\n" + MARK + b"EMC\n"
    src = third_party_pdf(tmp_path / "x.pdf", body)
    assert uc.scan_watermarks.execute(src).count(StampKind.TEXT) == 1  # classé « texte » d'après le contenu
    result = uc.remove_watermarks.execute(src, [StampKind.TEXT], str(tmp_path / "o.pdf"))
    assert page_words(result.path) == ["Contenu", "reel"]


def test_optional_content_layer_named_watermark(tmp_path):
    body = b"/OC /MC0 BDC\n" + MARK + b"EMC\n"
    src = third_party_pdf(tmp_path / "x.pdf", body, layer_name="Watermark")
    assert uc.scan_watermarks.execute(src).total == 1
    result = uc.remove_watermarks.execute(src, ALL, str(tmp_path / "o.pdf"))
    assert page_words(result.path) == ["Contenu", "reel"]


def test_other_optional_content_layers_are_left_alone(tmp_path):
    body = b"/OC /MC0 BDC\n" + MARK + b"EMC\n"
    src = third_party_pdf(tmp_path / "x.pdf", body, layer_name="Calque cotes")
    assert uc.scan_watermarks.execute(src).total == 0


def test_ordinary_marked_content_is_not_a_watermark(tmp_path):
    body = b"/Artifact <</Type /Pagination /Subtype /Footer>> BDC\n" + MARK + b"EMC\n"
    assert uc.scan_watermarks.execute(third_party_pdf(tmp_path / "x.pdf", body)).total == 0


def test_nested_watermarks_are_counted_and_removed_once(tmp_path):
    body = (b"/Artifact <</Subtype /Watermark>> BDC\n/Artifact <</Subtype /Watermark>> BDC\n"
            + MARK + b"EMC\nEMC\n")
    src = third_party_pdf(tmp_path / "x.pdf", body)
    assert uc.scan_watermarks.execute(src).total == 1
    result = uc.remove_watermarks.execute(src, ALL, str(tmp_path / "o.pdf"))
    assert page_words(result.path) == ["Contenu", "reel"] and PdfReader(str(result.path)).pages[0].get_contents().get_data().count(b"BDC") == 0


def test_flattened_watermark_is_not_detected(tmp_path):
    """Texte « filigrane » écrit comme du contenu ordinaire : indiscernable, donc laissé."""
    src = third_party_pdf(tmp_path / "x.pdf", MARK)
    assert uc.scan_watermarks.execute(src).total == 0
