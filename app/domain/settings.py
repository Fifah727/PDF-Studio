"""Préférences utilisateur : valeurs, valeurs par défaut et validation."""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import Any

THEME_SYSTEM = "system"
THEME_LIGHT = "light"
THEME_DARK = "dark"
THEMES = (THEME_SYSTEM, THEME_LIGHT, THEME_DARK)


@dataclass(frozen=True, slots=True)
class Settings:
    theme: str = THEME_SYSTEM
    fit_a4_default: bool = True
    remember_last_folder: bool = True
    offer_open_folder: bool = True
    last_folder: str | None = None

    @classmethod
    def from_mapping(cls, data: Any) -> "Settings":
        """
        Construit des préférences à partir de données non fiables (fichier
        édité à la main, ancienne version…). Toute valeur inconnue ou de
        mauvais type retombe sur la valeur par défaut.
        """
        defaults = cls()
        if not isinstance(data, dict):
            return defaults

        values: dict[str, Any] = {}
        for field in fields(cls):
            raw = data.get(field.name, getattr(defaults, field.name))
            values[field.name] = _coerce(field.name, raw, getattr(defaults, field.name))
        return cls(**values)

    def with_changes(self, **changes: Any) -> "Settings":
        unknown = set(changes) - {f.name for f in fields(self)}
        if unknown:
            raise KeyError(f"Paramètre inconnu : {', '.join(sorted(unknown))}")
        merged = {
            name: _coerce(name, value, getattr(self, name))
            for name, value in changes.items()
        }
        return replace(self, **merged)


def _coerce(name: str, value: Any, default: Any) -> Any:
    if name == "theme":
        return value if value in THEMES else default
    if name == "last_folder":
        return value if isinstance(value, str) and value else None
    return value if isinstance(value, bool) else default
