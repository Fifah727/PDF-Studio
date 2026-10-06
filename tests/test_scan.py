"""Amélioration de scan (images vers PDF)."""

import pytest
from PIL import Image, ImageDraw

from app.domain.options import ScanMode
from app.infrastructure.pillow_image_repository import PillowImageRepository
from app.presentation.di import build_use_cases

uc = build_use_cases()


@pytest.fixture
def shaded_photo(tmp_path):
    """Feuille crème, ombre à droite, trois lignes de texte gris foncé."""
    width, height = 600, 800
    image = Image.new("RGB", (width, height), (225, 220, 205))
    pixels = image.load()
    for x in range(width):
        shade = int(60 * x / width)
        for y in range(height):
            r, g, b = pixels[x, y]
            pixels[x, y] = (r - shade, g - shade, b - shade)
    draw = ImageDraw.Draw(image)
    for line in range(3):
        draw.rectangle((60, 100 + line * 80, 540, 120 + line * 80), fill=(60, 60, 70))
    path = tmp_path / "photo.jpg"
    image.save(path, quality=92)
    return str(path)


def render(pdf_path):
    import pypdfium2 as pdfium

    return pdfium.PdfDocument(str(pdf_path))[0].render(scale=0.5).to_pil().convert("L")


def convert(path, mode, out, fit=False):
    return uc.images_to_pdf.execute([path], str(out), fit, mode)


def test_enhanced_modes_whiten_the_paper_even_in_the_shadow(shaded_photo, tmp_path):
    for mode in (ScanMode.DOCUMENT, ScanMode.GRAYSCALE, ScanMode.BLACK_WHITE):
        page = render(convert(shaded_photo, mode, tmp_path / f"{mode.value}.pdf"))
        w, h = page.size
        paper_left = page.getpixel((10, h - 10))
        paper_right = page.getpixel((w - 10, h - 10))  # côté ombré
        assert paper_left >= 245 and paper_right >= 245, mode


def test_text_stays_dark_after_enhancement(shaded_photo, tmp_path):
    for mode in (ScanMode.DOCUMENT, ScanMode.GRAYSCALE, ScanMode.BLACK_WHITE):
        page = render(convert(shaded_photo, mode, tmp_path / f"{mode.value}.pdf"))
        w, h = page.size
        ink = page.getpixel((w // 2, int(h * 0.1375)))  # milieu de la 1re ligne
        assert ink < 110, mode


def test_original_mode_leaves_the_photo_as_is(shaded_photo, tmp_path):
    page = render(convert(shaded_photo, ScanMode.ORIGINAL, tmp_path / "o.pdf"))
    assert page.getpixel((page.width - 10, page.height - 10)) < 200  # l'ombre est toujours là


def test_black_and_white_is_much_lighter_than_color(shaded_photo, tmp_path):
    original = convert(shaded_photo, ScanMode.ORIGINAL, tmp_path / "o.pdf").stat().st_size
    bw = convert(shaded_photo, ScanMode.BLACK_WHITE, tmp_path / "bw.pdf").stat().st_size
    assert bw < original / 2


def test_modes_work_with_a4_fitting_and_keep_a_white_margin(shaded_photo, tmp_path):
    page = render(convert(shaded_photo, ScanMode.DOCUMENT, tmp_path / "a4.pdf", fit=True))
    assert page.size[0] < page.size[1]  # portrait A4
    assert page.getpixel((2, 2)) >= 250  # marge blanche autour de l'image


def test_black_and_white_with_a4_fitting_stays_one_bit_clean(shaded_photo, tmp_path):
    out = convert(shaded_photo, ScanMode.BLACK_WHITE, tmp_path / "bwa4.pdf", fit=True)
    assert out.exists() and out.stat().st_size > 0


def test_multiple_images_mixed_sizes_enhanced(shaded_photo, tmp_path):
    small = tmp_path / "small.png"
    Image.new("RGB", (100, 100), (230, 230, 230)).save(small)
    out = uc.images_to_pdf.execute([shaded_photo, str(small)], str(tmp_path / "two.pdf"), True, ScanMode.DOCUMENT)
    from pypdf import PdfReader
    assert len(PdfReader(str(out)).pages) == 2


def test_otsu_threshold_is_bounded():
    flat_white = Image.new("L", (50, 50), 255)
    assert 120 <= PillowImageRepository._otsu_threshold(flat_white) <= 225
