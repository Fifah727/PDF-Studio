from __future__ import annotations

import flet as ft

from app.presentation.theme import Palette


def _title(title: str, accent: str, icon: str | None, subtitle: str | None) -> ft.Control:
    """Titre de l'écran : pastille de l'outil (si on connaît son icône), nom, sous-titre éventuel."""
    texts: list[ft.Control] = [
        ft.Text(
            title,
            size=17,
            weight=ft.FontWeight.W_700,
            color=Palette.ink,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
    ]
    if subtitle:
        texts.append(
            ft.Text(
                subtitle,
                size=12,
                color=Palette.ink_muted,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            )
        )
    row: list[ft.Control] = []
    if icon:
        row.append(
            ft.Container(
                width=34,
                height=34,
                border_radius=11,
                bgcolor=ft.Colors.with_opacity(0.14, accent),
                alignment=ft.Alignment(0, 0),
                content=ft.Icon(icon, size=19, color=accent),
            )
        )
    row.append(ft.Column(texts, spacing=0, tight=True, expand=True))
    return ft.Row(
        row,
        spacing=10,
        tight=True,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def tool_app_bar(
    title: str,
    accent: str,
    on_back,
    icon: str | None = None,
    subtitle: str | None = None,
    actions: list[ft.Control] | None = None,
) -> ft.AppBar:
    """
    Barre d'application aux couleurs de l'outil courant.

    - ``accent`` : couleur de l'outil (pastille de l'icône et liseré à droite).
    - ``icon`` : icône de l'outil ; sans elle, seul le titre est affiché (comme avant).
    - ``subtitle`` : courte précision sous le titre (facultative).
    - ``actions`` : boutons supplémentaires, placés avant le liseré (facultatif).
    """
    return ft.AppBar(
        title=_title(title, accent, icon, subtitle),
        center_title=False,
        leading=ft.IconButton(
            icon=ft.Icons.ARROW_BACK_IOS_NEW,
            icon_size=20,
            icon_color=Palette.ink,
            tooltip="Retour",
            on_click=on_back,
        ),
        bgcolor=Palette.surface,
        shape=ft.RoundedRectangleBorder(radius=0),
        toolbar_height=64 if subtitle else 60,
        actions=[
            *(actions or []),
            ft.Container(width=5, height=64 if subtitle else 60, bgcolor=accent),
        ],
    )