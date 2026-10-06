from __future__ import annotations

from typing import Callable

import flet as ft

from app.presentation.theme import Palette


def primary_button(
    label: str, icon: str, accent: str, on_click: Callable
) -> ft.Button:
    return ft.Button(
        content=label,
        icon=icon,
        on_click=on_click,
        style=ft.ButtonStyle(
            bgcolor={
                ft.ControlState.DEFAULT: accent,
                ft.ControlState.DISABLED: Palette.line,
            },
            color={
                ft.ControlState.DEFAULT: Palette.surface,
                ft.ControlState.DISABLED: Palette.ink_muted,
            },
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=ft.Padding(left=22, right=22, top=17, bottom=17),
            elevation=0,
        ),
    )


def secondary_button(label: str, icon: str, on_click: Callable) -> ft.OutlinedButton:
    return ft.OutlinedButton(
        content=label,
        icon=icon,
        on_click=on_click,
        style=ft.ButtonStyle(
            color=Palette.ink,
            side=ft.BorderSide(1, Palette.line_strong),
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=ft.Padding(left=18, right=18, top=14, bottom=14),
        ),
    )
