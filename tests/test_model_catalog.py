from __future__ import annotations

import unittest

from korail_program.model_catalog import SystemProfile, recommend_model, system_profile_label


class ModelCatalogTests(unittest.TestCase):
    def test_recommends_8b_for_16gb_ram_and_8gb_vram(self) -> None:
        option = recommend_model(SystemProfile(ram_gb=16, gpu_name="RTX 2070", gpu_vram_gb=8))

        self.assertEqual(option.tag, "qwen3-vl:8b")

    def test_recommends_4b_for_midrange_memory(self) -> None:
        option = recommend_model(SystemProfile(ram_gb=12, gpu_name="GTX", gpu_vram_gb=4))

        self.assertEqual(option.tag, "qwen3-vl:4b")

    def test_recommends_3b_for_low_memory(self) -> None:
        option = recommend_model(SystemProfile(ram_gb=8, gpu_name=None, gpu_vram_gb=None))

        self.assertEqual(option.tag, "qwen2.5vl:3b")

    def test_system_profile_label(self) -> None:
        label = system_profile_label(SystemProfile(ram_gb=16, gpu_name="RTX", gpu_vram_gb=8))

        self.assertIn("RAM 16GB", label)
        self.assertIn("RTX", label)


if __name__ == "__main__":
    unittest.main()
