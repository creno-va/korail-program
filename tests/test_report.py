from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from korail_program.analysis.report import build_html_report, build_markdown_report
from korail_program.core.models import JudgeObservation, RiskLevel


class ReportTests(unittest.TestCase):
    def test_reports_show_risk_level_without_probability_score(self) -> None:
        observation = JudgeObservation(
            video_id=1,
            video_time_ms=12000,
            has_tree=True,
            bamboo_likely=0.87,
            near_catenary=True,
            risk_level=RiskLevel.HIGH,
            bbox_hint=None,
            evidence="전차선 가까이에 가지가 보임",
            needs_human_review=False,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            capture = output_dir / "capture.jpg"
            capture.write_bytes(b"")
            records = [
                {
                    "video_name": "sample.mp4",
                    "frame_path": str(capture),
                    "capture_path": str(capture),
                    "observation": observation,
                }
            ]

            markdown = build_markdown_report(
                video_count=1,
                sampled_frame_count=1,
                suspicious_records=records,
                events=[],
                failures=[],
            )
            html = build_html_report(
                video_count=1,
                sampled_frame_count=1,
                suspicious_records=records,
                events=[],
                failures=[],
                output_dir=output_dir,
            )

        self.assertIn("위험도: 높음", markdown)
        self.assertNotIn("가능성", markdown)
        self.assertNotIn("0.87", markdown)
        self.assertIn(">높음</span>", html)
        self.assertNotIn("가능성", html)
        self.assertNotIn("0.87", html)


if __name__ == "__main__":
    unittest.main()
