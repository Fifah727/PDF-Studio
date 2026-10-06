"""
Système de tokens visuels, clair et sombre.

Idée directrice : l'application manipule des documents papier, pas des
widgets logiciels génériques. Chaque outil porte sa propre couleur
d'accent, comme les onglets d'un classeur à intercalaires — elle identifie
l'outil dans la liste d'accueil puis se retrouve dans son écran (icône,
bouton principal, liseré). Le reste reste sobre : fond papier, encre
presque noire, bordures fines.

``Palette`` est volontairement mutable : ``Palette.apply(dark)`` bascule
toutes les couleurs d'un coup. Les écrans lisent ``Palette`` à leur
construction ; après un changement de thème on reconstruit donc la vue
courante (voir ``ThemeController``).
"""

from __future__ import annotations

from dataclasses import dataclass

import flet as ft


@dataclass(frozen=True, slots=True)
class ToolAccent:
    color: str
    soft: str


_LIGHT = dict(
    ink="#1E2422",
    ink_muted="#5B6560",
    paper="#F2F1EA",
    surface="#FFFFFF",
    line="#DEDBCF",
    line_strong="#C7C3B3",
    danger="#A6443B",
    danger_soft="#F5E3E0",
    success="#2F7D4F",
    success_soft="#E1EFE6",
    hero_start="#1E2422",
    hero_end="#33423D",
    on_hero="#FFFFFF",
    heart="#D94F5C",
    neutral=ToolAccent("#1E2422", "#E9E7DD"),
    split=ToolAccent("#2F6F63", "#E1EEE9"),
    extract=ToolAccent("#B8793A", "#F3E7D6"),
    merge=ToolAccent("#5C5490", "#E7E4F1"),
    delete=ToolAccent("#A6443B", "#F5E3E0"),
    landscape=ToolAccent("#3D6C8A", "#DDEAF0"),
    images=ToolAccent("#6B7A3A", "#E7ECD8"),
    rotate=ToolAccent("#8A6D1F", "#F2EBD3"),
    password=ToolAccent("#8C4A5E", "#F3E3E8"),
    reorder=ToolAccent("#4F6BA8", "#E2E8F4"),
    insert=ToolAccent("#2E7D8C", "#DCEDF0"),
    interleave=ToolAccent("#9A5B8F", "#F1E3EE"),
    crop=ToolAccent("#B05A2F", "#F4E4DA"),
    compress=ToolAccent("#2F7D4F", "#DFEEE4"),
    metadata=ToolAccent("#5E6B7A", "#E4E8EC"),
    bookmarks=ToolAccent("#7A5C2E", "#EFE6D8"),
    watermark=ToolAccent("#C0502F", "#F6E2DB"),
    signature=ToolAccent("#3F4FA0", "#E3E6F4"),
    numbering=ToolAccent("#2B7A78", "#DBEDEC"),
    images_out=ToolAccent("#8A5A9E", "#EDE2F1"),
    text_out=ToolAccent("#4A7C2E", "#E4EEDA"),
    batch=ToolAccent("#A0452F", "#F4E2DC"),
    unmark=ToolAccent("#7B4FA0", "#EBE2F3"),
)


_DARK = dict(
    ink="#ECEBE4",
    ink_muted="#A3ABA6",
    paper="#14181A",
    surface="#1E2427",
    line="#2D3538",
    line_strong="#46515A",
    danger="#E5897F",
    danger_soft="#3A2523",
    success="#78C99A",
    success_soft="#1D3527",
    hero_start="#1F2D31",
    hero_end="#2C4147",
    on_hero="#F1F0E9",
    heart="#F0707C",
    neutral=ToolAccent("#ECEBE4", "#2A3135"),
    split=ToolAccent("#5FB5A3", "#1D3A34"),
    extract=ToolAccent("#E0A163", "#3B2D1B"),
    merge=ToolAccent("#A39BDB", "#2B2845"),
    delete=ToolAccent("#E5897F", "#3A2523"),
    landscape=ToolAccent("#7FB2D1", "#1C3340"),
    images=ToolAccent("#A3B86A", "#2C3319"),
    rotate=ToolAccent("#D6B755", "#3A3115"),
    password=ToolAccent("#D58AA0", "#3C2530"),
    reorder=ToolAccent("#8FA8E0", "#222C42"),
    insert=ToolAccent("#6FC0CF", "#1B3338"),
    interleave=ToolAccent("#D69BCA", "#3A2536"),
    crop=ToolAccent("#E39A6F", "#3C281C"),
    compress=ToolAccent("#78C99A", "#1D3527"),
    metadata=ToolAccent("#A5B2C0", "#2A323A"),
    bookmarks=ToolAccent("#D6B27A", "#3A2F1C"),
    watermark=ToolAccent("#E88C6F", "#3D2620"),
    signature=ToolAccent("#8F9FE0", "#232846"),
    numbering=ToolAccent("#6FCAC7", "#1B3433"),
    images_out=ToolAccent("#C99BDB", "#33243B"),
    text_out=ToolAccent("#9CCB78", "#26341B"),
    batch=ToolAccent("#E58E78", "#3B2620"),
    unmark=ToolAccent("#BF9BE0", "#2F2440"),
)



class Palette:
    """Couleurs courantes. Clair par défaut ; ``apply`` change de thème."""

    dark = False

    ink: str
    ink_muted: str
    paper: str
    surface: str
    line: str
    line_strong: str
    danger: str
    danger_soft: str
    success: str
    success_soft: str
    hero_start: str
    hero_end: str
    on_hero: str
    heart: str
    neutral: ToolAccent
    split: ToolAccent
    extract: ToolAccent
    merge: ToolAccent
    delete: ToolAccent
    landscape: ToolAccent
    images: ToolAccent
    rotate: ToolAccent
    password: ToolAccent
    reorder: ToolAccent
    insert: ToolAccent
    interleave: ToolAccent
    crop: ToolAccent
    compress: ToolAccent
    metadata: ToolAccent
    bookmarks: ToolAccent
    watermark: ToolAccent
    signature: ToolAccent
    numbering: ToolAccent
    images_out: ToolAccent
    text_out: ToolAccent
    batch: ToolAccent
    unmark: ToolAccent

    @classmethod
    def apply(cls, dark: bool) -> None:
        cls.dark = dark
        for name, value in (_DARK if dark else _LIGHT).items():
            setattr(cls, name, value)


Palette.apply(False)


class Space:
    xs = 4
    sm = 8
    md = 14
    lg = 20
    xl = 28
    xxl = 40

    page_width = 720


def build_theme() -> ft.Theme:
    """Thème Flet construit depuis la palette courante (clair ou sombre)."""
    return ft.Theme(
        color_scheme=ft.ColorScheme(
            primary=Palette.ink,
            on_primary=Palette.surface,
            surface=Palette.surface,
            on_surface=Palette.ink,
            on_surface_variant=Palette.ink_muted,
            outline=Palette.line_strong,
            outline_variant=Palette.line,
            error=Palette.danger,
        ),
        scrollbar_theme=ft.ScrollbarTheme(
            thumb_color=Palette.line_strong,
            track_visibility=False,
        ),
        # Transition douce entre les écrans (fondu + léger glissement).
        page_transitions=ft.PageTransitionsTheme(
            android=ft.PageTransitionTheme.FADE_FORWARDS,
            ios=ft.PageTransitionTheme.CUPERTINO,
            linux=ft.PageTransitionTheme.FADE_UPWARDS,
            macos=ft.PageTransitionTheme.FADE_UPWARDS,
            windows=ft.PageTransitionTheme.FADE_UPWARDS,
        ),
    )
