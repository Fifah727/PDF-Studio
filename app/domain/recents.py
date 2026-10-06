"""Fichiers récemment créés (historique léger affiché sur l'accueil)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class RecentFile:
    path: str
    label: str  # ce qui a été fait : « PDF pivoté créé »
    created_at: datetime  # avec fuseau horaire
