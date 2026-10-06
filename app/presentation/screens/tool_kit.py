"""
Squelette commun des outils « un PDF en entrée, un fichier en sortie ».

Un écran déclare seulement ce qui lui est propre (ses champs, sa validation,
son traitement). Le choix du fichier, l'activation du bouton, la validation
avant la boîte « Enregistrer sous » et la notification finale sont ici,
écrits une seule fois.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

import flet as ft

from app.presentation.screens.base import (
    FilePickerService,
    bind_ready,
    check,
    page_shell,
    pdf_chooser,
    run_save,
    suggest_name,
)
from app.presentation.theme import Palette, ToolAccent
from app.presentation.widgets.buttons import primary_button
from app.presentation.widgets.cards import section_label
from app.presentation.widgets.file_tray import FileTray


class Ready:
    """
    Rappel « l'état a changé, réévalue le bouton ».

    Les champs sont créés avant le bouton : ils reçoivent cet objet, qui sera
    relié au bouton une fois celui-ci construit.
    """

    def __init__(self) -> None:
        self._callback: Callable[[], None] = lambda: None
        self.state: dict[str, Any] = {}  # fichier choisi, nombre de pages… (lecture seule)

    def bind(self, callback: Callable[[], None]) -> None:
        self._callback = callback

    def __call__(self, *_: Any) -> None:
        self._callback()


def build_pdf_tool(
    page: ft.Page,
    picker: FilePickerService,
    notify: Callable[..., None],
    use_cases,
    *,
    tool: ToolAccent,
    title: str,
    icon: str,
    description: str,
    controls: Sequence[ft.Control],
    button_label: str,
    button_icon: str,
    save_title: str,
    suffix: str,
    success: str,
    prepare: Callable[[str], Any],
    produce: Callable[[str, Any, str], Any],
    ready: Ready,
    extension: str = ".pdf",
    is_ready: Callable[[dict], bool] | None = None,
    on_file_chosen: Callable[[str], None] | None = None,
    on_file_cleared: Callable[[], None] | None = None,
    message: Callable[[Any, Any], str] | None = None,
    tray: FileTray | None = None,
    count_pages: bool = True,
) -> ft.View:
    """
    ``prepare(path)`` valide et renvoie les paramètres du traitement (ou lève
    une erreur affichée telle quelle, avant d'ouvrir « Enregistrer sous »).
    ``produce(path, params, destination)`` écrit le résultat et le renvoie
    (un chemin, ou un objet résultat dont ``message`` tire le texte final).
    """
    state: dict[str, Any] = {"path": None, "total": None}
    tray = tray or FileTray(tool)
    outcome: dict[str, Any] = {}

    async def launch(_=None) -> None:
        path = state["path"]
        if not path:
            notify("Sélectionnez d'abord un PDF.", True)
            return
        holder: dict[str, Any] = {}
        if not check(notify, lambda: holder.update(params=prepare(path))):
            return
        params = holder["params"]

        def run(destination: str):
            result = produce(path, params, destination)
            outcome["result"] = result
            return getattr(result, "path", result)

        await run_save(
            notify,
            picker,
            save_title,
            suggest_name(path, suffix, extension),
            run,
            success,
            message=(lambda saved: message(outcome.get("result"), saved)) if message else None,
        )

    action = primary_button(button_label, button_icon, tool.color, launch)

    def can_run() -> bool:
        return bool(state["path"]) and (is_ready(state) if is_ready else True)

    # Dit pourquoi le bouton est grisé : un bouton muet laisse l'utilisateur deviner.
    status = ft.Text(size=12.5, color=Palette.ink_muted, text_align=ft.TextAlign.CENTER)

    def describe_status() -> str:
        if can_run():
            return ""
        return "Choisissez d'abord un fichier PDF." if not state["path"] else "Complétez les réglages pour continuer."

    status.value = describe_status()
    status.visible = bool(status.value)
    base_refresh = bind_ready(action, can_run)

    def refresh() -> None:
        base_refresh()
        status.value = describe_status()
        status.visible = bool(status.value)
        try:
            status.update()
        except RuntimeError:
            pass  # pas encore monté

    ready.state = state
    ready.bind(refresh)

    base_choose, base_clear = pdf_chooser(
        picker, use_cases, tray, state, refresh, count_pages=count_pages
    )

    async def choose(event=None) -> None:
        await base_choose(event)
        if state["path"] and on_file_chosen:
            on_file_chosen(state["path"])
            refresh()

    def clear(event=None) -> None:
        base_clear(event)
        if on_file_cleared:
            on_file_cleared()

    tray.bind(choose, clear)

    body: list[ft.Control] = [section_label("Fichier"), tray]
    if controls:
        body += [section_label("Réglages"), *controls]
    body += [action, status]
    return page_shell(page, title, tool, body, icon=icon, description=description)


def second_tray(
    picker: FilePickerService,
    tool: ToolAccent,
    holder: dict,
    on_change: Callable[[], None],
    *,
    kind: str = "pdf",
    empty: str = "Aucun fichier sélectionné",
    pick_label: str = "Choisir un PDF",
) -> FileTray:
    """Deuxième emplacement de fichier (PDF à insérer, image, versos…)."""
    tray = FileTray(tool, pick_label=pick_label)
    tray.set_empty(empty)

    async def choose(_=None) -> None:
        paths = await (picker.pick_images(multiple=False) if kind == "image" else picker.pick_pdf())
        if not paths:
            return
        holder["path"] = paths[0]
        tray.set_file(paths[0])
        on_change()

    def clear(_=None) -> None:
        holder["path"] = None
        on_change()

    tray.bind(choose, clear)
    return tray


def switch(label: str, accent: str, value: bool = False, on_change: Callable | None = None) -> ft.Switch:
    return ft.Switch(label=label, value=value, active_color=accent, on_change=on_change)


def hint(text: str) -> ft.Text:
    return ft.Text(text, size=12.5, color=Palette.ink_muted)
