"""Video metadata probing through ffprobe."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from korail_program.core.models import VideoMetadata


def build_ffprobe_command(
    file_path: str | Path, *, ffprobe_path: str | Path = "ffprobe"
) -> list[str]:
    return [
        str(ffprobe_path),
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(file_path),
    ]


def probe_video(
    file_path: str | Path, *, video_id: int = 0, ffprobe_path: str | Path = "ffprobe"
) -> VideoMetadata:
    result = subprocess.run(
        build_ffprobe_command(file_path, ffprobe_path=ffprobe_path),
        check=True,
        capture_output=True,
        text=True,
    )
    return parse_ffprobe_json(result.stdout, file_path=file_path, video_id=video_id)


def parse_ffprobe_json(payload: str, *, file_path: str | Path, video_id: int = 0) -> VideoMetadata:
    data = json.loads(payload)
    streams = data.get("streams", [])
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    if video_stream is None:
        raise ValueError("ffprobe payload does not contain a video stream")

    duration = video_stream.get("duration") or data.get("format", {}).get("duration") or 0
    return VideoMetadata(
        video_id=video_id,
        file_path=str(file_path),
        duration_ms=int(float(duration) * 1000),
        width=int(video_stream.get("width") or 0),
        height=int(video_stream.get("height") or 0),
        fps=_parse_rate(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")),
    )


def _parse_rate(value: str | None) -> float:
    if not value or value == "0/0":
        return 0.0
    if "/" not in value:
        return float(value)
    numerator, denominator = value.split("/", 1)
    denominator_number = float(denominator)
    if denominator_number == 0:
        return 0.0
    return float(numerator) / denominator_number
