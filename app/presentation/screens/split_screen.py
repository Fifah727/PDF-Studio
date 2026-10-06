from __future__ import annotations

import flet as ft

from app.presentation.di import UseCases
from app.presentation.screens.base import (
    FilePickerService,
    bind_ready,
    page_shell,
    pdf_chooser,
    run_save,
    suggest_name,
)
from app.presentation.theme import Palette
from app.presentation.widgets.buttons import primary_button
from app.presentation.widgets.file_tray import FileTray
from app.presentation.widgets.lottie import lottie

LOTTIE_SRC = "animations/split_pdf.json"  # dans assets/animations/


def build_split(
    page: ft.Page, use_cases: UseCases, picker: FilePickerService, notify
) -> ft.View:
    tool = Palette.split
    state = {"path": None, "total": None}
    tray = FileTray(tool)

    animation = lottie(LOTTIE_SRC, 150)
    illustration: list[ft.Control] = (
        [ft.Row([animation], alignment=ft.MainAxisAlignment.CENTER)] if animation else []
    )

    async def launch(_=None):
        path = state["path"]
        if not path:
            notify("Sélectionnez d'abord un PDF.", True)
            return
        await run_save(
            notify,
            picker,
            "Enregistrer les pages",
            suggest_name(path, "_pages", ".zip"),
            lambda destination: use_cases.split_pdf.execute(path, destination),
            "PDF divisé",
        )

    action = primary_button("Diviser et enregistrer", ft.Icons.CALL_SPLIT, tool.color, launch)
    refresh = bind_ready(action, lambda: bool(state["path"]))
    choose, clear = pdf_chooser(picker, use_cases, tray, state, refresh)
    tray.bind(choose, clear)

    return page_shell(
        page,
        "Diviser un PDF",
        tool,
        [*illustration, tray, action],
        icon=ft.Icons.CALL_SPLIT,
        description="Transforme chaque page en PDF individuel, livré dans une archive ZIP.",
    )