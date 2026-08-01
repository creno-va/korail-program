from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QMimeData, QUrl
from PySide6.QtWidgets import QApplication, QLabel

from korail_program.app.main_window import MainWindow, _build_frame_entries
from korail_program.app.pdf_viewer import PdfViewerDialog
from korail_program.core.video_files import collect_video_candidates


class AppVideoCandidateTests(unittest.TestCase):
    def test_pdf_viewer_loads_multi_page_report(self) -> None:
        from reportlab.pdfgen import canvas
        from shiboken6 import delete

        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "preview.pdf"
            document = canvas.Canvas(str(pdf_path))
            document.drawString(72, 720, "page 1")
            document.showPage()
            document.drawString(72, 720, "page 2")
            document.showPage()
            document.save()

            viewer = PdfViewerDialog(pdf_path)
            try:
                self.assertEqual(viewer.document.pageCount(), 2)
                self.assertEqual(viewer.page_count_label.text(), "2페이지")
            finally:
                viewer.reject()
                delete(viewer)
                app.processEvents()

    def test_saved_pdf_opens_in_app_viewer(self) -> None:
        app = QApplication.instance() or QApplication([])

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = root / "source.pdf"
            target = root / "saved-report.pdf"
            source.write_bytes(b"test-pdf")
            window = MainWindow()
            window._last_result = mock.Mock(report_pdf=source)
            try:
                with (
                    mock.patch.object(
                        window,
                        "_log",
                    ),
                    mock.patch(
                        "korail_program.app.main_window.QFileDialog.getSaveFileName",
                        return_value=(str(target), "PDF Files (*.pdf)"),
                    ),
                    mock.patch(
                        "korail_program.app.main_window.PdfViewerDialog"
                    ) as viewer_type,
                ):
                    window.save_pdf_report()

                self.assertEqual(target.read_bytes(), b"test-pdf")
                viewer_type.assert_called_once_with(target, parent=window)
                viewer_type.return_value.exec.assert_called_once_with()
            finally:
                window.close()
                app.processEvents()

    def test_window_accepts_video_drop_from_any_page(self) -> None:
        app = QApplication.instance() or QApplication([])

        with tempfile.TemporaryDirectory() as tmp_dir:
            video_path = Path(tmp_dir) / "window-drop.mp4"
            video_path.write_bytes(b"")
            mime_data = QMimeData()
            mime_data.setUrls([QUrl.fromLocalFile(str(video_path))])
            event = mock.Mock()
            event.mimeData.return_value = mime_data

            window = MainWindow()
            try:
                self.assertTrue(window.acceptDrops())
                with mock.patch.object(window, "add_video_files") as add_video_files:
                    window.dropEvent(event)

                add_video_files.assert_called_once_with([video_path])
                event.acceptProposedAction.assert_called_once_with()
            finally:
                window.close()
                app.processEvents()

    def test_home_stepper_and_detail_navigation_share_analysis_state(self) -> None:
        app = QApplication.instance() or QApplication([])

        with tempfile.TemporaryDirectory() as tmp_dir:
            video_path = Path(tmp_dir) / "stepper-sample.mp4"
            video_path.write_bytes(b"")
            window = MainWindow()
            try:
                self.assertIs(window.page_stack.currentWidget(), window.home_page)
                self.assertEqual(window.home_page.upload_button.text(), "영상 업로드")
                self.assertEqual(window.home_page.analysis_button.text(), "분석")
                self.assertEqual(window.home_page.report_button.text(), "보고서")
                self.assertEqual(
                    window.home_page.findChild(QLabel, "HomeTitle").text(),
                    "전차선로 지장수목 분석",
                )
                self.assertFalse(window.home_page.korail_logo.pixmap().isNull())
                self.assertFalse(window.home_page.crenova_logo.pixmap().isNull())
                self.assertEqual(
                    window.home_page.findChild(QLabel, "HomeBrandingSeparator").text(),
                    "×",
                )
                self.assertTrue(
                    window.home_page._step_frames[0].isAncestorOf(
                        window.home_page.selected_file_label
                    )
                )
                self.assertFalse(window.home_page.analysis_button.isEnabled())
                self.assertEqual(
                    window.home_page._step_frames[0].property("stepState"), "active"
                )

                with mock.patch.object(window.video_player, "set_video"):
                    window.add_video_files([video_path])

                self.assertEqual(window.home_page.selected_file_label.text(), video_path.name)
                self.assertTrue(window.home_page.analysis_button.isEnabled())
                self.assertEqual(
                    window.home_page._step_frames[1].property("stepState"), "active"
                )

                window._set_analysis_progress(37, "primary")
                self.assertEqual(window.progress.value(), 37)
                self.assertEqual(window.home_page.progress.value(), 37)

                window._show_detail_page()
                self.assertIs(window.page_stack.currentWidget(), window.detail_page)
                window._show_home_page()
                self.assertIs(window.page_stack.currentWidget(), window.home_page)

                window._last_result = mock.Mock()
                window._sync_primary_actions()
                self.assertTrue(window.home_page.report_button.isEnabled())
                self.assertEqual(
                    window.home_page._step_frames[2].property("stepState"), "active"
                )
            finally:
                window.close()
                app.processEvents()

    def test_result_sidebar_keeps_each_suspicious_capture(self) -> None:
        events = [
            {
                "video_id": 1,
                "start_time_ms": 10_000,
                "end_time_ms": 40_000,
                "risk_level": "높음",
                "summary": "이벤트 요약",
            }
        ]
        records = [
            {
                "capture_path": f"capture-{index}.jpg",
                "observation": {
                    "video_id": 1,
                    "video_time_ms": video_time_ms,
                    "risk_level": "높음",
                    "evidence": f"프레임 {index}",
                },
            }
            for index, video_time_ms in enumerate((15_000, 30_000), start=1)
        ]

        entries = _build_frame_entries(events, records)

        self.assertEqual(len(entries), 2)
        self.assertEqual([item[0]["frame_time_ms"] for item in entries], [15_000, 30_000])
        self.assertEqual([item[0]["summary"] for item in entries], ["프레임 1", "프레임 2"])

    def test_collects_multiple_files_and_folder_contents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            first = root / "first.mp4"
            second = root / "second.mov"
            ignored = root / "notes.txt"
            nested = root / "nested"
            first.write_bytes(b"")
            second.write_bytes(b"")
            ignored.write_text("skip", encoding="utf-8")
            nested.mkdir()

            candidates, skipped = collect_video_candidates([first, root, ignored, nested])
            expected = sorted({first.resolve(), second.resolve()})

        self.assertEqual(candidates, expected)
        self.assertEqual(skipped, 2)

    def test_sidebar_selection_updates_one_video_detail_view(self) -> None:
        app = QApplication.instance() or QApplication([])

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            first = root / "first.mp4"
            second = root / "second.mp4"
            first.write_bytes(b"")
            second.write_bytes(b"")

            window = MainWindow()
            try:
                with mock.patch.object(window.video_player, "set_video") as set_video:
                    window.add_video_files([first, second])
                first_path = first.resolve()
                second_path = second.resolve()

                self.assertEqual(window._selected_video_path, first_path)
                self.assertEqual(set(window.analysis_list.selected_keys()), {first_path})
                set_video.assert_called_once_with(first_path)

                with mock.patch.object(window.video_player, "set_video") as set_video:
                    window.analysis_list.select_key(second_path)

                self.assertEqual(window._selected_video_path, second_path)
                self.assertEqual(set(window.analysis_list.selected_keys()), {second_path})
                set_video.assert_called_once_with(second_path)
                self.assertEqual(window.selected_video_title.text(), second.name)

                window._pending_analysis_path = second_path
                window._sync_primary_actions()

                self.assertFalse(window.analysis_button.isEnabled())
                self.assertEqual(window.analysis_button.text(), "준비 중")
            finally:
                window.close()
                app.processEvents()

    def test_selecting_result_frame_seeks_video_and_updates_detail(self) -> None:
        app = QApplication.instance() or QApplication([])

        with tempfile.TemporaryDirectory() as tmp_dir:
            video_path = Path(tmp_dir) / "sample.mp4"
            video_path.write_bytes(b"")
            window = MainWindow()
            try:
                with mock.patch.object(window.video_player, "set_video"):
                    window.add_video_files([video_path])
                window._event_payloads[1] = {
                    "video_id": 1,
                    "start_time_ms": 15_000,
                    "end_time_ms": 30_000,
                    "section_start": "서울",
                    "section_end": "대전",
                    "risk_level": "높음",
                    "summary": "전차선 인접 수목 확인",
                }

                with mock.patch.object(window.video_player, "seek") as seek:
                    window._update_inspector_from_event(1)

                seek.assert_called_once_with(15_000)
                self.assertEqual(window.detail_labels["위험도"].text(), "높음")
                self.assertIn("전차선 인접 수목", window.evidence_panel.label.text())
            finally:
                window.close()
                app.processEvents()

    def test_analysis_action_switches_between_start_and_stop(self) -> None:
        app = QApplication.instance() or QApplication([])

        with tempfile.TemporaryDirectory() as tmp_dir:
            video_path = Path(tmp_dir) / "sample.mp4"
            video_path.write_bytes(b"")
            window = MainWindow()
            try:
                with mock.patch.object(window.video_player, "set_video"):
                    window.add_video_files([video_path])
                resolved_path = video_path.resolve()

                self.assertEqual(window.analysis_button.text(), "분석 시작")
                self.assertTrue(window.analysis_button.isEnabled())

                worker = mock.Mock()
                worker.isInterruptionRequested.return_value = False
                window._analysis_workers[resolved_path] = worker
                window._sync_primary_actions()

                self.assertEqual(window.analysis_button.text(), "분석 정지")
                self.assertTrue(window.analysis_button.isEnabled())
                with mock.patch.object(window, "_stop_video_analysis") as stop_analysis:
                    window._toggle_selected_analysis()
                stop_analysis.assert_called_once_with(resolved_path)

                worker.isInterruptionRequested.return_value = True
                window._sync_primary_actions()
                self.assertEqual(window.analysis_button.text(), "중지 중")
                self.assertFalse(window.analysis_button.isEnabled())
            finally:
                window._analysis_workers.clear()
                window.close()
                app.processEvents()


if __name__ == "__main__":
    unittest.main()
