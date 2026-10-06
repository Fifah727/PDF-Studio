"""Accueil : salutation, accès rapide, en-têtes de catégorie, bandeau « Ouvrir », historique."""

from datetime import datetime

import flet as ft
import pytest

from app.infrastructure.recent_files_store import JsonRecentFilesStore
from app.presentation.router import TOOL_SCREENS
from app.presentation.screens.home_screen import (
    GROUP_ICONS,
    QUICK_ACCESS,
    TOOLS,
    build_home,
    greeting,
)
from app.presentation.widgets.brand import FAN_CLOSED, logo_fan
from tests.test_ui import FakePage, _reset_palette, env, find, walk  # noqa: F401


def texts(view):
    return [c.value for c in walk(view) if isinstance(c, ft.Text)]


def at(hour):
    return lambda: datetime(2026, 10, 5, hour, 30)


def navigate(env):
    """Remplace la navigation du double de page par un enregistreur de routes."""
    routes = []
    env.page.push_route = "push_route"
    env.page.run_task = lambda fn, route=None, *a, **k: routes.append(route)
    return routes


# ------------------------------------------------------------------ salutation
@pytest.mark.parametrize(
    "hour,expected",
    [(0, "Bonsoir"), (4, "Bonsoir"), (5, "Bonjour"), (11, "Bonjour"), (12, "Bon après-midi"),
     (17, "Bon après-midi"), (18, "Bonsoir"), (23, "Bonsoir")],
)
def test_greeting_follows_the_hour(hour, expected):
    assert greeting(hour) == expected


def test_hero_shows_the_greeting_of_the_moment(env):
    assert "Bonjour" in texts(build_home(env.page, now=at(9)))
    assert "Bon après-midi" in texts(build_home(env.page, now=at(15)))
    assert "Bonsoir" in texts(build_home(env.page, now=at(21)))


def test_hero_logo_opens_about(env):
    routes = navigate(env)
    view = build_home(env.page, now=at(9))
    logo = next(c for c in walk(view) if isinstance(c, ft.Container) and c.tooltip == "À propos" and isinstance(c.content, ft.Stack))
    logo.on_click(None)
    assert routes == ["/a-propos"]


# ------------------------------------------------------------------ accès rapide
def test_quick_access_points_to_real_tools_with_short_unique_labels():
    routes = {tool.route for tool in TOOLS}
    titles = {tool.title for tool in TOOLS}
    assert {route for route, _ in QUICK_ACCESS} <= routes
    assert all(label not in titles for _, label in QUICK_ACCESS)  # un titre ne s'affiche qu'une fois
    assert {route for route, _ in QUICK_ACCESS} <= set(TOOL_SCREENS)


def test_quick_access_tiles_open_their_tool(env):
    routes = navigate(env)
    view = build_home(env.page, now=at(9))
    assert "ACCÈS RAPIDE" in texts(view)
    for route, label in QUICK_ACCESS:
        tile = next(c for c in walk(view) if isinstance(c, ft.Container) and c.on_click and isinstance(c.content, ft.Column)
                    and any(isinstance(t, ft.Text) and t.value == label for t in walk(c.content)))
        tile.on_click(None)
        assert routes[-1] == route


def test_quick_access_hidden_while_filtering(env):
    view = build_home(env.page, now=at(9))
    search = find(view, ft.TextField)
    search.value = "fusion"
    search.on_change(None)
    assert "ACCÈS RAPIDE" not in texts(view)
    search.value = ""
    search.on_change(None)
    assert "ACCÈS RAPIDE" in texts(view)


# ------------------------------------------------------------------ en-têtes de catégorie
def test_every_group_has_an_icon_and_a_header_with_its_count(env):
    assert {tool.group for tool in TOOLS} <= set(GROUP_ICONS)
    view = build_home(env.page, now=at(9))
    shown = texts(view)
    for group in dict.fromkeys(tool.group for tool in TOOLS):
        count = sum(1 for tool in TOOLS if tool.group == group)
        assert str(count) in shown and shown.count(group) >= 2  # puce de filtre + en-tête


def test_group_filter_keeps_only_that_header(env):
    view = build_home(env.page, now=at(9))
    chip = next(c for c in walk(view) if isinstance(c, ft.Container) and isinstance(c.content, ft.Text) and c.content.value == "Extraire")
    chip.on_click(None)
    shown = texts(view)
    assert "Organiser" in shown  # reste une puce de filtre…
    assert shown.count("Extraire") == 2 and shown.count("Organiser") == 1  # …mais plus d'en-tête


# ------------------------------------------------------------------ bandeau « Ouvrir »
def test_open_banner_appears_only_for_a_single_match_and_opens_it(env):
    routes = navigate(env)
    view = build_home(env.page, now=at(9))
    search = find(view, ft.TextField)
    banner = next(c for c in walk(view) if isinstance(c, ft.Container) and c.visible is False and c.ink and c.border_radius == 14 and c.content is None)

    search.value = "signer"
    search.on_change(None)
    assert banner.visible and "Ouvrir « Signer un PDF »" in texts(view)
    banner.on_click(None)
    assert routes == ["/signature"]

    search.value = "pages"  # plusieurs résultats : pas de bandeau
    search.on_change(None)
    assert banner.visible is False and not any(t.startswith("Ouvrir « ") for t in texts(view))

    search.value = ""
    search.on_change(None)
    assert banner.visible is False


# ------------------------------------------------------------------ historique : retirer un élément
def test_each_recent_file_can_be_removed_individually(env, tmp_path):
    store = JsonRecentFilesStore(tmp_path / "r.json")
    store.add("/x/un.pdf", "PDF créé")
    store.add("/x/deux.pdf", "PDF compressé")
    view = build_home(env.page, store, now=at(9))
    buttons = [c for c in walk(view) if isinstance(c, ft.IconButton) and c.tooltip == "Retirer de la liste"]
    assert len(buttons) == 2
    buttons[0].on_click(None)  # le plus récent : deux.pdf
    assert [i.path for i in store.items] == ["/x/un.pdf"]
    shown = texts(view)
    assert "un.pdf" in shown and "deux.pdf" not in shown and "RÉCENTS" in shown
    [b for b in walk(view) if isinstance(b, ft.IconButton) and b.tooltip == "Retirer de la liste"][0].on_click(None)
    assert store.items == [] and "RÉCENTS" not in texts(view)


def test_store_remove(tmp_path):
    store = JsonRecentFilesStore(tmp_path / "r.json")
    store.add("/a.pdf", "ok")
    assert store.remove("/a.pdf") is True and store.remove("/a.pdf") is False
    assert JsonRecentFilesStore(tmp_path / "r.json").items == []


# ------------------------------------------------------------------ logo partagé
def test_logo_fan_scales_and_adapts_to_dark_backgrounds():
    big, big_pages = logo_fan(1.0)
    small, small_pages = logo_fan(0.5)
    assert (small.width, small.height) == (big.width / 2, big.height / 2)
    assert [round(__import__("math").degrees(p.rotate.angle)) for p in big_pages] == list(FAN_CLOSED)
    on_dark, dark_pages = logo_fan(1.0, on_dark=True)
    assert dark_pages[0].bgcolor != big_pages[0].bgcolor  # papier clair sur fond sombre


def test_home_cards_wear_a_tint_and_stay_themed(env):
    light = build_home(env.page, now=at(9))
    env.theme.set_mode("dark")
    dark = build_home(env.page, now=at(9))
    gradients = lambda v: [c.gradient.colors for c in walk(v) if getattr(c, "gradient", None)]  # noqa: E731
    assert len(gradients(light)) > 23 and gradients(light) != gradients(dark)
