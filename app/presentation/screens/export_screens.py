"""Outils d'extraction : images et texte d'un PDF."""

from __future__ import annotations

import flet as ft

from app.presentation.di import UseCases
from app.presentation.screens.base import FilePickerService
from app.presentation.screens.tool_kit import Ready, build_pdf_tool, hint, switch
from app.presentation.theme import Palette
from app.presentation.widgets.lottie import lottie

IMAGES_LOTTIE_SRC = "animations/extract_images.json"  # dans assets/animations/
TEXT_LOTTIE_SRC = "animations/extract_text.json"


def _illustration(src: str) -> list[ft.Control]:
    """Animation centrée ; liste vide si ``flet-lottie`` est absent (l'écran reste complet)."""
    animation = lottie(src, 150)
    return [ft.Row([animation], alignment=ft.MainAxisAlignment.CENTER)] if animation else []


def build_extract_images(
    page: ft.Page, use_cases: UseCases, picker: FilePickerService, notify
) -> ft.View:
    tool = Palette.images_out

    def message(result, saved) -> str:
        count = getattr(result, "items", 0)
        return f"{count} image{'s' if count > 1 else ''} extraite{'s' if count > 1 else ''} · {saved.name}"

    return build_pdf_tool(
        page, picker, notify, use_cases,
        tool=tool, title="Extraire les images", icon=ft.Icons.PHOTO_LIBRARY_OUTLINED,
        description="Récupérez les photos et illustrations d'un PDF dans une archive ZIP.",
        controls=[*_illustration(IMAGES_LOTTIE_SRC),
                  hint("Les images répétées sur chaque page (logo) ne sont gardées qu'une fois. "
                       "Les petites décorations sont ignorées.")],
        button_label="Extraire et enregistrer", button_icon=ft.Icons.PHOTO_LIBRARY_OUTLINED,
        save_title="Enregistrer les images", suffix="_images", success="Images extraites",
        extension=".zip",
        prepare=lambda path: None,
        produce=lambda path, _p, dest: use_cases.extract_images.execute(path, dest),
        message=message,
        ready=Ready(),
    )


def build_extract_text(
    page: ft.Page, use_cases: UseCases, picker: FilePickerService, notify
) -> ft.View:
    tool = Palette.text_out
    markers = switch("Indiquer le numéro de chaque page", tool.color, True)

    def message(result, saved) -> str:
        count = getattr(result, "items", 0)
        return f"Texte de {count} page{'s' if count > 1 else ''} extrait · {saved.name}"

    return build_pdf_tool(
        page, picker, notify, use_cases,
        tool=tool, title="Extraire le texte", icon=ft.Icons.TEXT_SNIPPET_OUTLINED,
        description="Copiez le texte d'un PDF dans un fichier .txt.",
        controls=[*_illustration(TEXT_LOTTIE_SRC), markers,
                  hint("Fonctionne sur les PDF « numériques ». Un scan (une image de page) "
                                "n'a pas de texte à extraire.")],
        button_label="Extraire et enregistrer", button_icon=ft.Icons.TEXT_SNIPPET_OUTLINED,
        save_title="Enregistrer le texte", suffix="_texte", success="Texte extrait",
        extension=".txt",
        prepare=lambda path: bool(markers.value),
        produce=lambda path, with_markers, dest: use_cases.extract_text.execute(path, dest, with_markers),
        message=message,
        ready=Ready(),
    )