from __future__ import annotations

import asyncio
import weakref
from pathlib import Path

import flet as ft

from app.presentation.system import reveal_in_folder
from app.presentation.theme import Palette


def _is_desktop(page: ft.Page) -> bool:
    return not (page.web or page.platform.is_mobile())


def _text_button(label: str, icon: str, color: str, on_click) -> ft.TextButton:
    """Bouton texte avec icône (le contenu est un Row : indépendant de la version de Flet)."""
    return ft.TextButton(
        content=ft.Row(
            [ft.Icon(icon, size=16, color=color), ft.Text(label, size=13, weight=ft.FontWeight.W_600, color=color)],
            spacing=6,
            tight=True,
        ),
        on_click=on_click,
        style=ft.ButtonStyle(padding=ft.Padding(left=8, right=10, top=4, bottom=4)),
    )


class ResultBanner(ft.Container):
    """
    Dernier résultat d'une opération, affiché dans l'écran de l'outil.

    NB : ``make_notifier`` ne l'affiche plus par défaut (une seule notification suffit) ;
    la classe reste disponible, et ``page_shell`` peut continuer à l'enregistrer.

    La notification (snackbar) disparaît au bout de quelques secondes ; ce
    bandeau reste en place jusqu'à la prochaine opération. Il montre un titre
    (« Opération terminée » / « Une erreur est survenue »), le message, le
    dossier du fichier créé, et propose « Ouvrir le dossier » (succès, bureau)
    ou « Copier le message » (erreur, pour le joindre à une demande d'aide).
    Il entre et sort en fondu.
    """

    _SHOWN = ft.Offset(0, 0)
    _HIDDEN = ft.Offset(0, -0.08)

    def __init__(self) -> None:
        super().__init__(
            visible=False,
            border_radius=16,
            padding=ft.Padding(left=14, right=6, top=14, bottom=12),
            opacity=0,
            offset=self._HIDDEN,
            animate_opacity=ft.Animation(220, ft.AnimationCurve.EASE_OUT),
            animate_offset=ft.Animation(260, ft.AnimationCurve.EASE_OUT),
        )
        self.title = ft.Text(size=14, weight=ft.FontWeight.W_700)
        self.message = ft.Text(size=13.5, selectable=True)
        self.detail = ft.Text(
            size=12, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, visible=False
        )
        self.icon = ft.Icon(ft.Icons.CHECK_CIRCLE, size=20, color=Palette.surface)
        self.badge = ft.Container(
            width=38,
            height=38,
            border_radius=19,
            alignment=ft.Alignment(0, 0),
            content=self.icon,
        )
        self.actions = ft.Row(spacing=2, tight=True, wrap=True, run_spacing=0)
        self.close_button = ft.IconButton(
            ft.Icons.CLOSE, icon_size=18, tooltip="Fermer",
            icon_color=Palette.ink_muted, on_click=lambda _: self.hide(),
        )
        self.content = ft.Row(
            [
                self.badge,
                ft.Column(
                    [self.title, self.message, self.detail, self.actions],
                    spacing=2,
                    expand=True,
                ),
                self.close_button,
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
        self.is_error = False
        self._token = 0  # une apparition/disparition plus récente annule la précédente

    # ------------------------------------------------------------------ affichage
    def show(
        self,
        message: str,
        error: bool = False,
        reveal: Path | None = None,
        can_reveal: bool = False,
        title: str | None = None,
    ) -> None:
        self._token += 1
        token = self._token
        self.is_error = error
        color = Palette.danger if error else Palette.success

        self.bgcolor = Palette.danger_soft if error else Palette.success_soft
        self.border = ft.Border.all(1, color)
        self.badge.bgcolor = color
        self.icon.icon = ft.Icons.ERROR_OUTLINE if error else ft.Icons.CHECK_CIRCLE_OUTLINE
        self.title.value = title or ("Une erreur est survenue" if error else "Opération terminée")
        self.title.color = Palette.ink
        self.message.value = message
        self.message.color = Palette.ink

        if reveal is not None and not error:
            self.detail.value = f"Dossier : {Path(reveal).parent}"
            self.detail.tooltip = str(reveal)
            self.detail.color = Palette.ink_muted
            self.detail.visible = True
        else:
            self.detail.visible = False

        buttons: list[ft.Control] = []
        if reveal is not None and not error and can_reveal:
            buttons.append(
                _text_button("Ouvrir le dossier", ft.Icons.FOLDER_OPEN_OUTLINED, color,
                             lambda _: reveal_in_folder(reveal))
            )
        if error:
            buttons.append(_text_button("Copier le message", ft.Icons.CONTENT_COPY, color, self._copy_message))
        self.actions.controls = buttons
        self.actions.visible = bool(buttons)

        # Entrée en fondu : d'abord invisible et légèrement remontée, puis on bascule.
        self.visible = True
        self.opacity = 0
        self.offset = self._HIDDEN
        self._refresh()
        self._schedule(self._enter, token)

    def hide(self) -> None:
        self._token += 1
        token = self._token
        self.opacity = 0
        self.offset = self._HIDDEN
        self._refresh()
        if not self._schedule(self._leave, token):
            self.visible = False
            self._refresh()

    # ------------------------------------------------------------------ interne
    async def _enter(self, token: int) -> None:
        await asyncio.sleep(0.03)
        if token == self._token:
            self.opacity = 1
            self.offset = self._SHOWN
            self._refresh()

    async def _leave(self, token: int) -> None:
        await asyncio.sleep(0.25)
        if token == self._token:
            self.visible = False
            self._refresh()

    async def _copy_message(self, _=None) -> None:
        try:
            await ft.Clipboard().set(self.message.value or "")
        except Exception:  # noqa: BLE001 - copie impossible sur cet appareil
            pass

    def _schedule(self, coroutine_function, token: int) -> bool:
        """Lance l'animation ; sans page (pas encore montée), on affiche directement l'état final."""
        try:
            self.page.run_task(coroutine_function, token)
            return True
        except Exception:  # noqa: BLE001
            if coroutine_function == self._enter:
                self.opacity = 1
                self.offset = self._SHOWN
                self._refresh()
            return False

    def _refresh(self) -> None:
        try:
            self.update()
        except Exception:  # noqa: BLE001 - pas encore monté sur la page
            pass


# Un bandeau par page (l'écran affiché) : enregistré par ``page_shell``.
_banners: "weakref.WeakKeyDictionary[ft.Page, ResultBanner]" = weakref.WeakKeyDictionary()


def register_banner(page: ft.Page, banner: ResultBanner) -> None:
    _banners[page] = banner


def banner_for(page: ft.Page) -> ResultBanner | None:
    try:
        return _banners.get(page)
    except TypeError:  # objet non référençable faiblement
        return None


def make_notifier(page: ft.Page, settings=None):
    """
    Retourne ``notify(message, error=False, reveal=None, show_banner=False)`` liée à la page.

    Une seule notification (snackbar) porte tout le résultat : titre, message,
    dossier du fichier créé et, sur le bureau, le bouton « Ouvrir le dossier »
    (« Copier le message » en cas d'erreur). Le bandeau vert ``ResultBanner`` n'est
    plus affiché, sauf demande explicite avec ``show_banner=True``.
    """

    def notify(
        message: str, error: bool = False, reveal: Path | None = None, show_banner: bool = False
    ) -> None:
        desktop = _is_desktop(page)
        wants_action = settings is None or settings.current.offer_open_folder

        action = None
        on_action = None
        if error:
            action = "Copier le message"

            async def on_action(_=None) -> None:  # noqa: F811
                try:
                    await ft.Clipboard().set(message)
                except Exception:  # noqa: BLE001 - copie impossible sur cet appareil
                    pass

        elif reveal is not None and wants_action and desktop:
            action = "Ouvrir le dossier"
            on_action = lambda _: reveal_in_folder(reveal)  # noqa: E731

        banner = banner_for(page) if show_banner else None
        if banner is not None:
            banner.show(message, error, reveal, can_reveal=wants_action and desktop)

        title = "Une erreur est survenue" if error else "Opération terminée"
        lines: list[ft.Control] = [
            ft.Text(title, color=Palette.surface, size=14, weight=ft.FontWeight.W_700),
            ft.Text(
                message,
                color=ft.Colors.with_opacity(0.92, Palette.surface),
                size=13.5,
                max_lines=4,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
        ]
        if reveal is not None and not error:
            lines.append(
                ft.Text(
                    f"Dossier : {Path(reveal).parent}",
                    color=ft.Colors.with_opacity(0.7, Palette.surface),
                    size=12,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    tooltip=str(reveal),
                )
            )

        # Le message doit rester assez longtemps pour être lu (et l'action utilisable).
        duration = 9000 if (error or action) else 5000

        # Flutter interdit « width » et « margin » ensemble : large pastille centrée sur
        # bureau, pleine largeur avec marges sur mobile.
        layout: dict = {}
        if desktop:
            layout["width"] = max(280, min(560, (page.width or 560) - 32))
        else:
            layout["margin"] = ft.Margin.all(16)

        page.show_dialog(
            ft.SnackBar(
                content=ft.Row(
                    [
                        ft.Container(
                            width=30,
                            height=30,
                            border_radius=15,
                            alignment=ft.Alignment(0, 0),
                            bgcolor=ft.Colors.with_opacity(0.18, Palette.surface),
                            content=ft.Icon(
                                ft.Icons.ERROR_OUTLINE if error else ft.Icons.CHECK_CIRCLE_OUTLINE,
                                color=Palette.surface,
                                size=19,
                            ),
                        ),
                        ft.Column(lines, spacing=2, tight=True, expand=True),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=Palette.danger if error else Palette.ink,
                behavior=ft.SnackBarBehavior.FLOATING,
                shape=ft.RoundedRectangleBorder(radius=14),
                show_close_icon=True,
                action=action,
                on_action=on_action,
                duration=duration,
                **layout,
            )
        )

    return notify


class BusyIndicator:
    """Fenêtre modale « Traitement en cours… » pendant une opération longue."""

    DEFAULT_DETAIL = "Patientez un moment..."

    def __init__(self, page: ft.Page):
        self._page = page
        self._dialog: ft.AlertDialog | None = None

    def show(self, message: str = "Traitement en cours…", detail: str | None = DEFAULT_DETAIL) -> None:
        texts: list[ft.Control] = [
            ft.Text(message, size=14.5, weight=ft.FontWeight.W_700, color=Palette.ink)
        ]
        if detail:
            texts.append(ft.Text(detail, size=12.5, color=Palette.ink_muted))
        self._dialog = ft.AlertDialog(
            modal=True,
            bgcolor=Palette.surface,
            shape=ft.RoundedRectangleBorder(radius=20),
            content_padding=ft.Padding(left=24, right=24, top=22, bottom=22),
            content=ft.Container(
                width=300,
                content=ft.Row(
                    [
                        ft.ProgressRing(width=30, height=30, stroke_width=3.5, color=Palette.ink),
                        ft.Column(texts, spacing=3, tight=True, expand=True),
                    ],
                    spacing=18,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ),
        )
        self._page.show_dialog(self._dialog)

    def hide(self) -> None:
        if self._dialog is not None:
            self._dialog.open = False
            try:
                self._dialog.update()
            except Exception:  # noqa: BLE001 - déjà fermée
                pass
            self._dialog = None