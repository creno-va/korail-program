from __future__ import annotations

import base64
import importlib.util
import tempfile
import unittest
from pathlib import Path

from korail_program.analysis.report import build_html_report, build_markdown_report, write_reports
from korail_program.core.models import AnalysisEvent, JudgeObservation, RiskLevel


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

    @unittest.skipUnless(
        importlib.util.find_spec("reportlab") and importlib.util.find_spec("pypdf"),
        "PDF verification dependencies are not installed",
    )
    def test_pdf_report_uses_one_page_per_suspicious_frame(self) -> None:
        from pypdf import PdfReader

        image_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
            "/x8AAusB9Wl2mQoAAAAASUVORK5CYII="
        )
        observations = [
            JudgeObservation(
                video_id=1,
                video_time_ms=time_ms,
                has_tree=True,
                bamboo_likely=0.1,
                near_catenary=True,
                risk_level=RiskLevel.HIGH,
                bbox_hint=None,
                evidence=f"프레임 {index} 판단 근거",
                needs_human_review=False,
            )
            for index, time_ms in enumerate((12_000, 24_000), start=1)
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            records: list[dict[str, object]] = []
            for index, observation in enumerate(observations, start=1):
                capture = output_dir / f"capture_{index}.png"
                capture.write_bytes(image_bytes)
                records.append(
                    {
                        "video_name": "sample.mp4",
                        "frame_path": str(capture),
                        "capture_path": str(capture),
                        "observation": observation,
                    }
                )

            _, _, pdf_path = write_reports(
                output_dir=output_dir,
                video_count=1,
                sampled_frame_count=2,
                ocr_observation_count=0,
                suspicious_records=records,
                events=[
                    AnalysisEvent(
                        video_id=1,
                        start_time_ms=0,
                        end_time_ms=30_000,
                        section_start="서울",
                        section_end="대전",
                        risk_level=RiskLevel.HIGH,
                        summary="전차선 인접 수목",
                        needs_human_review=False,
                        source_observation_count=2,
                        capture_count=2,
                    )
                ],
                failures=[],
            )

            self.assertTrue(pdf_path.exists())
            self.assertEqual(len(PdfReader(str(pdf_path)).pages), len(records))


if __name__ == "__main__":
    unittest.main()
