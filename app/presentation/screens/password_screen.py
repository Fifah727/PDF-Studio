from __future__ import annotations

import flet as ft

from app.presentation.di import UseCases
from app.presentation.screens.base import (
    FilePickerService,
    bind_ready,
    page_shell,
    pdf_chooser,
    run_save,
    suggest_name,
)
from app.presentation.theme import Palette
from app.presentation.widgets.buttons import primary_button
from app.presentation.widgets.fields import password_field
from app.presentation.widgets.file_tray import FileTray
from app.presentation.widgets.lottie import lottie

PROTECT = "protect"
UNLOCK = "unlock"

# Libellés selon le mode : déverrouiller ne demande un mot de passe que si le PDF en exige un pour s'ouvrir.
LABELS = {
    UNLOCK: "Mot de passe (facultatif)",
    PROTECT: "Mot de passe",
}
UNLOCK_HELP = (
    "Laissez vide si le PDF s'ouvre librement mais interdit la copie, l'impression ou la "
    "modification. Saisissez le mot de passe seulement si le PDF en demande un pour s'ouvrir."
)

LOTTIE_SRC = "animations/unlock_pdf.json"  # dans assets/animations/


def build_password(
    page: ft.Page, use_cases: UseCases, picker: FilePickerService, notify
) -> ft.View:
    tool = Palette.password
    state = {"path": None, "total": None}
    tray = FileTray(tool)

    animation = lottie(LOTTIE_SRC, 150, reverse=True)
    illustration: list[ft.Control] = (
        [ft.Row([animation], alignment=ft.MainAxisAlignment.CENTER)] if animation else []
    )

    mode = ft.RadioGroup(
        value=UNLOCK,
        content=ft.Row(
            [
                ft.Radio(value=UNLOCK, label="Déverrouiller", active_color=tool.color),
                ft.Radio(value=PROTECT, label="Protéger", active_color=tool.color),
            ],
            spacing=24,
        ),
    )
    password = password_field(tool.color, LABELS[UNLOCK])
    confirm = password_field(tool.color, "Confirmer le mot de passe")
    confirm.visible = False
    unlock_help = ft.Text(UNLOCK_HELP, size=12.5, color=Palette.ink_muted)

    async def launch(_=None):
        path = state["path"]
        if not path:
            notify("Sélectionnez d'abord un PDF.", True)
            return
        secret = password.value or ""
        protecting = mode.value == PROTECT

        # Protéger exige un mot de passe ; déverrouiller non (restrictions seules).
        if protecting:
            if not secret:
                notify("Saisissez le mot de passe.", True)
                return
            if secret != (confirm.value or ""):
                notify("Les deux mots de passe ne correspondent pas.", True)
                return

        if protecting:
            await run_save(
                notify,
                picker,
                "Enregistrer le PDF protégé",
                suggest_name(path, "_protege"),
                lambda destination: use_cases.protect_pdf.execute(path, secret, destination),
                "PDF protégé créé",
            )
        else:
            await run_save(
                notify,
                picker,
                "Enregistrer le PDF déverrouillé",
                suggest_name(path, "_deverrouille"),
                lambda destination: use_cases.unlock_pdf.execute(path, secret, destination),
                "PDF déverrouillé créé",
            )

    action = primary_button("Appliquer et enregistrer", ft.Icons.LOCK_OUTLINE, tool.color, launch)
    refresh = bind_ready(
        action,
        lambda: bool(state["path"]) and (mode.value == UNLOCK or bool(password.value)),
    )
    # Un PDF protégé doit pouvoir être choisi ici : pas de lecture des pages.
    choose, clear = pdf_chooser(picker, use_cases, tray, state, refresh, count_pages=False)
    tray.bind(choose, clear)

    def on_mode_change(_):
        protecting = mode.value == PROTECT
        confirm.visible = protecting
        unlock_help.visible = not protecting
        password.label = LABELS[mode.value]
        if not protecting:
            confirm.value = ""
        page.update()
        refresh()

    mode.on_change = on_mode_change
    password.on_change = lambda _: refresh()
    password.on_submit = launch

    return page_shell(
        page,
        "Mot de passe",
        tool,
        [*illustration, tray, mode, unlock_help, password, confirm, action],
        icon=ft.Icons.LOCK_OUTLINE,
        description=(
            "Protégez un PDF (chiffrement AES-256) ou retirez ses restrictions. Un PDF "
            "qui s'ouvre librement se déverrouille sans mot de passe ; s'il en demande un "
            "pour s'ouvrir, saisissez-le. Le mot de passe n'est ni enregistré ni transmis."
        ),
    )