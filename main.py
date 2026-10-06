from __future__ import annotations

import logging

import flet as ft

from app import APP_NAME, __version__
from app.infrastructure.app_dirs import app_data_dir
from app.infrastructure.json_settings_store import JsonSettingsStore
from app.infrastructure.recent_files_store import JsonRecentFilesStore
from app.logging_setup import configure_logging
from app.presentation.di import build_use_cases
from app.presentation.router import register_router
from app.presentation.screens.base import FilePickerService
from app.presentation.theme import Palette
from app.presentation.theme_controller import ThemeController
from app.presentation.widgets.feedback import make_notifier

logger = logging.getLogger("app.main")


def main(page: ft.Page) -> None:
    log_file = configure_logging()
    logger.info("Démarrage de %s %s (journal : %s)", APP_NAME, __version__, log_file)

    settings = JsonSettingsStore(app_data_dir() / "settings.json")
    theme = ThemeController(page, settings)
    theme.apply()

    page.title = APP_NAME
    page.padding = 0
    page.window.icon = "icon.png"

    if page.web:
        # Le navigateur ne donne pas accès au chemin des fichiers locaux :
        # les PDF doivent être lus et écrits sur l'appareil.
        page.add(
            ft.Container(
                padding=24,
                content=ft.Text(
                    "PDF Studio fonctionne uniquement en application "
                    "(Windows, macOS, Linux, Android, iOS), pas dans un navigateur.",
                    color=Palette.ink,
                ),
            )
        )
        return

    if not page.platform.is_mobile():
        page.window.maximized = True  # Ouvre la fenêtre en mode agrandi
        page.window.min_width = 420
        page.window.min_height = 520

    use_cases = build_use_cases()
    recents = JsonRecentFilesStore(app_data_dir() / "recents.json")
    picker = FilePickerService(page, settings, recents)
    notify = make_notifier(page, settings)

    register_router(page, use_cases, picker, notify, settings, theme, recents)


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
