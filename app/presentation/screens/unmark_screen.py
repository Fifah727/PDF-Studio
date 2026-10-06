"""Retirer des filigranes (texte, image, signature) quand le PDF en contient."""

from __future__ import annotations

import logging

import flet as ft

from app.domain.exceptions import PdfError
from app.domain.options import RemovalResult, StampKind
from app.presentation.di import UseCases
from app.presentation.screens.base import FilePickerService
from app.presentation.screens.tool_kit import Ready, build_pdf_tool, hint
from app.presentation.theme import Palette
from app.presentation.widgets.lottie import lottie

logger = logging.getLogger(__name__)

UNMARK_LOTTIE_SRC = "animations/unmark_pdf.json"  # dans assets/animations/

LABELS = {
    StampKind.TEXT: "Filigranes texte",
    StampKind.IMAGE: "Filigranes image / logo",
    StampKind.SIGNATURE: "Signatures",
}
SHORT = {StampKind.TEXT: "texte", StampKind.IMAGE: "image", StampKind.SIGNATURE: "signature"}


def removal_message(result: RemovalResult | None, saved) -> str:
    if result is None:
        return f"Filigranes retirés · {saved.name}"
    parts = ", ".join(
        f"{number} {SHORT[kind]}{'s' if number > 1 and kind is not StampKind.TEXT else ''}"
        for kind, number in result.removed.counts
    )
    return f"Filigranes retirés ({parts}) · {saved.name}"


def build_unmark(
    page: ft.Page, use_cases: UseCases, picker: FilePickerService, notify
) -> ft.View:
    tool = Palette.unmark
    ready = Ready()
    boxes = {
        kind: ft.Checkbox(
            label=f"{LABELS[kind]} — en attente d'un fichier",
            value=False,
            disabled=True,
            active_color=tool.color,
            on_change=ready,
        )
        for kind in StampKind
    }
    summary = ft.Text(
        "Choisissez un PDF : ses filigranes seront repérés automatiquement.",
        size=13.5,
        color=Palette.ink_muted,
    )

    animation = lottie(UNMARK_LOTTIE_SRC, 160)
    illustration: list[ft.Control] = (
        [ft.Row([animation], alignment=ft.MainAxisAlignment.CENTER)] if animation else []
    )

    def reset(message: str, error: bool = False) -> None:
        for kind, box in boxes.items():
            box.label, box.value, box.disabled = f"{LABELS[kind]} — aucun", False, True
        summary.value = message
        summary.color = Palette.danger if error else Palette.ink_muted

    def on_file_chosen(path: str) -> None:
        try:
            report = use_cases.scan_watermarks.execute(path)
        except PdfError as exc:
            reset(str(exc), error=True)
        except Exception:
            logger.exception("Analyse des filigranes impossible")
            reset("Impossible d'analyser ce fichier.", error=True)
        else:
            if report.total == 0:
                reset(
                    "Aucun filigrane identifiable. Un filigrane intégré à l'image des pages "
                    "(scan, impression en PDF) ne peut pas être retiré automatiquement."
                )
            else:
                for kind, box in boxes.items():
                    number = report.count(kind)
                    box.label = f"{LABELS[kind]} ({number})" if number else f"{LABELS[kind]} — aucun"
                    box.disabled, box.value = number == 0, number > 0
                summary.value = (
                    f"{report.total} filigrane{'s' if report.total > 1 else ''} repéré"
                    f"{'s' if report.total > 1 else ''} sur {report.pages} page"
                    f"{'s' if report.pages > 1 else ''}."
                )
                summary.color = Palette.ink
        page.update()

    def on_file_cleared() -> None:
        reset("Choisissez un PDF : ses filigranes seront repérés automatiquement.")
        for kind, box in boxes.items():
            box.label = f"{LABELS[kind]} — en attente d'un fichier"
        page.update()

    def chosen() -> list[StampKind]:
        return [kind for kind, box in boxes.items() if box.value and not box.disabled]

    return build_pdf_tool(
        page, picker, notify, use_cases,
        tool=tool, title="Retirer des filigranes", icon=ft.Icons.AUTO_FIX_HIGH,
        description="Repère les filigranes texte, image et signatures d'un PDF, et retire ceux que vous cochez.",
        controls=[
            *illustration,
            summary,
            *boxes.values(),
            hint("Retire les filigranes créés par PDF Studio et ceux que d'autres outils déclarent comme "
                 "tels. À utiliser sur vos propres documents ou avec l'accord de leur auteur. Le texte et "
                 "les images du document ne sont pas touchés."),
        ],
        button_label="Retirer et enregistrer", button_icon=ft.Icons.AUTO_FIX_HIGH,
        save_title="Enregistrer le PDF sans filigrane", suffix="_sans_filigrane",
        success="Filigranes retirés",
        prepare=lambda path: chosen(),
        produce=lambda path, kinds, dest: use_cases.remove_watermarks.execute(path, kinds, dest),
        message=removal_message,
        is_ready=lambda _s: bool(chosen()),
        on_file_chosen=on_file_chosen, on_file_cleared=on_file_cleared,
        ready=ready,
    )