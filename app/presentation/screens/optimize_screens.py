"""Outils d'optimisation : compression, métadonnées, signets."""

from __future__ import annotations

import logging

import flet as ft

from app.domain.options import (
    CompressionLevel,
    CompressionResult,
    PdfMetadata,
    format_bookmarks,
    parse_bookmarks,
)
from app.presentation.di import UseCases
from app.presentation.screens.base import FilePickerService
from app.presentation.screens.tool_kit import Ready, build_pdf_tool, hint, switch
from app.presentation.theme import Palette
from app.presentation.widgets.file_tray import human_size
from app.presentation.widgets.forms import choice, live_check, text_input
from app.presentation.widgets.lottie import lottie

logger = logging.getLogger(__name__)

COMPRESS_LOTTIE_SRC = "animations/compress_pdf.json"  # dans assets/animations/
METADATA_LOTTIE_SRC = "animations/metadata_pdf.json"
BOOKMARKS_LOTTIE_SRC = "animations/bookmarks_pdf.json"

LEVEL_LABELS = (
    (CompressionLevel.LIGHT.value, "Légère — qualité quasi intacte"),
    (CompressionLevel.MEDIUM.value, "Moyenne — bon compromis"),
    (CompressionLevel.STRONG.value, "Forte — fichier le plus petit"),
)


def compression_message(result: CompressionResult | None, saved) -> str:
    """Texte final : taille avant → après, ou constat qu'on ne peut pas faire mieux."""
    if result is None or not result.improved:
        return (
            f"Ce PDF est déjà optimisé : une copie identique a été enregistrée ({saved.name})."
        )
    percent = round(result.saved_ratio * 100)
    return (
        f"PDF compressé : {human_size(result.original_size)} → "
        f"{human_size(result.final_size)} (−{percent} %) · {saved.name}"
    )


# ====================================================================== compression
def build_compress(
    page: ft.Page, use_cases: UseCases, picker: FilePickerService, notify
) -> ft.View:
    tool = Palette.compress
    ready = Ready()
    level = choice("Niveau de compression", LEVEL_LABELS, CompressionLevel.MEDIUM.value, tool.color)

    animation = lottie(COMPRESS_LOTTIE_SRC, 160)
    illustration: list[ft.Control] = (
        [ft.Row([animation], alignment=ft.MainAxisAlignment.CENTER)] if animation else []
    )

    return build_pdf_tool(
        page, picker, notify, use_cases,
        tool=tool, title="Compresser un PDF", icon=ft.Icons.COMPRESS,
        description="Réduisez le poids d'un PDF pour l'envoyer par e-mail ou messagerie.",
        controls=[
            *illustration,
            level,
            hint("Les images sont réencodées ; le texte et les tracés restent nets. "
                 "Un PDF sans image gagne peu. Le fichier original n'est jamais modifié."),
        ],
        button_label="Compresser et enregistrer", button_icon=ft.Icons.COMPRESS,
        save_title="Enregistrer le PDF compressé", suffix="_compresse", success="PDF compressé",
        prepare=lambda path: CompressionLevel(level.value or CompressionLevel.MEDIUM.value),
        produce=lambda path, chosen, dest: use_cases.compress_pdf.execute(path, chosen, dest),
        message=compression_message,
        ready=ready,
    )


# ====================================================================== métadonnées
_FIELDS = (
    ("title", "Titre"),
    ("author", "Auteur"),
    ("subject", "Sujet"),
    ("keywords", "Mots-clés"),
    ("creator", "Créé avec"),
    ("producer", "Convertisseur PDF"),
)


def build_metadata(
    page: ft.Page, use_cases: UseCases, picker: FilePickerService, notify
) -> ft.View:
    tool = Palette.metadata
    ready = Ready()
    inputs = {name: text_input(label, tool.color, on_change=ready, max_length=300) for name, label in _FIELDS}
    wipe = switch("Effacer toutes les métadonnées", tool.color)

    animation = lottie(METADATA_LOTTIE_SRC, 160)
    illustration: list[ft.Control] = (
        [ft.Row([animation], alignment=ft.MainAxisAlignment.CENTER)] if animation else []
    )

    def on_wipe(_=None) -> None:
        for field in inputs.values():
            field.disabled = bool(wipe.value)
        page.update()

    wipe.on_change = on_wipe

    def on_file_chosen(path: str) -> None:
        try:
            current = use_cases.read_metadata.execute(path)
        except Exception:
            logger.exception("Lecture des métadonnées impossible")
            current = PdfMetadata()
        for name, field in inputs.items():
            field.value = getattr(current, name)
        page.update()

    def on_file_cleared() -> None:
        for field in inputs.values():
            field.value = ""
        page.update()

    def metadata() -> PdfMetadata:
        return PdfMetadata(**{name: (field.value or "") for name, field in inputs.items()})

    return build_pdf_tool(
        page, picker, notify, use_cases,
        tool=tool, title="Métadonnées", icon=ft.Icons.BADGE_OUTLINED,
        description="Modifiez ou effacez l'auteur, le titre et les autres informations cachées du PDF.",
        controls=[
            *illustration, *inputs.values(), wipe,
            hint("Effacer les métadonnées retire l'auteur, le logiciel utilisé et les dates : "
                 "utile avant de partager un document."),
        ],
        button_label="Appliquer et enregistrer", button_icon=ft.Icons.BADGE_OUTLINED,
        save_title="Enregistrer le PDF", suffix="_metadonnees", success="PDF mis à jour",
        prepare=lambda path: (metadata(), bool(wipe.value)),
        produce=lambda path, p, dest: use_cases.write_metadata.execute(path, p[0], dest, p[1]),
        ready=ready, on_file_chosen=on_file_chosen, on_file_cleared=on_file_cleared,
    )


# ====================================================================== signets
def build_bookmarks(
    page: ft.Page, use_cases: UseCases, picker: FilePickerService, notify
) -> ft.View:
    tool = Palette.bookmarks
    ready = Ready()
    editor = text_input(
        "Signets", tool.color, multiline=True,
        hint="1: Introduction\n- 3: Contexte\n5: Conclusion",
        helper="Une ligne par signet : « page: titre ». Un tiret au début descend d'un niveau.",
    )
    live_check(editor, lambda text: parse_bookmarks(text, ready.state.get("total")), ready)

    animation = lottie(BOOKMARKS_LOTTIE_SRC, 160)
    illustration: list[ft.Control] = (
        [ft.Row([animation], alignment=ft.MainAxisAlignment.CENTER)] if animation else []
    )

    def on_file_chosen(path: str) -> None:
        try:
            editor.value = format_bookmarks(use_cases.read_bookmarks.execute(path))
        except Exception:
            logger.exception("Lecture des signets impossible")
            editor.value = ""
        page.update()

    def on_file_cleared() -> None:
        editor.value = ""
        page.update()

    return build_pdf_tool(
        page, picker, notify, use_cases,
        tool=tool, title="Signets", icon=ft.Icons.BOOKMARK_BORDER,
        description="Créez la table des matières cliquable d'un PDF. Laisser vide supprime les signets.",
        controls=[*illustration, editor],
        button_label="Appliquer et enregistrer", button_icon=ft.Icons.BOOKMARK_BORDER,
        save_title="Enregistrer le PDF avec signets", suffix="_signets", success="Signets enregistrés",
        prepare=lambda path: (use_cases.write_bookmarks.validate(path, editor.value or ""), editor.value or "")[1],
        produce=lambda path, text, dest: use_cases.write_bookmarks.execute(path, text, dest),
        ready=ready, on_file_chosen=on_file_chosen, on_file_cleared=on_file_cleared,
    )