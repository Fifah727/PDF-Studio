"""
Écran « À propos » : l'identité de l'application, ce qu'elle promet, et de quoi elle est faite.

Presque tout est calculé à partir de l'application elle-même (liste des outils,
versions réellement installées, dossier de données) : l'écran ne peut donc pas
« mentir » ni vieillir quand on ajoute un outil.

Mouvement : l'écran entre en cascade, les carreaux des outils apparaissent un à un et
le « voyage d'un fichier » s'illumine étape par étape. Tout est décoratif : si une
animation échoue (contrôle pas encore affiché, page quittée…), l'écran s'affiche
simplement dans son état final.
"""

from __future__ import annotations

import asyncio
import platform

import flet as ft

from app import (
    APP_NAME,
    AUTHOR_COUNTRY,
    AUTHOR_EMAIL,
    AUTHOR_NAME,
    AUTHOR_ROLE,
    COPYRIGHT_YEAR,
    __version__,
)
from app.infrastructure.app_dirs import app_data_dir
from app.infrastructure.diagnostics import build_report, existing_data_file, library_versions
from app.presentation.screens.base import page_shell
from app.presentation.screens.home_screen import TOOLS
from app.presentation.system import reveal_in_folder
from app.presentation.theme import Palette, Space
from app.presentation.widgets.buttons import secondary_button
from app.presentation.widgets.cards import card, icon_tile, section_label
from app.presentation.widgets.lottie import lottie

ABOUT_ROUTE = "/a-propos"

AVATAR_LOTTIE_SRC = "animations/developer_avatar.json"  # dans assets/animations/
AVATAR_SIZE = 84
AVATAR_BG = "#FFC83D"  # jaune du fond de l'animation : jamais de « trou noir » si une image tarde à se dessiner

PROMISES = (
    (ft.Icons.WIFI_OFF, "Hors-ligne", "Fonctionne sans Internet", "password"),
    (ft.Icons.PERSON_OFF_OUTLINED, "Sans compte", "Ouvrez, utilisez, c'est tout", "signature"),
    (ft.Icons.SHIELD_OUTLINED, "Originaux intacts", "Le résultat est toujours un nouveau fichier", "merge"),
    (ft.Icons.VISIBILITY_OFF_OUTLINED, "Aucun suivi", "Aucune donnée n'est collectée", "metadata"),
)

# Date de la dernière révision du texte ci-dessous : à mettre à jour à chaque modification.
PRIVACY_UPDATED = "octobre 2026"

PRIVACY_SUMMARY = "Aucune donnée collectée : tout reste sur votre appareil."

# (titre, texte). « {email} » est remplacé par l'adresse de contact.
PRIVACY_POLICY = (
    (
        "En bref",
        "L'application fonctionne entièrement sur votre appareil. Nous ne collectons, "
        "ne transmettons, ne partageons et ne vendons aucune donnée personnelle.",
    ),
    (
        "Vos fichiers",
        "Les PDF et les images que vous ouvrez sont lus et traités localement : ils ne sont "
        "envoyés à aucun serveur. Vos originaux ne sont jamais modifiés ; le résultat est "
        "toujours un nouveau fichier, enregistré à l'endroit que vous choisissez. Les mots de "
        "passe que vous saisissez servent uniquement au traitement en cours.",
    ),
    (
        "Ce qui est gardé sur votre appareil",
        "Seuls vos réglages et la liste des derniers fichiers créés (nom, emplacement, date) "
        "sont conservés, dans le dossier de données indiqué plus haut. Vous pouvez retirer un "
        "fichier de cette liste ou l'effacer entièrement depuis l'accueil ; supprimer ce dossier "
        "ou désinstaller l'application supprime tout le reste.",
    ),
    (
        "Aucun suivi",
        "Pas de compte, pas de publicité, pas d'outil d'analyse, pas de traceur ni d'identifiant "
        "publicitaire. Aucun rapport n'est envoyé automatiquement, même en cas d'erreur.",
    ),
    (
        "Connexion Internet",
        "Aucune connexion n'est nécessaire pour traiter vos fichiers. Seules les actions que "
        "vous déclenchez vous-même touchent à l'extérieur de l'application : « Écrire un "
        "e-mail » ouvre votre messagerie, et les boutons « Copier » placent un texte dans "
        "le presse-papiers de votre appareil.",
    ),
    (
        "Informations de diagnostic",
        "Le bouton « Copier les infos de diagnostic » rassemble des informations techniques "
        "(version de l'application, bibliothèques, système) dans votre presse-papiers. Rien "
        "n'est envoyé : c'est vous qui décidez de les coller dans un message si vous demandez de l'aide.",
    ),
    (
        "Enfants",
        "Comme aucune donnée n'est collectée, aucune donnée d'enfant ne l'est non plus.",
    ),
    (
        "Modifications de cette politique",
        "Si l'application évolue d'une façon qui change ces règles, ce texte sera mis à jour "
        "avant la sortie de la version concernée, avec une nouvelle date de révision.",
    ),
    (
        "Une question ?",
        "Écrivez à {email}.",
    ),
)

# Premier paragraphe de l'écran ; les nombres sont calculés à partir de la liste des outils.
APP_DESCRIPTION = (
    "Cette application réunit au même endroit tout ce qu'il faut pour travailler vos PDF : "
    "extraire, fusionner, diviser, pivoter ou réorganiser des pages, compresser un fichier, "
    "ajouter une signature, un filigrane ou des numéros de page, protéger un document par "
    "mot de passe, transformer des images en PDF ou en récupérer le texte."
)
APP_DESCRIPTION_2 = (
    "{tools} outils, répartis en {groups} catégories, vous accompagnent de la simple retouche "
    "jusqu'au traitement de plusieurs fichiers à la fois. Tout se passe sur votre appareil, sans "
    "compte ni connexion Internet, et vos documents d'origine ne sont jamais modifiés : "
    "le résultat est toujours un nouveau fichier, enregistré où vous le souhaitez."
)

JOURNEY = (
    (ft.Icons.DESCRIPTION_OUTLINED, "Votre PDF"),
    (ft.Icons.MEMORY, "Traité ici, sur l'appareil"),
    (ft.Icons.SAVE_ALT, "Enregistré où vous voulez"),
)

_ENTER_FADE = ft.Animation(420, ft.AnimationCurve.EASE_OUT)
_ENTER_SLIDE = ft.Animation(520, ft.AnimationCurve.EASE_OUT)
_POP = ft.Animation(260, ft.AnimationCurve.EASE_OUT_BACK)

# Chaque ouverture de l'écran prend un numéro : une boucle d'animation plus ancienne s'arrête seule.
_generation = [0]


def _initials(name: str) -> str:
    return "".join(part[0] for part in name.split()[:2]).upper()


def _safe_update(*controls: ft.Control) -> bool:
    """Met à jour des contrôles qui ne sont peut-être pas (ou plus) affichés."""
    ok = True
    for control in controls:
        try:
            control.update()
        except Exception:  # noqa: BLE001 - l'animation est décorative
            ok = False
    return ok


def _avatar(name: str) -> ft.Control:
    """
    Portrait animé de la développeuse, rond ; repli : pastille avec les initiales
    (si ``flet-lottie`` n'est pas installé).
    """
    animation = lottie(AVATAR_LOTTIE_SRC, AVATAR_SIZE, width=AVATAR_SIZE)
    if animation is not None:
        return ft.Container(
            width=AVATAR_SIZE,
            height=AVATAR_SIZE,
            border_radius=AVATAR_SIZE // 2,
            bgcolor=AVATAR_BG,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=animation,
        )
    return ft.Container(
        width=AVATAR_SIZE,
        height=AVATAR_SIZE,
        border_radius=AVATAR_SIZE // 2,
        gradient=ft.LinearGradient(
            begin=ft.Alignment(-1, -1),
            end=ft.Alignment(1, 1),
            colors=[Palette.hero_start, Palette.hero_end],
        ),
        alignment=ft.Alignment(0, 0),
        content=ft.Text(
            _initials(name),
            size=26,
            weight=ft.FontWeight.W_700,
            color=Palette.on_hero,
        ),
    )


def _promises() -> ft.Control:
    def promise(icon: str, title: str, detail: str, accent_name: str) -> ft.Control:
        return ft.Container(
            col={"xs": 6, "md": 3},
            padding=Space.md,
            border=ft.Border.all(1, Palette.line),
            border_radius=14,
            bgcolor=Palette.surface,
            content=ft.Column(
                [
                    icon_tile(icon, getattr(Palette, accent_name), size=38),
                    ft.Text(title, size=14, weight=ft.FontWeight.W_700, color=Palette.ink),
                    ft.Text(detail, size=12, color=Palette.ink_muted),
                ],
                spacing=6,
            ),
        )

    return ft.ResponsiveRow(
        [promise(*item) for item in PROMISES],
        columns=12,
        spacing=Space.sm,
        run_spacing=Space.sm,
    )


def _collapsible(page: ft.Page, title: str, subtitle: str, body: ft.Control, subtitle_color=None) -> ft.Control:
    """Carte repliable : un en-tête cliquable (titre, résumé, chevron) et un corps masqué au départ."""
    body_box = ft.Container(content=body, visible=False, padding=ft.Padding(left=0, right=0, top=Space.sm, bottom=0))
    chevron = ft.Container(content=ft.Icon(ft.Icons.EXPAND_MORE, size=22, color=Palette.ink_muted))

    def toggle(_=None) -> None:
        body_box.visible = not body_box.visible
        chevron.content = ft.Icon(
            ft.Icons.EXPAND_LESS if body_box.visible else ft.Icons.EXPAND_MORE,
            size=22, color=Palette.ink_muted,
        )
        page.update()

    return card(
        [
            ft.Container(
                ink=True,
                border_radius=10,
                on_click=toggle,
                content=ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text(title, size=14, weight=ft.FontWeight.W_700, color=Palette.ink),
                                ft.Text(subtitle, size=12, color=subtitle_color or Palette.ink_muted),
                            ],
                            spacing=1,
                            expand=True,
                        ),
                        chevron,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ),
            body_box,
        ]
    )


def _privacy_body() -> ft.Control:
    blocks: list[ft.Control] = []
    for title, text in PRIVACY_POLICY:
        blocks.append(
            ft.Column(
                [
                    ft.Text(title, size=13.5, weight=ft.FontWeight.W_700, color=Palette.ink),
                    ft.Text(text.format(email=AUTHOR_EMAIL), size=12.5, color=Palette.ink_muted, selectable=True),
                ],
                spacing=2,
            )
        )
    return ft.Column(blocks, spacing=Space.md)


def _under_the_hood(libraries: list) -> ft.Control:
    rows: list[ft.Control] = []
    for library, version in libraries:
        rows.append(
            ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text(library.label, size=14, weight=ft.FontWeight.W_600, color=Palette.ink),
                            ft.Text(f"{library.role} · {library.license}", size=12, color=Palette.ink_muted),
                        ],
                        spacing=1,
                        expand=True,
                    ),
                    ft.Text(
                        version or "indisponible",
                        size=13,
                        color=Palette.ink if version else Palette.danger,
                        weight=ft.FontWeight.W_600,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
    return ft.Column(rows, spacing=Space.md)


# ====================================================================== écran
def build_about(page: ft.Page, notify) -> ft.View:
    tool = Palette.neutral
    centered = ft.CrossAxisAlignment.CENTER
    desktop = not (page.web or page.platform.is_mobile())
    _generation[0] += 1
    generation = _generation[0]

    def go(route: str):
        def navigate(_) -> None:
            page.run_task(page.push_route, route)

        return navigate

    def toast(message: str, error: bool = False) -> None:
        """Notification (snackbar) seule : ici, pas de bandeau vert dans l'écran."""
        notify(message, error, show_banner=False)

    # ------------------------------------------------------------ actions
    async def write_email(_=None) -> None:
        try:
            await ft.UrlLauncher().launch_url(f"mailto:{AUTHOR_EMAIL}")
        except Exception:
            toast(f"Impossible d'ouvrir votre messagerie. Écrivez à {AUTHOR_EMAIL}.", True)

    async def copy_email(_=None) -> None:
        try:
            await ft.Clipboard().set(AUTHOR_EMAIL)
            toast("Adresse e-mail copiée.")
        except Exception:
            toast(f"Copie impossible. Adresse : {AUTHOR_EMAIL}", True)

    async def copy_diagnostic(_=None) -> None:
        try:
            await ft.Clipboard().set(build_report(APP_NAME, __version__))
            toast("Informations copiées : collez-les dans votre message d'aide.")
        except Exception:
            toast("Copie impossible sur cet appareil.", True)

    # ------------------------------------------------------------ mouvement : entrées en cascade
    entrances: list[ft.Container] = []

    def enter(control: ft.Control) -> ft.Container:
        """Enveloppe une section : invisible et légèrement descendue, jusqu'à son tour d'apparaître."""
        box = ft.Container(
            content=control,
            opacity=0,
            offset=ft.Offset(0, 0.06),
            animate_opacity=_ENTER_FADE,
            animate_offset=_ENTER_SLIDE,
        )
        entrances.append(box)
        return box

    def section(title: str, *controls: ft.Control) -> ft.Container:
        return enter(ft.Column([section_label(title), *controls], spacing=Space.sm))

    # ------------------------------------------------------------ description de l'application
    group_count = len({t.group for t in TOOLS})
    description = card(
        [
            ft.Text(APP_DESCRIPTION, size=14.5, color=Palette.ink),
            ft.Text(
                APP_DESCRIPTION_2.format(tools=len(TOOLS), groups=group_count),
                size=14,
                color=Palette.ink_muted,
            ),
        ]
    )

    # ------------------------------------------------------------ le voyage d'un fichier (étapes qui s'allument)
    journey_accent = Palette.merge
    journey_tiles: list[tuple[ft.Container, ft.Icon]] = []

    def journey_step(icon: str, label: str) -> ft.Control:
        glyph = ft.Icon(icon, size=22, color=Palette.ink_muted)
        tile = ft.Container(
            width=46,
            height=46,
            border_radius=14,
            bgcolor=tool.soft,
            alignment=ft.Alignment(0, 0),
            animate=ft.Animation(350, ft.AnimationCurve.EASE_OUT),
            content=glyph,
        )
        journey_tiles.append((tile, glyph))
        return ft.Column(
            [tile, ft.Text(label, size=12, color=Palette.ink, text_align=ft.TextAlign.CENTER)],
            spacing=6,
            horizontal_alignment=centered,
            expand=True,
        )

    arrow = lambda: ft.Icon(ft.Icons.ARROW_FORWARD, size=18, color=Palette.ink_muted)  # noqa: E731
    journey_row: list[ft.Control] = []
    for index, (icon, label) in enumerate(JOURNEY):
        if index:
            journey_row.append(arrow())
        journey_row.append(journey_step(icon, label))

    journey = card(
        [
            ft.Row(journey_row, vertical_alignment=ft.CrossAxisAlignment.START, spacing=Space.sm),
            ft.Row(
                [
                    ft.Icon(ft.Icons.CLOUD_OFF_OUTLINED, size=16, color=Palette.ink_muted),
                    ft.Text(
                        "Aucune connexion Internet n'est utilisée pour traiter vos fichiers.",
                        size=12.5,
                        color=Palette.ink_muted,
                        expand=True,
                    ),
                ],
                spacing=8,
            ),
        ]
    )

    def light_journey(active: int) -> None:
        for index, (tile, glyph) in enumerate(journey_tiles):
            on = index == active
            tile.bgcolor = journey_accent.color if on else tool.soft
            glyph.color = Palette.surface if on else Palette.ink_muted
        _safe_update(*(tile for tile, _ in journey_tiles), *(glyph for _, glyph in journey_tiles))

    # ------------------------------------------------------------ mosaïque des outils
    mosaic_tiles: list[ft.Container] = []

    def tool_tile(item) -> ft.Container:
        accent = getattr(Palette, item.accent)

        def on_hover(event) -> None:
            event.control.scale = 1.12 if event.data in (True, "true", "True") else 1.0
            _safe_update(event.control)

        tile = ft.Container(
            width=46,
            height=46,
            border_radius=13,
            bgcolor=accent.soft,
            alignment=ft.Alignment(0, 0),
            ink=True,
            tooltip=item.title,
            on_click=go(item.route),
            on_hover=on_hover,
            scale=0.5,
            opacity=0,
            animate_scale=_POP,
            animate_opacity=ft.Animation(240, ft.AnimationCurve.EASE_OUT),
            content=ft.Icon(item.icon, color=accent.color, size=22),
        )
        mosaic_tiles.append(tile)
        return tile

    mosaic = ft.Row(
        [tool_tile(item) for item in TOOLS], wrap=True, spacing=Space.sm, run_spacing=Space.sm
    )
    mosaic_caption = ft.Text(
        f"Touchez un carreau pour ouvrir l'outil · {len(TOOLS)} outils en {group_count} catégories",
        size=12.5,
        color=Palette.ink_muted,
    )

    # ------------------------------------------------------------ auteur et contact
    author = card(
        [
            ft.Row(
                [
                    _avatar(AUTHOR_NAME),
                    ft.Column(
                        [
                            ft.Text(AUTHOR_NAME, size=16, weight=ft.FontWeight.W_700, color=Palette.ink),
                            ft.Text(f"{AUTHOR_ROLE} · {AUTHOR_COUNTRY}", size=13, color=Palette.ink_muted),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                ],
                spacing=Space.md,
                vertical_alignment=centered,
            ),
            ft.Container(
                ink=True,
                border_radius=12,
                on_click=copy_email,
                tooltip="Copier l'adresse",
                content=ft.Row(
                    [
                        icon_tile(ft.Icons.MAIL_OUTLINE, tool, size=40),
                        ft.Text(AUTHOR_EMAIL, size=14, weight=ft.FontWeight.W_600, color=Palette.ink, expand=True),
                        ft.Icon(ft.Icons.CONTENT_COPY, size=16, color=Palette.ink_muted),
                    ],
                    spacing=Space.md,
                    vertical_alignment=centered,
                ),
            ),
            ft.Row(
                [
                    secondary_button("Écrire un e-mail", ft.Icons.SEND_OUTLINED, write_email),
                    secondary_button("Copier l'adresse", ft.Icons.CONTENT_COPY, copy_email),
                ],
                wrap=True,
                spacing=Space.sm,
                run_spacing=Space.sm,
            ),
        ]
    )

    # ------------------------------------------------------------ données et diagnostic
    data_dir = app_data_dir()
    data_file = existing_data_file(data_dir) if desktop else None
    data_actions: list[ft.Control] = [
        secondary_button("Copier les infos de diagnostic", ft.Icons.CONTENT_COPY, copy_diagnostic)
    ]
    if data_file is not None:
        data_actions.append(
            secondary_button(
                "Ouvrir le dossier", ft.Icons.FOLDER_OPEN_OUTLINED, lambda _: reveal_in_folder(data_file)
            )
        )
    data = card(
        [
            ft.Text("Où sont mes données ?", size=14, weight=ft.FontWeight.W_700, color=Palette.ink),
            ft.Text(
                "Seuls vos réglages et la liste des derniers fichiers créés sont gardés ici. "
                "Vos PDF restent là où vous les enregistrez.",
                size=12.5,
                color=Palette.ink_muted,
            ),
            ft.Text(str(data_dir), size=12, color=Palette.ink, selectable=True),
            ft.Row(data_actions, wrap=True, spacing=Space.sm, run_spacing=Space.sm),
            ft.Text(
                "Un souci ? Copiez les infos de diagnostic et collez-les dans votre message.",
                size=12,
                color=Palette.ink_muted,
            ),
        ],
    )

    # ------------------------------------------------------------ sous le capot (repliable)
    libraries = list(library_versions())
    missing = sum(1 for _lib, version in libraries if not version)
    hood_summary = (
        f"{len(libraries)} bibliothèques · Python {platform.python_version()} · {platform.system() or '?'}"
        + (f" · {missing} indisponible{'s' if missing > 1 else ''}" if missing else "")
    )
    hood = _collapsible(
        page, "Bibliothèques et versions", hood_summary, _under_the_hood(libraries),
        subtitle_color=Palette.danger if missing else None,
    )

    # ------------------------------------------------------------ confidentialité
    privacy = ft.Column(
        [
            card(
                [
                    ft.Row(
                        [
                            icon_tile(ft.Icons.SHIELD_OUTLINED, Palette.password, size=40),
                            ft.Column(
                                [
                                    ft.Text(PRIVACY_SUMMARY, size=14, weight=ft.FontWeight.W_700,
                                            color=Palette.ink),
                                    ft.Text(f"Dernière mise à jour : {PRIVACY_UPDATED}", size=12,
                                            color=Palette.ink_muted),
                                ],
                                spacing=1,
                                expand=True,
                            ),
                        ],
                        spacing=Space.md,
                        vertical_alignment=centered,
                    ),
                ]
            ),
            _collapsible(page, "Politique de confidentialité", "Lire le texte complet", _privacy_body()),
        ],
        spacing=Space.sm,
    )

    # ------------------------------------------------------------ pied de page
    heart = ft.Container(
        scale=1.0,
        animate_scale=ft.Animation(420, ft.AnimationCurve.EASE_IN_OUT),
        content=ft.Icon(ft.Icons.FAVORITE, size=16, color=Palette.heart),
    )
    footer = ft.Column(
        [
            ft.Row(
                [ft.Text("Conçu avec", size=13.5, color=Palette.ink), heart],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=6,
            ),
            ft.Text(
                f"© {COPYRIGHT_YEAR} PDF Studio",
                size=12,
                color=Palette.ink_muted,
                text_align=ft.TextAlign.CENTER,
            ),
        ],
        spacing=4,
        horizontal_alignment=centered,
    )

    # ------------------------------------------------------------ chorégraphie
    def settle() -> None:
        """État final garanti, même si une animation a échoué en route."""
        for box in entrances:
            box.opacity = 1
            box.offset = ft.Offset(0, 0)
        for tile in mosaic_tiles:
            tile.scale = 1.0
            tile.opacity = 1
        try:
            page.update()
        except Exception:  # noqa: BLE001
            pass

    async def wait_until_shown(control: ft.Control) -> bool:
        for _ in range(30):
            if _safe_update(control):
                return True
            await asyncio.sleep(0.1)
        return False

    async def intro() -> None:
        if not entrances or not await wait_until_shown(entrances[0]):
            return
        for box in entrances:
            box.opacity = 1
            box.offset = ft.Offset(0, 0)
            _safe_update(box)
            await asyncio.sleep(0.07)
        for tile in mosaic_tiles:
            tile.scale = 1.0
            tile.opacity = 1
            _safe_update(tile)
            await asyncio.sleep(0.02)

    async def ambient() -> None:
        """Vie discrète : le cœur bat, le voyage s'allume étape par étape."""
        tick = 0
        await asyncio.sleep(0.8)
        while page.route == ABOUT_ROUTE and generation == _generation[0]:
            inhale = tick % 2 == 0
            heart.scale = 1.25 if inhale else 1.0
            _safe_update(heart)
            if tick % 3 == 0:
                light_journey((tick // 3) % len(JOURNEY))
            tick += 1
            await asyncio.sleep(1.1)

    async def run_motion() -> None:
        try:
            await intro()
        except Exception:  # noqa: BLE001
            pass
        finally:
            settle()
        try:
            await ambient()
        except Exception:  # noqa: BLE001
            pass

    page.run_task(run_motion)

    return page_shell(
        page,
        "À propos",
        tool,
        [
            section("L'application", description),
            section("Le voyage d'un fichier", journey),
            section("Nos promesses", _promises()),
            section("Tous les outils", mosaic, mosaic_caption),
            section("Données", data),
            section("Confidentialité", privacy),
            section("Sous le capot", hood),
            section("Développeuse", author),
            enter(ft.Container(content=footer, alignment=ft.Alignment(0, 0), padding=Space.md)),
        ],
    )