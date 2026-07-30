from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from korail_program.app.main_window import MainWindow, _video_candidates


class AppVideoCandidateTests(unittest.TestCase):
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

            candidates, skipped = _video_candidates([first, root, ignored, nested])
            expected = sorted({first.resolve(), second.resolve()})

        self.assertEqual(candidates, expected)
        self.assertEqual(skipped, 2)

    def test_analysis_log_keeps_one_selected_video(self) -> None:
        app = QApplication.instance() or QApplication([])

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            first = root / "first.mp4"
            second = root / "second.mp4"
            first.write_bytes(b"")
            second.write_bytes(b"")

            window = MainWindow()
            try:
                window.add_video_files([first, second])
                first_path = first.resolve()
                second_path = second.resolve()

                self.assertEqual(window._selected_video_path, first_path)
                self.assertEqual(set(window.analysis_list.selected_keys()), {first_path})

                window.analysis_list.select_key(second_path)

                self.assertEqual(window._selected_video_path, second_path)
                self.assertEqual(set(window.analysis_list.selected_keys()), {second_path})

                window._pending_analysis_path = second_path
                window._sync_primary_actions()

                self.assertFalse(window.start_button.isEnabled())
                self.assertFalse(window._analysis_cards[first_path].run_button.isEnabled())
            finally:
                window.close()
                app.processEvents()


if __name__ == "__main__":
    unittest.main()
