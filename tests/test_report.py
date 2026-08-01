from __future__ import annotations

import base64
import importlib.util
import tempfile
import unittest
from pathlib import Path

from korail_program.analysis.pdf_report import _normalize_pdf_text
from korail_program.analysis.report import build_html_report, build_markdown_report, write_reports
from korail_program.core.models import AnalysisEvent, JudgeObservation, RiskLevel


class ReportTests(unittest.TestCase):
    def test_pdf_text_normalizer_repairs_utf8_mojibake(self) -> None:
        mojibake = "서울_대전.mp4".encode().decode("latin-1")
        self.assertEqual(_normalize_pdf_text(mojibake), "서울_대전.mp4")

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
    def test_pdf_report_uses_template_layout_with_two_frames_per_page(self) -> None:
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
            for index, time_ms in enumerate((12_000, 24_000, 28_000), start=1)
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = Path(tmp_dir)
            records: list[dict[str, object]] = []
            for index, observation in enumerate(observations, start=1):
                capture = output_dir / f"capture_{index}.png"
                capture.write_bytes(image_bytes)
                records.append(
                    {
                        "video_name": "서울_대전_선로점검.mp4",
                        "frame_path": str(capture),
                        "capture_path": str(capture),
                        "observation": observation,
                    }
                )

            _, _, pdf_path = write_reports(
                output_dir=output_dir,
                video_count=1,
                sampled_frame_count=3,
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
                        source_observation_count=3,
                        capture_count=3,
                    )
                ],
                failures=[],
                video_titles=["서울_대전_선로점검.mp4"],
            )

            self.assertTrue(pdf_path.exists())
            reader = PdfReader(str(pdf_path))
            self.assertEqual(len(reader.pages), 2)
            extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)
            first_page_text = reader.pages[0].extract_text() or ""
            self.assertEqual(reader.metadata.title, "전차선로 지장수목 분석 REPORT")
            self.assertIn("서울_대전_선로점검.mp4", extracted_text)
            self.assertIn("분석현황", extracted_text)
            self.assertIn("분석사진", extracted_text)
            self.assertIn("분석일시", extracted_text)
            self.assertIn("분석영상", extracted_text)
            self.assertIn("OCR 추정 구간", extracted_text)
            self.assertIn("서울 - 대전", extracted_text)
            self.assertIn("프레임 1 판단 근거", first_page_text)
            self.assertIn("프레임 2 판단 근거", first_page_text)
            self.assertNotIn("촬영날짜", extracted_text)
            self.assertNotIn("위치", extracted_text)


if __name__ == "__main__":
    unittest.main()
