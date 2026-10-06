"""Champs de formulaire communs aux outils avancés."""

from __future__ import annotations

from typing import Callable, Sequence

import flet as ft

from app.domain.exceptions import InvalidOptionError, PdfError
from app.domain.options import Position
from app.presentation.theme import Palette

_DIGITS = ft.InputFilter(regex_string=r"[0-9]", allow=True)
_DECIMAL = ft.InputFilter(regex_string=r"[0-9.,]", allow=True)

POSITION_LABELS: Sequence[tuple[Position, str]] = (
    (Position.TOP_LEFT, "En haut à gauche"),
    (Position.TOP_CENTER, "En haut au centre"),
    (Position.TOP_RIGHT, "En haut à droite"),
    (Position.MIDDLE_LEFT, "Au milieu à gauche"),
    (Position.CENTER, "Au centre"),
    (Position.MIDDLE_RIGHT, "Au milieu à droite"),
    (Position.BOTTOM_LEFT, "En bas à gauche"),
    (Position.BOTTOM_CENTER, "En bas au centre"),
    (Position.BOTTOM_RIGHT, "En bas à droite"),
)


def choice(
    label: str,
    options: Sequence[tuple[str, str]],
    value: str,
    accent: str,
    on_change: Callable | None = None,
) -> ft.Dropdown:
    """Liste déroulante ``(clé, libellé)``."""
    return ft.Dropdown(
        label=label,
        value=value,
        options=[ft.DropdownOption(key=key, text=text) for key, text in options],
        border_color=Palette.line_strong,
        focused_border_color=accent,
        on_select=on_change,
    )


def position_choice(accent: str, value: Position, label: str = "Emplacement") -> ft.Dropdown:
    return choice(label, [(p.value, text) for p, text in POSITION_LABELS], value.value, accent)


def text_input(
    label: str,
    accent: str,
    value: str = "",
    hint: str | None = None,
    helper: str | None = None,
    on_change: Callable | None = None,
    multiline: bool = False,
    max_length: int | None = None,
) -> ft.TextField:
    return ft.TextField(
        label=label,
        value=value,
        hint_text=hint,
        helper=helper,
        multiline=multiline,
        min_lines=4 if multiline else None,
        max_lines=12 if multiline else 1,
        max_length=max_length,
        border_color=Palette.line_strong,
        focused_border_color=accent,
        on_change=on_change,
    )


def number_input(
    label: str,
    accent: str,
    value: str = "",
    suffix: str | None = None,
    decimal: bool = False,
    helper: str | None = None,
    on_change: Callable | None = None,
    expand: bool = False,
) -> ft.TextField:
    return ft.TextField(
        label=label,
        value=value,
        suffix=suffix,
        helper=helper,
        keyboard_type=ft.KeyboardType.NUMBER,
        input_filter=_DECIMAL if decimal else _DIGITS,
        border_color=Palette.line_strong,
        focused_border_color=accent,
        on_change=on_change,
        expand=expand,
    )


def percent_slider(
    accent: str, value: int, low: int = 5, high: int = 100, on_change: Callable | None = None
) -> ft.Slider:
    return ft.Slider(
        min=low,
        max=high,
        value=value,
        divisions=(high - low) // 5,
        label="{value} %",
        active_color=accent,
        on_change=on_change,
    )


def labelled(title: str, control: ft.Control) -> ft.Column:
    """Petit titre au-dessus d'un contrôle sans label propre (curseur…)."""
    return ft.Column(
        [ft.Text(title, size=13, color=Palette.ink_muted), control], spacing=0, tight=True
    )


# ------------------------------------------------------------------ lecture
def read_int(text: str | None, label: str, default: int | None = None) -> int:
    cleaned = (text or "").strip()
    if not cleaned:
        if default is not None:
            return default
        raise InvalidOptionError(f"{label} : saisissez un nombre.")
    try:
        return int(cleaned)
    except ValueError:
        raise InvalidOptionError(f"{label} : « {cleaned} » n'est pas un nombre entier.") from None


def read_float(text: str | None, label: str, default: float | None = None) -> float:
    cleaned = (text or "").strip().replace(",", ".")
    if not cleaned:
        if default is not None:
            return default
        raise InvalidOptionError(f"{label} : saisissez un nombre.")
    try:
        return float(cleaned)
    except ValueError:
        raise InvalidOptionError(f"{label} : « {cleaned} » n'est pas un nombre.") from None


# ------------------------------------------------------------------ validation en direct
def live_check(
    field: ft.TextField,
    validator: Callable[[str], object],
    then: Callable[[], None] | None = None,
) -> ft.TextField:
    """
    Valide ``field`` à chaque frappe et affiche l'erreur sous le champ.

    Un champ vide n'est pas une erreur (le bouton reste simplement
    désactivé) : on ne reproche rien tant que l'utilisateur n'a rien saisi.
    ``then`` est rappelé après chaque validation (réévaluation du bouton).
    """

    def handler(_=None) -> None:
        text = field.value or ""
        message = None
        if text.strip():
            try:
                validator(text)
            except (PdfError, ValueError) as exc:
                message = str(exc)
        field.error = message
        try:
            field.update()
        except RuntimeError:
            pass  # pas encore monté
        if then:
            then()

    field.on_change = handler
    return field
