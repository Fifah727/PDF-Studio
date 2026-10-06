from __future__ import annotations

import flet as ft

from app.presentation.di import UseCases
from app.presentation.screens.base import (
    FilePickerService,
    bind_ready,
    check,
    page_shell,
    pdf_chooser,
    run_save,
    suggest_name,
)
from app.presentation.theme import Palette
from app.presentation.widgets.buttons import primary_button
from app.presentation.widgets.fields import pages_field
from app.presentation.widgets.file_tray import FileTray
from app.presentation.widgets.lottie import lottie

LOTTIE_SRC = "animations/rotate_pdf.json"  # dans assets/animations/


def build_rotate(
    page: ft.Page, use_cases: UseCases, picker: FilePickerService, notify
) -> ft.View:
    tool = Palette.rotate
    state = {"path": None, "total": None}
    tray = FileTray(tool)
    selection = pages_field(tool.color, "Pages à pivoter", "Vide = toutes les pages")
    angle = ft.Dropdown(
        label="Rotation",
        value="90",
        options=[
            ft.DropdownOption(key="90", text="90° vers la droite"),
            ft.DropdownOption(key="180", text="180°"),
            ft.DropdownOption(key="270", text="90° vers la gauche"),
        ],
        border_color=Palette.line_strong,
        focused_border_color=tool.color,
    )

    animation = lottie(LOTTIE_SRC, 150)
    illustration: list[ft.Control] = (
        [ft.Row([animation], alignment=ft.MainAxisAlignment.CENTER)] if animation else []
    )

    async def launch(_=None):
        path = state["path"]
        if not path:
            notify("Sélectionnez d'abord un PDF.", True)
            return
        text = selection.value or ""
        degrees = int(angle.value or 90)
        if not check(notify, lambda: use_cases.rotate_pages.validate(path, text, degrees)):
            return
        await run_save(
            notify,
            picker,
            "Enregistrer le PDF pivoté",
            suggest_name(path, "_pivote"),
            lambda destination: use_cases.rotate_pages.execute(
                path, text, degrees, destination
            ),
            "PDF pivoté créé",
        )

    action = primary_button("Pivoter et enregistrer", ft.Icons.ROTATE_RIGHT, tool.color, launch)
    refresh = bind_ready(action, lambda: bool(state["path"]))
    choose, clear = pdf_chooser(picker, use_cases, tray, state, refresh)
    tray.bind(choose, clear)
    selection.on_submit = launch

    return page_shell(
        page,
        "Pivoter des pages",
        tool,
        [*illustration, tray, selection, angle, action],
        icon=ft.Icons.ROTATE_RIGHT,
        description="Redresse des pages scannées à l'envers ou couchées.",
    )