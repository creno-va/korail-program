from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from korail_program.core.video_files import discover_video_files, is_supported_video


class VideoFileTests(unittest.TestCase):
    def test_discovery_respects_recursive_option_and_extension_case(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            first = root / "first.mp4"
            nested_dir = root / "nested"
            second = nested_dir / "second.MOV"
            ignored = nested_dir / "notes.txt"
            nested_dir.mkdir()
            first.write_bytes(b"")
            second.write_bytes(b"")
            ignored.write_text("skip", encoding="utf-8")

            self.assertEqual(discover_video_files([root]), [first.resolve()])
            self.assertEqual(
                discover_video_files([root], recursive=True),
                sorted([first.resolve(), second.resolve()]),
            )
            self.assertTrue(is_supported_video(second))
            self.assertFalse(is_supported_video(ignored))


if __name__ == "__main__":
    unittest.main()
