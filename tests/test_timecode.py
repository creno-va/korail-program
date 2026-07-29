from __future__ import annotations

import unittest

from korail_program.core.timecode import format_timecode, parse_timecode


class TimecodeTests(unittest.TestCase):
    def test_format_timecode_without_milliseconds(self) -> None:
        self.assertEqual(format_timecode(754000), "00:12:34")

    def test_format_timecode_with_milliseconds(self) -> None:
        self.assertEqual(format_timecode(754321, include_ms=True), "00:12:34.321")

    def test_parse_timecode(self) -> None:
        self.assertEqual(parse_timecode("00:12:34.321"), 754321)
        self.assertEqual(parse_timecode("12:34"), 754000)


if __name__ == "__main__":
    unittest.main()

