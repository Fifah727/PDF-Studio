from __future__ import annotations

import flet as ft


def lottie(
    src: str,
    height: int,
    *,
    width: int | None = None,
    reverse: bool = False,
    repeat: bool = True,
) -> ft.Control | None:
    """
    Animation Lottie (``src`` est relatif au dossier d'assets), ou ``None`` si
    ``flet-lottie`` n'est pas installé : l'appelant doit prévoir ce cas pour que
    l'écran reste fonctionnel sans l'animation.

    ``reverse=True`` : à la fin, l'animation repart à l'envers (aller-retour).
    """
    try:
        import flet_lottie as fl
    except ImportError:
        return None
    return fl.Lottie(
        src=src,
        repeat=repeat,
        reverse=reverse,
        animate=True,
        height=height,
        width=width,
    )