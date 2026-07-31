"""Shared video-file discovery and validation helpers."""

from __future__ import annotations

from pathlib import Path

SUPPORTED_VIDEO_EXTENSIONS = frozenset({".mp4", ".avi", ".mov", ".mkv"})


def is_supported_video(path: Path) -> bool:
    """Return whether *path* is an existing, supported video file."""

    return path.is_file() and path.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS


def discover_video_files(inputs: list[Path], *, recursive: bool = False) -> list[Path]:
    """Resolve files, directories, and simple glob inputs for batch analysis."""

    candidates = inputs or [Path.cwd()]
    videos: list[Path] = []
    for candidate in candidates:
        if _has_wildcard(candidate):
            matches = candidate.parent.glob(candidate.name)
            videos.extend(path for path in matches if is_supported_video(path))
            continue
        if is_supported_video(candidate):
            videos.append(candidate)
            continue
        if candidate.is_dir():
            pattern = "**/*" if recursive else "*"
            videos.extend(path for path in candidate.glob(pattern) if is_supported_video(path))

    return sorted({path.resolve() for path in videos})


def collect_video_candidates(paths: list[Path]) -> tuple[list[Path], int]:
    """Collect immediate video files for the GUI and count rejected inputs."""

    candidates: list[Path] = []
    skipped = 0
    for path in paths:
        try:
            if path.is_dir():
                videos = [item for item in path.iterdir() if is_supported_video(item)]
                candidates.extend(videos)
                if not videos:
                    skipped += 1
                continue
            if is_supported_video(path):
                candidates.append(path)
            else:
                skipped += 1
        except OSError:
            skipped += 1

    resolved: dict[Path, None] = {}
    for candidate in candidates:
        try:
            resolved[candidate.resolve()] = None
        except OSError:
            skipped += 1
    return sorted(resolved), skipped


def _has_wildcard(path: Path) -> bool:
    return any(char in str(path) for char in "*?[")
