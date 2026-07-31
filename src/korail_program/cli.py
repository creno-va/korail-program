"""Command-line entry points for development and batch utilities."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from korail_program.analysis.batch import BatchAnalysisConfig, run_batch_analysis
from korail_program.config import (
    DEFAULT_ANALYSIS_INTERVAL_SEC,
    DEFAULT_MAX_FRAME_WIDTH,
    DEFAULT_OCR_INTERVAL_SEC,
    DEFAULT_OPENAI_API_KEY_ENV,
    DEFAULT_OPENAI_BASE_URL,
    DEFAULT_VISION_MODEL,
)
from korail_program.core.event_merger import merge_judge_observations
from korail_program.core.models import RiskLevel, SectionMapping, to_jsonable
from korail_program.db.repository import initialize_database
from korail_program.judge.schema import judge_observation_from_payload
from korail_program.runtime import resolve_ffmpeg_executable, resolve_ffprobe_executable


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="korail-analyzer")
    parser.add_argument("--version", action="store_true", help="Print package version and exit.")
    subparsers = parser.add_subparsers(dest="command")

    init_db = subparsers.add_parser("init-db", help="Create or migrate a SQLite database.")
    init_db.add_argument("database", type=Path)

    merge = subparsers.add_parser("merge-events", help="Merge judge and section JSON files.")
    merge.add_argument("--judge-json", required=True, type=Path)
    merge.add_argument("--sections-json", required=True, type=Path)
    merge.add_argument("--out", type=Path)
    merge.add_argument("--sample-interval-ms", type=int, default=1000)
    merge.add_argument("--gap-tolerance-ms", type=int, default=1500)
    merge.add_argument("--min-event-duration-ms", type=int, default=2000)

    analyze = subparsers.add_parser(
        "analyze-videos",
        help="Sample videos, judge frames with GPT vision, and write a report.",
    )
    analyze.add_argument(
        "inputs",
        nargs="*",
        type=Path,
        help="Video files, directories, or simple glob paths. Defaults to the current directory.",
    )
    analyze.add_argument("--out", type=Path, default=Path("output") / "analysis")
    analyze.add_argument("--interval-sec", type=float, default=DEFAULT_ANALYSIS_INTERVAL_SEC)
    analyze.add_argument(
        "--model", default=os.environ.get("KORAIL_VISION_MODEL", DEFAULT_VISION_MODEL)
    )
    analyze.add_argument(
        "--openai-base-url",
        default=os.environ.get("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE_URL),
    )
    analyze.add_argument(
        "--openai-api-key-env",
        default=os.environ.get("KORAIL_OPENAI_API_KEY_ENV", DEFAULT_OPENAI_API_KEY_ENV),
        help="Environment variable that contains the OpenAI API key.",
    )
    analyze.add_argument("--route-hint")
    analyze.add_argument(
        "--ffmpeg", default=os.environ.get("FFMPEG_PATH") or str(resolve_ffmpeg_executable())
    )
    analyze.add_argument(
        "--ffprobe", default=os.environ.get("FFPROBE_PATH") or str(resolve_ffprobe_executable())
    )
    analyze.add_argument("--max-width", type=int, default=DEFAULT_MAX_FRAME_WIDTH)
    analyze.add_argument(
        "--ocr-backend",
        choices=["vlm", "auto", "paddle", "none"],
        default=os.environ.get("KORAIL_OCR_BACKEND", "vlm"),
        help=(
            "Station OCR backend. 'vlm' uses the configured GPT vision API "
            "and needs no OCR package."
        ),
    )
    analyze.add_argument(
        "--ocr-interval-sec",
        type=float,
        default=float(os.environ.get("KORAIL_OCR_INTERVAL_SEC", str(DEFAULT_OCR_INTERVAL_SEC))),
        help="Sampling interval for station OCR. Use 0 to disable OCR.",
    )
    analyze.add_argument(
        "--station-dictionary",
        type=Path,
        default=os.environ.get("KORAIL_STATION_DICTIONARY"),
        help="Optional station-name text/CSV dictionary for OCR correction.",
    )
    analyze.add_argument(
        "--min-report-risk",
        choices=["low", "medium", "high", "낮음", "중간", "높음"],
        default="낮음",
        help="Minimum risk level to copy into captures and reports.",
    )
    analyze.add_argument("--recursive", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    from korail_program.env import load_default_env_files

    load_default_env_files()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        from korail_program import __version__

        print(__version__)
        return 0

    if args.command == "init-db":
        initialize_database(args.database)
        print(f"Initialized database: {args.database}")
        return 0

    if args.command == "merge-events":
        return _merge_events(args)

    if args.command == "analyze-videos":
        return _analyze_videos(args)

    parser.print_help()
    return 0


def _merge_events(args: argparse.Namespace) -> int:
    judge_payloads = json.loads(args.judge_json.read_text(encoding="utf-8"))
    section_payloads = json.loads(args.sections_json.read_text(encoding="utf-8"))
    if not isinstance(judge_payloads, list):
        raise SystemExit("--judge-json must contain a JSON array")
    if not isinstance(section_payloads, list):
        raise SystemExit("--sections-json must contain a JSON array")

    observations = [
        judge_observation_from_payload(
            video_id=int(item["video_id"]),
            video_time_ms=int(item["video_time_ms"]),
            payload=item.get("payload", item),
        )
        for item in judge_payloads
    ]
    sections = [
        SectionMapping(
            video_id=int(item["video_id"]),
            start_time_ms=int(item["start_time_ms"]),
            end_time_ms=int(item["end_time_ms"]),
            section_start=str(item["section_start"]),
            section_end=str(item["section_end"]),
            confidence=float(item.get("confidence", 1.0)),
        )
        for item in section_payloads
    ]
    events = merge_judge_observations(
        observations,
        sections,
        sample_interval_ms=args.sample_interval_ms,
        gap_tolerance_ms=args.gap_tolerance_ms,
        min_event_duration_ms=args.min_event_duration_ms,
    )
    output_text = json.dumps(to_jsonable(events), ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(output_text + "\n", encoding="utf-8")
        print(f"Wrote {len(events)} events: {args.out}")
    else:
        print(output_text, file=sys.stdout)
    return 0


def _analyze_videos(args: argparse.Namespace) -> int:
    result = run_batch_analysis(
        BatchAnalysisConfig(
            inputs=args.inputs or [Path.cwd()],
            output_dir=args.out,
            interval_s=args.interval_sec,
            model=args.model,
            openai_base_url=args.openai_base_url,
            openai_api_key_env=args.openai_api_key_env,
            route_hint=args.route_hint,
            ffmpeg_path=args.ffmpeg,
            ffprobe_path=args.ffprobe,
            max_width=args.max_width,
            min_report_risk=RiskLevel.coerce(args.min_report_risk),
            recursive=args.recursive,
            ocr_backend=args.ocr_backend,
            ocr_interval_s=args.ocr_interval_sec if args.ocr_interval_sec > 0 else None,
            station_dictionary_path=args.station_dictionary,
        )
    )
    print(f"Videos: {result.video_count}")
    print(f"Sampled frames: {result.sampled_frame_count}")
    print(f"Suspicious captures: {result.suspicious_frame_count}")
    print(f"OCR observations: {result.ocr_observation_count}")
    print(f"Events: {result.event_count}")
    if result.failure_count:
        print(f"Failures: {result.failure_count}", file=sys.stderr)
    print(f"Report HTML: {result.report_html}")
    print(f"Report Markdown: {result.report_markdown}")
    print(f"Report PDF: {result.report_pdf}")
    print(f"Observations JSON: {result.observations_json}")
    print(f"Events JSON: {result.events_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
