from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from korail_program.analysis.batch import (
    AnalysisCancelled,
    BatchAnalysisConfig,
    _build_section_mappings,
    _read_station_observation,
    run_batch_analysis,
)
from korail_program.core.models import OcrObservation, VideoMetadata


class BatchAnalysisTests(unittest.TestCase):
    def test_station_name_falls_back_to_visible_raw_ocr_text(self) -> None:
        engine = Mock(method="vlm")
        engine.read_station_text.return_value = SimpleNamespace(
            raw_text="서울역 1번 출구",
            station_name=None,
            confidence=0.4,
        )

        observation = _read_station_observation(
            engine=engine,
            matcher=None,
            frame_path=Path("sample.jpg"),
            video_id=1,
            video_time_ms=20_000,
            route_hint=None,
        )

        self.assertIsNotNone(observation)
        assert observation is not None
        self.assertEqual(observation.station_name, "서울역")
        self.assertEqual(observation.confidence, 0.5)

    def test_section_mapping_covers_complete_video_timeline(self) -> None:
        observations = [
            OcrObservation(1, 10_000, "서울역", "서울역", 0.8),
            OcrObservation(1, 20_000, "서울 역", "서울역", 0.95),
            OcrObservation(1, 50_000, "대전역", "대전역", 0.9),
        ]
        metadata = [VideoMetadata(1, "sample.mp4", 100_000, 1920, 1080, 30.0)]

        sections = _build_section_mappings(
            observations,
            metadata_items=metadata,
            sample_interval_ms=10_000,
        )

        self.assertEqual(
            [
                (
                    item.start_time_ms,
                    item.end_time_ms,
                    item.section_start,
                    item.section_end,
                )
                for item in sections
            ],
            [
                (0, 10_000, "서울역", "서울역"),
                (10_000, 50_000, "서울역", "대전역"),
                (50_000, 100_000, "대전역", "대전역"),
            ],
        )

    def test_single_station_marks_whole_video_as_station_vicinity(self) -> None:
        observations = [OcrObservation(1, 20_000, "서울역", "서울역", 0.9)]
        metadata = [VideoMetadata(1, "sample.mp4", 100_000, 1920, 1080, 30.0)]

        sections = _build_section_mappings(
            observations,
            metadata_items=metadata,
            sample_interval_ms=10_000,
        )

        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0].start_time_ms, 0)
        self.assertEqual(sections[0].end_time_ms, 100_000)
        self.assertEqual(sections[0].section_start, "서울역")
        self.assertEqual(sections[0].section_end, "서울역")

    def test_cancellation_is_not_recorded_as_a_frame_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            video_path = root / "sample.mp4"
            frame_path = root / "sample.jpg"
            video_path.write_bytes(b"")
            frame_path.write_bytes(b"")
            cancel_callback = Mock(side_effect=[False, False, True])

            config = BatchAnalysisConfig(
                inputs=[video_path],
                output_dir=root / "output",
                ocr_backend="none",
                cancel_callback=cancel_callback,
            )

            with (
                patch(
                    "korail_program.analysis.batch.extract_frames",
                    return_value=[frame_path],
                ),
                self.assertRaises(AnalysisCancelled),
            ):
                run_batch_analysis(config)


if __name__ == "__main__":
    unittest.main()
