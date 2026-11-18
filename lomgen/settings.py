"""App settings in ~/.config/letter-of-motivation-editor/settings.toml."""

from __future__ import annotations

import tomllib

import tomlkit

from .core import CONFIG_DIR

PATH = CONFIG_DIR / "settings.toml"
DEFAULTS = {"root": "", "last": "", "signed": False, "width": 1400, "height": 900, "maximized": False}


def load() -> dict:
    data = dict(DEFAULTS)
    try:
        data.update(tomllib.loads(PATH.read_text(encoding="utf-8")))
    except (OSError, tomllib.TOMLDecodeError):
        pass
    return data


def save(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    PATH.write_text(tomlkit.dumps({k: data[k] for k in DEFAULTS if k in data}), encoding="utf-8")
