from __future__ import annotations

import flet as ft

from app.presentation.theme import Palette

# Chiffres, virgules, tirets, points-virgules et espaces uniquement.
_PAGES_FILTER = ft.InputFilter(regex_string=r"[0-9,;\- ]", allow=True)


def pages_field(accent: str, label: str, hint: str) -> ft.TextField:
    """Champ de sélection de pages : « 1-3, 5, 8-10 »."""
    return ft.TextField(
        label=label,
        hint_text=hint,
        helper="Pages séparées par des virgules, plages avec un tiret.",
        input_filter=_PAGES_FILTER,
        border_color=Palette.line_strong,
        focused_border_color=accent,
    )


def password_field(accent: str, label: str) -> ft.TextField:
    return ft.TextField(
        label=label,
        password=True,
        can_reveal_password=True,
        border_color=Palette.line_strong,
        focused_border_color=accent,
    )
