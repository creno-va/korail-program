from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from korail_program.env import load_env_file


class EnvTests(unittest.TestCase):
    def test_load_env_file_without_overwriting_existing_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / ".env"
            env_path.write_text(
                "KORAIL_EXISTING='from-file'\nKORAIL_TEST_ENV=value\n",
                encoding="utf-8",
            )
            previous_value = os.environ.get("KORAIL_EXISTING")
            os.environ["KORAIL_EXISTING"] = "from-env"
            try:
                load_env_file(env_path)

                self.assertEqual(os.environ["KORAIL_EXISTING"], "from-env")
                self.assertEqual(os.environ["KORAIL_TEST_ENV"], "value")
            finally:
                if previous_value is None:
                    os.environ.pop("KORAIL_EXISTING", None)
                else:
                    os.environ["KORAIL_EXISTING"] = previous_value
                os.environ.pop("KORAIL_TEST_ENV", None)


if __name__ == "__main__":
    unittest.main()
