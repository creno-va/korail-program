from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from korail_program.app.main_window import _video_candidates


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


if __name__ == "__main__":
    unittest.main()
