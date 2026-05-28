"""
Фоновая проверка обновлений через GitHub Releases API.
Запускается при старте, затем каждые 24 часа.
"""
import json
import logging
import threading
from typing import Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com/repos/GMEP-IPN/Trends/releases/latest"
_RELEASES_PAGE = "https://github.com/GMEP-IPN/Trends/releases/latest"
_CHECK_INTERVAL = 24 * 3600

_latest_version: Optional[str] = None
_update_available: bool = False
_releases_url: str = _RELEASES_PAGE


import re

def _parse_version(v: str) -> tuple:
    try:
        parts = re.findall(r'\d+', v)
        return tuple(int(x) for x in parts)
    except Exception:
        return (0,)


def _check() -> None:
    global _latest_version, _update_available, _releases_url
    from app import __version__
    try:
        # Load GitHub Token if configured
        token = None
        try:
            from app.config.config_loader import get_config
            cfg = get_config()
            token = getattr(cfg, 'github_token', None)
        except Exception:
            pass
            
        if not token:
            import os
            token = os.environ.get("TRENDS_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")

        headers = {"User-Agent": f"Trends/{__version__}"}
        if token:
            headers["Authorization"] = f"token {token}"

        req = Request(_GITHUB_API, headers=headers)
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        tag = data.get("tag_name", "")
        if not tag:
            return
        _latest_version = tag.lstrip("v")
        _releases_url = data.get("html_url", _RELEASES_PAGE)
        _update_available = _parse_version(tag) > _parse_version(__version__)
        if _update_available:
            logger.info("Update available: %s → %s", __version__, _latest_version)
    except (URLError, Exception) as exc:
        logger.debug("Update check failed: %s", exc)


def _loop() -> None:
    while True:
        _check()
        threading.Event().wait(_CHECK_INTERVAL)


def start() -> None:
    threading.Thread(target=_loop, name="update-checker", daemon=True).start()


def get_info() -> dict:
    return {
        "update_available": _update_available,
        "latest_version": _latest_version,
        "releases_url": _releases_url if _update_available else None,
    }
