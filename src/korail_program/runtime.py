"""Runtime dependency discovery for bundled and installed executables."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys


def application_root() -> Path:
    """Return the installed app root or the repository root during development."""

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def user_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base) / "KorailAnalyzer"
    return Path.home() / ".korail_analyzer"


def ollama_models_dir() -> Path:
    return user_data_dir() / "models"


def bundled_ollama_executable() -> Path:
    return application_root() / "runtime" / "ollama" / "ollama.exe"


def bundled_ollama_server_executable() -> Path:
    return application_root() / "runtime" / "ollama" / "lib" / "ollama" / "llama-server.exe"


def bundled_ollama_runtime_ready() -> bool:
    return bundled_ollama_executable().exists() and bundled_ollama_server_executable().exists()


def resolve_ollama_executable() -> Path | None:
    bundled = bundled_ollama_executable()
    if bundled_ollama_runtime_ready():
        return bundled

    path_value = shutil.which("ollama")
    if path_value:
        return Path(path_value)

    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidate = Path(local) / "Programs" / "Ollama" / "ollama.exe"
        if candidate.exists():
            return candidate
    return None


def bundled_ffmpeg_executable() -> Path:
    return application_root() / "runtime" / "ffmpeg" / "bin" / "ffmpeg.exe"


def bundled_ffprobe_executable() -> Path:
    return application_root() / "runtime" / "ffmpeg" / "bin" / "ffprobe.exe"


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


def ollama_process_environment() -> dict[str, str]:
    models_dir = ollama_models_dir()
    models_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.setdefault("OLLAMA_MODELS", str(models_dir))
    env.setdefault("OLLAMA_HOST", "127.0.0.1:11434")
    return env
