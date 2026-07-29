from __future__ import annotations

import unittest

from korail_program.ocr.station_matcher import StationMatcher, normalize_station_text


class StationMatcherTests(unittest.TestCase):
    def test_normalize_station_text(self) -> None:
        self.assertEqual(normalize_station_text(" 몽 탄 역 "), "몽탄역")

    def test_exact_match_without_station_suffix(self) -> None:
        matcher = StationMatcher(["일로역", "몽탄역", "무안역"])
        match = matcher.match("몽탄")
        self.assertTrue(match.matched)
        self.assertEqual(match.station_name, "몽탄역")

    def test_fuzzy_match(self) -> None:
        matcher = StationMatcher(["일로역", "몽탄역", "무안역"])
        match = matcher.match("몽단역")
        self.assertTrue(match.matched)
        self.assertEqual(match.station_name, "몽탄역")

    def test_no_match(self) -> None:
        matcher = StationMatcher(["일로역", "몽탄역", "무안역"])
        match = matcher.match("서울역")
        self.assertFalse(match.matched)


if __name__ == "__main__":
    unittest.main()

