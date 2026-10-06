"""Applique le thème choisi (clair / sombre / système) à l'application."""

from __future__ import annotations

import logging
from typing import Callable

import flet as ft

from app.domain.settings import THEME_DARK, THEME_LIGHT, THEME_SYSTEM
from app.presentation.theme import Palette, build_theme

logger = logging.getLogger(__name__)


class ThemeController:
    """
    Source unique de vérité pour le thème.

    - ``apply()`` résout le mode (le mode « système » suit la luminosité
      de l'OS), met à jour ``Palette`` et les propriétés de la page ;
    - ``set_mode()`` mémorise le choix puis prévient les abonnés (le
      routeur reconstruit la vue courante avec les nouvelles couleurs) ;
    - un changement de thème de l'OS est suivi en direct en mode « système ».
    """

    def __init__(self, page: ft.Page, settings):
        self._page = page
        self._settings = settings
        self._listeners: list[Callable[[], None]] = []
        page.on_platform_brightness_change = self._on_system_change

    def subscribe(self, listener: Callable[[], None]) -> None:
        self._listeners.append(listener)

    def is_dark(self) -> bool:
        mode = self._settings.current.theme
        if mode == THEME_DARK:
            return True
        if mode == THEME_LIGHT:
            return False
        return self._page.platform_brightness == ft.Brightness.DARK

    def apply(self) -> None:
        dark = self.is_dark()
        Palette.apply(dark)
        page = self._page
        page.theme_mode = ft.ThemeMode.DARK if dark else ft.ThemeMode.LIGHT
        page.theme = build_theme()
        page.dark_theme = build_theme()
        page.bgcolor = Palette.paper

    def set_mode(self, mode: str) -> None:
        self._settings.update(theme=mode)
        self.refresh()

    def refresh(self) -> None:
        """Réapplique le thème et reconstruit la vue courante."""
        self.apply()
        for listener in self._listeners:
            listener()

    def _on_system_change(self, _=None) -> None:
        if self._settings.current.theme == THEME_SYSTEM:
            self.refresh()
