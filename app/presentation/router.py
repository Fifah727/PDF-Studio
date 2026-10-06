from __future__ import annotations

import flet as ft

from app.presentation.di import UseCases
from app.presentation.screens.about_screen import build_about
from app.presentation.screens.base import FilePickerService
from app.presentation.screens.batch_screen import build_batch
from app.presentation.screens.delete_screen import build_delete
from app.presentation.screens.export_screens import build_extract_images, build_extract_text
from app.presentation.screens.extract_screen import build_extract
from app.presentation.screens.home_screen import build_home
from app.presentation.screens.images_to_pdf_screen import build_images_to_pdf
from app.presentation.screens.landscape_screen import build_landscape
from app.presentation.screens.merge_screen import build_merge
from app.presentation.screens.optimize_screens import build_bookmarks, build_compress, build_metadata
from app.presentation.screens.organize_screens import (
    build_crop,
    build_insert,
    build_interleave,
    build_reorder,
)
from app.presentation.screens.password_screen import build_password
from app.presentation.screens.rotate_screen import build_rotate
from app.presentation.screens.settings_screen import build_settings
from app.presentation.screens.split_screen import build_split
from app.presentation.screens.unmark_screen import build_unmark
from app.presentation.screens.stamp_screens import (
    build_image_watermark,
    build_numbering,
    build_signature,
    build_watermark,
)
from app.presentation.theme_controller import ThemeController

# route -> constructeur d'écran d'outil (page, use_cases, picker, notify)
TOOL_SCREENS = {
    "/diviser": build_split,
    "/extraire": build_extract,
    "/fusionner": build_merge,
    "/supprimer": build_delete,
    "/pivoter": build_rotate,
    "/paysage": build_landscape,
    "/mot-de-passe": build_password,
    "/images-vers-pdf": build_images_to_pdf,
    "/reorganiser": build_reorder,
    "/inserer": build_insert,
    "/recto-verso": build_interleave,
    "/rogner": build_crop,
    "/compresser": build_compress,
    "/metadonnees": build_metadata,
    "/signets": build_bookmarks,
    "/filigrane": build_watermark,
    "/filigrane-image": build_image_watermark,
    "/signature": build_signature,
    "/numeroter": build_numbering,
    "/retirer-filigranes": build_unmark,
    "/extraire-images": build_extract_images,
    "/extraire-texte": build_extract_text,
    "/lot": build_batch,
}


def register_router(
    page: ft.Page,
    use_cases: UseCases,
    picker: FilePickerService,
    notify,
    settings,
    theme: ThemeController,
    recents=None,
) -> None:

    routes = {
        "/": lambda: build_home(page, recents),
        "/parametres": lambda: build_settings(page, settings, theme, notify),
        "/a-propos": lambda: build_about(page, notify),
    }
    for route, builder in TOOL_SCREENS.items():
        routes[route] = lambda b=builder: b(page, use_cases, picker, notify)

    async def route_change(e: ft.RouteChangeEvent | None = None) -> None:
        route = page.route or "/"
        builder = routes.get(route, routes["/"])

        page.views.clear()
        page.views.append(builder())
        page.update()

    async def view_pop(e: ft.ViewPopEvent) -> None:
        if len(page.views) > 1:
            page.views.pop()
            await page.push_route(page.views[-1].route)
        else:
            await page.push_route("/")

    page.on_route_change = route_change
    page.on_view_pop = view_pop

    # Un changement de thème reconstruit la vue courante avec les nouvelles couleurs.
    theme.subscribe(lambda: page.run_task(route_change))

    # IMPORTANT :
    # Construire immédiatement la première View.
    # Ne pas utiliser push_route() ici.
    page.run_task(route_change)
