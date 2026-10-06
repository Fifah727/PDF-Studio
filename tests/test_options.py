"""Objets-valeur des options : validations et conversions."""

import pytest

from app.domain.exceptions import (
    InvalidBookmarksError,
    InvalidOptionError,
    UnsupportedTextError,
)
from app.domain.options import (
    BatchPlan,
    Bookmark,
    CompressionResult,
    CropMargins,
    ImageStamp,
    PageNumbering,
    PdfMetadata,
    Position,
    TextWatermark,
    format_bookmarks,
    parse_bookmarks,
)


def test_watermark_accepts_french_and_malagasy_letters():
    assert TextWatermark("  Très   confidentiel – ñô ").text == "Très confidentiel – ñô"


@pytest.mark.parametrize("text", ["", "   ", "x" * 61])
def test_watermark_rejects_empty_or_long(text):
    with pytest.raises(InvalidOptionError):
        TextWatermark(text)


def test_watermark_rejects_unsupported_scripts():
    with pytest.raises(UnsupportedTextError, match="Caractères non pris en charge"):
        TextWatermark("Привет")


@pytest.mark.parametrize("field,value", [("opacity", 0.0), ("opacity", 1.5), ("angle", 120), ("scale", 0.05)])
def test_watermark_bounds(field, value):
    with pytest.raises(InvalidOptionError):
        TextWatermark("OK", **{field: value})


def test_numbering_needs_placeholder_and_renders():
    with pytest.raises(InvalidOptionError, match=r"\{n\}"):
        PageNumbering("Page")
    numbering = PageNumbering("Page {n} sur {total}", start=5)
    assert numbering.render(7, 12) == "Page 7 sur 12"


def test_crop_margins_require_something_and_convert_mm():
    with pytest.raises(InvalidOptionError):
        CropMargins()
    with pytest.raises(InvalidOptionError):
        CropMargins(top=-1)
    top, bottom, left, right = CropMargins(top=25.4, left=10).in_points()
    assert round(top, 2) == 72.0 and bottom == 0 and round(left, 2) == 28.35 and right == 0


def test_image_stamp_bounds():
    ImageStamp()
    with pytest.raises(InvalidOptionError):
        ImageStamp(width_fraction=2)
    with pytest.raises(InvalidOptionError):
        ImageStamp(opacity=0)


def test_position_axes():
    assert (Position.TOP_RIGHT.horizontal, Position.TOP_RIGHT.vertical) == ("right", "top")
    assert (Position.CENTER.horizontal, Position.CENTER.vertical) == ("center", "middle")
    assert (Position.MIDDLE_LEFT.horizontal, Position.MIDDLE_LEFT.vertical) == ("left", "middle")
    assert (Position.BOTTOM_CENTER.horizontal, Position.BOTTOM_CENTER.vertical) == ("center", "bottom")


def test_parse_bookmarks_levels_and_roundtrip():
    text = "1: Introduction\n- 3: Contexte\n-- 4: Détail\n\n5: Conclusion"
    parsed = parse_bookmarks(text, total_pages=6)
    assert [(b.title, b.page, b.level) for b in parsed] == [
        ("Introduction", 1, 0), ("Contexte", 3, 1), ("Détail", 4, 2), ("Conclusion", 5, 0),
    ]
    assert parse_bookmarks(format_bookmarks(parsed), 6) == parsed
    assert parse_bookmarks("", 6) == [] and parse_bookmarks(None) == []


@pytest.mark.parametrize(
    "text,expect",
    [
        ("Introduction", "Ligne 1 invalide"),
        ("1: A\n3: ", "Ligne 2 invalide"),
        ("1: A\n9: B", "page 9 n'existe pas"),
        ("-- 1: Trop profond", "sous-signet"),
        ("1: A\n--- 2: B", "sous-signet"),
    ],
)
def test_parse_bookmarks_errors(text, expect):
    with pytest.raises(InvalidBookmarksError, match=expect):
        parse_bookmarks(text, total_pages=5)


def test_bookmark_validates_itself():
    with pytest.raises(InvalidBookmarksError):
        Bookmark("  ", 1)
    with pytest.raises(InvalidBookmarksError):
        Bookmark("A", 0)


def test_compression_result_ratio():
    from pathlib import Path

    better = CompressionResult(Path("x"), 1000, 250)
    assert better.improved and better.saved_ratio == 0.75
    same = CompressionResult(Path("x"), 1000, 1000)
    assert not same.improved and same.saved_ratio == 0.0


def test_batch_plan_needs_a_step_and_orders_them():
    with pytest.raises(InvalidOptionError):
        BatchPlan()
    plan = BatchPlan(password="x", clear_metadata=True, numbering=PageNumbering("{n}"))
    assert plan.steps == ("numbering", "metadata", "password")


def test_pdf_metadata_cleaned_and_empty():
    assert PdfMetadata(title="  T ").cleaned().title == "T"
    assert PdfMetadata().is_empty and not PdfMetadata(author="A").is_empty
