"""
Load environment variables from:
  1) <repo>/.env
  2) <repo>/backend/.env   (later file wins on duplicate keys)

Use this everywhere we previously only loaded the repo root .env so local
keys in backend/.env are picked up when running uvicorn from backend/.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("insure_route.env")

_loaded = False


def load_insure_route_env() -> None:
    global _loaded
    if _loaded:
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    backend_dir = Path(__file__).resolve().parent
    root_dir = backend_dir.parent
    for path in (root_dir / ".env", backend_dir / ".env"):
        if path.is_file():
            ok = load_dotenv(path, override=True)
            logger.debug("dotenv %s loaded=%s", path, ok)
    _loaded = True
