"""Journal d'exécution : indispensable pour diagnostiquer une app déployée."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.infrastructure.app_dirs import app_data_dir

_configured: Path | None = None


def configure_logging() -> Path | None:
    """
    Écrit les logs dans ``<dossier de données>/logs/pdf_studio.log`` avec
    rotation automatique. Idempotent.
    """
    global _configured
    if _configured is not None:
        return _configured

    try:
        log_dir = app_data_dir() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "pdf_studio.log"
        handler = RotatingFileHandler(
            log_file, maxBytes=512_000, backupCount=3, encoding="utf-8"
        )
    except OSError:
        return None

    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logger = logging.getLogger("app")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    _configured = log_file
    return log_file
