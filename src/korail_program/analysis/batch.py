"""Interval-based video VQA analysis pipeline."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
import json
from pathlib import Path
import shutil

from korail_program.analysis.report import write_reports
from korail_program.config import DEFAULT_OLLAMA_URL, DEFAULT_VISION_MODEL
from korail_program.core.event_merger import merge_judge_observations
from korail_program.core.frame_extractor import FrameExtractionConfig, extract_frames
from korail_program.core.models import (
    AnalysisEvent,
    JudgeObservation,
    OcrObservation,
    RiskLevel,
    SectionMapping,
    VideoMetadata,
    to_jsonable,
)
from korail_program.core.timecode import format_timecode
from korail_program.core.video_probe import probe_video
from korail_program.judge.gemma_client import (
    OllamaApiError,
    OllamaVisionConfig,
    OllamaVisionJudgeClient,
)
from korail_program.judge.schema import judge_observation_from_text
from korail_program.ocr.paddle_ocr_engine import PaddleOcrEngine
from korail_program.ocr.station_dictionary import load_station_names
from korail_program.ocr.station_matcher import StationMatcher
from korail_program.ocr.vlm_ocr_engine import VlmStationOcrEngine

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}
MAX_CONSECUTIVE_JUDGE_FAILURES = 3


@dataclass(frozen=True, slots=True)
class BatchAnalysisConfig:
    inputs: list[Path]
    output_dir: Path
    interval_s: float = 10.0
    model: str = DEFAULT_VISION_MODEL
    ollama_url: str = DEFAULT_OLLAMA_URL
    route_hint: str | None = None
    ffmpeg_path: str | Path = "ffmpeg"
    ffprobe_path: str | Path = "ffprobe"
    max_width: int | None = 1280
    min_report_risk: RiskLevel = RiskLevel.MEDIUM
    recursive: bool = False
    ocr_backend: str = "vlm"
    ocr_interval_s: float | None = 30.0
    station_dictionary_path: Path | None = None


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
    ocr_observation_count: int = 0
    aborted: bool = False
    failure_summary: str | None = None


def run_batch_analysis(config: BatchAnalysisConfig) -> BatchAnalysisResult:
    if config.interval_s <= 0:
        raise ValueError("interval_s must be positive")
    if config.ocr_interval_s is not None and config.ocr_interval_s <= 0:
        raise ValueError("ocr_interval_s must be positive when OCR is enabled")

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
    ocr_engine = _create_ocr_engine(config)
    station_matcher = _create_station_matcher(config)
    interval_ms = int(round(config.interval_s * 1000))
    ocr_interval_ms = (
        int(round(config.ocr_interval_s * 1000)) if config.ocr_interval_s is not None else interval_ms
    )
    ocr_every_n_frames = max(1, int(round(ocr_interval_ms / interval_ms)))
    sampled_frame_count = 0
    metadata_items: list[VideoMetadata] = []
    records: list[dict[str, object]] = []
    ocr_observations: list[OcrObservation] = []
    failures: list[dict[str, object]] = []
    consecutive_judge_failures = 0
    failure_summary: str | None = None

    for video_id, video_path in enumerate(videos, start=1):
        if failure_summary:
            break
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
            if failure_summary:
                break
            video_time_ms = (frame_index - 1) * interval_ms
            if ocr_engine is not None and _should_run_ocr(frame_index, ocr_every_n_frames):
                try:
                    ocr_observation = _read_station_observation(
                        engine=ocr_engine,
                        matcher=station_matcher,
                        frame_path=frame_path,
                        video_id=video_id,
                        video_time_ms=video_time_ms,
                        route_hint=config.route_hint,
                    )
                    if ocr_observation is not None:
                        ocr_observations.append(ocr_observation)
                except Exception as exc:  # noqa: BLE001
                    failures.append(
                        {
                            "stage": "ocr",
                            "video_id": video_id,
                            "video_name": video_path.name,
                            "frame_path": str(frame_path),
                            "video_time_ms": video_time_ms,
                            "error": _error_text(exc),
                        }
                    )

            try:
                raw_response = client.judge_image(frame_path, route_hint=config.route_hint)
                observation = judge_observation_from_text(
                    video_id=video_id,
                    video_time_ms=video_time_ms,
                    text=raw_response,
                )
            except Exception as exc:  # noqa: BLE001
                error_text = _error_text(exc)
                failures.append(
                    {
                        "video_id": video_id,
                        "video_name": video_path.name,
                        "frame_path": str(frame_path),
                        "video_time_ms": video_time_ms,
                        "stage": "judge",
                        "error": error_text,
                    }
                )
                consecutive_judge_failures += 1
                if _is_model_failure(exc) and consecutive_judge_failures >= MAX_CONSECUTIVE_JUDGE_FAILURES:
                    failure_summary = _model_failure_summary(error_text)
                    failures.append(
                        {
                            "stage": "system",
                            "video_id": video_id,
                            "video_name": video_path.name,
                            "frame_path": str(frame_path),
                            "video_time_ms": video_time_ms,
                            "error": failure_summary,
                        }
                    )
                    break
                continue
            consecutive_judge_failures = 0

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

    if failure_summary is None and sampled_frame_count and not records:
        judge_failure = next(
            (failure for failure in failures if failure.get("stage") == "judge"),
            None,
        )
        if judge_failure is not None:
            failure_summary = _model_failure_summary(str(judge_failure.get("error", "")))

    suspicious_records = [record for record in records if record.get("capture_path")]
    suspicious_observations = [
        record["observation"]
        for record in suspicious_records
        if isinstance(record["observation"], JudgeObservation)
    ]
    sections = _build_section_mappings(
        ocr_observations,
        metadata_items=metadata_items,
        sample_interval_ms=interval_ms,
    )
    events = merge_judge_observations(
        suspicious_observations,
        sections,
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
                "ocr_observations": [to_jsonable(item) for item in ocr_observations],
                "sections": [to_jsonable(item) for item in sections],
                "records": [_record_payload(record) for record in records],
                "failures": failures,
                "failure_summary": failure_summary,
                "aborted": failure_summary is not None and not records,
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
        ocr_observation_count=len(ocr_observations),
        suspicious_records=suspicious_records,
        events=events,
        failures=failures,
        failure_summary=failure_summary,
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
        ocr_observation_count=len(ocr_observations),
        aborted=failure_summary is not None and not records,
        failure_summary=failure_summary,
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


def _error_text(exc: Exception) -> str:
    text = str(exc).strip()
    return text or exc.__class__.__name__


def _is_model_failure(exc: Exception) -> bool:
    return isinstance(exc, OllamaApiError)


def _model_failure_summary(error_text: str) -> str:
    if not error_text:
        return "로컬 모델 호출이 반복 실패했습니다. 모델 설치 상태와 PC 메모리를 확인하세요."
    lowered = error_text.lower()
    if "memory" in lowered or "ram" in lowered or "vram" in lowered:
        return f"로컬 모델 메모리 부족으로 분석을 중단했습니다: {error_text}"
    if "not found" in lowered or "pull model" in lowered:
        return f"모델이 설치되지 않았거나 찾을 수 없습니다: {error_text}"
    if "does not support images" in lowered or "vision" in lowered:
        return f"현재 모델이 이미지 입력을 처리하지 못합니다: {error_text}"
    return f"로컬 모델 호출이 반복 실패해 분석을 중단했습니다: {error_text}"


def _create_ocr_engine(config: BatchAnalysisConfig) -> object | None:
    backend = config.ocr_backend.strip().lower()
    if backend in {"none", "off", "disabled"}:
        return None
    if backend == "vlm":
        return VlmStationOcrEngine(
            OllamaVisionConfig(base_url=config.ollama_url, model=config.model)
        )
    if backend == "paddle":
        return PaddleOcrEngine()
    if backend == "auto":
        try:
            return PaddleOcrEngine()
        except RuntimeError:
            return VlmStationOcrEngine(
                OllamaVisionConfig(base_url=config.ollama_url, model=config.model)
            )
    raise ValueError(f"Unsupported OCR backend: {config.ocr_backend!r}")


def _create_station_matcher(config: BatchAnalysisConfig) -> StationMatcher | None:
    station_names: list[str] = []
    if config.station_dictionary_path is not None:
        station_names.extend(load_station_names(config.station_dictionary_path))
    station_names.extend(_station_names_from_hint(config.route_hint))
    if not station_names:
        return None
    return StationMatcher(station_names)


def _station_names_from_hint(route_hint: str | None) -> list[str]:
    if not route_hint:
        return []
    normalized = route_hint.replace("->", ",").replace(">", ",").replace("/", ",")
    normalized = normalized.replace("~", ",").replace("-", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def _should_run_ocr(frame_index: int, ocr_every_n_frames: int) -> bool:
    return frame_index == 1 or (frame_index - 1) % ocr_every_n_frames == 0


def _read_station_observation(
    *,
    engine: object,
    matcher: StationMatcher | None,
    frame_path: Path,
    video_id: int,
    video_time_ms: int,
    route_hint: str | None,
) -> OcrObservation | None:
    method = str(getattr(engine, "method", engine.__class__.__name__)).lower()
    raw_text = ""
    station_name: str | None = None
    confidence = 0.0

    if hasattr(engine, "read_station_text"):
        result = engine.read_station_text(frame_path, route_hint=route_hint)
        raw_text = str(getattr(result, "raw_text", "") or "").strip()
        station_name = getattr(result, "station_name", None)
        confidence = float(getattr(result, "confidence", 0.0) or 0.0)
    elif hasattr(engine, "read_text"):
        raw_text, confidence = engine.read_text(frame_path)
    else:
        raise TypeError(f"Unsupported OCR engine: {engine!r}")

    candidate_text = station_name or raw_text
    if matcher is not None and candidate_text:
        match = matcher.match(candidate_text)
        if match.matched:
            station_name = match.station_name
            confidence = max(confidence, match.confidence)

    if not raw_text and not station_name:
        return None

    return OcrObservation(
        video_id=video_id,
        video_time_ms=video_time_ms,
        raw_text=raw_text or station_name or "",
        station_name=station_name,
        confidence=round(max(0.0, min(1.0, confidence)), 4),
        method=method,
    )


def _build_section_mappings(
    ocr_observations: list[OcrObservation],
    *,
    metadata_items: list[VideoMetadata],
    sample_interval_ms: int,
) -> list[SectionMapping]:
    duration_by_video = {item.video_id: item.duration_ms for item in metadata_items}
    sections: list[SectionMapping] = []
    by_video: dict[int, list[OcrObservation]] = {}
    for observation in ocr_observations:
        if observation.station_name:
            by_video.setdefault(observation.video_id, []).append(observation)

    for video_id, observations in by_video.items():
        unique = _deduplicate_station_observations(observations)
        if len(unique) == 1:
            only = unique[0]
            end_time_ms = duration_by_video.get(video_id, 0) or only.video_time_ms + sample_interval_ms
            sections.append(
                SectionMapping(
                    video_id=video_id,
                    start_time_ms=only.video_time_ms,
                    end_time_ms=max(end_time_ms, only.video_time_ms + sample_interval_ms),
                    section_start=only.station_name or "구간 미확인",
                    section_end="구간 미확인",
                    confidence=only.confidence,
                )
            )
            continue

        for current, next_item in zip(unique, unique[1:], strict=False):
            if next_item.video_time_ms <= current.video_time_ms:
                continue
            sections.append(
                SectionMapping(
                    video_id=video_id,
                    start_time_ms=current.video_time_ms,
                    end_time_ms=next_item.video_time_ms,
                    section_start=current.station_name or "구간 미확인",
                    section_end=next_item.station_name or "구간 미확인",
                    confidence=round(min(current.confidence, next_item.confidence), 4),
                )
            )
    return sections


def _deduplicate_station_observations(
    observations: list[OcrObservation],
) -> list[OcrObservation]:
    unique: list[OcrObservation] = []
    for observation in sorted(observations, key=lambda item: item.video_time_ms):
        if unique and unique[-1].station_name == observation.station_name:
            if observation.confidence > unique[-1].confidence:
                unique[-1] = observation
            continue
        unique.append(observation)
    return unique


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
        "ocr_backend": config.ocr_backend,
        "ocr_interval_s": config.ocr_interval_s,
        "station_dictionary_path": str(config.station_dictionary_path)
        if config.station_dictionary_path
        else None,
    }


def _has_wildcard(path: Path) -> bool:
    return any(char in str(path) for char in "*?[")


def _is_video(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
