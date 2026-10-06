import pytest

from app.application.files import suggest_name, with_extension
from app.domain.exceptions import PageRangeError
from app.domain.models import PageRange, PageSelection


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("mon rapport", "mon rapport.pdf"),
        ("scan.v2", "scan.v2.pdf"),
        ("Bilan.PDF", "Bilan.PDF"),
        ("bilan.", "bilan.pdf"),
        ("  x  ", "x.pdf"),
        ("extrait.pdf", "extrait.pdf"),
    ],
)
def test_with_extension(raw, expected):
    assert with_extension(raw, ".pdf") == expected


def test_suggest_name():
    assert suggest_name("/a/b/rapport.pdf", "_extrait") == "rapport_extrait.pdf"
    assert suggest_name("/a/b/rapport.pdf", "_pages", ".zip") == "rapport_pages.zip"


def test_page_range_invalid():
    with pytest.raises(PageRangeError):
        PageRange(0, 3)
    with pytest.raises(PageRangeError):
        PageRange(5, 2)


def test_selection_parse_and_order():
    assert PageSelection.parse("1-3, 5, 8-9").pages(10) == [1, 2, 3, 5, 8, 9]
    assert PageSelection.parse("5,1-2").pages(10) == [5, 1, 2]  # ordre saisi conservé
    assert PageSelection.parse("1-3,2-4").pages(10) == [1, 2, 3, 4]  # doublons ignorés
    assert PageSelection.parse("1,,2;3,").pages(5) == [1, 2, 3]


@pytest.mark.parametrize("bad", ["", "  ", None, "a", "1-", "-3", "1--3", "3-1", "0"])
def test_selection_invalid(bad):
    with pytest.raises(PageRangeError):
        PageSelection.parse(bad)


def test_selection_out_of_bounds():
    with pytest.raises(PageRangeError, match="3 page"):
        PageSelection.parse("2-9").pages(3)
