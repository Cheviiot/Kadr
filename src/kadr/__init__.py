"""Kadr — приложение для поиска торрентов фильмов и сериалов."""

from pathlib import Path

__version__ = '2.0.0'
APP_ID = 'io.github.cheviiot.kadr'
APP_NAME = 'Kadr'

# Paths: try development first, then fall back to installed locations
_PKG_DIR = Path(__file__).parent
_DATA_DIR = _PKG_DIR.parent.parent / 'data'

# Icon
_DEV_ICON = _DATA_DIR / 'Kadr.png'
ICON_PATH = _DEV_ICON if _DEV_ICON.exists() else None

# Hicolor icon theme directory (for dev runs)
_ICONS_DIR = _DATA_DIR / 'icons'
ICONS_DIR = _ICONS_DIR if _ICONS_DIR.is_dir() else None

# CSS (in package data)
_PKG_CSS = _PKG_DIR / 'data' / 'style.css'
CSS_PATH = _PKG_CSS if _PKG_CSS.exists() else None
