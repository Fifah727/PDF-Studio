import pytest
from PIL import Image
from pypdf import PdfReader

from app.domain.exceptions import InvalidImageError
from app.presentation.di import build_use_cases

uc = build_use_cases()


def size(path, i=0):
    box = PdfReader(str(path)).pages[i].mediabox
    return round(float(box.width)), round(float(box.height))


def test_fit_a4_portrait_and_landscape(tmp_path):
    Image.new("RGB", (800, 1200), "red").save(tmp_path / "p.png")
    Image.new("RGB", (3000, 1000), "blue").save(tmp_path / "l.jpg")
    out = uc.images_to_pdf.execute(
        [str(tmp_path / "p.png"), str(tmp_path / "l.jpg")], str(tmp_path / "o.pdf")
    )
    assert size(out, 0) == (595, 842)
    assert size(out, 1) == (842, 595)


def test_original_size_mode(tmp_path):
    Image.new("RGB", (1500, 750), "green").save(tmp_path / "a.png")
    out = uc.images_to_pdf.execute(
        [str(tmp_path / "a.png")], str(tmp_path / "o.pdf"), fit_a4=False
    )
    assert size(out) == (720, 360)  # 150 ppp


def test_exif_orientation_is_applied(tmp_path):
    img = Image.new("RGB", (1000, 500), "white")  # paysage brut
    exif = Image.Exif()
    exif[0x0112] = 6  # à pivoter de 90° -> portrait
    img.save(tmp_path / "photo.jpg", exif=exif)
    out = uc.images_to_pdf.execute([str(tmp_path / "photo.jpg")], str(tmp_path / "o.pdf"))
    assert size(out) == (595, 842)


def test_transparent_png_gets_white_background(tmp_path):
    Image.new("RGBA", (50, 50), (0, 0, 0, 0)).save(tmp_path / "t.png")
    out = uc.images_to_pdf.execute(
        [str(tmp_path / "t.png")], str(tmp_path / "o.pdf"), fit_a4=False
    )
    from pypdf import PdfReader as R

    assert R(str(out)).pages[0].images[0].image.getpixel((5, 5))[:3] == (255, 255, 255)


def test_bad_image(tmp_path):
    (tmp_path / "x.png").write_bytes(b"not an image")
    with pytest.raises(InvalidImageError):
        uc.images_to_pdf.execute([str(tmp_path / "x.png")], str(tmp_path / "o.pdf"))
    assert not list(tmp_path.glob("*.pdf")) and not list(tmp_path.glob(".*.part"))
