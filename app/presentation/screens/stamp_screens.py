"""Outils de personnalisation : filigrane, image/signature, numérotation."""

from __future__ import annotations

import flet as ft

from app.domain.options import (
    ImageStamp,
    PageNumbering,
    Position,
    StampColor,
    TextWatermark,
)
from app.presentation.di import UseCases
from app.presentation.screens.base import FilePickerService
from app.presentation.screens.tool_kit import Ready, build_pdf_tool, hint, second_tray, switch
from app.presentation.theme import Palette
from app.presentation.widgets.fields import pages_field
from app.presentation.widgets.forms import (
    choice,
    live_check,
    labelled,
    number_input,
    percent_slider,
    position_choice,
    read_int,
    text_input,
)
from app.presentation.widgets.lottie import lottie

COLOR_LABELS = (
    (StampColor.GRAY.value, "Gris"),
    (StampColor.BLACK.value, "Noir"),
    (StampColor.RED.value, "Rouge"),
    (StampColor.BLUE.value, "Bleu"),
    (StampColor.GREEN.value, "Vert"),
)
ANGLE_LABELS = (("45", "Diagonale montante"), ("0", "Horizontale"), ("-45", "Diagonale descendante"))

# Une animation par écran, dans assets/animations/
WATERMARK_TEXT_LOTTIE_SRC = "animations/watermark_text_pdf.json"
WATERMARK_IMAGE_LOTTIE_SRC = "animations/watermark_image_pdf.json"
SIGNATURE_LOTTIE_SRC = "animations/signature_pdf.json"
NUMBERING_LOTTIE_SRC = "animations/numbering_pdf.json"


def _illustration(src: str) -> list[ft.Control]:
    """Animation de l'écran, centrée ; liste vide si ``flet-lottie`` est absent."""
    animation = lottie(src, 150)
    return [ft.Row([animation], alignment=ft.MainAxisAlignment.CENTER)] if animation else []


# ====================================================================== filigrane texte
def build_watermark(
    page: ft.Page, use_cases: UseCases, picker: FilePickerService, notify
) -> ft.View:
    tool = Palette.watermark
    ready = Ready()
    text = text_input("Texte du filigrane", tool.color, hint="Ex. CONFIDENTIEL", max_length=60)
    live_check(text, lambda value: TextWatermark(value), ready)
    color = choice("Couleur", COLOR_LABELS, StampColor.GRAY.value, tool.color)
    angle = choice("Orientation", ANGLE_LABELS, "45", tool.color)
    opacity = percent_slider(tool.color, 25)
    selection = pages_field(tool.color, "Pages concernées", "Vide = toutes les pages")

    def prepare(path: str):
        watermark = TextWatermark(
            text=text.value or "",
            color=StampColor(color.value),
            opacity=(opacity.value or 25) / 100,
            angle=int(angle.value or 45),
        )
        use_cases.watermark_text.validate(path, selection.value or "")
        return watermark, selection.value or ""

    return build_pdf_tool(
        page, picker, notify, use_cases,
        tool=tool, title="Filigrane texte", icon=ft.Icons.WATER_DROP_OUTLINED,
        description="Écrivez un texte translucide en travers des pages (CONFIDENTIEL, COPIE, BROUILLON…).",
        controls=[*_illustration(WATERMARK_TEXT_LOTTIE_SRC), text, color, angle, labelled("Opacité", opacity), selection],
        button_label="Ajouter et enregistrer", button_icon=ft.Icons.WATER_DROP_OUTLINED,
        save_title="Enregistrer le PDF filigrané", suffix="_filigrane", success="PDF filigrané créé",
        prepare=prepare,
        produce=lambda path, p, dest: use_cases.watermark_text.execute(path, p[0], p[1], dest),
        ready=ready, is_ready=lambda _s: bool((text.value or "").strip()) and not text.error,
    )


# ====================================================================== image / signature
def _build_image_stamp(
    page: ft.Page,
    use_cases: UseCases,
    picker: FilePickerService,
    notify,
    *,
    signing: bool,
) -> ft.View:
    tool = Palette.signature if signing else Palette.watermark
    ready = Ready()
    image: dict = {"path": None}
    image_tray = second_tray(
        picker, tool, image, ready, kind="image",
        empty="Aucune image sélectionnée", pick_label="Choisir une image",
    )
    position = position_choice(
        tool.color, Position.BOTTOM_RIGHT if signing else Position.CENTER
    )
    size = percent_slider(tool.color, 25 if signing else 50)
    opacity = percent_slider(tool.color, 100 if signing else 30)
    white = switch(
        "Retirer le fond blanc (signature photographiée ou scannée)", tool.color, signing
    )
    selection = pages_field(
        tool.color,
        "Pages concernées",
        "Vide = dernière page" if signing else "Vide = toutes les pages",
    )
    case = use_cases.sign_pdf if signing else use_cases.stamp_image

    def prepare(path: str):
        stamp = ImageStamp(
            position=Position(position.value),
            width_fraction=(size.value or 25) / 100,
            opacity=(opacity.value or 100) / 100,
            remove_white_background=bool(white.value),
        )
        case.validate(path, image["path"], selection.value or "")
        return stamp, selection.value or ""

    title = "Signer un PDF" if signing else "Filigrane image"
    icon = ft.Icons.DRAW_OUTLINED if signing else ft.Icons.IMAGE_OUTLINED
    return build_pdf_tool(
        page, picker, notify, use_cases,
        tool=tool, title=title, icon=icon,
        description=(
            "Posez une image de votre signature (photo ou scan) sur le PDF."
            if signing
            else "Ajoutez un logo ou un tampon translucide sur les pages."
        ),
        controls=[
            *_illustration(SIGNATURE_LOTTIE_SRC if signing else WATERMARK_IMAGE_LOTTIE_SRC),
            image_tray, position,
            labelled("Taille (largeur de la page)", size),
            labelled("Opacité", opacity),
            white, selection,
            hint("La signature insérée est une image : ce n'est pas une signature électronique certifiée."
                 if signing else "Les PNG transparents gardent leur transparence."),
        ],
        button_label="Ajouter et enregistrer", button_icon=icon,
        save_title="Enregistrer le PDF signé" if signing else "Enregistrer le PDF",
        suffix="_signe" if signing else "_logo",
        success="PDF signé créé" if signing else "PDF créé",
        prepare=prepare,
        produce=lambda path, p, dest: case.execute(path, image["path"], p[0], p[1], dest),
        ready=ready, is_ready=lambda _s: bool(image["path"]),
    )


def build_signature(page, use_cases, picker, notify) -> ft.View:
    return _build_image_stamp(page, use_cases, picker, notify, signing=True)


def build_image_watermark(page, use_cases, picker, notify) -> ft.View:
    return _build_image_stamp(page, use_cases, picker, notify, signing=False)


# ====================================================================== numérotation
def build_numbering(
    page: ft.Page, use_cases: UseCases, picker: FilePickerService, notify
) -> ft.View:
    tool = Palette.numbering
    ready = Ready()
    template = text_input(
        "Format", tool.color, "{n}", hint="Page {n} sur {total}",
        helper="{n} = numéro de la page, {total} = dernier numéro.", max_length=40,
    )
    live_check(template, lambda value: PageNumbering(value), ready)
    position = position_choice(tool.color, Position.BOTTOM_CENTER, "Emplacement du numéro")
    start = number_input("Numéro de départ", tool.color, "1", on_change=ready)
    selection = pages_field(tool.color, "Pages à numéroter", "Vide = toutes les pages")

    def prepare(path: str):
        numbering = PageNumbering(
            template=template.value or "",
            position=Position(position.value),
            start=read_int(start.value, "Numéro de départ", 1),
        )
        use_cases.number_pages.validate(path, selection.value or "")
        return numbering, selection.value or ""

    return build_pdf_tool(
        page, picker, notify, use_cases,
        tool=tool, title="Numéroter les pages", icon=ft.Icons.FORMAT_LIST_NUMBERED,
        description="Ajoutez un numéro de page : « 3 », « Page 3 sur 12 », « - 3 -»…",
        controls=[*_illustration(NUMBERING_LOTTIE_SRC), template, position, start, selection],
        button_label="Numéroter et enregistrer", button_icon=ft.Icons.FORMAT_LIST_NUMBERED,
        save_title="Enregistrer le PDF numéroté", suffix="_numerote", success="PDF numéroté créé",
        prepare=prepare,
        produce=lambda path, p, dest: use_cases.number_pages.execute(path, p[0], p[1], dest),
        ready=ready, is_ready=lambda _s: bool((template.value or "").strip()) and not template.error,
    )