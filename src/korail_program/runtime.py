"""Runtime discovery and isolation for bundled Ollama and FFmpeg executables."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from korail_program.config import DEFAULT_OLLAMA_URL


def application_root() -> Path:
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


def ollama_models_dir() -> Path:
    return user_data_dir() / "ollama" / "models"


def bundled_ollama_executable() -> Path:
    return _first_existing_path(_bundled_ollama_executable_candidates())


def bundled_ollama_server_executable() -> Path:
    return _first_existing_path(_bundled_ollama_server_candidates())


def bundled_ollama_runtime_ready() -> bool:
    if not bundled_ollama_executable().exists():
        return False
    if os.name == "nt":
        return bundled_ollama_server_executable().exists()
    return True


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
    if sys.platform == "darwin":
        for candidate in (
            Path("/Applications/Ollama.app/Contents/Resources/ollama"),
            Path.home() / "Applications" / "Ollama.app" / "Contents" / "Resources" / "ollama",
        ):
            if candidate.exists():
                return candidate
    return None


def ollama_process_environment() -> dict[str, str]:
    models_dir = ollama_models_dir()
    models_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["OLLAMA_MODELS"] = str(models_dir)
    env["OLLAMA_HOST"] = DEFAULT_OLLAMA_URL.removeprefix("http://").removeprefix("https://")
    env["OLLAMA_NO_CLOUD"] = "1"
    return env


def list_installed_ollama_models(
    ollama_path: str | Path | None = None,
    *,
    base_url: str = DEFAULT_OLLAMA_URL,
    timeout_s: int = 5,
) -> set[str]:
    try:
        request = urllib.request.Request(f"{base_url.rstrip('/')}/api/tags")
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            body = json.loads(response.read().decode("utf-8"))
        return {
            str(item.get("name") or item.get("model") or "").strip()
            for item in body.get("models", [])
            if isinstance(item, dict) and (item.get("name") or item.get("model"))
        }
    except (OSError, ValueError, urllib.error.URLError):
        pass
    if ollama_path is None:
        return set()
    try:
        result = subprocess.run(
            [str(ollama_path), "list"],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=ollama_process_environment(),
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    if result.returncode != 0:
        return set()
    models: set[str] = set()
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("name "):
            continue
        models.add(stripped.split(maxsplit=1)[0])
    return models


def is_ollama_server_ready(*, base_url: str = DEFAULT_OLLAMA_URL, timeout_s: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=timeout_s):
            return True
    except (OSError, urllib.error.URLError):
        return False


def bundled_ffmpeg_executable() -> Path:
    return _first_existing_path(_bundled_ffmpeg_candidates("ffmpeg"))


def bundled_ffprobe_executable() -> Path:
    return _first_existing_path(_bundled_ffmpeg_candidates("ffprobe"))


def resolve_ffmpeg_executable() -> Path | str:
    bundled = bundled_ffmpeg_executable()
    return bundled if bundled.exists() else shutil.which("ffmpeg") or "ffmpeg"


def resolve_ffprobe_executable() -> Path | str:
    bundled = bundled_ffprobe_executable()
    return bundled if bundled.exists() else shutil.which("ffprobe") or "ffprobe"


def _binary_name(name: str) -> str:
    return f"{name}.exe" if os.name == "nt" else name


def _runtime_root() -> Path:
    return application_root() / "runtime"


def _bundled_ollama_executable_candidates() -> list[Path]:
    root = _runtime_root() / "ollama"
    return [
        root / _binary_name("ollama"),
        root / "ollama",
        root / "bin" / _binary_name("ollama"),
        root / "bin" / "ollama",
        root / "Ollama.app" / "Contents" / "Resources" / "ollama",
    ]


def _bundled_ollama_server_candidates() -> list[Path]:
    root = _runtime_root() / "ollama"
    return [
        root / "lib" / "ollama" / _binary_name("llama-server"),
        root / "lib" / "ollama" / "llama-server",
        root / "Ollama.app" / "Contents" / "Resources" / "lib" / "ollama" / "llama-server",
    ]


def _bundled_ffmpeg_candidates(name: str) -> list[Path]:
    root = _runtime_root() / "ffmpeg"
    executable = _binary_name(name)
    return [root / "bin" / executable, root / "bin" / name, root / executable, root / name]


def _first_existing_path(candidates: list[Path]) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]
