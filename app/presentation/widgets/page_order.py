"""Liste de pages réordonnable (↑ / ↓), pour l'outil « Réorganiser »."""

from __future__ import annotations

from typing import Callable

import flet as ft

from app.presentation.theme import Palette, Space, ToolAccent

MAX_LISTED_PAGES = 80  # au-delà, la liste serait pénible à parcourir : saisie au clavier


class PageOrderList(ft.Column):
    """L'ordre affiché est l'ordre des pages du PDF produit."""

    def __init__(self, tool: ToolAccent, on_change: Callable[[], None] | None = None):
        super().__init__(spacing=6)
        self._tool = tool
        self._on_change = on_change
        self.order: list[int] = []

    def load(self, total: int) -> None:
        self.order = list(range(1, total + 1))
        self._render()

    def clear(self) -> None:
        self.order = []
        self._render()

    def reverse(self) -> None:
        self.order.reverse()
        self._render()

    @property
    def is_modified(self) -> bool:
        return self.order != sorted(self.order)

    def move(self, index: int, delta: int) -> None:
        target = index + delta
        if 0 <= target < len(self.order):
            self.order[index], self.order[target] = self.order[target], self.order[index]
            self._render()

    # ------------------------------------------------------------ interne
    def _row(self, index: int, number: int) -> ft.Control:
        last = len(self.order) - 1
        return ft.Container(
            padding=ft.Padding(left=Space.sm, right=Space.sm, top=2, bottom=2),
            bgcolor=Palette.surface,
            border=ft.Border.all(1, Palette.line),
            border_radius=10,
            content=ft.Row(
                [
                    ft.Container(
                        width=28,
                        height=28,
                        border_radius=14,
                        bgcolor=self._tool.soft,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Text(
                            str(number), size=12, weight=ft.FontWeight.W_700, color=self._tool.color
                        ),
                    ),
                    ft.Text(f"Page {number}", expand=True, size=13, color=Palette.ink),
                    ft.IconButton(
                        ft.Icons.ARROW_UPWARD,
                        icon_size=22,
                        icon_color=Palette.ink_muted,
                        tooltip="Monter",
                        disabled=index == 0,
                        on_click=lambda _, i=index: self.move(i, -1),
                    ),
                    ft.IconButton(
                        ft.Icons.ARROW_DOWNWARD,
                        icon_size=22,
                        icon_color=Palette.ink_muted,
                        tooltip="Descendre",
                        disabled=index == last,
                        on_click=lambda _, i=index: self.move(i, 1),
                    ),
                ],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def _render(self) -> None:
        self.controls = [self._row(i, n) for i, n in enumerate(self.order)]
        try:
            self.update()
        except RuntimeError:
            pass  # pas encore monté sur la page
        if self._on_change:
            self._on_change()
