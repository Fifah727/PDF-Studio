"""Cartes et blocs de mise en page réutilisables."""

from __future__ import annotations

from typing import Callable, Iterable

import flet as ft

from app.presentation.theme import Palette, Space, ToolAccent


def icon_tile(icon: str, tool: ToolAccent, size: int = 44) -> ft.Container:
    return ft.Container(
        width=size,
        height=size,
        border_radius=size // 4,
        bgcolor=tool.soft,
        alignment=ft.Alignment(0, 0),
        content=ft.Icon(icon, color=tool.color, size=size * 0.5),
    )


def tool_card(
    icon: str,
    title: str,
    description: str,
    tool: ToolAccent,
    on_click: Callable,
) -> ft.Container:
    """Carte d'outil de l'accueil : icône teintée, titre, description."""

    def on_hover(event) -> None:
        hovered = event.data in (True, "true", "True")
        control = event.control
        control.border = ft.Border.all(1, tool.color if hovered else Palette.line)
        control.scale = 1.015 if hovered else 1.0
        control.shadow = (
            ft.BoxShadow(blur_radius=18, color="#00000022", offset=ft.Offset(0, 6))
            if hovered and not Palette.dark
            else None
        )
        control.update()

    return ft.Container(
        col={"xs": 12, "sm": 6},
        padding=Space.md,
        border=ft.Border.all(1, Palette.line),
        border_radius=16,
        # Un voile de la couleur de l'outil, qui s'efface vers la droite : on repère
        # les familles d'outils au premier regard sans alourdir la carte.
        gradient=ft.LinearGradient(
            begin=ft.Alignment(-1, 0),
            end=ft.Alignment(1, 0),
            colors=[ft.Colors.with_opacity(0.85, tool.soft), Palette.surface],
        ),
        ink=True,
        scale=1.0,
        animate_scale=ft.Animation(140, ft.AnimationCurve.EASE_OUT),
        on_click=on_click,
        on_hover=on_hover,
        content=ft.Row(
            [
                icon_tile(icon, tool),
                ft.Column(
                    [
                        ft.Text(
                            title, size=15, weight=ft.FontWeight.W_600, color=Palette.ink
                        ),
                        ft.Text(description, size=12.5, color=Palette.ink_muted),
                    ],
                    spacing=2,
                    expand=True,
                ),
                ft.Icon(ft.Icons.CHEVRON_RIGHT, size=20, color=Palette.ink_muted),
            ],
            spacing=Space.md,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def hero_card(
    title: str,
    subtitle: str,
    badges: list[tuple[str, str]],
    actions: list[ft.Control],
    leading: ft.Control | None = None,
    eyebrow: str | None = None,
) -> ft.Container:
    """
    Bandeau d'accueil : dégradé, marque, accès rapides et points forts.

    ``leading`` remplace la pastille d'icône par un visuel (le logo) ;
    ``eyebrow`` ajoute une petite ligne au-dessus du titre (salutation).
    """
    on_hero = Palette.on_hero
    faint = lambda opacity: ft.Colors.with_opacity(opacity, on_hero)  # noqa: E731

    mark = leading or ft.Container(
        width=52,
        height=52,
        border_radius=14,
        bgcolor=faint(0.16),
        alignment=ft.Alignment(0, 0),
        content=ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, color=on_hero, size=28),
    )
    heading: list[ft.Control] = []
    if eyebrow:
        heading.append(
            ft.Text(eyebrow, size=13, weight=ft.FontWeight.W_500, color=faint(0.7))
        )
    heading += [
        ft.Text(title, size=26, weight=ft.FontWeight.W_800, color=on_hero),
        ft.Text(subtitle, size=13.5, color=faint(0.78)),
    ]
    brand = ft.Row(
        [
            mark,
            ft.Column(heading, spacing=1, expand=True),
            ft.Column(actions, spacing=0, tight=True),
        ],
        spacing=Space.md,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    chips = ft.Row(
        [
            ft.Container(
                padding=ft.Padding(left=10, right=12, top=6, bottom=6),
                border_radius=16,
                bgcolor=faint(0.12),
                content=ft.Row(
                    [
                        ft.Icon(icon, size=14, color=on_hero),
                        ft.Text(text, size=12, color=on_hero),
                    ],
                    spacing=6,
                    tight=True,
                ),
            )
            for icon, text in badges
        ],
        wrap=True,
        spacing=Space.sm,
        run_spacing=Space.sm,
    )

    return ft.Container(
        border_radius=18,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        gradient=ft.LinearGradient(
            begin=ft.Alignment(-1, -1),
            end=ft.Alignment(1, 1),
            colors=[Palette.hero_start, Palette.hero_end],
        ),
        content=ft.Stack(
            [
                # Cercles décoratifs, discrets, pour casser l'aplat du dégradé.
                ft.Container(
                    right=-40, top=-50, width=170, height=170, border_radius=85,
                    bgcolor=faint(0.07),
                ),
                ft.Container(
                    right=60, bottom=-70, width=120, height=120, border_radius=60,
                    bgcolor=faint(0.05),
                ),
                ft.Container(
                    padding=Space.lg,
                    content=ft.Column([brand, chips], spacing=Space.md),
                ),
            ]
        ),
    )


def tool_header(icon: str, tool: ToolAccent, description: str) -> ft.Control:
    """En-tête d'un écran d'outil : icône de l'outil + ce qu'il fait."""
    return ft.Row(
        [
            icon_tile(icon, tool, size=48),
            ft.Text(description, size=14, color=Palette.ink_muted, expand=True),
        ],
        spacing=Space.md,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def section_label(text: str) -> ft.Text:
    return ft.Text(
        text.upper(),
        size=11.5,
        weight=ft.FontWeight.W_700,
        color=Palette.ink_muted,
    )


def card(controls: Iterable[ft.Control], padding: int = Space.md) -> ft.Container:
    """Bloc à bordure fine, fond « surface »."""
    return ft.Container(
        padding=padding,
        border=ft.Border.all(1, Palette.line),
        border_radius=14,
        bgcolor=Palette.surface,
        content=ft.Column(list(controls), spacing=Space.md),
    )


def setting_row(title: str, subtitle: str, control: ft.Control) -> ft.Control:
    return ft.Row(
        [
            ft.Column(
                [
                    ft.Text(title, size=14, weight=ft.FontWeight.W_600, color=Palette.ink),
                    ft.Text(subtitle, size=12.5, color=Palette.ink_muted),
                ],
                spacing=2,
                expand=True,
            ),
            control,
        ],
        spacing=Space.md,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
