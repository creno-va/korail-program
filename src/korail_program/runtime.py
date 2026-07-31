"""Runtime dependency discovery for bundled and installed executables."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def application_root() -> Path:
    """Return the installed app root or the repository root during development."""

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def user_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base) / "KorailAnalyzer"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "KorailAnalyzer"
    return Path.home() / ".korail_analyzer"


def bundled_ffmpeg_executable() -> Path:
    return _first_existing_path(_bundled_ffmpeg_candidates("ffmpeg"))


def bundled_ffprobe_executable() -> Path:
    return _first_existing_path(_bundled_ffmpeg_candidates("ffprobe"))


def resolve_ffmpeg_executable() -> Path | str:
    bundled = bundled_ffmpeg_executable()
    if bundled.exists():
        return bundled
    return shutil.which("ffmpeg") or "ffmpeg"


def resolve_ffprobe_executable() -> Path | str:
    bundled = bundled_ffprobe_executable()
    if bundled.exists():
        return bundled
    return shutil.which("ffprobe") or "ffprobe"


def _binary_name(name: str) -> str:
    return f"{name}.exe" if os.name == "nt" else name


def _runtime_root() -> Path:
    return application_root() / "runtime"


def _bundled_ffmpeg_candidates(name: str) -> list[Path]:
    root = _runtime_root() / "ffmpeg"
    executable = _binary_name(name)
    return [
        root / "bin" / executable,
        root / "bin" / name,
        root / executable,
        root / name,
    ]


def _first_existing_path(candidates: list[Path]) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]
