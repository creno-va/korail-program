"""FFmpeg frame extraction helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from korail_program.config import DEFAULT_MAX_FRAME_WIDTH


@dataclass(frozen=True, slots=True)
class FrameExtractionConfig:
    input_path: Path
    output_dir: Path
    fps: float = 1.0
    prefix: str = "frame"
    start_time_ms: int | None = None
    end_time_ms: int | None = None
    image_ext: str = "jpg"
    max_width: int | None = DEFAULT_MAX_FRAME_WIDTH


def build_ffmpeg_frame_command(
    config: FrameExtractionConfig,
    *,
    ffmpeg_path: str | Path = "ffmpeg",
) -> list[str]:
    if config.fps <= 0:
        raise ValueError("fps must be positive")
    if config.end_time_ms is not None and config.start_time_ms is not None:
        if config.end_time_ms <= config.start_time_ms:
            raise ValueError("end_time_ms must be greater than start_time_ms")

    output_pattern = config.output_dir / f"{config.prefix}_%08d.{config.image_ext}"
    command = [str(ffmpeg_path), "-hide_banner", "-loglevel", "error"]
    if config.start_time_ms is not None:
        command.extend(["-ss", _seconds(config.start_time_ms)])
    command.extend(["-i", str(config.input_path)])
    if config.end_time_ms is not None:
        duration_ms = config.end_time_ms - (config.start_time_ms or 0)
        command.extend(["-t", _seconds(duration_ms)])
    command.extend(["-vf", _video_filter(config), "-q:v", "2", str(output_pattern)])
    return command


def extract_frames(
    config: FrameExtractionConfig,
    *,
    ffmpeg_path: str | Path = "ffmpeg",
    timeout_s: int | None = None,
) -> list[Path]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    command = build_ffmpeg_frame_command(config, ffmpeg_path=ffmpeg_path)
    subprocess.run(command, check=True, timeout=timeout_s)
    return sorted(config.output_dir.glob(f"{config.prefix}_*.{config.image_ext}"))


def _seconds(milliseconds: int) -> str:
    return f"{milliseconds / 1000:.3f}"


def _video_filter(config: FrameExtractionConfig) -> str:
    filters = [f"fps={config.fps:g}"]
    if config.max_width is not None and config.max_width > 0:
        filters.append(f"scale='min({config.max_width},iw)':-2")
    return ",".join(filters)
