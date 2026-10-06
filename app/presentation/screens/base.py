from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Callable

import flet as ft

from app.application.files import suggest_name, with_extension  # noqa: F401  (ré-exportés pour les écrans)
from app.domain.exceptions import PdfError
from app.presentation.theme import Palette, Space, ToolAccent
from app.presentation.widgets.app_bar import tool_app_bar
from app.presentation.widgets.cards import tool_header
from app.presentation.widgets.feedback import BusyIndicator, ResultBanner, register_banner

logger = logging.getLogger(__name__)

# produce(destination) -> chemin du fichier créé
Producer = Callable[[str], "Path | str"]


class FilePickerService:
    """
    Enveloppe autour de ft.FilePicker.

    Dans Flet 1.0, ``pick_files`` / ``save_file`` sont des méthodes
    asynchrones qui renvoient directement leur résultat. Cette classe
    expose donc des méthodes ``async`` que les écrans doivent ``await``.

    ``save_result`` gère les deux familles de plateformes :
    - bureau : la boîte « Enregistrer sous » renvoie un chemin, on y écrit ;
    - mobile : Flet exige les octets du fichier (``src_bytes``) ; on
      génère donc le résultat dans un dossier temporaire puis on le remet
      au sélecteur.
    """

    def __init__(self, page: ft.Page, settings=None, recents=None):
        self._page = page
        self._busy = BusyIndicator(page)
        self.settings = settings
        self.recents = recents  # historique des fichiers créés (facultatif)

    # ------------------------------------------------------------ dossier mémorisé
    def _initial_dir(self) -> str | None:
        """Dernier dossier utilisé (bureau seulement, si l'option est active)."""
        if self.settings is None or self._is_mobile():
            return None
        current = self.settings.current
        if current.remember_last_folder and current.last_folder:
            if Path(current.last_folder).is_dir():
                return current.last_folder
        return None

    def _remember(self, path: str | Path) -> None:
        if self.settings is not None and self.settings.current.remember_last_folder:
            self.settings.update(last_folder=str(Path(path).parent))

    # ------------------------------------------------------------ sélection
    async def pick_pdf(self, multiple: bool = False) -> list[str]:
        files = await ft.FilePicker().pick_files(
            dialog_title="Choisir un fichier PDF",
            initial_directory=self._initial_dir(),
            allow_multiple=multiple,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["pdf"],
        )
        paths = [file.path for file in files or [] if file.path]
        if paths:
            self._remember(paths[0])
        return paths

    async def pick_images(self, multiple: bool = True) -> list[str]:
        files = await ft.FilePicker().pick_files(
            dialog_title="Choisir une ou plusieurs images",
            initial_directory=self._initial_dir(),
            allow_multiple=multiple,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=[
                "jpg", "jpeg", "png", "bmp", "gif", "tiff", "tif", "webp",
            ],
        )
        paths = [file.path for file in files or [] if file.path]
        if paths:
            self._remember(paths[0])
        return paths

    # ------------------------------------------------------------ enregistrement
    def _is_mobile(self) -> bool:
        return bool(self._page.platform.is_mobile())

    async def save_as(self, title: str, filename: str) -> str | None:
        """
        Boîte « Enregistrer sous » (bureau). Renvoie un chemin toujours
        muni de la bonne extension, même si l'utilisateur l'a effacée en
        renommant le fichier.
        """
        extension = Path(filename).suffix
        chosen = await ft.FilePicker().save_file(
            dialog_title=title,
            file_name=filename,
            initial_directory=self._initial_dir(),
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=[extension.lstrip(".")] if extension else None,
        )
        if not chosen:
            return None
        final = with_extension(chosen, extension) if extension else chosen
        self._remember(final)
        return final

    async def save_result(
        self, title: str, filename: str, produce: Producer
    ) -> Path | None:
        """
        Demande où enregistrer, puis exécute ``produce(destination)`` dans un
        thread (l'interface reste réactive) derrière un indicateur de
        progression. Renvoie le fichier créé, ou ``None`` si annulé.
        """
        if self._is_mobile():
            with tempfile.TemporaryDirectory() as folder:
                produced = await self._produce(produce, str(Path(folder) / filename))
                chosen = await ft.FilePicker().save_file(
                    dialog_title=title,
                    file_name=filename,
                    src_bytes=produced.read_bytes(),
                )
            return Path(chosen) if chosen else None

        destination = await self.save_as(title, filename)
        if not destination:
            return None
        return await self._produce(produce, destination)

    async def _produce(self, produce: Producer, destination: str) -> Path:
        self._busy.show()
        try:
            return Path(await asyncio.to_thread(produce, destination))
        finally:
            self._busy.hide()


async def run_save(
    notify: Callable[..., None],
    picker: FilePickerService,
    title: str,
    filename: str,
    produce: Producer,
    success_prefix: str = "Fichier créé",
    message: Callable[[Path], str] | None = None,
) -> None:
    """
    Enregistre le résultat d'une opération et traduit l'issue en notification.

    ``message`` remplace le texte de succès par défaut quand il faut détailler
    le résultat (gain de compression, fichiers ignorés d'un lot…).
    """
    try:
        result = await picker.save_result(title, filename, produce)
        if result is not None:
            notify(message(result) if message else f"{success_prefix} : {result.name}", False, result)
            recents = getattr(picker, "recents", None)
            if recents is not None:
                recents.add(result, success_prefix)
    except PdfError as exc:
        notify(str(exc), True)
    except (FileNotFoundError, ValueError, PermissionError) as exc:
        logger.warning("Opération refusée : %s", exc)
        notify(str(exc), True)
    except Exception as exc:
        logger.exception("Erreur inattendue pendant l'opération")
        notify(f"Une erreur inattendue est survenue : {exc}", True)


def check(notify: Callable[..., None], validation: Callable[[], object]) -> bool:
    """Exécute une validation ; notifie l'erreur et renvoie False si elle échoue."""
    try:
        validation()
        return True
    except PdfError as exc:
        notify(str(exc), True)
    except (FileNotFoundError, ValueError) as exc:
        notify(str(exc), True)
    except Exception as exc:
        logger.exception("Erreur inattendue pendant la validation")
        notify(f"Une erreur inattendue est survenue : {exc}", True)
    return False


def content_width(page: ft.Page) -> float:
    """Largeur du contenu : 720 px max, moins si la fenêtre est plus étroite."""
    available = page.width or Space.page_width
    return min(Space.page_width, available)


def bind_responsive_width(page: ft.Page, container: ft.Container) -> None:
    """Ajuste la largeur du contenu quand la fenêtre est redimensionnée."""

    def on_resize(_) -> None:
        container.width = content_width(page)
        container.update()

    page.on_resize = on_resize


def page_shell(
    page: ft.Page,
    title: str,
    tool: ToolAccent,
    controls: list[ft.Control],
    icon: str | None = None,
    description: str | None = None,
) -> ft.View:

    async def go_home() -> None:
        await page.push_route("/")

    header = [tool_header(icon, tool, description)] if icon and description else []
    banner = ResultBanner()
    register_banner(page, banner)

    body = ft.Container(
        content=ft.Column(
            [*header, *controls, banner],
            spacing=Space.lg,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
        padding=Space.lg,
        width=content_width(page),
        alignment=ft.Alignment(0, -1),
    )
    bind_responsive_width(page, body)

    return ft.View(
        route=page.route,
        appbar=tool_app_bar(
            title,
            tool.color,
            on_back=lambda _: page.run_task(go_home),
        ),
        bgcolor=Palette.paper,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        # Défilement dynamique : la barre n'apparaît que si le contenu
        # dépasse la hauteur de la fenêtre.
        scroll=ft.ScrollMode.AUTO,
        controls=[body],
    )


# ---------------------------------------------------------------- aides d'écran
def bind_ready(button: ft.Control, condition: Callable[[], bool]) -> Callable[[], None]:
    """
    Désactive ``button`` tant que ``condition()`` est fausse (aucun fichier,
    sélection vide…). Renvoie la fonction à rappeler quand l'état change.
    """

    def refresh() -> None:
        button.disabled = not condition()
        try:
            button.update()
        except RuntimeError:
            pass  # pas encore monté

    button.disabled = not condition()
    return refresh


def pdf_chooser(
    picker: FilePickerService,
    use_cases,
    tray,
    state: dict,
    on_change: Callable[[], None],
    describe: Callable[[int], str] | None = None,
    count_pages: bool = True,
):
    """
    Gestionnaires « choisir » et « retirer » d'un écran à un seul PDF.

    Lit le nombre de pages pour l'afficher dans la zone de dépôt ; un PDF
    illisible ou protégé est signalé en rouge sans bloquer l'écran.
    """

    async def choose(_=None) -> None:
        paths = await picker.pick_pdf()
        if not paths:
            return
        path = paths[0]
        state["path"], state["total"] = path, None
        if not count_pages:
            tray.set_file(path)
        else:
            try:
                total = use_cases.count_pages.execute(path)
                state["total"] = total
                tray.set_file(path, describe(total) if describe else f"{total} page(s)")
            except PdfError as exc:
                tray.set_file(path, str(exc), error=True)
            except Exception:
                logger.exception("Lecture du PDF impossible : %s", path)
                tray.set_file(path, "Fichier illisible.", error=True)
        on_change()

    def clear(_=None) -> None:
        state["path"], state["total"] = None, None
        on_change()

    return choose, clear
