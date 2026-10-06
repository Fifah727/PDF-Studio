from __future__ import annotations

from pathlib import Path
from typing import Callable

import flet as ft

from app.presentation.theme import Palette, Space, ToolAccent


def human_size(size: int) -> str:
    """Taille lisible, à la française : ``1,2 Mo``."""
    value = float(size)
    for unit in ("o", "Ko", "Mo", "Go"):
        if value < 1024 or unit == "Go":
            text = f"{value:.0f}" if unit == "o" else f"{value:.1f}".replace(".", ",")
            return f"{text} {unit}"
        value /= 1024
    return f"{size} o"


class FileTray(ft.Container):
    """
    Emplacement d'un fichier PDF : toute la zone est cliquable.

    Vide, il invite à choisir un fichier ; rempli, il montre le nom, le
    nombre de pages et la taille, avec un bouton pour changer et une croix
    pour retirer la sélection. Une erreur de lecture (PDF protégé,
    fichier corrompu) s'affiche en rouge directement dans la zone.
    """

    _EMPTY_HINT = "Cliquez ici pour parcourir vos dossiers"

    def __init__(
        self,
        tool: ToolAccent,
        on_pick: Callable | None = None,
        on_clear: Callable | None = None,
        pick_label: str = "Choisir un PDF",
    ):
        self._accent = tool.color
        self._soft = tool.soft
        self._pick_label = pick_label
        self._on_clear = on_clear
        self.has_file = False

        self._icon = ft.Icon(ft.Icons.FILE_UPLOAD_OUTLINED, color=tool.color, size=24)
        self._tile = ft.Container(
            width=48,
            height=48,
            border_radius=12,
            bgcolor=tool.soft,
            alignment=ft.Alignment(0, 0),
            content=self._icon,
        )
        self._label = ft.Text(
            "Aucun fichier sélectionné",
            size=14,
            weight=ft.FontWeight.W_600,
            color=Palette.ink,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        self._meta = ft.Text(self._EMPTY_HINT, size=12.5, color=Palette.ink_muted)
        self.pick_button = ft.OutlinedButton(
            content=pick_label,
            on_click=on_pick,
            style=ft.ButtonStyle(
                color=Palette.ink,
                side=ft.BorderSide(1, Palette.line_strong),
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
        )
        self.clear_button = ft.IconButton(
            ft.Icons.CLOSE,
            icon_size=18,
            icon_color=Palette.ink_muted,
            tooltip="Retirer le fichier",
            visible=False,
            on_click=self._clear,
        )

        super().__init__(
            content=ft.Row(
                [
                    self._tile,
                    ft.Column([self._label, self._meta], spacing=2, expand=True),
                    self.clear_button,
                    self.pick_button,
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=Space.sm,
            ),
            padding=Space.md,
            border=ft.Border.all(1, Palette.line),
            border_radius=14,
            bgcolor=Palette.surface,
            ink=True,
            on_click=on_pick,
        )

    def bind(self, on_pick: Callable, on_clear: Callable | None = None) -> "FileTray":
        """Branche les gestionnaires une fois créés (ils ont besoin du tray)."""
        self.on_click = on_pick
        self.pick_button.on_click = on_pick
        self._on_clear = on_clear
        return self

    # ------------------------------------------------------------ état
    def set_empty(self, prompt: str = "Aucun fichier sélectionné") -> None:
        self.has_file = False
        self._icon.icon = ft.Icons.FILE_UPLOAD_OUTLINED
        self._icon.color = self._accent
        self._tile.bgcolor = self._soft
        self._label.value = prompt
        self._label.color = Palette.ink
        self._label.weight = ft.FontWeight.W_600
        self._meta.value = self._EMPTY_HINT
        self._meta.color = Palette.ink_muted
        self.clear_button.visible = False
        self.pick_button.content = self._pick_label
        self.border = ft.Border.all(1, Palette.line)
        self._refresh()

    def set_file(self, path: str, meta: str = "", error: bool = False) -> None:
        self.has_file = True
        try:
            size = human_size(Path(path).stat().st_size)
        except OSError:
            size = ""
        details = " · ".join(part for part in (meta, size) if part)

        tone = Palette.danger if error else self._accent
        self._icon.icon = ft.Icons.ERROR_OUTLINE if error else ft.Icons.DESCRIPTION_OUTLINED
        self._icon.color = tone
        self._tile.bgcolor = Palette.danger_soft if error else self._soft
        self._label.value = Path(path).name
        self._label.color = Palette.ink
        self._label.weight = ft.FontWeight.W_600
        self._meta.value = meta if error else details
        self._meta.color = Palette.danger if error else Palette.ink_muted
        self.clear_button.visible = self._on_clear is not None
        self.pick_button.content = "Changer"
        self.border = ft.Border.only(
            left=ft.BorderSide(3, tone),
            top=ft.BorderSide(1, Palette.line),
            right=ft.BorderSide(1, Palette.line),
            bottom=ft.BorderSide(1, Palette.line),
        )
        self._refresh()

    def _clear(self, event) -> None:
        self.set_empty()
        if self._on_clear:
            self._on_clear(event)

    def _refresh(self) -> None:
        try:
            self.update()
        except RuntimeError:
            pass  # pas encore monté sur la page
