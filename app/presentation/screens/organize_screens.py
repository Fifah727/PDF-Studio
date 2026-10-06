"""Outils d'organisation : réorganiser, insérer, recto-verso, rogner."""

from __future__ import annotations

import flet as ft

from app.domain.options import CropMargins
from app.presentation.di import UseCases
from app.presentation.screens.base import FilePickerService, bind_ready, check, page_shell, run_save
from app.presentation.screens.tool_kit import Ready, build_pdf_tool, hint, second_tray, switch
from app.presentation.theme import Palette
from app.presentation.widgets.buttons import primary_button
from app.presentation.widgets.fields import pages_field
from app.presentation.widgets.forms import number_input, read_float, read_int
from app.presentation.widgets.lottie import lottie
from app.presentation.widgets.page_order import MAX_LISTED_PAGES, PageOrderList

# Animations dans assets/animations/
LOTTIE_REORDER = "animations/reorder_pdf.json"
LOTTIE_INSERT = "animations/insert_pdf.json"
LOTTIE_INTERLEAVE = "animations/interleave_pdf.json"
LOTTIE_CROP = "animations/crop_pdf.json"


def _illustration(src: str) -> list[ft.Control]:
    animation = lottie(src, 150)
    return [ft.Row([animation], alignment=ft.MainAxisAlignment.CENTER)] if animation else []


# ====================================================================== réorganiser
def build_reorder(
    page: ft.Page, use_cases: UseCases, picker: FilePickerService, notify
) -> ft.View:
    tool = Palette.reorder
    ready = Ready()
    order = PageOrderList(tool, on_change=lambda: ready())
    typed = pages_field(tool.color, "Nouvel ordre des pages", "Ex. 3, 1, 2")
    typed.helper = "Les pages non citées suivent, dans leur ordre d'origine."
    typed.visible = False
    typed.on_change = ready
    reverse = ft.OutlinedButton(
        content="Inverser tout l'ordre",
        icon=ft.Icons.SWAP_VERT,
        on_click=lambda _: order.reverse(),
        style=ft.ButtonStyle(color=Palette.ink, side=ft.BorderSide(1, Palette.line_strong)),
    )
    reverse.visible = False
    state_ref: dict = {}

    def on_file_chosen(path: str) -> None:
        total = use_cases.count_pages.execute(path)
        listed = total <= MAX_LISTED_PAGES
        state_ref["listed"] = listed
        typed.visible, reverse.visible = not listed, listed
        order.load(total) if listed else order.clear()
        typed.value = ""
        page.update()

    def on_file_cleared() -> None:
        order.clear()
        typed.visible = reverse.visible = False

    def selection() -> str:
        return ",".join(map(str, order.order)) if state_ref.get("listed") else typed.value or ""

    def prepare(path: str):
        text = selection()
        use_cases.reorder_pages.validate(path, text)
        return text

    def is_ready(_state) -> bool:
        return order.is_modified if state_ref.get("listed") else bool((typed.value or "").strip())

    return build_pdf_tool(
        page, picker, notify, use_cases,
        tool=tool, title="Réorganiser les pages", icon=ft.Icons.SWAP_VERT,
        description="Changez l'ordre des pages avec les flèches, ou saisissez-le pour un long document.",
        controls=[*_illustration(LOTTIE_REORDER), reverse, order, typed],
        button_label="Réorganiser et enregistrer", button_icon=ft.Icons.SWAP_VERT,
        save_title="Enregistrer le PDF réorganisé", suffix="_reorganise", success="PDF réorganisé créé",
        prepare=prepare,
        produce=lambda path, text, dest: use_cases.reorder_pages.execute(path, text, dest),
        ready=ready, is_ready=is_ready,
        on_file_chosen=on_file_chosen, on_file_cleared=on_file_cleared,
    )


# ====================================================================== insérer
BLANK, FROM_PDF = "blank", "pdf"


def build_insert(
    page: ft.Page, use_cases: UseCases, picker: FilePickerService, notify
) -> ft.View:
    tool = Palette.insert
    ready = Ready()
    extra: dict = {"path": None}
    mode = ft.RadioGroup(
        value=BLANK,
        content=ft.Row(
            [
                ft.Radio(value=BLANK, label="Pages blanches", active_color=tool.color),
                ft.Radio(value=FROM_PDF, label="Pages d'un autre PDF", active_color=tool.color),
            ],
            spacing=24, wrap=True,
        ),
    )
    count = number_input("Nombre de pages blanches", tool.color, "1", on_change=ready)
    other = second_tray(picker, tool, extra, ready, empty="Aucun PDF à insérer")
    other.visible = False
    position = number_input(
        "Insérer après la page", tool.color, "0",
        helper="0 = au tout début du document.", on_change=ready,
    )

    def on_mode(_=None) -> None:
        count.visible = mode.value == BLANK
        other.visible = mode.value == FROM_PDF
        page.update()
        ready()

    mode.on_change = on_mode

    def prepare(path: str):
        after = read_int(position.value, "Position", 0)
        blanks = read_int(count.value, "Nombre de pages", 0) if mode.value == BLANK else 0
        insert_path = extra["path"] if mode.value == FROM_PDF else None
        use_cases.insert_pages.validate(path, after, insert_path, blanks)
        return after, insert_path, blanks

    def is_ready(_state) -> bool:
        return bool((count.value or "").strip()) if mode.value == BLANK else bool(extra["path"])

    return build_pdf_tool(
        page, picker, notify, use_cases,
        tool=tool, title="Insérer des pages", icon=ft.Icons.NOTE_ADD_OUTLINED,
        description="Ajoutez des pages blanches ou les pages d'un autre PDF, à l'endroit voulu.",
        controls=[*_illustration(LOTTIE_INSERT), mode, count, other, position],
        button_label="Insérer et enregistrer", button_icon=ft.Icons.NOTE_ADD_OUTLINED,
        save_title="Enregistrer le PDF complété", suffix="_complete", success="PDF complété créé",
        prepare=prepare,
        produce=lambda path, p, dest: use_cases.insert_pages.execute(
            path, p[0], dest, insert_path=p[1], blank_count=p[2]
        ),
        ready=ready, is_ready=is_ready,
        on_file_cleared=None,
    )


# ====================================================================== recto-verso
def build_interleave(
    page: ft.Page, use_cases: UseCases, picker: FilePickerService, notify
) -> ft.View:
    tool = Palette.interleave
    fronts = {"path": None}
    backs = {"path": None}
    refresh = lambda: None  # noqa: E731  (relié plus bas, quand le bouton existe)

    def changed() -> None:
        refresh()

    front_tray = second_tray(picker, tool, fronts, changed, empty="Scan des rectos (pages 1, 3, 5…)",
                             pick_label="Choisir les rectos")
    back_tray = second_tray(picker, tool, backs, changed, empty="Scan des versos (pages 2, 4, 6…)",
                            pick_label="Choisir les versos")
    reversed_backs = switch("Les versos sont dans l'ordre inverse", tool.color, True)

    async def launch(_=None) -> None:
        if not (fronts["path"] and backs["path"]):
            notify("Sélectionnez les deux fichiers.", True)
            return
        if not check(
            notify, lambda: use_cases.interleave_pdfs.validate(fronts["path"], backs["path"])
        ):
            return
        await run_save(
            notify, picker, "Enregistrer le PDF recto-verso", "recto_verso.pdf",
            lambda dest: use_cases.interleave_pdfs.execute(
                fronts["path"], backs["path"], dest, bool(reversed_backs.value)
            ),
            "PDF recto-verso créé",
        )

    action = primary_button("Fusionner et enregistrer", ft.Icons.FLIP, tool.color, launch)
    refresh = bind_ready(action, lambda: bool(fronts["path"] and backs["path"]))

    return page_shell(
        page, "Fusion recto-verso", tool,
        [*_illustration(LOTTIE_INTERLEAVE), front_tray, back_tray, reversed_backs,
         hint("Cas typique : le scanner lit d'abord toutes les rectos, puis la pile retournée "
              "(versos dans l'ordre inverse). Si les versos sont déjà dans l'ordre, désactivez l'option."),
         action],
        icon=ft.Icons.FLIP,
        description="Combinez le scan des rectos et celui des versos en un seul document.",
    )


# ====================================================================== rogner
def build_crop(
    page: ft.Page, use_cases: UseCases, picker: FilePickerService, notify
) -> ft.View:
    tool = Palette.crop
    ready = Ready()
    top = number_input("Haut", tool.color, "0", suffix="mm", decimal=True, on_change=ready, expand=True)
    bottom = number_input("Bas", tool.color, "0", suffix="mm", decimal=True, on_change=ready, expand=True)
    left = number_input("Gauche", tool.color, "0", suffix="mm", decimal=True, on_change=ready, expand=True)
    right = number_input("Droite", tool.color, "0", suffix="mm", decimal=True, on_change=ready, expand=True)
    selection = pages_field(tool.color, "Pages à rogner", "Vide = toutes les pages")

    def margins() -> CropMargins:
        return CropMargins(
            top=read_float(top.value, "Haut", 0.0),
            bottom=read_float(bottom.value, "Bas", 0.0),
            left=read_float(left.value, "Gauche", 0.0),
            right=read_float(right.value, "Droite", 0.0),
        )

    def prepare(path: str):
        wanted = margins()
        text = selection.value or ""
        use_cases.crop_pages.validate(path, text, wanted)
        return wanted, text

    return build_pdf_tool(
        page, picker, notify, use_cases,
        tool=tool, title="Rogner les marges", icon=ft.Icons.CROP,
        description="Retirez les bords inutiles d'un scan. Les marges se mesurent comme à l'écran.",
        controls=[*_illustration(LOTTIE_CROP), ft.Row([top, bottom], spacing=12), ft.Row([left, right], spacing=12), selection,
                  hint("Le contenu n'est pas détruit : la page est seulement recadrée.")],
        button_label="Rogner et enregistrer", button_icon=ft.Icons.CROP,
        save_title="Enregistrer le PDF rogné", suffix="_rogne", success="PDF rogné créé",
        prepare=prepare,
        produce=lambda path, p, dest: use_cases.crop_pages.execute(path, p[1], p[0], dest),
        ready=ready,
    )