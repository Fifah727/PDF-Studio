"""Identité visuelle : le logo « éventail de pages », partagé par l'accueil et « À propos »."""

from __future__ import annotations

import math

import flet as ft

from app.presentation.theme import Palette

FAN_CLOSED = (-8, 0, 8)  # inclinaison des trois pages, en degrés
FAN_OPEN = (-26, 0, 26)

_PAPER = "#F6F4EC"  # papier clair, pour le logo posé sur un fond sombre (bandeau d'accueil)
_PAPER_LINE = "#D8D5C7"


def rotated(degrees: float) -> ft.Rotate:
    """Rotation autour du bas de la page : les pages s'ouvrent en éventail."""
    return ft.Rotate(angle=math.radians(degrees), alignment=ft.Alignment(0, 1))


def _fan_page(accent, angle: float, left: float, scale: float, on_dark: bool) -> ft.Container:
    """Une « page » en papier : bandeau coloré et fausses lignes de texte."""
    line_color = _PAPER_LINE if on_dark else Palette.line_strong

    def line(width: float) -> ft.Container:
        return ft.Container(
            width=width * scale, height=max(3.0, 4 * scale), border_radius=2, bgcolor=line_color
        )

    return ft.Container(
        left=left * scale,
        top=10 * scale,
        width=70 * scale,
        height=92 * scale,
        border_radius=10 * scale,
        bgcolor=_PAPER if on_dark else Palette.surface,
        border=ft.Border.all(1, line_color),
        rotate=rotated(angle),
        animate_rotation=ft.Animation(380, ft.AnimationCurve.EASE_OUT_BACK),
        padding=ft.Padding(
            left=10 * scale, right=10 * scale, top=12 * scale, bottom=10 * scale
        ),
        content=ft.Column(
            [
                ft.Container(
                    width=26 * scale, height=8 * scale, border_radius=4, bgcolor=accent.color
                ),
                line(48),
                line(40),
                line(46),
            ],
            spacing=7 * scale,
        ),
    )


def logo_fan(scale: float = 1.0, on_dark: bool = False) -> tuple[ft.Stack, list[ft.Container]]:
    """
    Pile de pages en éventail, avec l'icône de l'application sur la page du dessus.

    ``scale`` agrandit ou réduit tout le logo ; ``on_dark`` adapte les couleurs
    à un fond sombre. Renvoie le logo et ses trois pages (dans l'ordre gauche,
    milieu, droite) pour pouvoir les animer.
    """
    accents = (Palette.compress, Palette.merge, Palette.watermark)
    pages = [
        _fan_page(accent, angle, offset, scale, on_dark)
        for accent, angle, offset in zip(accents, FAN_CLOSED, (8, 38, 68))
    ]
    front = pages[1]
    front.padding = 0
    front.border_radius = 9 * scale
    front.content = ft.Container(
        alignment=ft.Alignment(0, 0),
        border_radius=9 * scale,
        bgcolor="#FFFFFF" if on_dark else None,
        gradient=None
        if on_dark
        else ft.LinearGradient(
            begin=ft.Alignment(-1, -1),
            end=ft.Alignment(1, 1),
            colors=[Palette.hero_start, Palette.hero_end],
        ),
        content=ft.Icon(
            ft.Icons.DESCRIPTION_OUTLINED,
            color=Palette.hero_start if on_dark else Palette.on_hero,
            size=34 * scale,
        ),
    )
    stack = ft.Stack([pages[0], pages[2], front], width=150 * scale, height=118 * scale)
    return stack, pages
