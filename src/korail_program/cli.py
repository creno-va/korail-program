"""Command-line entry points for development and batch utilities."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from korail_program.core.event_merger import merge_judge_observations
from korail_program.core.models import SectionMapping, to_jsonable
from korail_program.db.repository import initialize_database
from korail_program.judge.schema import judge_observation_from_payload

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

    return parser


def main(argv: list[str] | None = None) -> int:
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


if __name__ == "__main__":
    raise SystemExit(main())
