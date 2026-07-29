from __future__ import annotations

import json
import unittest

from korail_program.core.video_probe import parse_ffprobe_json


class VideoProbeTests(unittest.TestCase):
    def test_parse_ffprobe_json(self) -> None:
        metadata = parse_ffprobe_json(
            json.dumps(
                {
                    "streams": [
                        {
                            "codec_type": "video",
                            "width": 1920,
                            "height": 1080,
                            "duration": "12.5",
                            "avg_frame_rate": "30000/1001",
                        }
                    ],
                    "format": {"duration": "12.5"},
                }
            ),
            file_path="sample.mp4",
            video_id=7,
        )

        self.assertEqual(metadata.video_id, 7)
        self.assertEqual(metadata.duration_ms, 12500)
        self.assertEqual(metadata.width, 1920)
        self.assertAlmostEqual(metadata.fps, 29.97, places=2)


if __name__ == "__main__":
    unittest.main()

