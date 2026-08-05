from __future__ import annotations

import unittest

from korail_program.model_catalog import (
    SystemProfile,
    ordered_model_options,
    recommend_model,
    system_profile_details,
    system_profile_label,
)


class ModelCatalogTests(unittest.TestCase):
    def test_recommends_8b_for_16gb_ram_and_8gb_vram(self) -> None:
        profile = SystemProfile(ram_gb=16, gpu_name="RTX 2070", gpu_vram_gb=8)

        self.assertEqual(recommend_model(profile).tag, "qwen3-vl:8b")

    def test_recommends_4b_for_midrange_memory(self) -> None:
        profile = SystemProfile(ram_gb=12, gpu_name="RTX", gpu_vram_gb=6)

        self.assertEqual(recommend_model(profile).tag, "qwen3-vl:4b")

    def test_recommends_2b_for_low_memory(self) -> None:
        profile = SystemProfile(ram_gb=8, gpu_name=None, gpu_vram_gb=None)

        self.assertEqual(recommend_model(profile).tag, "qwen3-vl:2b")

    def test_recommended_model_is_first(self) -> None:
        profile = SystemProfile(ram_gb=16, gpu_name="RTX", gpu_vram_gb=8)

        self.assertEqual(ordered_model_options(profile)[0].tag, recommend_model(profile).tag)

    def test_system_profile_labels_hardware_and_storage(self) -> None:
        profile = SystemProfile(
            os_name="Windows",
            cpu_name="Example CPU",
            ram_gb=16,
            gpu_name="RTX",
            gpu_vram_gb=8,
            free_disk_gb=120,
        )

        self.assertIn("RAM 16GB", system_profile_label(profile))
        details = "\n".join(system_profile_details(profile))
        self.assertIn("Example CPU", details)
        self.assertIn("120.0GB", details)


if __name__ == "__main__":
    unittest.main()
