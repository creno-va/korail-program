from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from korail_program.env import load_env_file


class EnvTests(unittest.TestCase):
    def test_load_env_file_without_overwriting_existing_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / ".env"
            env_path.write_text(
                "OPENAI_API_KEY='from-file'\nKORAIL_TEST_ENV=value\n",
                encoding="utf-8",
            )
            previous_key = os.environ.get("OPENAI_API_KEY")
            os.environ["OPENAI_API_KEY"] = "from-env"
            try:
                load_env_file(env_path)

                self.assertEqual(os.environ["OPENAI_API_KEY"], "from-env")
                self.assertEqual(os.environ["KORAIL_TEST_ENV"], "value")
            finally:
                if previous_key is None:
                    os.environ.pop("OPENAI_API_KEY", None)
                else:
                    os.environ["OPENAI_API_KEY"] = previous_key
                os.environ.pop("KORAIL_TEST_ENV", None)


if __name__ == "__main__":
    unittest.main()
