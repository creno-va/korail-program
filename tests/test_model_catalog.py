from __future__ import annotations

import unittest

from korail_program.model_catalog import SystemProfile, recommend_model, system_profile_label


class ModelCatalogTests(unittest.TestCase):
    def test_recommends_default_gpt_model_for_high_spec_machine(self) -> None:
        option = recommend_model(SystemProfile(ram_gb=16, gpu_name="RTX 2070", gpu_vram_gb=8))

        self.assertEqual(option.tag, "gpt-5.6-terra")

    def test_recommends_default_gpt_model_for_low_spec_machine(self) -> None:
        option = recommend_model(SystemProfile(ram_gb=8, gpu_name=None, gpu_vram_gb=None))

        self.assertEqual(option.tag, "gpt-5.6-terra")

    def test_system_profile_label(self) -> None:
        label = system_profile_label(SystemProfile(ram_gb=16, gpu_name="RTX", gpu_vram_gb=8))

        self.assertIn("RAM 16GB", label)
        self.assertIn("RTX", label)


if __name__ == "__main__":
    unittest.main()
