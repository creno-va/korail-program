from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from korail_program.analysis.batch import (
    AnalysisCancelled,
    BatchAnalysisConfig,
    run_batch_analysis,
)


class BatchAnalysisTests(unittest.TestCase):
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
