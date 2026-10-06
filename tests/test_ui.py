"""Tests d'interface sans fenêtre : on pilote les gestionnaires d'évènements."""

import asyncio
from pathlib import Path
from types import SimpleNamespace

import flet as ft
import pytest
from pypdf import PdfReader

from app.presentation.di import build_use_cases
from app.presentation.screens import base
from app.presentation.screens.base import FilePickerService
from app.presentation.router import TOOL_SCREENS
from app.infrastructure.json_settings_store import JsonSettingsStore
from app.presentation.screens.about_screen import build_about
from app.presentation.screens.home_screen import TOOLS, build_home
from app.presentation.screens.settings_screen import build_settings
from app.presentation.theme import Palette
from app.presentation.theme_controller import ThemeController
from app.presentation.widgets.file_tray import FileTray, human_size
from tests.helpers import make_pdf, widths


class FakePage:
    def __init__(self, mobile=False):
        self.width = 500
        self.route = "/"
        self.web = False
        self.platform = SimpleNamespace(is_mobile=lambda: mobile)
        self.dialogs = []
        self.on_resize = None
        self.platform_brightness = ft.Brightness.LIGHT
        self.on_platform_brightness_change = None
        self.theme_mode = self.theme = self.dark_theme = self.bgcolor = None
        self.views = []

    def show_dialog(self, d): self.dialogs.append(d)
    def update(self): pass
    def run_task(self, *a, **k): pass


class FakeFilePicker:
    """Remplace ft.FilePicker : enregistre les appels, renvoie des valeurs scénarisées."""

    picked: list = []
    save_to: str | None = None
    calls: list = []

    async def pick_files(self, **kw):
        FakeFilePicker.calls.append(("pick", kw))
        return [SimpleNamespace(path=p) for p in FakeFilePicker.picked]

    async def save_file(self, **kw):
        FakeFilePicker.calls.append(("save", kw))
        return FakeFilePicker.save_to


@pytest.fixture(autouse=True)
def _reset_palette():
    yield
    Palette.apply(False)


@pytest.fixture
def env(monkeypatch, tmp_path_factory):
    monkeypatch.setattr(ft, "FilePicker", FakeFilePicker)
    monkeypatch.setattr(ft.AlertDialog, "update", lambda self: None)
    FakeFilePicker.picked, FakeFilePicker.save_to, FakeFilePicker.calls = [], None, []
    notes = []

    def notify(msg, error=False, reveal=None):
        notes.append((msg, error, reveal))

    page = FakePage()
    settings = JsonSettingsStore(tmp_path_factory.mktemp("cfg") / "settings.json")
    return SimpleNamespace(
        page=page, notes=notes, notify=notify, uc=build_use_cases(),
        settings=settings, picker=FilePickerService(page, settings),
        theme=ThemeController(page, settings),
    )


def walk(control):
    yield control
    for attr in ("content", "controls"):
        child = getattr(control, attr, None)
        if child is None or isinstance(child, str):
            continue
        for c in (child if isinstance(child, list) else [child]):
            if hasattr(c, "__dict__") or hasattr(c, "_c"):
                yield from walk(c)


def find(view, kind, text=None):
    for c in walk(view):
        if isinstance(c, kind):
            label = getattr(c, "content", None) or getattr(c, "label", None)
            if text is None or label == text:
                return c
    raise AssertionError(f"{kind.__name__} {text!r} introuvable")


def click(view, label):
    if label in ("Choisir un PDF", "Changer"):
        asyncio.run(_call(find(view, FileTray).pick_button.on_click))
        return
    asyncio.run(_call(find(view, (ft.Button, ft.OutlinedButton), label).on_click))


async def _call(fn):
    r = fn(None)
    if asyncio.iscoroutine(r):
        await r


def test_every_screen_builds_and_scrolls(env):
    home = build_home(env.page)
    assert home.scroll == ft.ScrollMode.AUTO
    assert len(TOOLS) == len(TOOL_SCREENS) == 23
    assert {t.route for t in TOOLS} == set(TOOL_SCREENS)
    assert all(hasattr(Palette, t.accent) for t in TOOLS)
    for route, builder in TOOL_SCREENS.items():
        view = builder(env.page, env.uc, env.picker, env.notify)
        assert view.scroll == ft.ScrollMode.AUTO, route
        assert view.appbar is not None
    for extra in (
        build_about(env.page, env.notify),
        build_settings(env.page, env.settings, env.theme, env.notify),
    ):
        assert extra.scroll == ft.ScrollMode.AUTO


def test_extract_rename_without_extension(env, tmp_path):
    src = make_pdf(tmp_path / "doc.pdf", 5)
    FakeFilePicker.picked = [src]
    FakeFilePicker.save_to = str(tmp_path / "mon extrait perso")  # l'utilisateur a renommé, sans extension

    view = TOOL_SCREENS["/extraire"](env.page, env.uc, env.picker, env.notify)
    click(view, "Choisir un PDF")
    find(view, ft.TextField).value = "4-5, 1"
    click(view, "Extraire et enregistrer")

    out = tmp_path / "mon extrait perso.pdf"
    assert out.exists() and widths(out) == [140, 150, 110]
    save_call = [kw for kind, kw in FakeFilePicker.calls if kind == "save"][0]
    assert save_call["file_name"] == "doc_extrait.pdf"
    assert save_call["allowed_extensions"] == ["pdf"]
    msg, error, reveal = env.notes[-1]
    assert not error and reveal == out and "mon extrait perso.pdf" in msg
    assert not any(p.name.endswith(".part") for p in tmp_path.iterdir())


def test_invalid_selection_never_opens_save_dialog(env, tmp_path):
    FakeFilePicker.picked = [make_pdf(tmp_path / "doc.pdf", 3)]
    view = TOOL_SCREENS["/supprimer"](env.page, env.uc, env.picker, env.notify)
    click(view, "Choisir un PDF")
    for bad, expect in (("9", "3 page"), ("1-3", "toutes les pages"), ("abc", "")):
        find(view, ft.TextField).value = bad
        click(view, "Supprimer et enregistrer")
        assert env.notes[-1][1] is True and expect in env.notes[-1][0]
    assert not [1 for kind, _ in FakeFilePicker.calls if kind == "save"]


def test_overwriting_source_is_reported(env, tmp_path):
    src = make_pdf(tmp_path / "doc.pdf", 3)
    FakeFilePicker.picked = [src]
    FakeFilePicker.save_to = src  # l'utilisateur choisit le fichier source
    view = TOOL_SCREENS["/extraire"](env.page, env.uc, env.picker, env.notify)
    click(view, "Choisir un PDF")
    find(view, ft.TextField).value = "1"
    click(view, "Extraire et enregistrer")
    assert env.notes[-1][1] is True and "écraser" in env.notes[-1][0]
    assert widths(src) == [110, 120, 130]


def test_cancel_save_dialog_does_nothing(env, tmp_path):
    FakeFilePicker.picked = [make_pdf(tmp_path / "doc.pdf", 3)]
    FakeFilePicker.save_to = None
    view = TOOL_SCREENS["/diviser"](env.page, env.uc, env.picker, env.notify)
    click(view, "Choisir un PDF")
    click(view, "Diviser et enregistrer")
    assert env.notes == []
    # indicateur de progression ouvert puis refermé proprement
    assert all(d.open is False for d in env.page.dialogs)


def test_merge_reorder_then_save(env, tmp_path):
    a = make_pdf(tmp_path / "a.pdf", 1, 100)
    b = make_pdf(tmp_path / "b.pdf", 1, 200)
    FakeFilePicker.picked = [a, b]
    FakeFilePicker.save_to = str(tmp_path / "fusion.pdf")
    view = TOOL_SCREENS["/fusionner"](env.page, env.uc, env.picker, env.notify)
    click(view, "Ajouter des PDF")

    from app.presentation.widgets.file_list import FileList
    files = find(view, FileList)
    assert files.paths == [a, b]
    files._move(1, -1)  # ↑ sur le 2e fichier
    assert files.paths == [b, a]
    click(view, "Fusionner et enregistrer")
    assert widths(tmp_path / "fusion.pdf") == [210, 110]


def test_images_screen_fit_switch(env, tmp_path):
    from PIL import Image

    Image.new("RGB", (400, 300), "red").save(tmp_path / "i.png")
    FakeFilePicker.picked = [str(tmp_path / "i.png")]
    FakeFilePicker.save_to = str(tmp_path / "o")
    view = TOOL_SCREENS["/images-vers-pdf"](env.page, env.uc, env.picker, env.notify)
    click(view, "Ajouter des images")
    find(view, ft.Switch).value = False
    click(view, "Convertir et enregistrer")
    box = PdfReader(str(tmp_path / "o.pdf")).pages[0].mediabox
    assert (round(float(box.width)), round(float(box.height))) == (192, 144)  # 400x300 px à 150 ppp


def test_rotate_defaults_and_all_pages(env, tmp_path):
    FakeFilePicker.picked = [make_pdf(tmp_path / "doc.pdf", 2)]
    FakeFilePicker.save_to = str(tmp_path / "r.pdf")
    view = TOOL_SCREENS["/pivoter"](env.page, env.uc, env.picker, env.notify)
    assert find(view, ft.Dropdown).value == "90"
    click(view, "Choisir un PDF")
    click(view, "Pivoter et enregistrer")
    assert [p.get("/Rotate", 0) for p in PdfReader(str(tmp_path / "r.pdf")).pages] == [90, 90]


def test_password_screen_protect_and_unlock(env, tmp_path):
    src = make_pdf(tmp_path / "doc.pdf", 2)
    FakeFilePicker.picked = [src]
    view = TOOL_SCREENS["/mot-de-passe"](env.page, env.uc, env.picker, env.notify)
    fields = [c for c in walk(view) if isinstance(c, ft.TextField)]
    password, confirm = fields
    radio = find(view, ft.RadioGroup)
    assert confirm.visible is False

    radio.value = "protect"
    radio.on_change(None)
    assert confirm.visible is True

    click(view, "Choisir un PDF")
    password.value, confirm.value = "abc", "abd"
    click(view, "Appliquer et enregistrer")
    assert "ne correspondent pas" in env.notes[-1][0]

    confirm.value = "abc"
    FakeFilePicker.save_to = str(tmp_path / "prot")
    click(view, "Appliquer et enregistrer")
    protected = tmp_path / "prot.pdf"
    assert PdfReader(str(protected)).is_encrypted

    # Déverrouillage avec un mauvais puis le bon mot de passe
    FakeFilePicker.picked = [str(protected)]
    radio.value = "unlock"
    radio.on_change(None)
    click(view, "Choisir un PDF")
    password.value = "wrong"
    FakeFilePicker.save_to = str(tmp_path / "open")
    click(view, "Appliquer et enregistrer")
    assert env.notes[-1][1] is True and "incorrect" in env.notes[-1][0]
    password.value = "abc"
    click(view, "Appliquer et enregistrer")
    assert widths(tmp_path / "open.pdf") == [110, 120]


def test_mobile_save_goes_through_src_bytes(monkeypatch, tmp_path):
    monkeypatch.setattr(ft, "FilePicker", FakeFilePicker)
    monkeypatch.setattr(ft.AlertDialog, "update", lambda self: None)
    FakeFilePicker.calls = []
    FakeFilePicker.save_to = "/storage/emulated/0/Download/fusion.pdf"
    page = FakePage(mobile=True)
    picker = FilePickerService(page)
    src = make_pdf(tmp_path / "doc.pdf", 3)
    notes = []
    uc = build_use_cases()

    asyncio.run(base.run_save(
        lambda *a: notes.append(a), picker, "Enregistrer", "extrait.pdf",
        lambda dest: uc.extract_pages.execute(src, "1-2", dest), "OK",
    ))
    save = [kw for kind, kw in FakeFilePicker.calls if kind == "save"][0]
    assert save["src_bytes"].startswith(b"%PDF") and save["file_name"] == "extrait.pdf"
    assert notes and notes[-1][0].startswith("OK : fusion.pdf")


def test_unexpected_error_is_logged_and_reported(env, caplog):
    def boom(dest):
        raise RuntimeError("kaboom")

    FakeFilePicker.save_to = "/tmp/x.pdf"
    asyncio.run(base.run_save(env.notify, env.picker, "t", "x.pdf", boom))
    assert env.notes[-1][1] is True and "kaboom" in env.notes[-1][0]
    assert any("kaboom" in r.getMessage() or r.exc_info for r in caplog.records)


# ====================================================================== nouveautés
def texts(view):
    return [c.value for c in walk(view) if isinstance(c, ft.Text)]


def test_human_size_french_format():
    assert human_size(512) == "512 o"
    assert human_size(1536) == "1,5 Ko"
    assert human_size(5 * 1024 * 1024) == "5,0 Mo"


def test_theme_modes_switch_palette_and_rebuild(env):
    rebuilt = []
    env.theme.subscribe(lambda: rebuilt.append(Palette.dark))

    env.theme.set_mode("dark")
    assert Palette.dark and env.page.theme_mode == ft.ThemeMode.DARK
    assert env.page.bgcolor == Palette.paper == "#14181A"
    assert env.settings.current.theme == "dark"

    env.theme.set_mode("light")
    assert not Palette.dark and env.page.theme_mode == ft.ThemeMode.LIGHT
    assert env.page.bgcolor == "#F2F1EA"
    assert rebuilt == [True, False]  # le routeur est prévenu à chaque changement


def test_system_mode_follows_os_brightness(env):
    env.theme.set_mode("system")
    assert not Palette.dark
    env.page.platform_brightness = ft.Brightness.DARK
    env.page.on_platform_brightness_change(None)  # l'OS passe en sombre
    assert Palette.dark
    # Un choix explicite « clair » ignore l'OS
    env.theme.set_mode("light")
    env.page.on_platform_brightness_change(None)
    assert not Palette.dark


def test_new_screens_use_dark_colors_after_switch(env):
    env.theme.set_mode("dark")
    view = TOOL_SCREENS["/extraire"](env.page, env.uc, env.picker, env.notify)
    assert view.bgcolor == "#14181A"
    assert find(view, FileTray).bgcolor == Palette.surface == "#1E2427"


def test_settings_screen_persists_every_change(env):
    view = build_settings(env.page, env.settings, env.theme, env.notify)

    seg = find(view, ft.SegmentedButton)
    assert seg.selected == ["system"]
    seg.selected = ["dark"]
    seg.on_change(SimpleNamespace(control=seg))
    assert env.settings.current.theme == "dark" and Palette.dark

    switches = [c for c in walk(view) if isinstance(c, ft.Switch)]
    assert len(switches) == 3  # dernier dossier, ouvrir le dossier, A4 par défaut
    for sw in switches:
        sw.value = False
        sw.on_change(SimpleNamespace(control=sw))
    cur = env.settings.current
    assert (cur.remember_last_folder, cur.offer_open_folder, cur.fit_a4_default) == (False,) * 3

    # Survit au redémarrage
    assert JsonSettingsStore(env.settings.path).current.theme == "dark"


def test_settings_reset(env):
    env.settings.update(theme="dark", fit_a4_default=False)
    view = build_settings(env.page, env.settings, env.theme, env.notify)
    click(view, "Réinitialiser")
    assert env.settings.current.theme == "system" and env.settings.current.fit_a4_default
    assert env.notes[-1][0] == "Paramètres réinitialisés." and not Palette.dark


def test_settings_hides_desktop_only_rows_on_mobile(env):
    env.page.platform = SimpleNamespace(is_mobile=lambda: True)
    view = build_settings(env.page, env.settings, env.theme, env.notify)
    assert len([c for c in walk(view) if isinstance(c, ft.Switch)]) == 2


def test_about_page_credits_the_author(env):
    all_text = " ".join(texts(build_about(env.page, env.notify)))
    assert "FIFALIANA SAROBIDY" in all_text and "Madagascar" in all_text
    assert "FS" in texts(build_about(env.page, env.notify))  # initiales de l'avatar
    assert "Version 1.3.0" in all_text


def test_images_switch_uses_saved_default(env):
    env.settings.update(fit_a4_default=False)
    view = TOOL_SCREENS["/images-vers-pdf"](env.page, env.uc, env.picker, env.notify)
    assert find(view, ft.Switch).value is False


def test_last_folder_is_remembered_and_reused(env, tmp_path):
    src = make_pdf(tmp_path / "doc.pdf", 3)
    FakeFilePicker.picked = [src]
    FakeFilePicker.save_to = str(tmp_path / "out")
    view = TOOL_SCREENS["/extraire"](env.page, env.uc, env.picker, env.notify)
    click(view, "Choisir un PDF")
    assert env.settings.current.last_folder == str(tmp_path)

    find(view, ft.TextField).value = "1"
    click(view, "Extraire et enregistrer")
    save_call = [kw for kind, kw in FakeFilePicker.calls if kind == "save"][0]
    assert save_call["initial_directory"] == str(tmp_path)

    # Option désactivée : plus d'initial_directory
    env.settings.update(remember_last_folder=False)
    FakeFilePicker.calls.clear()
    click(view, "Changer")
    assert FakeFilePicker.calls[0][1]["initial_directory"] is None


def test_open_folder_action_follows_setting(monkeypatch):
    from app.presentation.widgets.feedback import make_notifier

    for offered, expected in ((True, "Ouvrir le dossier"), (False, None)):
        page = FakePage()
        settings = SimpleNamespace(current=SimpleNamespace(offer_open_folder=offered))
        make_notifier(page, settings)("ok", False, Path("/tmp/x.pdf"))
        assert page.dialogs[-1].action == expected


def test_primary_button_disabled_until_ready(env, tmp_path):
    FakeFilePicker.picked = [make_pdf(tmp_path / "doc.pdf", 3)]
    view = TOOL_SCREENS["/extraire"](env.page, env.uc, env.picker, env.notify)
    action = find(view, ft.Button, "Extraire et enregistrer")
    field = find(view, ft.TextField)
    assert action.disabled is True

    click(view, "Choisir un PDF")
    assert action.disabled is True           # fichier OK, pages vides
    field.value = "1-2"
    field.on_change(None)
    assert action.disabled is False

    tray = find(view, FileTray)
    assert "3 page(s)" in tray._meta.value and "o" in tray._meta.value  # pages + taille
    assert tray.clear_button.visible and tray.pick_button.content == "Changer"

    tray.clear_button.on_click(None)         # croix : retire la sélection
    assert action.disabled is True and not tray.has_file
    assert tray.pick_button.content == "Choisir un PDF"


def test_tray_shows_error_for_protected_pdf(env, tmp_path):
    src = make_pdf(tmp_path / "doc.pdf", 2)
    protected = env.uc.protect_pdf.execute(src, "pw", str(tmp_path / "p.pdf"))
    FakeFilePicker.picked = [str(protected)]
    view = TOOL_SCREENS["/extraire"](env.page, env.uc, env.picker, env.notify)
    click(view, "Choisir un PDF")
    tray = find(view, FileTray)
    assert "protégé par un mot de passe" in tray._meta.value
    assert tray._meta.color == Palette.danger

    # Dans l'outil « Mot de passe », le même fichier est accepté sans erreur
    pw = TOOL_SCREENS["/mot-de-passe"](env.page, env.uc, env.picker, env.notify)
    click(pw, "Choisir un PDF")
    assert find(pw, FileTray)._meta.color != Palette.danger


def test_merge_button_needs_two_files(env, tmp_path):
    a, b = make_pdf(tmp_path / "a.pdf", 1), make_pdf(tmp_path / "b.pdf", 1)
    view = TOOL_SCREENS["/fusionner"](env.page, env.uc, env.picker, env.notify)
    action = find(view, ft.Button, "Fusionner et enregistrer")
    assert action.disabled is True
    FakeFilePicker.picked = [a]
    click(view, "Ajouter des PDF")
    assert action.disabled is True
    FakeFilePicker.picked = [b]
    click(view, "Ajouter des PDF")
    assert action.disabled is False
    find(view, ft.TextButton, "Tout retirer").on_click(None)
    assert action.disabled is True


def test_home_groups_tools_in_sections(env):
    texts_home = texts(build_home(env.page))
    for label in ("Organiser", "Convertir", "Sécurité"):  # en-têtes de catégorie
        assert label in texts_home
    # (l'ordre se lit après les puces de filtre : on compare les DERNIÈRES occurrences, celles des en-têtes)
    last = lambda label: len(texts_home) - 1 - texts_home[::-1].index(label)  # noqa: E731
    assert last("Organiser") < last("Convertir") < last("Sécurité")
    # accès aux paramètres et à l'à-propos depuis l'accueil
    tooltips = [getattr(c, "tooltip", None) for c in walk(build_home(env.page))]
    assert "Paramètres" in tooltips and "À propos" in tooltips


def test_settings_has_no_activity_log(env):
    all_text = " ".join(texts(build_settings(env.page, env.settings, env.theme, env.notify)))
    assert "journal" not in all_text.lower()
    assert "Réinitialiser les paramètres" in all_text


def test_about_role_email_and_heart(env):
    view = build_about(env.page, env.notify)
    all_text = " ".join(texts(view))
    assert "Développeuse · Madagascar" in all_text and "Développeur " not in all_text
    assert "ssarobidyfifaliana@gmail.com" in all_text
    assert "Conçu avec" in all_text
    hearts = [c for c in walk(view) if isinstance(c, ft.Icon) and c.icon == ft.Icons.FAVORITE]
    assert len(hearts) == 1 and hearts[0].color == Palette.heart


def test_about_contact_buttons(env, monkeypatch):
    launched, copied = [], []

    class FakeLauncher:
        async def launch_url(self, url, **kw): launched.append(url)

    class FakeClipboard:
        async def set(self, value): copied.append(value)

    monkeypatch.setattr(ft, "UrlLauncher", FakeLauncher)
    monkeypatch.setattr(ft, "Clipboard", FakeClipboard)
    view = build_about(env.page, env.notify)
    click(view, "Écrire un e-mail")
    click(view, "Copier l'adresse")
    assert launched == ["mailto:ssarobidyfifaliana@gmail.com"]
    assert copied == ["ssarobidyfifaliana@gmail.com"]
    assert env.notes[-1] == ("Adresse e-mail copiée.", False, None)


def test_about_contact_failure_is_reported(env, monkeypatch):
    class Broken:
        async def launch_url(self, *a, **k): raise RuntimeError("pas de messagerie")
        async def set(self, *a, **k): raise RuntimeError("pas de presse-papiers")

    monkeypatch.setattr(ft, "UrlLauncher", Broken)
    monkeypatch.setattr(ft, "Clipboard", Broken)
    view = build_about(env.page, env.notify)
    click(view, "Écrire un e-mail")
    assert env.notes[-1][1] is True and "ssarobidyfifaliana@gmail.com" in env.notes[-1][0]
    click(view, "Copier l'adresse")
    assert env.notes[-1][1] is True


def test_dark_theme_hero_and_light_hero_differ(env):
    light = build_home(env.page)
    env.theme.set_mode("dark")
    dark = build_home(env.page)
    grads = lambda v: [c.gradient.colors for c in walk(v) if getattr(c, "gradient", None)]
    assert grads(light) and grads(dark) and grads(light) != grads(dark)


def test_empty_tray_is_inviting(env):
    view = TOOL_SCREENS["/extraire"](env.page, env.uc, env.picker, env.notify)
    tray = find(view, FileTray)
    assert tray._label.value == "Aucun fichier sélectionné"
    assert "Cliquez" in tray._meta.value
