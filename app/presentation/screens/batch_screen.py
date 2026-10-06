"""Traitement par lot : les mêmes actions appliquées à plusieurs PDF, réunis dans un ZIP."""

from __future__ import annotations

import flet as ft

from app.domain.exceptions import InvalidOptionError
from app.domain.options import (
    BatchPlan,
    BatchResult,
    CompressionLevel,
    PageNumbering,
    StampColor,
    TextWatermark,
)
from app.presentation.di import UseCases
from app.presentation.screens.base import FilePickerService, bind_ready, check, page_shell, run_save
from app.presentation.screens.optimize_screens import LEVEL_LABELS
from app.presentation.screens.tool_kit import hint, switch
from app.presentation.theme import Palette, Space
from app.presentation.widgets.buttons import primary_button, secondary_button
from app.presentation.widgets.cards import card
from app.presentation.widgets.file_list import FileList
from app.presentation.widgets.fields import password_field
from app.presentation.widgets.forms import choice, text_input
from app.presentation.widgets.lottie import lottie

LOTTIE_SRC = "animations/batch_process.json"  # dans assets/animations/


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count <= 1 else (plural or singular + 's')}"


def batch_message(result: BatchResult | None, saved) -> str:
    if result is None:
        return f"Lot terminé : {saved.name}"
    text = f"{_plural(result.processed, 'PDF traité')} · {saved.name}"
    if result.failures:
        names = ", ".join(name for name, _ in result.failures[:3])
        more = "…" if len(result.failures) > 3 else ""
        text += f" · {_plural(len(result.failures), 'fichier ignoré')} ({names}{more})"
    return text


def _safe_update(*controls: ft.Control) -> None:
    """Met à jour des contrôles qui ne sont peut-être pas encore (ou plus) affichés."""
    for control in controls:
        try:
            control.update()
        except RuntimeError:
            pass


def build_batch(
    page: ft.Page, use_cases: UseCases, picker: FilePickerService, notify
) -> ft.View:
    tool = Palette.batch
    refresh = lambda: None  # noqa: E731  (relié plus bas, quand le bouton existe)

    # ------------------------------------------------------------------ 1. fichiers
    files = FileList(
        tool, ft.Icons.DESCRIPTION_OUTLINED,
        "Aucun PDF pour l'instant — ajoutez les fichiers à traiter.",
        on_change=lambda: refresh(),
    )

    # ------------------------------------------------------------------ 2. actions
    use_number = switch("Numéroter les pages", tool.color, False)
    number_format = text_input("Format du numéro", tool.color, "Page {n} sur {total}")
    use_mark = switch("Ajouter un filigrane texte", tool.color, False)
    mark_text = text_input("Texte du filigrane", tool.color, "CONFIDENTIEL", max_length=60)
    use_compress = switch("Compresser", tool.color, False)
    level = choice("Niveau", LEVEL_LABELS, CompressionLevel.MEDIUM.value, tool.color)
    use_clean = switch("Effacer les métadonnées", tool.color, False)
    use_lock = switch("Protéger par mot de passe", tool.color, False)
    secret = password_field(tool.color, "Mot de passe")
    confirm = password_field(tool.color, "Confirmer le mot de passe")

    def caption(text: str) -> ft.Text:
        return ft.Text(text, size=12.5, color=Palette.ink_muted)

    # Dans l'ordre d'exécution réel : (nom court, interrupteur, explication, réglages).
    steps = [
        ("numérotation", use_number, "Ajoute un numéro sur chaque page de chaque PDF.",
         [number_format, caption("{n} = numéro de la page · {total} = nombre de pages")]),
        ("filigrane", use_mark, "Texte gris en travers de chaque page.", [mark_text]),
        ("compression", use_compress, "Allège chaque fichier pour l'envoyer plus facilement.", [level]),
        ("métadonnées effacées", use_clean, "Retire auteur, titre et logiciel de chaque PDF.", []),
        ("mot de passe", use_lock, "Un même mot de passe protège tous les fichiers du lot.",
         [secret, confirm]),
    ]
    toggles = [toggle for _name, toggle, _text, _details in steps]

    panels: list[tuple[ft.Control, ft.Container, ft.Container, ft.Text, ft.Container]] = []

    def step_card(number: int, toggle, text: str, details: list[ft.Control]) -> ft.Container:
        badge_label = ft.Text(str(number), size=12.5, weight=ft.FontWeight.W_700, color=Palette.ink_muted)
        badge = ft.Container(
            width=26, height=26, border_radius=13, alignment=ft.Alignment(0, 0),
            bgcolor=Palette.line, content=badge_label,
        )
        body = ft.Container(
            visible=False,
            padding=ft.Padding(left=38, right=0, top=0, bottom=0),
            content=ft.Column(details, spacing=Space.sm),
        )
        box = ft.Container(
            padding=ft.Padding(left=Space.md, right=Space.md, top=Space.sm, bottom=Space.md),
            border_radius=14,
            border=ft.Border.all(1, Palette.line),
            bgcolor=Palette.surface,
            content=ft.Column(
                [
                    ft.Row(
                        [badge, ft.Column([toggle, caption(text)], spacing=0, expand=True)],
                        spacing=Space.sm,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    body,
                ],
                spacing=Space.sm,
            ),
        )
        panels.append((toggle, box, badge, badge_label, body))
        return box

    step_cards = [
        step_card(number, toggle, text, details)
        for number, (_name, toggle, text, details) in enumerate(steps, start=1)
    ]

    def style_steps() -> None:
        for toggle, box, badge, badge_label, body in panels:
            on = bool(toggle.value)
            body.visible = on and bool(body.content.controls)
            box.bgcolor = tool.soft if on else Palette.surface
            box.border = ft.Border.all(1, tool.color if on else Palette.line)
            badge.bgcolor = tool.color if on else Palette.line
            badge_label.color = Palette.surface if on else Palette.ink_muted

    def active_names() -> list[str]:
        return [name for name, toggle, _text, _details in steps if toggle.value]

    # ------------------------------------------------------------------ récapitulatif
    summary = ft.Text(size=13.5, weight=ft.FontWeight.W_600, color=Palette.ink)
    summary_hint = ft.Text(size=12.5, color=Palette.ink_muted)
    clear_button = ft.TextButton(
        content="Tout retirer", on_click=lambda _: files.clear(), visible=False,
        style=ft.ButtonStyle(color=Palette.ink_muted),
    )

    def update_summary() -> None:
        count = len(files.paths)
        actions = active_names()
        clear_button.visible = count > 0
        if count and actions:
            summary.value = f"{_plural(count, 'PDF')} · {', '.join(actions)}"
            summary_hint.value = "Le résultat sera une archive ZIP, un fichier traité par PDF."
        else:
            summary.value = "Prêt dès qu'il y a un PDF et une action."
            missing = []
            if not count:
                missing.append("ajoutez au moins un PDF")
            if not actions:
                missing.append("activez au moins une action")
            summary_hint.value = " et ".join(missing).capitalize() + "."

    def sync(_=None) -> None:
        style_steps()
        update_summary()
        page.update()
        refresh()

    for toggle in toggles:
        toggle.on_change = sync
    style_steps()
    update_summary()

    # ------------------------------------------------------------------ exécution
    def build_plan() -> BatchPlan:
        if use_lock.value:
            if not secret.value:
                raise InvalidOptionError("Saisissez le mot de passe.")
            if secret.value != (confirm.value or ""):
                raise InvalidOptionError("Les deux mots de passe ne correspondent pas.")
        return BatchPlan(
            numbering=PageNumbering(template=number_format.value or "") if use_number.value else None,
            watermark=(
                TextWatermark(text=mark_text.value or "", color=StampColor.GRAY)
                if use_mark.value else None
            ),
            compression=CompressionLevel(level.value) if use_compress.value else None,
            clear_metadata=bool(use_clean.value),
            password=secret.value if use_lock.value else None,
        )

    outcome: dict = {}

    animation = lottie(LOTTIE_SRC, 110)
    illustration: list[ft.Control] = (
        [ft.Row([animation], alignment=ft.MainAxisAlignment.CENTER)] if animation else []
    )

    async def choose(_=None) -> None:
        paths = await picker.pick_pdf(multiple=True)
        if paths:
            files.add(paths)

    async def launch(_=None) -> None:
        paths = list(files.paths)
        if not paths:
            notify("Ajoutez au moins un PDF.", True)
            return
        if not active_names():
            notify("Activez au moins une action à appliquer.", True)
            return
        holder: dict = {}
        if not check(notify, lambda: holder.update(plan=build_plan())):
            return
        plan = holder["plan"]

        def run(destination: str):
            result = use_cases.batch.execute(paths, plan, destination)
            outcome["result"] = result
            return result.path

        await run_save(
            notify, picker, "Enregistrer l'archive des PDF traités", "lot_traite.zip", run,
            "Lot traité", message=lambda saved: batch_message(outcome.get("result"), saved),
        )

    action = primary_button("Traiter et enregistrer en ZIP", ft.Icons.PLAYLIST_PLAY, tool.color, launch)
    ready = bind_ready(action, lambda: bool(files.paths) and bool(active_names()))

    def refresh() -> None:  # noqa: F811  (remplace le relais défini plus haut)
        update_summary()
        _safe_update(summary, summary_hint, clear_button)
        ready()

    def section(number: int, title: str) -> ft.Text:
        return ft.Text(f"{number}. {title}", size=15, weight=ft.FontWeight.W_700, color=Palette.ink)

    return page_shell(
        page, "Traitement par lot", tool,
        [
            *illustration,
            section(1, "Choisissez les PDF"),
            ft.Row([secondary_button("Ajouter des PDF", ft.Icons.ADD, choose), clear_button]),
            files,
            section(2, "Choisissez les actions"),
            *step_cards,
            hint("Les actions s'appliquent dans l'ordre numéroté, à chaque PDF. "
                 "Un fichier illisible est ignoré et signalé à la fin : il n'arrête pas le lot."),
            section(3, "Lancez le traitement"),
            card([summary, summary_hint]),
            action,
        ],
        icon=ft.Icons.PLAYLIST_PLAY,
        description="Appliquez les mêmes actions à plusieurs PDF d'un seul geste, "
                    "puis récupérez-les dans une archive ZIP.",
    )