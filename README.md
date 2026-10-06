# PDF Studio

Application de bureau (et mobile) en **Python + Flet 1.0** pour manipuler des PDF, **entièrement en local** :
aucun fichier ne quitte l'appareil.

**23 outils**, tous hors-connexion, avec le même code sur Android et Windows (aucune dépendance native de plus
que `Pillow` et `cryptography`).

| Groupe | Outil | Ce qu'il fait |
|---|---|---|
| Organiser | Extraire des pages | `1-3, 5, 8-10` — plusieurs plages, ordre conservé |
| | Fusionner | Plusieurs PDF, ordre modifiable avec les flèches ↑ ↓ |
| | Supprimer des pages | `2, 4-6` — refuse de tout supprimer |
| | Diviser | Un PDF par page, dans une archive ZIP |
| | Pivoter | 90° / 180° / 270°, sur une sélection ou tout le document |
| | **Réorganiser** | Flèches ↑ ↓ page par page (≤ 80 pages), saisie `3, 1, 2` au-delà, inversion de tout l'ordre |
| | **Insérer des pages** | Pages blanches (à la taille de la page voisine) ou pages d'un autre PDF, après la page N |
| | **Fusion recto-verso** | Rectos + versos scannés séparément (versos inversés ou non) ; tolère un dernier verso vierge |
| | **Rogner** | Marges en mm, vues à l'écran (pages pivotées comprises) ; le contenu n'est pas détruit |
| Optimiser | **Compresser** | 3 niveaux ; affiche « 12 Mo → 3,4 Mo (−72 %) » ; ne grossit jamais un fichier |
| | **Métadonnées** | Lire / modifier / effacer (Info + XMP) |
| | **Signets** | Table des matières imbriquée : `1: Titre`, `- 3: Sous-titre` |
| Personnaliser | **Filigrane texte** | Couleur, orientation, opacité, pages choisies |
| | **Filigrane image** | Logo / tampon, PNG transparent conservé |
| | **Signer un PDF** | Image de signature (fond blanc retiré), 9 emplacements, dernière page par défaut |
| | **Retirer des filigranes** | Repère les filigranes texte / image / signatures et retire ceux que vous cochez (voir limites) |
| | **Numéroter** | `{n}` / `{total}`, 9 emplacements, numéro de départ, pages choisies |
| Extraire | **Images** | Archive ZIP ; logos répétés dédoublonnés |
| | **Texte** | Fichier `.txt` (PDF numériques ; un scan est signalé comme tel) |
| Convertir | Images vers PDF | + **amélioration de scan** : Document / Gris / Noir et blanc (ombres corrigées) |
| | Pages en paysage | Deux pages A4 côte à côte par feuille |
| Lot | **Traitement par lot** | Numéroter, filigraner, compresser, effacer les métadonnées, protéger → ZIP ; un fichier en échec n'arrête pas le lot |
| Sécurité | Mot de passe | Protéger (AES-256) ou déverrouiller un PDF |

L'accueil affiche aussi les **8 derniers fichiers créés** (`recents.json`, effaçables).

### Ergonomie (v1.2)

- **Accueil** : recherche instantanée (insensible aux accents et aux majuscules, avec synonymes :
  « réduire », « signer », « enlever watermark »…), filtres par catégorie, compteur de résultats, état
  « aucun résultat », Entrée ouvre l'outil s'il est le seul trouvé. Les récents se masquent pendant la recherche.
- **Chaque outil** : sections « Fichier » / « Réglages », message sous le bouton qui explique pourquoi il est
  grisé, **bandeau de résultat persistant** (nom du fichier, gain de compression, « Ouvrir le dossier ») en plus
  de la notification.
- **Validation en direct** : le filigrane texte, le format de numérotation et les signets signalent l'erreur
  sous le champ pendant la frappe (caractères non gérés, `{n}` manquant, page de signet inexistante).
- Boutons ↑ ↓ de « Réorganiser » agrandis pour le tactile.

### Accueil (v1.3)

Bandeau avec le logo en éventail (touchez-le : « À propos ») et une salutation selon l'heure, **accès rapide**
aux 4 outils du quotidien, en-têtes de catégorie (icône + nombre d'outils), cartes teintées à la couleur de
l'outil, bandeau **« Ouvrir « … » »** quand la recherche ne trouve qu'un outil, et possibilité de retirer un
fichier de l'historique un par un (ou tout effacer). Le logo vit dans `widgets/brand.py`, partagé avec « À propos ».

### Écran « À propos » (v1.2.1)

Logo en éventail de pages (un appui l'ouvre et change la phrase d'accroche), « voyage d'un fichier », quatre
promesses, **mosaïque des outils** générée depuis le catalogue (chaque carreau ouvre son outil), versions
**réellement installées** des bibliothèques (indique « indisponible » si l'une manque sur l'appareil), bouton
« Copier les infos de diagnostic » (sans aucune donnée personnelle) et dossier de données de l'application.

### Filigranes : ce qui est retiré, et ce qui ne l'est pas

Les filigranes, images de logo et signatures posés par PDF Studio sont désormais balisés selon le standard PDF
(`/Artifact /Subtype /Watermark`), ce qui permet de les retrouver. L'outil retire aussi ceux que d'autres
logiciels déclarent de la même façon, ou placent dans un calque nommé « watermark » / « filigrane ».
**Un filigrane aplati dans l'image d'une page (scan, impression en PDF) n'est pas retirable automatiquement.**
Les PDF filigranés avec la v1.1.0 n'ont pas ce balisage : leurs tampons ne sont pas repérés.

## Lancer en développement

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows  (Linux/macOS : source .venv/bin/activate)
pip install -r requirements-dev.txt
flet run                      # ou : python main.py
pytest                        # 262 tests
```

## Construire l'application (déploiement)

`flet build` lit `pyproject.toml` (nom, version, identifiant, dépendances) et `assets/icon.png`.

```bash
flet build windows            # .exe dans build/windows/
flet build macos
flet build linux
flet build apk                # Android (nécessite le SDK Android)
```

Avant de livrer : **installez et testez le binaire produit**, pas seulement `flet run`.
Pour changer de version, modifiez `version` dans `pyproject.toml` **et** `app/__init__.py`.

## Paramètres et thème

Écran **Paramètres** (icône ⚙ de l'accueil), appliqué et sauvegardé immédiatement :

| Réglage | Effet |
|---|---|
| Thème Clair / Sombre / Système | « Système » suit le thème de l'appareil en direct |
| Se souvenir du dernier dossier | Les boîtes de dialogue s'ouvrent où vous avez travaillé en dernier |
| Proposer d'ouvrir le dossier | Bouton après chaque enregistrement (bureau) |
| Ajuster à A4 par défaut | Valeur initiale de « Images vers PDF » |
| Réinitialiser | Retour aux valeurs par défaut |

Les préférences sont dans `settings.json` (dossier de données : `~/.pdf_studio`, ou le stockage privé de
l'app sur mobile). Un fichier absent ou corrompu retombe sur les valeurs par défaut.
La page **À propos** (icône ℹ) affiche l'auteur ; les textes sont dans `app/__init__.py`
(`AUTHOR_NAME`, `AUTHOR_ROLE`, `AUTHOR_COUNTRY`, `AUTHOR_EMAIL`) ; elle propose aussi d'écrire à l'auteure ou de copier son e-mail.

## Architecture

```
app/
  domain/          modèles et options (PageSelection, TextWatermark, CropMargins…), exceptions, ports
                   (PdfRepository, PdfStamper, PdfOptimizer, ImageToPdfConverter, ArchiveWriter)
  application/     cas d'usage (organize/optimize/stamp/extract), lot, validation, noms de fichiers
  infrastructure/  pypdf (dépôt, tampon, optimiseur), Pillow, écriture atomique, JSON (préférences, récents)
  presentation/    Flet : écrans, widgets, routeur, thème clair/sombre (Palette + ThemeController)
tests/             domaine, cas d'usage, images, interface (sans fenêtre)
```

Principes à conserver :
- `pypdf` et `PIL` ne sont importés que dans `infrastructure/`.
- Un nouvel outil = une méthode sur un port, un cas d'usage, un écran basé sur `screens/tool_kit.py`, un test.
- Toute écriture est **atomique** (`atomic_write`) : pas de PDF tronqué si l'opération échoue.
- Un fichier de sortie ne peut jamais écraser un fichier source.
- Les opérations tournent dans un thread (`asyncio.to_thread`) derrière un indicateur de progression.
- Sur mobile, `save_file` exige les octets du fichier : `FilePickerService.save_result` gère les deux cas.

## Journal technique

Les erreurs inattendues sont consignées silencieusement dans `<dossier de données>/logs/pdf_studio.log`
(rotation automatique). Il n'est pas exposé dans l'interface ; il sert uniquement au diagnostic en cas de problème.

## Limites connues

- Pas de version **web** : le navigateur n'expose pas les chemins de fichiers locaux.
- Les PDF protégés par mot de passe doivent d'abord passer par l'outil « Mot de passe ».
- L'outil « Mot de passe » dépend de `cryptography` ; si cette bibliothèque n'est pas disponible sur une
  plateforme (à vérifier pour Android/iOS), un message clair est affiché et les autres outils restent utilisables.
- **Aucun moteur de rendu PDF n'est embarqué** (pas de miniatures de pages, de PDF → image, d'OCR ni de caviardage
  réel) : ces fonctions exigeraient une bibliothèque native dont la disponibilité sur Android n'est pas confirmée.
  Les pages se désignent par leur numéro ; le filigrane/numéro texte utilise Helvetica (lettres latines, accents
  français et malgaches compris — pas d'alphabet arabe ou cyrillique).
- La « signature » insérée est une image : ce n'est pas une signature électronique certifiée.
- Compression : seules les images sont réencodées ; un PDF sans image gagne peu. Les images à masque ou en 1 bit sont laissées intactes.
- À valider sur appareil avant publication : `flet build apk` avec `Pillow` et `cryptography`, puis un essai de chaque
  outil sur un vrai téléphone (le rognage, la signature et le lot n'ont été testés ici qu'en environnement de bureau).
