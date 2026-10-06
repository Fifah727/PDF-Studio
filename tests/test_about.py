"""Écran « À propos » : contenu calculé, interactions, diagnostic."""

import flet as ft

from app import APP_NAME, __version__
from app.infrastructure import diagnostics
from app.presentation.screens.about_screen import (
    FAN_CLOSED,
    FAN_OPEN,
    PROMISES,
    TAGLINES,
    build_about,
)
from app.presentation.screens.home_screen import TOOLS
from app.presentation.theme import Palette
from tests.test_ui import FakePage, _reset_palette, click, env, walk  # noqa: F401


def texts(view):
    return [c.value for c in walk(view) if isinstance(c, ft.Text)]


def mosaic_tiles(view):
    names = {t.title for t in TOOLS}
    return [c for c in walk(view) if isinstance(c, ft.Container) and c.tooltip in names]


# ------------------------------------------------------------------ contenu calculé
def test_mosaic_has_one_clickable_tile_per_tool_and_opens_it(env):
    routes = []
    env.page.push_route = "push_route"
    env.page.run_task = lambda fn, route=None, *a, **k: routes.append(route)
    view = build_about(env.page, env.notify)
    tiles = mosaic_tiles(view)
    assert sorted(t.tooltip for t in tiles) == sorted(t.title for t in TOOLS)
    signing = next(t for t in tiles if t.tooltip == "Signer un PDF")
    signing.on_click(None)
    assert routes == ["/signature"]
    assert f"{len(TOOLS)} outils · {len({t.group for t in TOOLS})} catégories" in " ".join(texts(view))


def test_library_versions_are_the_installed_ones(env):
    shown = " ".join(texts(build_about(env.page, env.notify)))
    for library, version in diagnostics.library_versions():
        assert library.label in shown
        assert (version or "indisponible") in shown


def test_missing_library_is_reported_not_invented(env, monkeypatch):
    monkeypatch.setattr(diagnostics, "installed_version", lambda name: None if name == "cryptography" else "9.9")
    monkeypatch.setattr(diagnostics, "library_versions", lambda lookup=diagnostics.installed_version: [
        (lib, None if lib.package == "cryptography" else "9.9") for lib in diagnostics.LIBRARIES])
    import app.presentation.screens.about_screen as module
    monkeypatch.setattr(module, "library_versions", diagnostics.library_versions)
    view = build_about(env.page, env.notify)
    missing = [c for c in walk(view) if isinstance(c, ft.Text) and c.value == "indisponible"]
    assert len(missing) == 1 and missing[0].color == Palette.danger


def test_promises_and_journey_are_present(env):
    shown = " ".join(texts(build_about(env.page, env.notify)))
    for _icon, title, detail in PROMISES:
        assert title in shown and detail in shown
    assert "Votre PDF" in shown and "Aucune connexion Internet" in shown


def test_exactly_one_heart_and_author_block_kept(env):
    view = build_about(env.page, env.notify)
    assert len([c for c in walk(view) if isinstance(c, ft.Icon) and c.icon == ft.Icons.FAVORITE]) == 1
    assert "Développeuse · Madagascar" in texts(view) and f"Version {__version__}" in texts(view)


# ------------------------------------------------------------------ logo interactif
def fan_pages(view):
    return [c for c in walk(view) if isinstance(c, ft.Container) and c.rotate is not None]


def test_logo_tap_opens_the_fan_and_cycles_taglines(env):
    view = build_about(env.page, env.notify)
    tagline = next(t for t in walk(view) if isinstance(t, ft.Text) and t.value == TAGLINES[0])
    logo = next(c for c in walk(view) if isinstance(c, ft.Container) and c.tooltip == "Touchez-moi")
    import math
    angles = lambda: sorted(round(math.degrees(p.rotate.angle)) for p in fan_pages(view))
    assert angles() == sorted(FAN_CLOSED)
    logo.on_click(None)
    assert angles() == sorted(FAN_OPEN) and tagline.value == TAGLINES[1]
    logo.on_click(None)
    assert angles() == sorted(FAN_CLOSED) and tagline.value == TAGLINES[2]
    for _ in range(len(TAGLINES) - 2):
        logo.on_click(None)
    assert tagline.value == TAGLINES[0]  # la boucle revient au début


# ------------------------------------------------------------------ diagnostic
def test_diagnostic_report_has_versions_and_no_personal_data():
    report = diagnostics.build_report("PDF Studio", "1.2.1", lookup=lambda p: {"flet": "1.0.3", "pypdf": "5.9"}.get(p))
    lines = report.splitlines()
    assert lines[0] == "PDF Studio 1.2.1" and "Flet : 1.0.3" in lines and "pypdf : 5.9" in lines
    assert "cryptography : indisponible" in lines and "Pillow : indisponible" in lines
    import getpass, os
    assert getpass.getuser() not in report and os.path.expanduser("~") not in report


def test_copy_diagnostic_button(env, monkeypatch):
    copied = []

    class Clip:
        async def set(self, value): copied.append(value)

    monkeypatch.setattr(ft, "Clipboard", Clip)
    click(build_about(env.page, env.notify), "Copier les infos de diagnostic")
    assert copied and copied[0].startswith(f"{APP_NAME} {__version__}")
    assert env.notes[-1][1] is False and "collez-les" in env.notes[-1][0]


def test_copy_diagnostic_failure_is_reported(env, monkeypatch):
    class Broken:
        async def set(self, *a, **k): raise RuntimeError("non")

    monkeypatch.setattr(ft, "Clipboard", Broken)
    click(build_about(env.page, env.notify), "Copier les infos de diagnostic")
    assert env.notes[-1] == ("Copie impossible sur cet appareil.", True, None)


def test_existing_data_file(tmp_path):
    assert diagnostics.existing_data_file(tmp_path) is None
    (tmp_path / "recents.json").write_text("[]")
    assert diagnostics.existing_data_file(tmp_path).name == "recents.json"
    (tmp_path / "settings.json").write_text("{}")
    assert diagnostics.existing_data_file(tmp_path).name == "settings.json"


def test_data_folder_shown_and_open_button_only_on_desktop(env, monkeypatch, tmp_path):
    import app.presentation.screens.about_screen as module
    (tmp_path / "settings.json").write_text("{}")
    monkeypatch.setattr(module, "app_data_dir", lambda: tmp_path)
    desktop = build_about(env.page, env.notify)
    assert str(tmp_path) in texts(desktop)
    assert any(isinstance(c, (ft.Button, ft.OutlinedButton)) and getattr(c, "content", None) == "Ouvrir le dossier" for c in walk(desktop))
    mobile = FakePage(mobile=True)
    view = build_about(mobile, env.notify)
    assert not any(isinstance(c, (ft.Button, ft.OutlinedButton)) and getattr(c, "content", None) == "Ouvrir le dossier" for c in walk(view))
