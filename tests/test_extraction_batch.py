"""Extraction d'images / de texte, traitement par lot, historique des fichiers."""

import zipfile
from datetime import datetime, timedelta, timezone

import pytest
from PIL import Image
from pypdf import PdfReader

from app.domain.exceptions import InsufficientFilesError, NoContentError, PdfError
from app.domain.options import BatchPlan, CompressionLevel, PageNumbering, TextWatermark
from app.infrastructure.recent_files_store import MAX_RECENT_FILES, JsonRecentFilesStore
from app.presentation.di import build_use_cases
from app.presentation.screens.batch_screen import batch_message
from tests.helpers import make_pdf, make_photo_pdf, make_text_pdf

uc = build_use_cases()


# ------------------------------------------------------------------ images
def test_extract_images_into_zip(tmp_path):
    src = make_photo_pdf(tmp_path / "photo.pdf", (800, 600))
    result = uc.extract_images.execute(src, str(tmp_path / "o.zip"))
    assert result.items == 1
    with zipfile.ZipFile(result.path) as archive:
        (name,) = archive.namelist()
        assert name.startswith("page_1_image_01")
        archive.extract(name, tmp_path)
    assert Image.open(tmp_path / name).size == (800, 600)


def test_extract_images_skips_repeated_logo(tmp_path):
    # Le même objet image sur 3 pages ne doit sortir qu'une fois.
    from pypdf import PdfWriter

    Image.new("RGB", (200, 200), (200, 30, 30)).save(tmp_path / "logo.png")
    base = PdfWriter()
    for _ in range(3):
        base.add_blank_page(width=300, height=300)
    base.write(tmp_path / "base.pdf")
    stamped = uc.stamp_image.execute(
        str(tmp_path / "base.pdf"), str(tmp_path / "logo.png"),
        __import__("app.domain.options", fromlist=["ImageStamp"]).ImageStamp(), "", str(tmp_path / "s.pdf"),
    )
    result = uc.extract_images.execute(str(stamped), str(tmp_path / "o.zip"))
    assert result.items >= 1
    with zipfile.ZipFile(result.path) as archive:
        assert len(archive.namelist()) == result.items


def test_extract_images_without_images_is_reported_and_leaves_no_file(tmp_path):
    src = make_pdf(tmp_path / "plain.pdf", 2)
    with pytest.raises(NoContentError, match="Aucune image"):
        uc.extract_images.execute(src, str(tmp_path / "o.zip"))
    assert not (tmp_path / "o.zip").exists()
    assert not any(p.name.endswith(".part") for p in tmp_path.iterdir())


# ------------------------------------------------------------------ texte
def test_extract_text_with_page_markers(tmp_path):
    src = make_text_pdf(tmp_path / "t.pdf", ["Premiere page", "Deuxieme page"])
    result = uc.extract_text.execute(src, str(tmp_path / "o.txt"))
    content = (tmp_path / "o.txt").read_text("utf-8")
    assert result.items == 2
    assert "--- Page 1 ---\nPremiere page" in content and "--- Page 2 ---\nDeuxieme page" in content


def test_extract_text_without_markers(tmp_path):
    src = make_text_pdf(tmp_path / "t.pdf", ["Alpha", "Beta"])
    uc.extract_text.execute(src, str(tmp_path / "o.txt"), page_markers=False)
    assert (tmp_path / "o.txt").read_text("utf-8").split() == ["Alpha", "Beta"]


def test_extract_text_of_a_scan_explains_why(tmp_path):
    src = make_photo_pdf(tmp_path / "scan.pdf")
    with pytest.raises(NoContentError, match="scan"):
        uc.extract_text.execute(src, str(tmp_path / "o.txt"))
    assert not (tmp_path / "o.txt").exists()


# ------------------------------------------------------------------ lot
def test_batch_applies_every_step_to_every_file(tmp_path):
    a = make_text_pdf(tmp_path / "a.pdf", ["Un", "Deux"])
    b = make_text_pdf(tmp_path / "b.pdf", ["Trois"])
    plan = BatchPlan(
        numbering=PageNumbering("n{n}"), watermark=TextWatermark("COPIE"),
        compression=CompressionLevel.LIGHT, clear_metadata=True, password="secret",
    )
    result = uc.batch.execute([a, b], plan, str(tmp_path / "lot.zip"))
    assert result.processed == 2 and result.failures == ()
    with zipfile.ZipFile(result.path) as archive:
        assert sorted(archive.namelist()) == ["a_traite.pdf", "b_traite.pdf"]
        archive.extractall(tmp_path / "out")
    reader = PdfReader(str(tmp_path / "out" / "a_traite.pdf"))
    assert reader.is_encrypted and reader.decrypt("secret")
    text = reader.pages[0].extract_text()
    assert "Un" in text and "COPIE" in text and "n1" in text
    assert len(reader.pages) == 2


def test_batch_continues_after_a_bad_file_and_reports_it(tmp_path):
    good = make_pdf(tmp_path / "good.pdf", 1)
    locked = tmp_path / "locked.pdf"
    uc.protect_pdf.execute(good, "pw", str(locked))
    plan = BatchPlan(numbering=PageNumbering("{n}"))
    result = uc.batch.execute([str(locked), good], plan, str(tmp_path / "lot.zip"))
    assert result.processed == 1
    assert [name for name, _ in result.failures] == ["locked.pdf"]
    assert "protégé" in result.failures[0][1]
    assert "1 PDF traité" in batch_message(result, result.path) and "locked.pdf" in batch_message(result, result.path)


def test_batch_with_only_failures_raises_and_writes_nothing(tmp_path):
    locked = tmp_path / "locked.pdf"
    uc.protect_pdf.execute(make_pdf(tmp_path / "g.pdf", 1), "pw", str(locked))
    with pytest.raises(PdfError, match="Aucun fichier n'a pu être traité"):
        uc.batch.execute([str(locked)], BatchPlan(clear_metadata=True), str(tmp_path / "lot.zip"))
    assert not (tmp_path / "lot.zip").exists()


def test_batch_disambiguates_same_names_and_refuses_empty_or_overwrite(tmp_path):
    (tmp_path / "x").mkdir(); (tmp_path / "y").mkdir()
    a = make_pdf(tmp_path / "x" / "doc.pdf", 1)
    b = make_pdf(tmp_path / "y" / "doc.pdf", 1)
    result = uc.batch.execute([a, b], BatchPlan(clear_metadata=True), str(tmp_path / "lot.zip"))
    with zipfile.ZipFile(result.path) as archive:
        assert sorted(archive.namelist()) == ["doc_traite.pdf", "doc_traite_2.pdf"]
    with pytest.raises(InsufficientFilesError):
        uc.batch.execute([], BatchPlan(clear_metadata=True), str(tmp_path / "e.zip"))
    from app.domain.exceptions import OutputOverwritesSourceError
    with pytest.raises(OutputOverwritesSourceError):
        uc.batch.execute([a], BatchPlan(clear_metadata=True), a)


def test_batch_cleans_up_its_temporary_files(tmp_path, monkeypatch):
    import tempfile
    from pathlib import Path

    created = []
    real = tempfile.TemporaryDirectory

    class Spy(real):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            created.append(Path(self.name))

    monkeypatch.setattr("app.application.batch.tempfile.TemporaryDirectory", Spy)
    uc.batch.execute([make_pdf(tmp_path / "a.pdf", 1)], BatchPlan(clear_metadata=True), str(tmp_path / "lot.zip"))
    assert created and not created[0].exists()


# ------------------------------------------------------------------ historique
def test_recent_files_most_recent_first_without_duplicates(tmp_path):
    store = JsonRecentFilesStore(tmp_path / "recents.json")
    store.add("/a.pdf", "PDF créé")
    store.add("/b.pdf", "PDF pivoté créé")
    store.add("/a.pdf", "PDF compressé")
    assert [(i.path, i.label) for i in store.items] == [("/a.pdf", "PDF compressé"), ("/b.pdf", "PDF pivoté créé")]


def test_recent_files_are_capped_and_persisted(tmp_path):
    path = tmp_path / "recents.json"
    store = JsonRecentFilesStore(path)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for n in range(MAX_RECENT_FILES + 4):
        store.add(f"/f{n}.pdf", "ok", base + timedelta(minutes=n))
    assert len(store.items) == MAX_RECENT_FILES
    reloaded = JsonRecentFilesStore(path)
    assert [i.path for i in reloaded.items] == [i.path for i in store.items]
    assert reloaded.items[0].path == f"/f{MAX_RECENT_FILES + 3}.pdf"
    reloaded.clear()
    assert JsonRecentFilesStore(path).items == []


def test_recent_files_survive_corrupt_or_partial_files(tmp_path):
    path = tmp_path / "recents.json"
    path.write_text("{pas du json", "utf-8")
    assert JsonRecentFilesStore(path).items == []
    path.write_text('[{"path": "/ok.pdf", "label": "ok", "created_at": "2026-01-01T10:00:00"}, {"bad": 1}, 7]', "utf-8")
    items = JsonRecentFilesStore(path).items
    assert [i.path for i in items] == ["/ok.pdf"] and items[0].created_at.tzinfo is not None
