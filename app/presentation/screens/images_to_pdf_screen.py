from __future__ import annotations

import flet as ft

from app.presentation.di import UseCases
from app.presentation.screens.base import (
    FilePickerService,
    bind_ready,
    page_shell,
    run_save,
)
from app.domain.options import ScanMode
from app.presentation.theme import Palette
from app.presentation.widgets.buttons import primary_button, secondary_button
from app.presentation.widgets.file_list import FileList
from app.presentation.widgets.forms import choice
from app.presentation.widgets.lottie import lottie

LOTTIE_SRC = "animations/image_to_pdf.json"  # dans assets/animations/


def build_images_to_pdf(
    page: ft.Page, use_cases: UseCases, picker: FilePickerService, notify
) -> ft.View:
    tool = Palette.images
    refresh = lambda: None  # noqa: E731
    files = FileList(
        tool,
        ft.Icons.IMAGE_OUTLINED,
        "Aucune image sélectionnée — JPG, PNG, GIF, BMP, TIFF, WEBP.",
        on_change=lambda: refresh(),
    )
    default_fit = True if picker.settings is None else picker.settings.current.fit_a4_default
    fit_a4 = ft.Switch(
        label="Ajuster chaque image à une page A4",
        value=default_fit,
        active_color=tool.color,
    )

    scan = choice(
        "Amélioration du scan",
        [
            (ScanMode.ORIGINAL.value, "Aucune — images telles quelles"),
            (ScanMode.DOCUMENT.value, "Document — fond blanc, texte net, couleurs"),
            (ScanMode.GRAYSCALE.value, "Niveaux de gris"),
            (ScanMode.BLACK_WHITE.value, "Noir et blanc — le plus léger"),
        ],
        ScanMode.ORIGINAL.value,
        tool.color,
    )

    animation = lottie(LOTTIE_SRC, 150, reverse=True)
    illustration: list[ft.Control] = (
        [ft.Row([animation], alignment=ft.MainAxisAlignment.CENTER)] if animation else []
    )

    async def choose(_=None):
        paths = await picker.pick_images(multiple=True)
        if paths:
            files.add(paths)

    def clear(_=None):
        files.clear()

    async def launch(_=None):
        paths = list(files.paths)
        if not paths:
            notify("Sélectionnez au moins une image.", True)
            return
        fit = bool(fit_a4.value)
        mode = ScanMode(scan.value or ScanMode.ORIGINAL.value)
        await run_save(
            notify,
            picker,
            "Enregistrer le PDF",
            "images.pdf",
            lambda destination: use_cases.images_to_pdf.execute(paths, destination, fit, mode),
            "PDF créé",
        )

    action = primary_button(
        "Convertir et enregistrer", ft.Icons.PICTURE_AS_PDF_OUTLINED, tool.color, launch
    )
    refresh = bind_ready(action, lambda: bool(files.paths))

    return page_shell(
        page,
        "Images vers PDF",
        tool,
        [
            *illustration,
            ft.Row(
                [
                    secondary_button(
                        "Ajouter des images", ft.Icons.ADD_PHOTO_ALTERNATE_OUTLINED, choose
                    ),
                    ft.TextButton(
                        content="Tout retirer",
                        on_click=clear,
                        style=ft.ButtonStyle(color=Palette.ink_muted),
                    ),
                ]
            ),
            files,
            fit_a4,
            scan,
            action,
        ],
        icon=ft.Icons.ADD_PHOTO_ALTERNATE_OUTLINED,
        description=(
            "Chaque image devient une page, dans l'ordre affiché ; "
            "utilisez les flèches pour le modifier."
        ),
    )