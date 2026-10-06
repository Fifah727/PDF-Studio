import json

from app.domain.settings import Settings
from app.infrastructure.json_settings_store import JsonSettingsStore


def test_defaults():
    s = Settings()
    assert (s.theme, s.fit_a4_default, s.remember_last_folder, s.offer_open_folder) == (
        "system", True, True, True,
    )
    assert s.last_folder is None


def test_untrusted_data_falls_back_per_field():
    s = Settings.from_mapping(
        {"theme": "neon", "fit_a4_default": "yes", "remember_last_folder": False,
         "last_folder": 12, "inconnu": 1}
    )
    assert s.theme == "system" and s.fit_a4_default is True
    assert s.remember_last_folder is False and s.last_folder is None
    assert Settings.from_mapping(["pas", "un", "dict"]) == Settings()


def test_with_changes_validates():
    s = Settings().with_changes(theme="dark", last_folder="/x")
    assert s.theme == "dark" and s.last_folder == "/x"
    assert s.with_changes(theme="bogus").theme == "dark"  # valeur invalide : on garde l'actuelle
    import pytest
    with pytest.raises(KeyError):
        s.with_changes(nope=1)


def test_store_roundtrip_and_reset(tmp_path):
    path = tmp_path / "sub" / "settings.json"
    store = JsonSettingsStore(path)
    assert store.current == Settings()          # fichier absent
    store.update(theme="dark", fit_a4_default=False)
    again = JsonSettingsStore(path)             # nouvelle session
    assert again.current.theme == "dark" and again.current.fit_a4_default is False
    assert json.loads(path.read_text("utf-8"))["theme"] == "dark"
    again.reset()
    assert JsonSettingsStore(path).current == Settings()
    assert not list(path.parent.glob(".*.part"))


def test_store_survives_corrupted_file(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{pas du json", "utf-8")
    store = JsonSettingsStore(path)
    assert store.current == Settings()
    store.update(theme="light")
    assert JsonSettingsStore(path).current.theme == "light"
