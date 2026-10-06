from __future__ import annotations

import difflib
import random
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Callable, NamedTuple

import flet as ft

from app import APP_NAME,COPYRIGHT_YEAR, __version__
from app.presentation.screens.base import content_width
from app.presentation.system import reveal_in_folder
from app.presentation.theme import Palette, Space
from app.presentation.widgets.brand import logo_fan
from app.presentation.widgets.cards import hero_card, icon_tile, section_label, tool_card
from app.presentation.widgets.lottie import lottie


class Tool(NamedTuple):
    group: str
    icon: str
    title: str
    description: str
    accent: str  # nom de l'attribut de Palette (lu à la construction : thème dynamique)
    route: str


TOOLS = [
    Tool("Organiser", ft.Icons.CONTENT_CUT, "Extraire des pages",
         "Conserver des pages ou des plages précises.", "extract", "/extraire"),
    Tool("Organiser", ft.Icons.MERGE_TYPE, "Fusionner des PDF",
         "Assembler plusieurs fichiers dans l'ordre choisi.", "merge", "/fusionner"),
    Tool("Organiser", ft.Icons.DELETE_OUTLINE, "Supprimer des pages",
         "Retirer des pages sans modifier l'original.", "delete", "/supprimer"),
    Tool("Organiser", ft.Icons.CALL_SPLIT, "Diviser un PDF",
         "Un fichier par page, dans une archive ZIP.", "split", "/diviser"),
    Tool("Organiser", ft.Icons.ROTATE_RIGHT, "Pivoter des pages",
         "Redresser des pages couchées ou à l'envers.", "rotate", "/pivoter"),
    Tool("Organiser", ft.Icons.SWAP_VERT, "Réorganiser les pages",
         "Changer l'ordre avec les flèches.", "reorder", "/reorganiser"),
    Tool("Organiser", ft.Icons.NOTE_ADD_OUTLINED, "Insérer des pages",
         "Pages blanches ou pages d'un autre PDF.", "insert", "/inserer"),
    Tool("Organiser", ft.Icons.FLIP, "Fusion recto-verso",
         "Rectos et versos scannés séparément.", "interleave", "/recto-verso"),
    Tool("Organiser", ft.Icons.CROP, "Rogner les marges",
         "Retirer les bords inutiles d'un scan.", "crop", "/rogner"),
    Tool("Optimiser", ft.Icons.COMPRESS, "Compresser un PDF",
         "Réduire le poids pour l'envoyer facilement.", "compress", "/compresser"),
    Tool("Optimiser", ft.Icons.BADGE_OUTLINED, "Métadonnées",
         "Modifier ou effacer auteur, titre, logiciel.", "metadata", "/metadonnees"),
    Tool("Optimiser", ft.Icons.BOOKMARK_BORDER, "Signets",
         "Créer une table des matières cliquable.", "bookmarks", "/signets"),
    Tool("Personnaliser", ft.Icons.WATER_DROP_OUTLINED, "Filigrane texte",
         "CONFIDENTIEL, COPIE… en travers des pages.", "watermark", "/filigrane"),
    Tool("Personnaliser", ft.Icons.IMAGE_OUTLINED, "Filigrane image",
         "Logo ou tampon translucide.", "watermark", "/filigrane-image"),
    Tool("Personnaliser", ft.Icons.DRAW_OUTLINED, "Signer un PDF",
         "Poser l'image de votre signature.", "signature", "/signature"),
    Tool("Personnaliser", ft.Icons.FORMAT_LIST_NUMBERED, "Numéroter les pages",
         "« 3 » ou « Page 3 sur 12 », où vous voulez.", "numbering", "/numeroter"),
    Tool("Personnaliser", ft.Icons.AUTO_FIX_HIGH, "Retirer des filigranes",
         "Texte, image ou signature, quand le PDF en contient.", "unmark", "/retirer-filigranes"),
    Tool("Contenu", ft.Icons.PHOTO_LIBRARY_OUTLINED, "Extraire les images",
         "Photos et illustrations dans un ZIP.", "images_out", "/extraire-images"),
    Tool("Contenu", ft.Icons.TEXT_SNIPPET_OUTLINED, "Extraire le texte",
         "Le texte du PDF dans un fichier .txt.", "text_out", "/extraire-texte"),
    Tool("Convertir", ft.Icons.ADD_PHOTO_ALTERNATE_OUTLINED, "Images vers PDF",
         "JPG, PNG… avec amélioration de scan.", "images", "/images-vers-pdf"),
    Tool("Convertir", ft.Icons.VIEW_COLUMN_OUTLINED, "Pages en paysage",
         "Deux pages A4 côte à côte sur chaque feuille.", "landscape", "/paysage"),
    Tool("Avancé", ft.Icons.PLAYLIST_PLAY, "Enchaîner des opérations",
         "Plusieurs opérations à la suite sur plusieurs PDF.", "batch", "/lot"),
    Tool("Avancé", ft.Icons.LOCK_OUTLINE, "Mot de passe",
         "Protéger un PDF ou retirer sa protection.", "password", "/mot-de-passe"),
]


# Synonymes que l'on tape sans connaître le nom exact de l'outil.
_KEYWORDS = {
    "/extraire": "garder conserver selectionner pages decouper couper",
    "/fusionner": "assembler joindre reunir combiner merge",
    "/supprimer": "enlever retirer effacer pages",
    "/diviser": "separer eclater decouper split zip",
    "/pivoter": "tourner rotation redresser retourner",
    "/reorganiser": "ordre deplacer trier monter descendre inverser",
    "/inserer": "ajouter page blanche vide intercaler",
    "/recto-verso": "scanner duplex deux faces recto verso",
    "/rogner": "recadrer marges bords couper crop",
    "/compresser": "reduire alleger poids taille mail email envoyer lourd compression",
    "/metadonnees": "auteur titre proprietes informations confidentialite anonymiser",
    "/signets": "table matieres sommaire marque-pages bookmarks",
    "/filigrane": "tampon confidentiel brouillon copie watermark",
    "/filigrane-image": "logo tampon watermark image",
    "/signature": "signer parapher manuscrite",
    "/numeroter": "numeros pagination page x sur y",
    "/retirer-filigranes": "enlever supprimer effacer watermark tampon signature nettoyer",
    "/extraire-images": "photos illustrations recuperer zip",
    "/extraire-texte": "copier contenu txt texte brut",
    "/images-vers-pdf": "photo jpg png scanner document convertir noir blanc",
    "/paysage": "deux pages feuille imprimer a4",
    "/lot": "enchainer chaine operations successives automatiser batch lot",
    "/mot-de-passe": "proteger securiser chiffrer deverrouiller cadenas",
}


# Les quatre outils les plus utiles au quotidien : (route, libellé court).
# Les libellés sont volontairement différents des titres complets : un titre
# n'apparaît ainsi qu'une fois à l'écran.
QUICK_ACCESS = (
    ("/compresser", "Compresser"),
    ("/fusionner", "Fusionner"),
    ("/signature", "Signer"),
    ("/images-vers-pdf", "Photos en PDF"),
)

GROUP_ICONS = {
    "Organiser": ft.Icons.FOLDER_COPY_OUTLINED,
    "Optimiser": ft.Icons.TUNE,
    "Personnaliser": ft.Icons.BRUSH_OUTLINED,
    "Contenu": ft.Icons.FILE_DOWNLOAD_OUTLINED,
    "Convertir": ft.Icons.SWAP_HORIZ,
    "Avancé": ft.Icons.PLAYLIST_PLAY,
}


# Animation Lottie (fichier placé dans le dossier d'assets de l'application).
LOTTIE_SRC = "animations/app_logo.json"
LOTTIE_EMPTY_SRC = "animations/empty_folder_lottie.json"


def greeting(hour: int) -> str:
    """Salutation selon l'heure locale."""
    if 5 <= hour < 12:
        return "Bonjour"
    if 12 <= hour < 18:
        return "Bon après-midi"
    return "Bonsoir"


# Fin de la phrase d'accueil, une au hasard à chaque ouverture : « Bonjour, … ».
PROMPTS = (
    "que souhaitez-vous faire aujourd'hui ?",
    "quel document voulez-vous préparer ?",
    "quel PDF avez-vous à préparer aujourd'hui ?",
    "par quoi commençons-nous ?",
    "sur quel fichier travaille-t-on aujourd'hui ?",
    "quelle tâche voulez-vous accomplir aujourd'hui ?",
    "que peut-on arranger pour vous aujourd'hui ?",
    "un PDF à assembler, signer ou alléger ?",
)


TOOL_BY_ROUTE = {tool.route: tool for tool in TOOLS}

# Garde-fous à l'import : une route mal écrite échoue ici, avec un message clair.
if len(TOOL_BY_ROUTE) != len(TOOLS):
    raise RuntimeError("Routes en double dans TOOLS")
_unknown = [r for r, _ in QUICK_ACCESS if r not in TOOL_BY_ROUTE]
_unknown += [r for r in _KEYWORDS if r not in TOOL_BY_ROUTE]
if _unknown:
    raise RuntimeError(f"Routes inconnues dans QUICK_ACCESS / _KEYWORDS : {_unknown}")
del _unknown


def _accent(tool: Tool):
    """Couleurs d'accent de l'outil (lues à l'appel : thème dynamique)."""
    return getattr(Palette, tool.accent)


def _group_header(group: str, count: int, accent) -> ft.Control:
    """En-tête de catégorie : pastille, nom, nombre d'outils, filet."""
    return ft.Row(
        [
            ft.Container(
                width=30,
                height=30,
                border_radius=9,
                bgcolor=accent.soft,
                alignment=ft.Alignment(0, 0),
                content=ft.Icon(GROUP_ICONS.get(group, ft.Icons.APPS), size=17, color=accent.color),
            ),
            ft.Text(group, size=15, weight=ft.FontWeight.W_700, color=Palette.ink),
            ft.Text(str(count), size=12.5, color=Palette.ink_muted),
            ft.Container(height=1, bgcolor=Palette.line, expand=True, margin=ft.Margin(left=6, right=0, top=0, bottom=0)),
        ],
        spacing=Space.sm,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _quick_tile(tool: Tool, label: str, on_click: Callable) -> ft.Container:
    """Grande tuile d'accès rapide : l'outil, en un geste."""
    accent = _accent(tool)

    def on_hover(event) -> None:
        hovered = event.data in (True, "true", "True")
        event.control.scale = 1.03 if hovered else 1.0
        event.control.border = ft.Border.all(1, accent.color if hovered else ft.Colors.with_opacity(0.35, accent.color))
        event.control.update()

    return ft.Container(
        col={"xs": 6, "md": 3},
        padding=Space.md,
        border_radius=18,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.35, accent.color)),
        gradient=ft.LinearGradient(
            begin=ft.Alignment(-1, -1),
            end=ft.Alignment(1, 1),
            colors=[accent.soft, Palette.surface],
        ),
        ink=True,
        scale=1.0,
        animate_scale=ft.Animation(140, ft.AnimationCurve.EASE_OUT),
        tooltip=tool.title,
        on_click=on_click,
        on_hover=on_hover,
        content=ft.Column(
            [
                ft.Container(
                    width=42,
                    height=42,
                    border_radius=13,
                    bgcolor=accent.color,
                    alignment=ft.Alignment(0, 0),
                    content=ft.Icon(tool.icon, size=22, color=Palette.surface),
                ),
                ft.Text(label, size=15, weight=ft.FontWeight.W_700, color=Palette.ink),
            ],
            spacing=Space.sm,
        ),
    )


def _show_open_match(banner: ft.Container, tool: Tool, on_click: Callable) -> None:
    """Configure la bannière « Ouvrir l'outil » (ou Entrée) pour l'outil proposé."""
    accent = _accent(tool)
    banner.visible = True
    banner.bgcolor = accent.soft
    banner.border = ft.Border.all(1, accent.color)
    banner.on_click = on_click
    banner.content = ft.Row(
        [
            icon_tile(tool.icon, accent, size=36),
            ft.Text(f"Ouvrir « {tool.title} »", size=14, weight=ft.FontWeight.W_600,
                    color=Palette.ink, expand=True),
            ft.Icon(ft.Icons.KEYBOARD_RETURN, size=18, color=accent.color, tooltip="Entrée"),
        ],
        spacing=Space.md,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _hide_open_match(banner: ft.Container) -> None:
    banner.visible = False
    banner.content = None
    banner.on_click = None


def _normalize(text: str) -> str:
    """Minuscules sans accents : « Réduire » et « reduire » se trouvent mutuellement."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text)


def _term_rank(term: str, title: str, keywords: str, other: str) -> int | None:
    """Rang d'un mot (0 = meilleur) : titre, puis synonymes, puis description ; None si absent."""
    if term in title:
        return 0
    if term in keywords:
        return 1
    if term in other:
        return 2
    if len(term) >= 4:  # tolérance aux fautes de frappe (« compreser »)
        vocabulary = set(_words(title)) | set(_words(keywords)) | set(_words(other))
        if difflib.get_close_matches(term, vocabulary, n=1, cutoff=0.78):
            return 3
    return None


def rank_tools(query: str = "", group: str | None = None) -> list[tuple[int, Tool]]:
    """
    Outils correspondant à ``query``, du meilleur au moins bon : ``(score, outil)``.

    Chaque mot doit être trouvé ; un mot dans le titre pèse moins (donc mieux) qu'un
    synonyme, lui-même mieux qu'une description. À score égal, l'ordre du catalogue
    est conservé. Sans requête, tous les outils sont renvoyés dans l'ordre du catalogue.
    """
    terms = _normalize(query).split()
    ranked = []
    for index, tool in enumerate(TOOLS):
        if group and tool.group != group:
            continue
        title = _normalize(tool.title)
        keywords = _normalize(_KEYWORDS.get(tool.route, ""))
        other = _normalize(f"{tool.description} {tool.group}")
        total = 0
        for term in terms:
            rank = _term_rank(term, title, keywords, other)
            if rank is None:
                break
            total += rank
        else:
            ranked.append((total, index, tool))
    ranked.sort(key=lambda entry: (entry[0], entry[1]))
    return [(score, tool) for score, _, tool in ranked]


def filter_tools(query: str = "", group: str | None = None) -> list[Tool]:
    """Outils correspondant à ``query`` (classés par pertinence si une requête est saisie)."""
    return [tool for _, tool in rank_tools(query, group)]


def best_tool(query: str = "", group: str | None = None) -> Tool | None:
    """
    Le résultat à ouvrir d'un appui sur Entrée : le seul résultat, ou le premier
    s'il est nettement meilleur que le suivant. None si la requête est vide ou ambiguë.
    """
    if not query.strip():
        return None
    ranked = rank_tools(query, group)
    if len(ranked) == 1:
        return ranked[0][1]
    if len(ranked) > 1 and ranked[0][0] < ranked[1][0]:
        return ranked[0][1]
    return None


def _empty_state(query: str, on_clear: Callable[[], None]) -> ft.Control:
    """Aucun résultat : on le dit, et on propose de repartir de zéro."""
    shown = query.strip()
    return ft.Container(
        padding=Space.xl,
        alignment=ft.Alignment(0, 0),
        content=ft.Column(
            [
                lottie(LOTTIE_EMPTY_SRC, 110) or ft.Icon(ft.Icons.SEARCH_OFF, size=36, color=Palette.ink_muted),
                ft.Text(
                    f"Aucun outil ne correspond à « {shown} »." if shown else "Aucun outil dans cette catégorie.",
                    size=14,
                    color=Palette.ink,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    "Essayez un autre mot : réduire, signer, assembler, protéger…",
                    size=12.5,
                    color=Palette.ink_muted,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.TextButton(content="Tout afficher", on_click=lambda _: on_clear()),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=Space.sm,
        ),
    )


RECENT_LIMIT = 5


def _exists(path: str) -> bool:
    try:
        return Path(path).exists()
    except OSError:
        return False


def _recent_section(
    recents, page: ft.Page, on_change: Callable[[], None]
) -> list[ft.Control]:
    """
    Derniers fichiers créés (rien si l'historique est vide ou absent).

    Seuls les fichiers qui existent encore sont montrés, au plus ``RECENT_LIMIT``.
    Toucher une ligne ouvre le fichier ; le bouton dossier (bureau) ouvre son dossier.

    ``on_change`` redessine l'accueil : après « Effacer », la liste doit disparaître
    immédiatement (on ne peut pas compter sur un changement de route, puisque
    l'on est déjà sur « / »).
    """
    items = recents.items if recents is not None else []
    items = [item for item in items if _exists(item.path)][:RECENT_LIMIT]
    if not items:
        return []

    desktop = not (page.web or page.platform.is_mobile())

    def open_file(path: str) -> None:
        page.run_task(page.launch_url, Path(path).resolve().as_uri())

    def _forget(path: str) -> None:
        recents.remove(path)
        on_change()

    def clear(_) -> None:
        recents.clear()
        on_change()

    rows: list[ft.Control] = []
    for item in items:
        try:
            when = item.created_at.astimezone().strftime("%d/%m %H:%M")
        except (ValueError, OSError, OverflowError):
            when = ""
        actions = []
        if desktop:
            actions.append(
                ft.IconButton(
                    ft.Icons.FOLDER_OPEN_OUTLINED,
                    icon_size=18,
                    icon_color=Palette.ink_muted,
                    tooltip="Ouvrir le dossier",
                    on_click=lambda _, path=item.path: reveal_in_folder(Path(path)),
                )
            )
        rows.append(
            ft.Container(
                padding=ft.Padding(left=Space.md, right=Space.sm, top=Space.sm, bottom=Space.sm),
                border=ft.Border.all(1, Palette.line),
                border_radius=12,
                bgcolor=Palette.surface,
                ink=True,
                on_click=lambda _, path=item.path: open_file(path),
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.HISTORY, size=18, color=Palette.ink_muted),
                        ft.Column(
                            [
                                ft.Text(Path(item.path).name, size=13.5, color=Palette.ink,
                                        weight=ft.FontWeight.W_600, max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS, tooltip=item.path),
                                ft.Text(f"{item.label} · {when}", size=12, color=Palette.ink_muted),
                            ],
                            spacing=1, expand=True,
                        ),
                        *actions,
                        ft.IconButton(
                            ft.Icons.CLOSE,
                            icon_size=18,
                            icon_color=Palette.ink_muted,
                            tooltip="Retirer de la liste",
                            on_click=lambda _, path=item.path: _forget(path),
                        ),
                    ],
                    spacing=Space.sm,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
        )

    return [
        ft.Row(
            [
                section_label("Récents"),
                ft.TextButton(content="Effacer", on_click=clear,
                              style=ft.ButtonStyle(color=Palette.ink_muted)),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        ft.Column(rows, spacing=Space.sm),
    ]


def build_home(
    page: ft.Page,
    recents=None,
    now: Callable[[], datetime] = datetime.now,
    pick: Callable[[tuple[str, ...]], str] = random.choice,
) -> ft.View:

    def go(route: str) -> Callable:
        def navigate(_) -> None:
            page.run_task(page.push_route, route)

        return navigate

    def hero_button(icon: str, tooltip: str, route: str) -> ft.IconButton:
        return ft.IconButton(
            icon, tooltip=tooltip, icon_color=Palette.on_hero, on_click=go(route)
        )

    desktop = not (page.web or page.platform.is_mobile())
    logo_height = 120 if desktop else 84
    animation = lottie(LOTTIE_SRC, logo_height, width=logo_height)
    mark, _pages = logo_fan(scale=0.72, on_dark=True)
    header = hero_card(
        APP_NAME,
        f"{greeting(now().hour)}, {pick(PROMPTS)}",
        [
            (ft.Icons.BUILD_OUTLINED, f"{len(TOOLS)} outils"),
            (ft.Icons.LOCK_OUTLINE, "100 % local"),
            (ft.Icons.BOLT_OUTLINED, "Sans compte"),
        ],
        actions=[
            hero_button(ft.Icons.SETTINGS_OUTLINED, "Paramètres", "/parametres"),
            hero_button(ft.Icons.INFO_OUTLINE, "À propos", "/a-propos"),
        ],
        leading=ft.Container(content=animation or mark, on_click=go("/a-propos"), tooltip="À propos"),
    )

    state = {"query": "", "group": None}
    groups = list(dict.fromkeys(tool.group for tool in TOOLS))  # ordre d'apparition

    tools_area = ft.Column(spacing=Space.md, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    chips_row = ft.Row(
        spacing=Space.sm,
        run_spacing=Space.sm,
        wrap=desktop,                                   # bureau : les catégories passent à la ligne
        scroll=None if desktop else ft.ScrollMode.HIDDEN,  # mobile : glissement au doigt, sans barre
    )
    count_label = ft.Text(size=12.5, color=Palette.ink_muted, visible=False)
    open_match = ft.Container(
        visible=False,
        padding=ft.Padding(left=Space.md, right=Space.md, top=Space.sm, bottom=Space.sm),
        border_radius=14,
        ink=True,
    )  # le contenu et les couleurs sont posés à chaque rendu (_show_open_match)

    def chip(label: str, value: str | None) -> ft.Container:
        selected = state["group"] == value
        return ft.Container(
            padding=ft.Padding(left=14, right=14, top=7, bottom=7),
            border_radius=20,
            bgcolor=Palette.ink if selected else Palette.surface,
            border=ft.Border.all(1, Palette.ink if selected else Palette.line_strong),
            ink=True,
            on_click=lambda _, v=value: choose_group(v),
            content=ft.Text(
                label,
                size=13,
                weight=ft.FontWeight.W_600 if selected else ft.FontWeight.W_500,
                color=Palette.surface if selected else Palette.ink,
            ),
        )

    def render() -> None:
        filtering = bool(state["query"].strip()) or state["group"] is not None
        matches = filter_tools(state["query"], state["group"])
        chips_row.controls = [chip("Tous", None), *(chip(g, g) for g in groups)]
        controls: list[ft.Control] = []

        if not filtering:
            controls += _recent_section(recents, page, refresh)
            controls.append(section_label("Accès rapide"))
            controls.append(
                ft.ResponsiveRow(
                    [
                        _quick_tile(TOOL_BY_ROUTE[route], label, go(route))
                        for route, label in QUICK_ACCESS
                    ],
                    columns=12,
                    spacing=Space.md,
                    run_spacing=Space.md,
                )
            )

        if not matches:
            controls.append(_empty_state(state["query"], clear_search))
        for group in dict.fromkeys(tool.group for tool in matches):
            in_group = [t for t in matches if t.group == group]
            controls.append(_group_header(group, len(in_group), _accent(in_group[0])))
            controls.append(
                ft.ResponsiveRow(
                    [
                        tool_card(t.icon, t.title, t.description, _accent(t), go(t.route))
                        for t in in_group
                    ],
                    columns=12,
                    spacing=Space.md,
                    run_spacing=Space.md,
                )
            )
        tools_area.controls = controls

        count_label.visible = filtering
        count_label.value = f"{len(matches)} outil{'s' if len(matches) > 1 else ''}"

        best = best_tool(state["query"], state["group"])
        if best:
            _show_open_match(open_match, best, go(best.route))
        else:
            _hide_open_match(open_match)

        search.suffix = (
            ft.IconButton(ft.Icons.CLOSE, tooltip="Effacer la recherche", icon_size=18, on_click=lambda _: clear_search())
            if state["query"]
            else None
        )

    def refresh() -> None:
        render()
        try:
            page.update()
        except RuntimeError:
            pass

    def on_search(event=None) -> None:
        state["query"] = search.value or ""
        refresh()

    def choose_group(value: str | None) -> None:
        state["group"] = value
        refresh()

    def clear_search() -> None:
        search.value = ""
        state["query"] = ""
        refresh()

    search = ft.TextField(
        hint_text="Rechercher un outil : compresser, signer, fusionner…",
        prefix_icon=ft.Icons.SEARCH,
        autofocus=desktop,
        border_radius=16,
        border_color=Palette.line_strong,
        focused_border_color=Palette.ink,
        bgcolor=Palette.surface,
        text_size=15,
        content_padding=ft.Padding(left=14, right=14, top=16, bottom=16),
        on_change=on_search,
        on_submit=lambda _: _open_only_match(),
    )

    def _open_only_match() -> None:
        """Entrée : on ouvre le meilleur résultat, s'il est clair."""
        best = best_tool(state["query"], state["group"])
        if best:
            go(best.route)(None)

    render()
    sections: list[ft.Control] = [
        search,
        open_match,
        chips_row,
        count_label,
        tools_area,
    ]

    footer = ft.Container(
        padding=ft.Padding(left=0, right=0, top=Space.lg, bottom=Space.xl),
        alignment=ft.Alignment(0, 0),
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(
                                       f"© {COPYRIGHT_YEAR} PDF Studio",
                                       size=12,
                                       color=Palette.ink_muted,
                                       text_align=ft.TextAlign.CENTER,
                                   ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=6,
                    wrap=True,
                )
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=Space.sm,
        ),
    )

    body = ft.Container(
        content=ft.Column(
            [header, *sections, footer],
            spacing=Space.md,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
        padding=ft.Padding(left=Space.lg, right=Space.lg, top=Space.lg, bottom=0),
        width=content_width(page),
    )

    def on_resize(_) -> None:
        if page.route != "/":  # l'accueil n'est plus affiché : `body` est périmé
            return
        body.width = content_width(page)
        try:
            page.update()
        except RuntimeError:
            pass

    page.on_resize = on_resize

    return ft.View(
        route="/",
        bgcolor=Palette.paper,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        scroll=ft.ScrollMode.AUTO,
        controls=[body],
    )