"""Interval-based video VQA analysis pipeline."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
import json
from pathlib import Path
import shutil

from korail_program.analysis.report import write_reports
from korail_program.core.event_merger import merge_judge_observations
from korail_program.core.frame_extractor import FrameExtractionConfig, extract_frames
from korail_program.core.models import AnalysisEvent, JudgeObservation, RiskLevel, VideoMetadata, to_jsonable
from korail_program.core.timecode import format_timecode
from korail_program.core.video_probe import probe_video
from korail_program.judge.gemma_client import OllamaVisionConfig, OllamaVisionJudgeClient
from korail_program.judge.schema import judge_observation_from_text

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}


@dataclass(frozen=True, slots=True)
class BatchAnalysisConfig:
    inputs: list[Path]
    output_dir: Path
    interval_s: float = 10.0
    model: str = "gemma3:4b"
    ollama_url: str = "http://localhost:11434"
    route_hint: str | None = None
    ffmpeg_path: str | Path = "ffmpeg"
    ffprobe_path: str | Path = "ffprobe"
    max_width: int | None = 1280
    min_report_risk: RiskLevel = RiskLevel.MEDIUM
    recursive: bool = False


@dataclass(frozen=True, slots=True)
class BatchAnalysisResult:
    output_dir: Path
    report_markdown: Path
    report_html: Path
    observations_json: Path
    events_json: Path
    video_count: int
    sampled_frame_count: int
    suspicious_frame_count: int
    event_count: int
    failure_count: int


def run_batch_analysis(config: BatchAnalysisConfig) -> BatchAnalysisResult:
    if config.interval_s <= 0:
        raise ValueError("interval_s must be positive")

    videos = discover_video_files(config.inputs, recursive=config.recursive)
    if not videos:
        raise ValueError("No supported video files were found")

    output_dir = _resolve_output_dir(config.output_dir)
    frames_root = output_dir / "frames"
    captures_root = output_dir / "captures"
    frames_root.mkdir(parents=True, exist_ok=True)
    captures_root.mkdir(parents=True, exist_ok=True)

    client = OllamaVisionJudgeClient(
        OllamaVisionConfig(base_url=config.ollama_url, model=config.model)
    )
    interval_ms = int(round(config.interval_s * 1000))
    sampled_frame_count = 0
    metadata_items: list[VideoMetadata] = []
    records: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []

    for video_id, video_path in enumerate(videos, start=1):
        video_key = f"video_{video_id:03d}"
        metadata_items.append(_probe_or_default(video_path, video_id=video_id, config=config))
        frame_dir = frames_root / video_key
        frames = extract_frames(
            FrameExtractionConfig(
                input_path=video_path,
                output_dir=frame_dir,
                fps=1 / config.interval_s,
                prefix="sample",
                max_width=config.max_width,
            ),
            ffmpeg_path=config.ffmpeg_path,
        )
        sampled_frame_count += len(frames)

        for frame_index, frame_path in enumerate(frames, start=1):
            video_time_ms = (frame_index - 1) * interval_ms
            try:
                raw_response = client.judge_image(frame_path, route_hint=config.route_hint)
                observation = judge_observation_from_text(
                    video_id=video_id,
                    video_time_ms=video_time_ms,
                    text=raw_response,
                )
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    {
                        "video_id": video_id,
                        "video_name": video_path.name,
                        "frame_path": str(frame_path),
                        "video_time_ms": video_time_ms,
                        "error": str(exc),
                    }
                )
                continue

            capture_path = _copy_capture_if_needed(
                frame_path=frame_path,
                captures_root=captures_root,
                video_key=video_key,
                video_time_ms=video_time_ms,
                observation=observation,
                min_report_risk=config.min_report_risk,
            )
            records.append(
                {
                    "video_id": video_id,
                    "video_name": video_path.name,
                    "video_path": str(video_path),
                    "frame_path": str(frame_path),
                    "capture_path": str(capture_path) if capture_path else None,
                    "video_time_ms": video_time_ms,
                    "observation": observation,
                    "raw_response": raw_response,
                }
            )

    suspicious_records = [record for record in records if record.get("capture_path")]
    suspicious_observations = [
        record["observation"]
        for record in suspicious_records
        if isinstance(record["observation"], JudgeObservation)
    ]
    events = merge_judge_observations(
        suspicious_observations,
        [],
        sample_interval_ms=interval_ms,
        gap_tolerance_ms=max(1500, interval_ms // 2),
        min_event_duration_ms=interval_ms,
    )
    events = _attach_capture_counts(events, suspicious_records)

    observations_json = output_dir / "observations.json"
    events_json = output_dir / "events.json"
    observations_json.write_text(
        json.dumps(
            {
                "config": _config_payload(config),
                "videos": [to_jsonable(item) for item in metadata_items],
                "records": [_record_payload(record) for record in records],
                "failures": failures,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    events_json.write_text(
        json.dumps([to_jsonable(event) for event in events], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report_markdown, report_html = write_reports(
        output_dir=output_dir,
        video_count=len(videos),
        sampled_frame_count=sampled_frame_count,
        suspicious_records=suspicious_records,
        events=events,
        failures=failures,
    )

    return BatchAnalysisResult(
        output_dir=output_dir,
        report_markdown=report_markdown,
        report_html=report_html,
        observations_json=observations_json,
        events_json=events_json,
        video_count=len(videos),
        sampled_frame_count=sampled_frame_count,
        suspicious_frame_count=len(suspicious_records),
        event_count=len(events),
        failure_count=len(failures),
    )


def discover_video_files(inputs: list[Path], *, recursive: bool = False) -> list[Path]:
    candidates = inputs or [Path.cwd()]
    videos: list[Path] = []
    for candidate in candidates:
        if _has_wildcard(candidate):
            matches = candidate.parent.glob(candidate.name)
            videos.extend(path for path in matches if _is_video(path))
            continue
        if candidate.is_file() and _is_video(candidate):
            videos.append(candidate)
            continue
        if candidate.is_dir():
            pattern = "**/*" if recursive else "*"
            videos.extend(path for path in candidate.glob(pattern) if _is_video(path))

    return sorted({path.resolve() for path in videos})


def _resolve_output_dir(output_dir: Path) -> Path:
    if output_dir.name:
        resolved = output_dir
    else:
        resolved = Path("output")
    if resolved.exists() and any(resolved.iterdir()):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        resolved = resolved.parent / f"{resolved.name}_{stamp}"
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved.resolve()


def _probe_or_default(video_path: Path, *, video_id: int, config: BatchAnalysisConfig) -> VideoMetadata:
    try:
        return probe_video(video_path, video_id=video_id, ffprobe_path=config.ffprobe_path)
    except Exception:  # noqa: BLE001
        return VideoMetadata(
            video_id=video_id,
            file_path=str(video_path),
            duration_ms=0,
            width=0,
            height=0,
            fps=0,
        )


def _copy_capture_if_needed(
    *,
    frame_path: Path,
    captures_root: Path,
    video_key: str,
    video_time_ms: int,
    observation: JudgeObservation,
    min_report_risk: RiskLevel,
) -> Path | None:
    if not observation.is_risky or observation.risk_level.priority < min_report_risk.priority:
        return None
    time_label = format_timecode(video_time_ms).replace(":", "-")
    target = captures_root / f"{video_key}_{time_label}{frame_path.suffix.lower()}"
    shutil.copy2(frame_path, target)
    return target


def _attach_capture_counts(
    events: list[AnalysisEvent],
    suspicious_records: list[dict[str, object]],
) -> list[AnalysisEvent]:
    updated: list[AnalysisEvent] = []
    for event in events:
        capture_count = 0
        for record in suspicious_records:
            observation = record.get("observation")
            if not isinstance(observation, JudgeObservation):
                continue
            if observation.video_id != event.video_id:
                continue
            if event.start_time_ms <= observation.video_time_ms < event.end_time_ms:
                capture_count += 1
        updated.append(replace(event, capture_count=capture_count))
    return updated


def _record_payload(record: dict[str, object]) -> dict[str, object]:
    payload = dict(record)
    payload["observation"] = to_jsonable(payload["observation"])
    return payload


def _config_payload(config: BatchAnalysisConfig) -> dict[str, object]:
    return {
        "inputs": [str(path) for path in config.inputs],
        "interval_s": config.interval_s,
        "model": config.model,
        "ollama_url": config.ollama_url,
        "route_hint": config.route_hint,
        "ffmpeg_path": str(config.ffmpeg_path),
        "ffprobe_path": str(config.ffprobe_path),
        "max_width": config.max_width,
        "min_report_risk": config.min_report_risk.value,
        "recursive": config.recursive,
    }


def _has_wildcard(path: Path) -> bool:
    return any(char in str(path) for char in "*?[")


def _is_video(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
