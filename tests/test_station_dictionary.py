from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from korail_program.ocr.station_dictionary import load_station_names


class StationDictionaryTests(unittest.TestCase):
    def test_load_text_dictionary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "stations.txt"
            path.write_text("# comment\n일로역\n몽탄역\n", encoding="utf-8")

            self.assertEqual(load_station_names(path), ["일로역", "몽탄역"])

    def test_load_csv_dictionary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "stations.csv"
            path.write_text("station_name,route\n일로역,호남선\n몽탄역,호남선\n", encoding="utf-8")

            self.assertEqual(load_station_names(path), ["일로역", "몽탄역"])


if __name__ == "__main__":
    unittest.main()

