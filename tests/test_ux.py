"""Améliorations d'ergonomie : recherche, filtres, bandeau de résultat, aides, validation en direct,
écran « Retirer des filigranes »."""

from pathlib import Path

import flet as ft
import pytest
from PIL import Image

from app.domain.options import ImageStamp, StampKind, TextWatermark
from app.presentation.screens.home_screen import TOOLS, _KEYWORDS, _normalize, build_home, filter_tools
from app.presentation.widgets.feedback import ResultBanner, banner_for, make_notifier, register_banner
from tests.helpers import make_pdf
from tests.test_ui import FakeFilePicker, FakePage, _reset_palette, click, env, find, walk  # noqa: F401
from tests.test_ui_tools import build, button, last_note, pick, trays


def texts(view):
    return [c.value for c in walk(view) if isinstance(c, ft.Text)]


def cards(view):
    return [c for c in walk(view) if isinstance(c, ft.Container) and getattr(c, "on_click", None) and c.ink and c.scale is not None]


# ------------------------------------------------------------------ recherche
@pytest.mark.parametrize(
    "query,expected",
    [
        ("compresser", "/compresser"),
        ("réduire", "/compresser"),  # synonyme, avec accent
        ("REDUIRE", "/compresser"),  # sans accent, en capitales
        ("alleger poids", "/compresser"),  # plusieurs mots : tous doivent correspondre
        ("signer", "/signature"),
        ("paraphe", "/signature"),
        ("assembler", "/fusionner"),
        ("cadenas", "/mot-de-passe"),
        ("enlever watermark", "/retirer-filigranes"),
        ("table des matieres", "/signets"),
    ],
)
def test_search_finds_tools_by_name_and_synonyms(query, expected):
    found = [t.route for t in filter_tools(query)]
    assert expected in found, (query, found)


def test_search_edge_cases():
    assert len(filter_tools("")) == len(TOOLS) == 23
    assert len(filter_tools("   ")) == 23
    assert filter_tools("zzzzqq") == []
    assert filter_tools("pdf compresser zzzz") == []  # un mot sans correspondance exclut tout
    assert {t.group for t in filter_tools("", "Extraire")} == {"Extraire"}
    assert [t.route for t in filter_tools("compresser", "Extraire")] == []  # filtre ET recherche
    assert _normalize("Réduire Éàç") == "reduire eac"


def test_every_tool_has_search_keywords_for_a_real_route():
    assert set(_KEYWORDS) <= {t.route for t in TOOLS}
    assert {t.route for t in TOOLS} <= set(_KEYWORDS)


# ------------------------------------------------------------------ accueil interactif
def home(env, recents=None):
    return build_home(env.page, recents)


def titles_shown(view):
    return [t for t in texts(view) if t in {x.title for x in TOOLS}]


def test_home_lists_every_tool_then_filters_live(env):
    view = home(env)
    assert len(titles_shown(view)) == 23
    search = find(view, ft.TextField)
    search.value = "signer"
    search.on_change(None)
    assert set(titles_shown(view)) == {"Signer un PDF"}
    assert "1 outil" in texts(view)


def test_home_filter_chips_and_clear(env):
    view = home(env)
    chip = next(c for c in walk(view) if isinstance(c, ft.Container) and isinstance(c.content, ft.Text) and c.content.value == "Extraire")
    chip.on_click(None)
    assert set(titles_shown(view)) == {"Extraire les images", "Extraire le texte"}
    assert "2 outils" in texts(view)
    all_chip = next(c for c in walk(view) if isinstance(c, ft.Container) and isinstance(c.content, ft.Text) and c.content.value == "Tous")
    all_chip.on_click(None)
    assert len(titles_shown(view)) == 23


def test_home_empty_state_offers_to_start_over(env):
    view = home(env)
    search = find(view, ft.TextField)
    search.value = "zzzz"
    search.on_change(None)
    assert titles_shown(view) == []
    assert any("Aucun outil ne correspond à « zzzz »" in t for t in texts(view))
    find(view, ft.TextButton, "Tout afficher").on_click(None)
    assert search.value == "" and len(titles_shown(view)) == 23


def test_home_hides_recents_while_searching(env, tmp_path):
    from app.infrastructure.recent_files_store import JsonRecentFilesStore

    store = JsonRecentFilesStore(tmp_path / "r.json")
    store.add("/x/doc.pdf", "PDF créé")
    view = home(env, store)
    assert "doc.pdf" in texts(view)
    search = find(view, ft.TextField)
    search.value = "fusion"
    search.on_change(None)
    assert "doc.pdf" not in texts(view) and "RÉCENTS" not in texts(view)


def test_enter_opens_the_only_match(env):
    routes = []
    env.page.push_route = "push_route"  # le double de page n'a pas de navigation réelle
    env.page.run_task = lambda fn, route=None, *a, **k: routes.append(route)
    view = home(env)
    search = find(view, ft.TextField)
    search.value = "signer"
    search.on_change(None)
    search.on_submit(None)
    assert routes == ["/signature"]
    routes.clear()
    search.value = "pages"  # plusieurs résultats : Entrée ne choisit pas à la place de l'utilisateur
    search.on_change(None)
    search.on_submit(None)
    assert routes == []


def test_search_autofocus_only_on_desktop(env):
    assert find(home(env), ft.TextField).autofocus is True
    mobile = FakePage(mobile=True)
    assert find(build_home(mobile), ft.TextField).autofocus is False


# ------------------------------------------------------------------ bandeau de résultat
def test_banner_shows_success_then_error_then_hides():
    banner = ResultBanner()
    assert banner.visible is False
    banner.show("PDF compressé : 5 Mo → 1 Mo", reveal=Path("/x/out.pdf"), can_reveal=True)
    assert banner.visible and banner.message.value.startswith("PDF compressé")
    assert any(getattr(b, "tooltip", "") == "Ouvrir le dossier" for b in banner.actions.controls)
    banner.show("Mot de passe incorrect.", error=True)
    assert banner.is_error and not any(getattr(b, "tooltip", "") == "Ouvrir le dossier" for b in banner.actions.controls)
    banner.hide()
    assert banner.visible is False


def test_banner_has_no_folder_button_when_not_offered():
    banner = ResultBanner()
    banner.show("ok", reveal=Path("/x"), can_reveal=False)
    assert [b.tooltip for b in banner.actions.controls] == ["Fermer"]


def test_notifier_feeds_the_banner_of_the_current_screen(monkeypatch):
    page = FakePage()
    banner = ResultBanner()
    register_banner(page, banner)
    assert banner_for(page) is banner
    notify = make_notifier(page)
    notify("Terminé", False, Path("/x/o.pdf"))
    assert banner.visible and banner.message.value == "Terminé" and len(page.dialogs) == 1  # + snackbar
    notify("Échec", True)
    assert banner.is_error and banner.message.value == "Échec"


def test_notifier_without_banner_still_shows_snackbar():
    page = FakePage()
    notify = make_notifier(page)
    notify("ok")
    assert len(page.dialogs) == 1 and banner_for(page) is None


def test_each_new_screen_replaces_the_previous_banner(env):
    build(env, "/compresser")
    banner_one = banner_for(env.page)
    build(env, "/rogner")
    assert banner_for(env.page) is not banner_one


# ------------------------------------------------------------------ aide sous le bouton
def status_text(view):
    return next(t for t in walk(view) if isinstance(t, ft.Text) and t.value in (
        "Choisissez d'abord un fichier PDF.", "Complétez les réglages pour continuer.", ""))


def test_status_explains_why_the_button_is_disabled(env, tmp_path):
    view = build(env, "/numeroter")
    status = status_text(view)
    assert status.visible and status.value == "Choisissez d'abord un fichier PDF."
    pick(view, make_pdf(tmp_path / "a.pdf", 2))
    assert status.visible is False  # format par défaut « {n} » : prêt
    field = find(view, ft.TextField, "Format")
    field.value = ""
    field.on_change(None)
    assert status.visible and status.value == "Complétez les réglages pour continuer."


def test_tool_screens_have_labelled_sections(env):
    view = build(env, "/compresser")
    assert "FICHIER" in texts(view) and "RÉGLAGES" in texts(view)


# ------------------------------------------------------------------ validation en direct
def test_watermark_field_flags_unsupported_characters_as_you_type(env, tmp_path):
    view = build(env, "/filigrane")
    pick(view, make_pdf(tmp_path / "a.pdf", 1))
    text = find(view, ft.TextField, "Texte du filigrane")
    action = button(view, "Ajouter et enregistrer")
    text.value = "Привет"
    text.on_change(None)
    assert "Caractères non pris en charge" in text.error and action.disabled
    text.value = "CONFIDENTIEL"
    text.on_change(None)
    assert text.error is None and not action.disabled
    text.value = ""
    text.on_change(None)
    assert text.error is None and action.disabled  # champ vide : pas d'erreur, juste inactif


def test_numbering_field_demands_the_placeholder_live(env, tmp_path):
    view = build(env, "/numeroter")
    pick(view, make_pdf(tmp_path / "a.pdf", 1))
    field = find(view, ft.TextField, "Format")
    action = button(view, "Numéroter et enregistrer")
    field.value = "Page"
    field.on_change(None)
    assert "{n}" in field.error and action.disabled
    field.value = "Page {n}"
    field.on_change(None)
    assert field.error is None and not action.disabled


def test_bookmark_editor_validates_syntax_and_page_range_live(env, tmp_path):
    view = build(env, "/signets")
    pick(view, make_pdf(tmp_path / "a.pdf", 3))
    editor = find(view, ft.TextField, "Signets")
    editor.value = "Introduction"
    editor.on_change(None)
    assert "Ligne 1 invalide" in editor.error
    editor.value = "1: A\n9: B"
    editor.on_change(None)
    assert "page 9" in editor.error  # le nombre de pages du PDF choisi est connu
    editor.value = "1: A\n- 2: B"
    editor.on_change(None)
    assert editor.error is None


# ------------------------------------------------------------------ écran « retirer des filigranes »
@pytest.fixture
def stamped(tmp_path, env):
    Image.new("RGB", (300, 100), (20, 40, 160)).save(tmp_path / "logo.png")
    base = make_pdf(tmp_path / "base.pdf", 2)
    a = env.uc.watermark_text.execute(base, TextWatermark("COPIE"), "", str(tmp_path / "a.pdf"))
    b = env.uc.sign_pdf.execute(str(a), str(tmp_path / "logo.png"), ImageStamp(), "", str(tmp_path / "b.pdf"))
    return str(b)


def boxes(view):
    return [c for c in walk(view) if isinstance(c, ft.Checkbox)]


def test_unmark_screen_scans_the_chosen_pdf(env, stamped):
    view = build(env, "/retirer-filigranes")
    action = button(view, "Retirer et enregistrer")
    assert action.disabled and all(b.disabled for b in boxes(view))
    pick(view, stamped)
    texte, image, signature = boxes(view)
    assert (texte.label, image.label, signature.label) == ("Filigranes texte (2)", "Filigranes image / logo — aucun", "Signatures (1)")
    assert (texte.value, texte.disabled, image.disabled, signature.value) == (True, False, True, True)
    assert not action.disabled
    assert "3 filigranes repérés sur 2 pages." in texts(view)


def test_unmark_screen_removes_only_what_is_ticked(env, stamped, tmp_path):
    view = build(env, "/retirer-filigranes")
    pick(view, stamped)
    boxes(view)[2].value = False  # on garde la signature
    boxes(view)[2].on_change(None)
    FakeFilePicker.save_to = str(tmp_path / "propre")
    click(view, "Retirer et enregistrer")
    msg, error, _ = last_note(env)
    assert not error and "Filigranes retirés (2 texte)" in msg
    after = env.uc.scan_watermarks.execute(str(tmp_path / "propre.pdf"))
    assert after.count(StampKind.TEXT) == 0 and after.count(StampKind.SIGNATURE) == 1
    assert FakeFilePicker.calls[-1][1]["file_name"] == "b_sans_filigrane.pdf"


def test_unmark_button_needs_at_least_one_box(env, stamped):
    view = build(env, "/retirer-filigranes")
    pick(view, stamped)
    action = button(view, "Retirer et enregistrer")
    for box in boxes(view):
        box.value = False
        box.on_change(None)
    assert action.disabled


def test_unmark_screen_explains_when_nothing_is_found(env, tmp_path):
    view = build(env, "/retirer-filigranes")
    pick(view, make_pdf(tmp_path / "propre.pdf", 2))
    assert any("Aucun filigrane identifiable" in t for t in texts(view))
    assert all(b.disabled and not b.value for b in boxes(view))
    assert button(view, "Retirer et enregistrer").disabled


def test_unmark_screen_reports_a_locked_pdf_without_crashing(env, tmp_path):
    locked = tmp_path / "locked.pdf"
    env.uc.protect_pdf.execute(make_pdf(tmp_path / "g.pdf", 1), "pw", str(locked))
    view = build(env, "/retirer-filigranes")
    pick(view, str(locked))
    summary = next(t for t in walk(view) if isinstance(t, ft.Text) and t.value and "mot de passe" in t.value.lower())
    assert summary.color == pytest.importorskip("app.presentation.theme").Palette.danger
    assert all(b.disabled for b in boxes(view))


def test_unmark_resets_when_the_file_is_removed(env, stamped):
    view = build(env, "/retirer-filigranes")
    action = button(view, "Retirer et enregistrer")
    pick(view, stamped)
    assert not action.disabled
    trays(view)[0]._on_clear(None)  # l'utilisateur retire le fichier
    assert action.disabled and all(b.disabled and not b.value for b in boxes(view))
    assert all("en attente" in b.label for b in boxes(view))


# ------------------------------------------------------------------ « Effacer » l'historique
def test_clear_button_empties_the_history_and_the_list_on_screen(env, tmp_path):
    from app.infrastructure.recent_files_store import JsonRecentFilesStore

    store = JsonRecentFilesStore(tmp_path / "r.json")
    store.add("/x/un.pdf", "PDF créé")
    store.add("/x/deux.pdf", "PDF compressé")
    view = build_home(env.page, store)
    assert {"un.pdf", "deux.pdf", "RÉCENTS"} <= set(texts(view))

    find(view, ft.TextButton, "Effacer").on_click(None)

    assert store.items == []                                  # historique vidé
    assert not {"un.pdf", "deux.pdf", "RÉCENTS"} & set(texts(view))  # et la liste disparaît tout de suite
    assert len(titles_shown(view)) == 23                      # les outils restent affichés
    assert JsonRecentFilesStore(tmp_path / "r.json").items == []  # vidé aussi sur le disque
