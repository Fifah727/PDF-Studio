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

LOTTIE_SRC = "animations/delete_pdf.json"  # dans assets/animations/


def build_delete(
    page: ft.Page, use_cases: UseCases, picker: FilePickerService, notify
) -> ft.View:
    tool = Palette.delete
    state = {"path": None, "total": None}
    tray = FileTray(tool)
    selection = pages_field(tool.color, "Pages à supprimer", "Ex. 3 ou 2-4, 7")

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
        if not check(notify, lambda: use_cases.delete_pages.validate(path, text)):
            return
        await run_save(
            notify,
            picker,
            "Enregistrer le résultat",
            suggest_name(path, "_modifie"),
            lambda destination: use_cases.delete_pages.execute(path, text, destination),
            "Nouveau PDF créé",
        )

    action = primary_button("Supprimer et enregistrer", ft.Icons.DELETE_OUTLINE, tool.color, launch)
    refresh = bind_ready(
        action, lambda: bool(state["path"]) and bool((selection.value or "").strip())
    )
    choose, clear = pdf_chooser(picker, use_cases, tray, state, refresh)
    tray.bind(choose, clear)
    selection.on_change = lambda _: refresh()
    selection.on_submit = launch

    return page_shell(
        page,
        "Supprimer des pages",
        tool,
        [*illustration, tray, selection, action],
        icon=ft.Icons.DELETE_OUTLINE,
        description="Retire une ou plusieurs pages du PDF et conserve l'original intact.",
    )