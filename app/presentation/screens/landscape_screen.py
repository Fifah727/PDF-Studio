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

LOTTIE_SRC = "animations/landscape_pdf.json"  # dans assets/animations/


def build_landscape(
    page: ft.Page, use_cases: UseCases, picker: FilePickerService, notify
) -> ft.View:
    tool = Palette.landscape
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
            "Enregistrer le PDF paysage",
            suggest_name(path, "_paysage"),
            lambda destination: use_cases.landscape_pair.execute(path, destination),
            "PDF paysage créé",
        )

    action = primary_button(
        "Convertir et enregistrer", ft.Icons.VIEW_COLUMN_OUTLINED, tool.color, launch
    )
    refresh = bind_ready(action, lambda: bool(state["path"]))
    choose, clear = pdf_chooser(
        picker, use_cases, tray, state, refresh,
        describe=lambda total: f"{total} page(s) → {(total + 1) // 2} feuille(s) paysage",
    )
    tray.bind(choose, clear)

    return page_shell(
        page,
        "Pages en paysage",
        tool,
        [*illustration, tray, action],
        icon=ft.Icons.VIEW_COLUMN_OUTLINED,
        description=(
            "Regroupe les pages deux par deux sur des feuilles paysage "
            "(deux pages A4 côte à côte, mises à l'échelle automatiquement)."
        ),
    )