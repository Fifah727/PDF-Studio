from __future__ import annotations

import asyncio
import time

import flet as ft

from app import APP_NAME, __version__
from app.domain.settings import THEME_DARK, THEME_LIGHT, THEME_SYSTEM
from app.presentation.screens.base import page_shell
from app.presentation.theme import Palette, Space
from app.presentation.theme_controller import ThemeController
from app.presentation.widgets.buttons import secondary_button
from app.presentation.widgets.cards import card, icon_tile

# Libellé et icône de chaque thème.
THEME_META = {
    THEME_LIGHT: ("Clair", ft.Icons.LIGHT_MODE_OUTLINED),
    THEME_DARK: ("Sombre", ft.Icons.DARK_MODE_OUTLINED),
    THEME_SYSTEM: ("Système", ft.Icons.BRIGHTNESS_AUTO_OUTLINED),
}

# Couleurs des petits aperçus : fixes, car chacun montre un thème précis,
# quel que soit le thème actuellement actif.
_PREVIEW = {
    THEME_LIGHT: dict(bg="#F3F5F9", bar="#CBD3DF", surface="#FFFFFF", dot="#2F80ED"),
    THEME_DARK: dict(bg="#14171D", bar="#363C49", surface="#1F232B", dot="#6FA8FF"),
}

# L'écran est reconstruit quand on change de thème : on ne rejoue l'animation
# d'entrée que si l'on vient réellement d'arriver sur l'écran.
_LAST_BUILD = [0.0]


def _ease(ms: int = 220, curve: ft.AnimationCurve = ft.AnimationCurve.EASE_OUT) -> ft.Animation:
    return ft.Animation(ms, curve)


def _safe_update(*controls: ft.Control) -> None:
    """Met à jour des contrôles sans planter si l'écran a été reconstruit entre-temps."""
    for control in controls:
        try:
            control.update()
        except Exception:  # noqa: BLE001  (contrôle pas (ou plus) affiché)
            pass


def _mini_ui(mode: str, bar_width: int) -> ft.Control:
    """Mini maquette d'écran (barre de titre + une carte) dans les couleurs d'un thème."""
    c = _PREVIEW[mode]
    return ft.Container(
        bgcolor=c["bg"],
        padding=7,
        expand=True,
        content=ft.Column(
            [
                ft.Container(width=bar_width, height=6, border_radius=3, bgcolor=c["bar"]),
                ft.Container(
                    height=22,
                    border_radius=6,
                    bgcolor=c["surface"],
                    padding=5,
                    content=ft.Row(
                        [
                            ft.Container(width=9, height=9, border_radius=5, bgcolor=c["dot"]),
                            ft.Container(height=5, border_radius=3, bgcolor=c["bar"], expand=True),
                        ],
                        spacing=4,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ),
            ],
            spacing=5,
        ),
    )


def _preview(mode: str) -> ft.Control:
    if mode == THEME_SYSTEM:  # moitié clair, moitié sombre
        inner: ft.Control = ft.Row(
            [_mini_ui(THEME_LIGHT, 18), _mini_ui(THEME_DARK, 18)], spacing=0, expand=True
        )
    else:
        inner = _mini_ui(mode, 34)
    return ft.Container(
        height=66,
        border_radius=10,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=inner,
    )


def build_settings(
    page: ft.Page,
    settings,
    theme: ThemeController,
    notify,
) -> ft.View:
    """
    Écran des paramètres. Chaque réglage s'applique et se sauvegarde
    immédiatement : pas de bouton « Enregistrer ». Une pastille « Enregistré »
    le confirme à chaque changement.
    """
    tool = Palette.neutral
    desktop = not (page.web or page.platform.is_mobile())
    current = settings.current
    active = tool.color if Palette.dark else Palette.ink

    now = time.monotonic()
    play_entrance = now - _LAST_BUILD[0] > 2.0
    _LAST_BUILD[0] = now

    # ------------------------------------------------------------ retour « enregistré »
    saved_token = {"n": 0}
    saved_chip = ft.Container(
        opacity=0,
        animate_opacity=_ease(220),
        padding=ft.Padding(left=10, right=12, top=5, bottom=5),
        border_radius=14,
        bgcolor=tool.soft,
        content=ft.Row(
            [
                ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=16, color=Palette.ink),
                ft.Text("Enregistré", size=12, weight=ft.FontWeight.W_600, color=Palette.ink),
            ],
            spacing=6,
            tight=True,
        ),
    )

    async def hide_saved_later(token: int) -> None:
        await asyncio.sleep(1.6)
        if token == saved_token["n"]:
            saved_chip.opacity = 0
            _safe_update(saved_chip)

    def flash_saved() -> None:
        saved_token["n"] += 1
        saved_chip.opacity = 1
        _safe_update(saved_chip)
        page.run_task(hide_saved_later, saved_token["n"])

    intro = ft.Row(
        [
            ft.Icon(ft.Icons.AUTO_MODE_OUTLINED, size=18, color=Palette.ink_muted),
            ft.Text(
                "Vos réglages s'enregistrent automatiquement.",
                size=13,
                color=Palette.ink_muted,
                expand=True,
            ),
            saved_chip,
        ],
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    # ------------------------------------------------------------ en-têtes de section
    def section_header(
        icon: str | None, accent, title: str, subtitle: str, leading: ft.Control | None = None
    ) -> ft.Control:
        return ft.Row(
            [
                leading if leading is not None else icon_tile(icon, accent, size=34),
                ft.Column(
                    [
                        ft.Text(title, size=15, weight=ft.FontWeight.W_700, color=Palette.ink),
                        ft.Text(subtitle, size=12.5, color=Palette.ink_muted),
                    ],
                    spacing=1,
                    expand=True,
                ),
            ],
            spacing=Space.sm,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    # ------------------------------------------------------------ apparence
    chosen = {"theme": current.theme}
    accent_theme = Palette.watermark

    def theme_glyph(value: str) -> ft.Control:
        return ft.Icon(THEME_META[value][1], size=20, color=accent_theme.color)

    header_icon = ft.AnimatedSwitcher(
        content=theme_glyph(chosen["theme"]),
        transition=ft.AnimatedSwitcherTransition.ROTATION,
        duration=350,
    )
    header_tile = ft.Container(
        width=34,
        height=34,
        border_radius=10,
        bgcolor=accent_theme.soft,
        alignment=ft.Alignment(0, 0),
        content=header_icon,
    )

    tiles: dict[str, dict] = {}

    def paint_tile(value: str) -> None:
        refs = tiles[value]
        selected = chosen["theme"] == value
        label, icon = THEME_META[value]
        refs["box"].border = ft.Border.all(2 if selected else 1, active if selected else Palette.line)
        refs["label"].color = Palette.ink if selected else Palette.ink_muted
        refs["label"].weight = ft.FontWeight.W_700 if selected else ft.FontWeight.W_500
        refs["mark"].content = ft.Icon(
            ft.Icons.CHECK_CIRCLE if selected else icon,
            size=16,
            color=active if selected else Palette.ink_muted,
        )

    def select_theme(value: str):
        def handler(_=None) -> None:
            if chosen["theme"] == value:
                return
            chosen["theme"] = value
            for key in tiles:
                paint_tile(key)
            header_icon.content = theme_glyph(value)
            page.update()
            theme.set_mode(value)   # peut reconstruire l'écran avec le nouveau thème
            flash_saved()

        return handler

    for value in (THEME_LIGHT, THEME_DARK, THEME_SYSTEM):
        label, icon = THEME_META[value]
        mark = ft.AnimatedSwitcher(
            content=ft.Icon(icon, size=16, color=Palette.ink_muted),
            transition=ft.AnimatedSwitcherTransition.SCALE,
            duration=220,
        )
        label_text = ft.Text(label, size=12.5, color=Palette.ink_muted)
        box = ft.Container(
            expand=1,
            padding=ft.Padding(left=6, right=6, top=6, bottom=9),
            border_radius=14,
            bgcolor=Palette.surface,
            border=ft.Border.all(1, Palette.line),
            animate=_ease(220),
            ink=True,
            on_click=select_theme(value),
            content=ft.Column(
                [
                    _preview(value),
                    ft.Row(
                        [mark, label_text],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=6,
                    ),
                ],
                spacing=8,
            ),
        )
        tiles[value] = {"box": box, "label": label_text, "mark": mark}
        paint_tile(value)

    appearance = card(
        [
            ft.Row([tiles[v]["box"] for v in (THEME_LIGHT, THEME_DARK, THEME_SYSTEM)], spacing=Space.sm),
            ft.Text(
                "« Système » suit automatiquement le thème de votre appareil.",
                size=12.5,
                color=Palette.ink_muted,
            ),
        ]
    )

    # ------------------------------------------------------------ interrupteurs
    def toggle_row(name: str, icon: str, accent, title: str, subtitle: str) -> ft.Control:
        switch = ft.Switch(value=bool(getattr(current, name)), active_color=active)
        badge = ft.Container(
            width=38,
            height=38,
            border_radius=11,
            alignment=ft.Alignment(0, 0),
            animate=_ease(240),
            content=ft.Icon(icon, size=20),
        )

        def paint() -> None:
            on = bool(switch.value)
            badge.bgcolor = accent.soft if on else tool.soft
            badge.content.color = accent.color if on else Palette.ink_muted

        def apply(value: bool) -> None:
            switch.value = value
            settings.update(**{name: value})
            paint()
            page.update()
            flash_saved()

        switch.on_change = lambda e: apply(bool(e.control.value))
        paint()
        return ft.Container(
            border_radius=12,
            ink=True,
            padding=ft.Padding(left=4, right=4, top=8, bottom=8),
            on_click=lambda _: apply(not switch.value),
            content=ft.Row(
                [
                    badge,
                    ft.Column(
                        [
                            ft.Text(title, size=14, weight=ft.FontWeight.W_600, color=Palette.ink),
                            ft.Text(subtitle, size=12.5, color=Palette.ink_muted),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    switch,
                ],
                spacing=Space.md,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    divider = lambda: ft.Divider(height=1, color=Palette.line)  # noqa: E731

    saving_rows: list[ft.Control] = [
        toggle_row(
            "remember_last_folder",
            ft.Icons.FOLDER_OPEN_OUTLINED,
            Palette.compress,
            "Se souvenir du dernier dossier",
            "Les boîtes de dialogue s'ouvrent là où vous avez travaillé en dernier.",
        )
    ]
    if desktop:
        saving_rows += [
            divider(),
            toggle_row(
                "offer_open_folder",
                ft.Icons.OPEN_IN_NEW,
                Palette.compress,
                "Proposer d'ouvrir le dossier",
                "Un bouton apparaît après chaque enregistrement réussi.",
            ),
        ]
    saving = card(saving_rows)

    images = card(
        [
            toggle_row(
                "fit_a4_default",
                ft.Icons.ASPECT_RATIO,
                Palette.images,
                "Ajuster à A4 par défaut",
                "Valeur initiale de l'option dans « Images vers PDF ».",
            )
        ]
    )

    # ------------------------------------------------------------ réinitialisation (avec confirmation)
    confirm_state = {"asking": False, "token": 0}
    reset_hint = ft.Text("Rétablit toutes les valeurs par défaut.", size=12.5, color=Palette.ink_muted)

    def do_reset(_=None) -> None:
        confirm_state["asking"] = False
        settings.reset()
        theme.refresh()  # reconstruit cet écran avec les valeurs par défaut
        notify("Paramètres réinitialisés.")

    normal_button = secondary_button("Réinitialiser", ft.Icons.RESTART_ALT, lambda _: ask())
    confirm_button = ft.TextButton(
        content="Confirmer ?",
        icon=ft.Icons.CHECK,
        on_click=do_reset,
        style=ft.ButtonStyle(color=Palette.danger),
    )
    slot = ft.AnimatedSwitcher(
        content=normal_button, transition=ft.AnimatedSwitcherTransition.SCALE, duration=200
    )

    def back_to_normal() -> None:
        confirm_state["asking"] = False
        slot.content = normal_button
        reset_hint.value = "Rétablit toutes les valeurs par défaut."
        reset_hint.color = Palette.ink_muted
        _safe_update(slot, reset_hint)

    async def cancel_later(token: int) -> None:
        await asyncio.sleep(3.5)
        if confirm_state["asking"] and token == confirm_state["token"]:
            back_to_normal()

    def ask() -> None:
        confirm_state["asking"] = True
        confirm_state["token"] += 1
        slot.content = confirm_button
        reset_hint.value = "Touchez « Confirmer » pour tout réinitialiser."
        reset_hint.color = Palette.danger
        page.update()
        page.run_task(cancel_later, confirm_state["token"])

    maintenance = card(
        [
            ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text(
                                "Réinitialiser les paramètres",
                                size=14,
                                weight=ft.FontWeight.W_600,
                                color=Palette.ink,
                            ),
                            reset_hint,
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    slot,
                ],
                spacing=Space.md,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        ]
    )

    # ------------------------------------------------------------ accès à « À propos »
    about = ft.Container(
        border_radius=14,
        ink=True,
        padding=Space.md,
        bgcolor=Palette.surface,
        border=ft.Border.all(1, Palette.line),
        on_click=lambda _: page.run_task(page.push_route, "/a-propos"),
        content=ft.Row(
            [
                icon_tile(ft.Icons.INFO_OUTLINE, tool, size=34),
                ft.Column(
                    [
                        ft.Text(f"À propos de {APP_NAME}", size=14, weight=ft.FontWeight.W_600, color=Palette.ink),
                        ft.Text(f"Version {__version__}", size=12.5, color=Palette.ink_muted),
                    ],
                    spacing=1,
                    expand=True,
                ),
                ft.Icon(ft.Icons.CHEVRON_RIGHT, color=Palette.ink_muted),
            ],
            spacing=Space.md,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    # ------------------------------------------------------------ apparition en cascade
    reveals: list[ft.Container] = []

    def reveal(control: ft.Control) -> ft.Control:
        box = ft.Container(
            content=control,
            opacity=0 if play_entrance else 1,
            offset=ft.Offset(0, 0.05 if play_entrance else 0),
            animate_opacity=_ease(380),
            animate_offset=_ease(380, ft.AnimationCurve.EASE_OUT_CUBIC),
        )
        reveals.append(box)
        return box

    def block(header: ft.Control, body: ft.Control) -> ft.Control:
        return reveal(ft.Column([header, body], spacing=Space.sm))

    content: list[ft.Control] = [
        reveal(intro),
        block(
            section_header(None, accent_theme, "Apparence", "Choisissez l'ambiance de l'application", leading=header_tile),
            appearance,
        ),
        block(
            section_header(ft.Icons.SAVE_OUTLINED, Palette.compress, "Enregistrement", "Où et comment vos fichiers sont gardés"),
            saving,
        ),
        block(
            section_header(ft.Icons.IMAGE_OUTLINED, Palette.images, "Images vers PDF", "Valeurs par défaut de l'outil"),
            images,
        ),
        block(
            section_header(ft.Icons.RESTART_ALT, Palette.password, "Réinitialisation", "Revenir aux réglages d'origine"),
            maintenance,
        ),
        reveal(about),
    ]

    async def play() -> None:
        await asyncio.sleep(0.12)
        for box in reveals:
            box.opacity = 1
            box.offset = ft.Offset(0, 0)
            try:
                page.update()
            except Exception:  # noqa: BLE001  (écran quitté entre-temps)
                return
            await asyncio.sleep(0.07)

    if play_entrance:
        page.run_task(play)

    return page_shell(page, "Paramètres", tool, content)