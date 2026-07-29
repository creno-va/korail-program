from __future__ import annotations

from pathlib import Path
import unittest

from korail_program.core.frame_extractor import FrameExtractionConfig, build_ffmpeg_frame_command


class FrameExtractorTests(unittest.TestCase):
    def test_build_ffmpeg_frame_command(self) -> None:
        command = build_ffmpeg_frame_command(
            FrameExtractionConfig(
                input_path=Path("input.mp4"),
                output_dir=Path("frames"),
                fps=1.0,
                prefix="judge",
                start_time_ms=1000,
                end_time_ms=4000,
            ),
            ffmpeg_path="ffmpeg.exe",
        )

        self.assertEqual(command[0], "ffmpeg.exe")
        self.assertIn("-ss", command)
        self.assertIn("1.000", command)
        self.assertIn("-t", command)
        self.assertIn("3.000", command)
        self.assertEqual(command[-1], str(Path("frames") / "judge_%08d.jpg"))


if __name__ == "__main__":
    unittest.main()

