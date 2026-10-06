"""Écrans des nouveaux outils : on pilote les gestionnaires comme le ferait l'utilisateur."""

import asyncio
import zipfile

import flet as ft
import pytest
from PIL import Image
from pypdf import PdfReader

from app.infrastructure.json_settings_store import JsonSettingsStore
from app.infrastructure.recent_files_store import JsonRecentFilesStore
from app.presentation.router import TOOL_SCREENS
from app.presentation.screens.base import FilePickerService
from app.presentation.screens.home_screen import TOOLS, build_home
from app.presentation.widgets.file_list import FileList
from app.presentation.widgets.file_tray import FileTray
from app.presentation.widgets.page_order import MAX_LISTED_PAGES, PageOrderList
from tests.helpers import make_pdf, make_photo_pdf, make_text_pdf, widths
from tests.test_ui import (  # noqa: F401  (les fixtures `env` et `_reset_palette` sont réutilisées)
    FakeFilePicker,
    FakePage,
    _call,
    _reset_palette,
    click,
    env,
    find,
    walk,
)


def build(env, route):
    return TOOL_SCREENS[route](env.page, env.uc, env.picker, env.notify)


def trays(view):
    return [c for c in walk(view) if isinstance(c, FileTray)]


def run(handler):
    asyncio.run(_call(handler))


def pick(view, path, index=0):
    """Choisit ``path`` dans le ``index``-ième emplacement de fichier de l'écran."""
    FakeFilePicker.picked = [path]
    run(trays(view)[index].pick_button.on_click)


def button(view, label):
    return find(view, (ft.Button, ft.OutlinedButton), label)


def last_note(env):
    return env.notes[-1]


def saves():
    return [kw for kind, kw in FakeFilePicker.calls if kind == "save"]


# ------------------------------------------------------------------ catalogue
def test_every_tool_has_a_route_icon_and_accent():
    assert len(TOOLS) == len(TOOL_SCREENS) == 23
    assert len({t.route for t in TOOLS}) == 23 and len({t.title for t in TOOLS}) == 23


def test_every_tool_screen_disables_its_button_until_a_file_is_chosen(env):
    for route, builder in TOOL_SCREENS.items():
        view = builder(env.page, env.uc, env.picker, env.notify)
        primaries = [c for c in walk(view) if isinstance(c, ft.Button)]
        assert primaries and all(b.disabled for b in primaries), route


# ------------------------------------------------------------------ compresser
def test_compress_screen_reports_the_gain(env, tmp_path):
    FakeFilePicker.save_to = str(tmp_path / "petit")
    view = build(env, "/compresser")
    assert find(view, ft.Dropdown).value == "medium"
    pick(view, make_photo_pdf(tmp_path / "photo.pdf"))
    find(view, ft.Dropdown).value = "strong"
    click(view, "Compresser et enregistrer")
    out = tmp_path / "petit.pdf"
    assert out.exists() and out.stat().st_size < (tmp_path / "photo.pdf").stat().st_size
    msg, error, reveal = last_note(env)
    assert not error and "→" in msg and "−" in msg and reveal == out
    assert saves()[0]["file_name"] == "photo_compresse.pdf"


def test_compress_screen_says_so_when_nothing_can_be_gained(env, tmp_path):
    FakeFilePicker.save_to = str(tmp_path / "idem")
    view = build(env, "/compresser")
    pick(view, make_pdf(tmp_path / "plain.pdf", 2))
    click(view, "Compresser et enregistrer")
    assert "déjà optimisé" in last_note(env)[0]


# ------------------------------------------------------------------ réorganiser
def test_reorder_screen_uses_arrows_then_saves(env, tmp_path):
    view = build(env, "/reorganiser")
    action = button(view, "Réorganiser et enregistrer")
    assert action.disabled
    pick(view, make_pdf(tmp_path / "a.pdf", 3))
    order = find(view, PageOrderList)
    assert order.order == [1, 2, 3] and action.disabled  # rien n'a changé : rien à faire
    order.move(2, -1)  # la page 3 monte
    assert order.order == [1, 3, 2] and not action.disabled
    FakeFilePicker.save_to = str(tmp_path / "ordre")
    click(view, "Réorganiser et enregistrer")
    assert widths(tmp_path / "ordre.pdf") == [110, 130, 120]


def test_reorder_screen_reverse_button(env, tmp_path):
    view = build(env, "/reorganiser")
    pick(view, make_pdf(tmp_path / "a.pdf", 3))
    run(button(view, "Inverser tout l'ordre").on_click)
    FakeFilePicker.save_to = str(tmp_path / "inv")
    click(view, "Réorganiser et enregistrer")
    assert widths(tmp_path / "inv.pdf") == [130, 120, 110]


def test_reorder_screen_falls_back_to_typing_for_long_documents(env, tmp_path):
    view = build(env, "/reorganiser")
    pick(view, make_pdf(tmp_path / "long.pdf", MAX_LISTED_PAGES + 5))
    field = find(view, ft.TextField)
    assert field.visible and find(view, PageOrderList).order == []
    field.value = "3, 1"
    field.on_change(None)
    FakeFilePicker.save_to = str(tmp_path / "long_ok")
    click(view, "Réorganiser et enregistrer")
    assert widths(tmp_path / "long_ok.pdf")[:3] == [130, 110, 120]


# ------------------------------------------------------------------ insérer
def test_insert_screen_blank_pages_and_validation(env, tmp_path):
    view = build(env, "/inserer")
    pick(view, make_pdf(tmp_path / "a.pdf", 3))
    position = find(view, ft.TextField, "Insérer après la page")
    position.value = "9"
    click(view, "Insérer et enregistrer")
    assert last_note(env)[1] is True and "Position invalide" in last_note(env)[0]
    assert not saves()

    position.value = "1"
    find(view, ft.TextField, "Nombre de pages blanches").value = "2"
    FakeFilePicker.save_to = str(tmp_path / "plus")
    click(view, "Insérer et enregistrer")
    assert widths(tmp_path / "plus.pdf") == [110, 110, 110, 120, 130]


def test_insert_screen_other_pdf_mode(env, tmp_path):
    view = build(env, "/inserer")
    pick(view, make_pdf(tmp_path / "a.pdf", 2))
    radio = find(view, ft.RadioGroup)
    radio.value = "pdf"
    radio.on_change(None)
    action = button(view, "Insérer et enregistrer")
    assert action.disabled  # il manque le PDF à insérer
    pick(view, make_pdf(tmp_path / "b.pdf", 1, base_width=500), index=1)
    assert not action.disabled
    find(view, ft.TextField, "Insérer après la page").value = "1"
    FakeFilePicker.save_to = str(tmp_path / "mix")
    click(view, "Insérer et enregistrer")
    assert widths(tmp_path / "mix.pdf") == [110, 510, 120]


# ------------------------------------------------------------------ recto-verso
def test_interleave_screen_needs_both_files(env, tmp_path):
    view = build(env, "/recto-verso")
    action = button(view, "Fusionner et enregistrer")
    assert action.disabled
    pick(view, make_pdf(tmp_path / "f.pdf", 2, 100), index=0)
    assert action.disabled
    pick(view, make_pdf(tmp_path / "b.pdf", 2, 500), index=1)
    assert not action.disabled
    FakeFilePicker.save_to = str(tmp_path / "rv")
    click(view, "Fusionner et enregistrer")
    assert widths(tmp_path / "rv.pdf") == [110, 520, 120, 510]  # versos inversés par défaut


def test_interleave_screen_reports_mismatch_before_saving(env, tmp_path):
    view = build(env, "/recto-verso")
    pick(view, make_pdf(tmp_path / "f.pdf", 5), index=0)
    pick(view, make_pdf(tmp_path / "b.pdf", 2), index=1)
    click(view, "Fusionner et enregistrer")
    assert last_note(env)[1] is True and "5 page" in last_note(env)[0] and not saves()


# ------------------------------------------------------------------ rogner
def test_crop_screen_needs_a_margin_and_crops(env, tmp_path):
    view = build(env, "/rogner")
    pick(view, make_pdf(tmp_path / "a.pdf", 2))
    click(view, "Rogner et enregistrer")
    assert last_note(env)[1] is True and "au moins une marge" in last_note(env)[0] and not saves()

    find(view, ft.TextField, "Haut").value = "10,5"  # virgule française acceptée
    FakeFilePicker.save_to = str(tmp_path / "rogne")
    click(view, "Rogner et enregistrer")
    page = PdfReader(str(tmp_path / "rogne.pdf")).pages[0]
    assert round(float(page.cropbox.top), 1) == round(300 - 10.5 * 72 / 25.4, 1)


def test_crop_screen_rejects_text_that_is_not_a_number(env, tmp_path):
    view = build(env, "/rogner")
    pick(view, make_pdf(tmp_path / "a.pdf", 1))
    find(view, ft.TextField, "Gauche").value = "1.2.3"
    click(view, "Rogner et enregistrer")
    assert last_note(env)[1] is True and "n'est pas un nombre" in last_note(env)[0]


# ------------------------------------------------------------------ métadonnées
def test_metadata_screen_prefills_edits_and_wipes(env, tmp_path):
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_metadata({"/Title": "Rapport", "/Author": "Jean"})
    writer.write(tmp_path / "m.pdf")

    view = build(env, "/metadonnees")
    pick(view, str(tmp_path / "m.pdf"))
    title, author = find(view, ft.TextField, "Titre"), find(view, ft.TextField, "Auteur")
    assert (title.value, author.value) == ("Rapport", "Jean")

    author.value = "Fifa"
    FakeFilePicker.save_to = str(tmp_path / "edit")
    click(view, "Appliquer et enregistrer")
    assert PdfReader(str(tmp_path / "edit.pdf")).metadata.author == "Fifa"

    wipe = find(view, ft.Switch)
    wipe.value = True
    wipe.on_change(None)
    assert title.disabled and author.disabled
    FakeFilePicker.save_to = str(tmp_path / "wipe")
    click(view, "Appliquer et enregistrer")
    info = PdfReader(str(tmp_path / "wipe.pdf")).metadata
    assert not info or not (info.get("/Title") or info.get("/Author"))


# ------------------------------------------------------------------ signets
def test_bookmarks_screen_validates_before_saving_then_writes(env, tmp_path):
    view = build(env, "/signets")
    pick(view, make_pdf(tmp_path / "a.pdf", 4))
    editor = find(view, ft.TextField, "Signets")
    editor.value = "1: Début\n9: Hors limites"
    click(view, "Appliquer et enregistrer")
    assert last_note(env)[1] is True and "page 9" in last_note(env)[0] and not saves()

    editor.value = "1: Début\n- 2: Suite\n4: Fin"
    FakeFilePicker.save_to = str(tmp_path / "sig")
    click(view, "Appliquer et enregistrer")
    marks = env.uc.read_bookmarks.execute(str(tmp_path / "sig.pdf"))
    assert [(b.title, b.level) for b in marks] == [("Début", 0), ("Suite", 1), ("Fin", 0)]

    # Rouvrir ce PDF préremplit l'éditeur avec les signets existants.
    pick(view, str(tmp_path / "sig.pdf"))
    assert editor.value == "1: Début\n- 2: Suite\n4: Fin"


# ------------------------------------------------------------------ filigrane / numéros / signature
def test_watermark_screen(env, tmp_path):
    view = build(env, "/filigrane")
    text = find(view, ft.TextField, "Texte du filigrane")
    action = button(view, "Ajouter et enregistrer")
    pick(view, make_pdf(tmp_path / "a.pdf", 2))
    assert action.disabled  # pas de texte
    text.value = "Привет"
    text.on_change(None)
    click(view, "Ajouter et enregistrer")
    assert last_note(env)[1] is True and "Caractères non pris en charge" in last_note(env)[0] and not saves()

    text.value = "CONFIDENTIEL"
    text.on_change(None)
    find(view, ft.Dropdown, "Couleur").value = "red"
    FakeFilePicker.save_to = str(tmp_path / "wm")
    click(view, "Ajouter et enregistrer")
    assert "CONFIDENTIEL" in PdfReader(str(tmp_path / "wm.pdf")).pages[1].extract_text()


def test_numbering_screen(env, tmp_path):
    view = build(env, "/numeroter")
    pick(view, make_pdf(tmp_path / "a.pdf", 3))
    find(view, ft.TextField, "Format").value = "Page {n}"
    find(view, ft.TextField, "Pages à numéroter").value = "2-3"
    FakeFilePicker.save_to = str(tmp_path / "num")
    click(view, "Numéroter et enregistrer")
    reader = PdfReader(str(tmp_path / "num.pdf"))
    assert [p.extract_text().strip() for p in reader.pages] == ["", "Page 1", "Page 2"]


def test_numbering_screen_requires_placeholder(env, tmp_path):
    view = build(env, "/numeroter")
    pick(view, make_pdf(tmp_path / "a.pdf", 1))
    find(view, ft.TextField, "Format").value = "Page"
    click(view, "Numéroter et enregistrer")
    assert last_note(env)[1] is True and "{n}" in last_note(env)[0]


@pytest.mark.parametrize("route,pages", [("/signature", [0, 0, 1]), ("/filigrane-image", [1, 1, 1])])
def test_image_stamp_screens_default_pages(env, tmp_path, route, pages):
    Image.new("RGB", (300, 100), (20, 40, 160)).save(tmp_path / "img.png")
    view = build(env, route)
    action = button(view, "Ajouter et enregistrer")
    pick(view, make_pdf(tmp_path / "a.pdf", 3))
    assert action.disabled  # il manque l'image
    FakeFilePicker.picked = [str(tmp_path / "img.png")]
    run(trays(view)[1].pick_button.on_click)
    assert not action.disabled
    FakeFilePicker.save_to = str(tmp_path / "res")
    click(view, "Ajouter et enregistrer")
    reader = PdfReader(str(tmp_path / "res.pdf"))
    counts = [
        len([x for x in p["/Resources"].get("/XObject", {}).values() if x.get_object().get("/Subtype") == "/Image"])
        for p in reader.pages
    ]
    assert counts == pages


def test_signature_screen_defaults_remove_white_and_position(env):
    view = build(env, "/signature")
    assert find(view, ft.Switch).value is True
    assert find(view, ft.Dropdown, "Emplacement").value == "bottom_right"
    logo = build(env, "/filigrane-image")
    assert find(logo, ft.Switch).value is False and find(logo, ft.Dropdown, "Emplacement").value == "center"


# ------------------------------------------------------------------ extraction
def test_extract_images_screen_success_and_empty(env, tmp_path):
    view = build(env, "/extraire-images")
    pick(view, make_photo_pdf(tmp_path / "photo.pdf", (400, 300)))
    FakeFilePicker.save_to = str(tmp_path / "imgs")
    click(view, "Extraire et enregistrer")
    assert "1 image extraite" in last_note(env)[0]
    with zipfile.ZipFile(tmp_path / "imgs.zip") as archive:
        assert len(archive.namelist()) == 1

    pick(view, make_pdf(tmp_path / "plain.pdf", 1))
    FakeFilePicker.save_to = str(tmp_path / "none")
    click(view, "Extraire et enregistrer")
    assert last_note(env)[1] is True and "Aucune image" in last_note(env)[0]
    assert not (tmp_path / "none.zip").exists()
    assert saves()[-1]["file_name"] == "plain_images.zip"


def test_extract_text_screen(env, tmp_path):
    view = build(env, "/extraire-texte")
    pick(view, make_text_pdf(tmp_path / "t.pdf", ["Bonjour", "Salama"]))
    find(view, ft.Switch).value = False
    FakeFilePicker.save_to = str(tmp_path / "txt")
    click(view, "Extraire et enregistrer")
    assert (tmp_path / "txt.txt").read_text("utf-8").split() == ["Bonjour", "Salama"]
    assert "2 pages" in last_note(env)[0]
    assert saves()[0]["file_name"] == "t_texte.txt"


# ------------------------------------------------------------------ images vers PDF (scan)
def test_images_screen_scan_mode(env, tmp_path):
    Image.new("RGB", (400, 300), (210, 205, 190)).save(tmp_path / "i.png")
    FakeFilePicker.picked = [str(tmp_path / "i.png")]
    FakeFilePicker.save_to = str(tmp_path / "scan")
    view = build(env, "/images-vers-pdf")
    assert find(view, ft.Dropdown, "Amélioration du scan").value == "original"
    click(view, "Ajouter des images")
    find(view, ft.Dropdown, "Amélioration du scan").value = "black_white"
    click(view, "Convertir et enregistrer")
    assert (tmp_path / "scan.pdf").exists()
    import pypdfium2 as pdfium

    page = pdfium.PdfDocument(str(tmp_path / "scan.pdf"))[0].render(scale=0.5).to_pil().convert("L")
    assert page.getpixel((5, 5)) == 255  # papier crème -> blanc pur


# ------------------------------------------------------------------ lot
def test_batch_screen_end_to_end(env, tmp_path):
    a, b = make_pdf(tmp_path / "a.pdf", 2), make_pdf(tmp_path / "b.pdf", 1)
    FakeFilePicker.picked = [a, b]
    view = build(env, "/lot")
    action = button(view, "Traiter le lot et enregistrer")
    assert action.disabled
    click(view, "Ajouter des PDF")
    assert find(view, FileList).paths == [a, b] and action.disabled  # aucune action choisie

    switch = find(view, ft.Switch, "Numéroter les pages")
    fmt = find(view, ft.TextField, "Format du numéro")
    assert fmt.visible is False
    switch.value = True
    switch.on_change(None)
    assert fmt.visible is True and not action.disabled

    FakeFilePicker.save_to = str(tmp_path / "resultat")
    click(view, "Traiter le lot et enregistrer")
    msg, error, _ = last_note(env)
    assert not error and "2 PDF traités" in msg
    with zipfile.ZipFile(tmp_path / "resultat.zip") as archive:
        assert sorted(archive.namelist()) == ["a_traite.pdf", "b_traite.pdf"]


def test_batch_screen_password_checks(env, tmp_path):
    FakeFilePicker.picked = [make_pdf(tmp_path / "a.pdf", 1)]
    view = build(env, "/lot")
    click(view, "Ajouter des PDF")
    lock = find(view, ft.Switch, "Protéger par mot de passe")
    lock.value = True
    lock.on_change(None)
    secret = find(view, ft.TextField, "Mot de passe")
    confirm = find(view, ft.TextField, "Confirmer le mot de passe")
    click(view, "Traiter le lot et enregistrer")
    assert "Saisissez le mot de passe" in last_note(env)[0]
    secret.value, confirm.value = "abc", "abd"
    click(view, "Traiter le lot et enregistrer")
    assert "ne correspondent pas" in last_note(env)[0] and not saves()


# ------------------------------------------------------------------ historique & accueil
def test_created_files_are_recorded_and_shown_on_home(monkeypatch, tmp_path):
    monkeypatch.setattr(ft, "FilePicker", FakeFilePicker)
    monkeypatch.setattr(ft.AlertDialog, "update", lambda self: None)
    FakeFilePicker.calls = []
    page = FakePage()
    settings = JsonSettingsStore(tmp_path / "settings.json")
    recents = JsonRecentFilesStore(tmp_path / "recents.json")
    picker = FilePickerService(page, settings, recents)
    notes = []
    uc = __import__("app.presentation.di", fromlist=["build_use_cases"]).build_use_cases()

    FakeFilePicker.picked = [make_pdf(tmp_path / "doc.pdf", 3)]
    FakeFilePicker.save_to = str(tmp_path / "extrait")
    view = TOOL_SCREENS["/extraire"](page, uc, picker, lambda *a: notes.append(a))
    click(view, "Choisir un PDF")
    find(view, ft.TextField).value = "1"
    click(view, "Extraire et enregistrer")

    assert [(i.path, i.label) for i in recents.items] == [(str(tmp_path / "extrait.pdf"), "Extrait créé")]
    home = build_home(page, recents)
    texts = [c.value for c in walk(home) if isinstance(c, ft.Text)]
    assert "RÉCENTS" in texts and "extrait.pdf" in texts
    assert "23 outils" in texts


def test_home_without_history_has_no_recent_section(env):
    texts = [c.value for c in walk(build_home(env.page)) if isinstance(c, ft.Text)]
    assert "RÉCENTS" not in texts
