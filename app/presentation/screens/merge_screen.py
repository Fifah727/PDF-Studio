from __future__ import annotations

import flet as ft

from app.presentation.di import UseCases
from app.presentation.screens.base import (
    FilePickerService,
    bind_ready,
    page_shell,
    run_save,
)
from app.presentation.theme import Palette
from app.presentation.widgets.buttons import primary_button, secondary_button
from app.presentation.widgets.file_list import FileList
from app.presentation.widgets.lottie import lottie

LOTTIE_SRC = "animations/fusion_document.json"  # dans assets/animations/


def build_merge(
    page: ft.Page, use_cases: UseCases, picker: FilePickerService, notify
) -> ft.View:
    tool = Palette.merge
    refresh = lambda: None  # noqa: E731  (remplacé plus bas, une fois le bouton créé)
    files = FileList(
        tool,
        ft.Icons.DESCRIPTION_OUTLINED,
        "Aucun PDF sélectionné — ajoutez au moins deux fichiers.",
        on_change=lambda: refresh(),
    )

    animation = lottie(LOTTIE_SRC, 150, reverse=True)
    illustration: list[ft.Control] = (
        [ft.Row([animation], alignment=ft.MainAxisAlignment.CENTER)] if animation else []
    )

    async def choose(_=None):
        paths = await picker.pick_pdf(multiple=True)
        if paths:
            files.add(paths)

    def clear(_=None):
        files.clear()

    async def launch(_=None):
        paths = list(files.paths)
        if len(paths) < 2:
            notify("Sélectionnez au moins 2 PDF.", True)
            return
        await run_save(
            notify,
            picker,
            "Enregistrer le PDF fusionné",
            "fusion.pdf",
            lambda destination: use_cases.merge_pdfs.execute(paths, destination),
            "Fusion terminée",
        )

    action = primary_button("Fusionner et enregistrer", ft.Icons.MERGE_TYPE, tool.color, launch)
    refresh = bind_ready(action, lambda: len(files.paths) >= 2)

    return page_shell(
        page,
        "Fusionner des PDF",
        tool,
        [
            *illustration,
            ft.Row(
                [
                    secondary_button("Ajouter des PDF", ft.Icons.ADD, choose),
                    ft.TextButton(
                        content="Tout retirer",
                        on_click=clear,
                        style=ft.ButtonStyle(color=Palette.ink_muted),
                    ),
                ]
            ),
            files,
            action,
        ],
        icon=ft.Icons.MERGE_TYPE,
        description=(
            "Les fichiers sont assemblés dans l'ordre affiché ; "
            "utilisez les flèches pour le modifier."
        ),
    )