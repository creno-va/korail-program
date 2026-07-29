from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from korail_program.db.repository import AnalysisRepository, connect


class RepositoryTests(unittest.TestCase):
    def test_create_schema_and_upsert_video(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            database_path = Path(tmp_dir) / "analysis.sqlite"
            connection = connect(database_path)
            try:
                repository = AnalysisRepository(connection)
                repository.create_schema()
                video_id = repository.upsert_video(
                    file_path="sample.mp4",
                    duration_ms=1000,
                    width=1920,
                    height=1080,
                    fps=30,
                )

                row = connection.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
            finally:
                connection.close()

        self.assertEqual(row["file_path"], "sample.mp4")
        self.assertEqual(row["duration_ms"], 1000)


if __name__ == "__main__":
    unittest.main()
