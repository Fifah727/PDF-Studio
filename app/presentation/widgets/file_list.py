from __future__ import annotations

from pathlib import Path
from typing import Callable

import flet as ft

from app.presentation.theme import Palette, Space, ToolAccent


class FileList(ft.Column):
    """
    Liste ordonnée de fichiers : ajout, retrait et réorganisation (↑ / ↓).

    L'ordre affiché est l'ordre de traitement (fusion, pages du PDF).
    """

    def __init__(
        self,
        tool: ToolAccent,
        icon: str,
        empty_text: str,
        on_change: Callable[[], None] | None = None,
    ):
        super().__init__(spacing=8)
        self.paths: list[str] = []
        self._tool = tool
        self._icon = icon
        self._empty_text = empty_text
        self._on_change = on_change
        self._render()

    # -- API publique -----------------------------------------------------
    def add(self, new_paths: list[str]) -> None:
        self.paths.extend(new_paths)
        self._render()

    def clear(self) -> None:
        self.paths.clear()
        self._render()

    # -- interne ----------------------------------------------------------
    def _move(self, index: int, delta: int) -> None:
        target = index + delta
        if 0 <= target < len(self.paths):
            self.paths[index], self.paths[target] = self.paths[target], self.paths[index]
            self._render()

    def _remove(self, index: int) -> None:
        self.paths.pop(index)
        self._render()

    def _row(self, index: int, path: str) -> ft.Control:
        last = len(self.paths) - 1
        return ft.Container(
            padding=ft.Padding(left=Space.sm, right=Space.sm, top=Space.sm, bottom=Space.sm),
            bgcolor=Palette.surface,
            border=ft.Border.all(1, Palette.line),
            border_radius=10,
            content=ft.Row(
                [
                    ft.Container(
                        width=22,
                        height=22,
                        border_radius=11,
                        bgcolor=self._tool.soft,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Text(
                            str(index + 1),
                            size=11,
                            weight=ft.FontWeight.W_700,
                            color=self._tool.color,
                        ),
                    ),
                    ft.Icon(self._icon, size=17, color=Palette.ink_muted),
                    ft.Text(
                        Path(path).name,
                        expand=True,
                        size=13,
                        color=Palette.ink,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        tooltip=path,
                    ),
                    ft.IconButton(
                        ft.Icons.ARROW_UPWARD,
                        icon_size=16,
                        icon_color=Palette.ink_muted,
                        tooltip="Monter",
                        disabled=index == 0,
                        on_click=lambda _, i=index: self._move(i, -1),
                    ),
                    ft.IconButton(
                        ft.Icons.ARROW_DOWNWARD,
                        icon_size=16,
                        icon_color=Palette.ink_muted,
                        tooltip="Descendre",
                        disabled=index == last,
                        on_click=lambda _, i=index: self._move(i, 1),
                    ),
                    ft.IconButton(
                        ft.Icons.CLOSE,
                        icon_size=16,
                        icon_color=Palette.ink_muted,
                        tooltip="Retirer",
                        on_click=lambda _, i=index: self._remove(i),
                    ),
                ],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def _render(self) -> None:
        if self.paths:
            self.controls = [self._row(i, p) for i, p in enumerate(self.paths)]
        else:
            self.controls = [
                ft.Container(
                    padding=Space.lg,
                    border=ft.Border.all(1, Palette.line),
                    border_radius=6,
                    alignment=ft.Alignment(0, 0),
                    content=ft.Text(
                        self._empty_text,
                        italic=True,
                        size=13,
                        color=Palette.ink_muted,
                    ),
                )
            ]
        try:
            self.update()
        except RuntimeError:
            pass  # pas encore monté sur la page (construction de l'écran)
        if self._on_change:
            self._on_change()
