"""Small dotenv loader for local API configuration."""

from __future__ import annotations

import os
from pathlib import Path

from korail_program.runtime import user_data_dir


def load_default_env_files() -> None:
    for path in (
        Path.cwd() / ".env",
        Path.cwd() / ".env.local",
        user_data_dir() / ".env",
        user_data_dir() / ".env.local",
    ):
        load_env_file(path)


def load_env_file(path: Path) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = _strip_quotes(value.strip())


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
