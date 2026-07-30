"""Local vision model catalog and lightweight hardware recommendation."""

from __future__ import annotations

from dataclasses import dataclass
import ctypes
import os
import platform
import subprocess


@dataclass(frozen=True, slots=True)
class ModelOption:
    tag: str
    name: str
    tier: str
    size_label: str
    min_ram_gb: int
    recommended_vram_gb: int | None
    description: str


@dataclass(frozen=True, slots=True)
class SystemProfile:
    ram_gb: float | None = None
    gpu_name: str | None = None
    gpu_vram_gb: float | None = None


MODEL_OPTIONS: tuple[ModelOption, ...] = (
    ModelOption(
        tag="qwen2.5vl:3b",
        name="Qwen2.5-VL 3B",
        tier="빠름",
        size_label="약 3.2GB",
        min_ram_gb=8,
        recommended_vram_gb=4,
        description="속도 우선. 16GB 미만 PC나 빠른 1차 확인용.",
    ),
    ModelOption(
        tag="qwen3-vl:4b",
        name="Qwen3-VL 4B",
        tier="균형",
        size_label="약 3.3GB",
        min_ram_gb=12,
        recommended_vram_gb=6,
        description="정확도와 속도의 균형. GPU 여유가 애매한 PC용.",
    ),
    ModelOption(
        tag="qwen3-vl:8b",
        name="Qwen3-VL 8B",
        tier="권장",
        size_label="약 6.1GB",
        min_ram_gb=16,
        recommended_vram_gb=8,
        description="기본 정밀 모델. 16GB RAM과 8GB급 NVIDIA GPU 권장.",
    ),
    ModelOption(
        tag="qwen2.5vl:7b",
        name="Qwen2.5-VL 7B",
        tier="호환",
        size_label="약 6.0GB",
        min_ram_gb=16,
        recommended_vram_gb=8,
        description="Qwen3-VL에서 문제가 있을 때 쓰는 7B 대체 모델.",
    ),
)


def get_model_option(tag: str) -> ModelOption:
    for option in MODEL_OPTIONS:
        if option.tag == tag:
            return option
    return MODEL_OPTIONS[0]


def detect_system_profile() -> SystemProfile:
    ram_gb = _detect_ram_gb()
    gpu_name, gpu_vram_gb = _detect_nvidia_gpu()
    return SystemProfile(ram_gb=ram_gb, gpu_name=gpu_name, gpu_vram_gb=gpu_vram_gb)


def recommend_model(profile: SystemProfile) -> ModelOption:
    ram = profile.ram_gb or 0
    vram = profile.gpu_vram_gb or 0
    if ram >= 16 and vram >= 7.5:
        return get_model_option("qwen3-vl:8b")
    if ram >= 12 and (vram >= 4 or profile.gpu_vram_gb is None):
        return get_model_option("qwen3-vl:4b")
    return get_model_option("qwen2.5vl:3b")


def system_profile_label(profile: SystemProfile) -> str:
    ram = f"RAM {profile.ram_gb:.0f}GB" if profile.ram_gb else "RAM 확인 불가"
    if profile.gpu_name and profile.gpu_vram_gb:
        return f"{ram} / {profile.gpu_name} {profile.gpu_vram_gb:.0f}GB"
    if profile.gpu_name:
        return f"{ram} / {profile.gpu_name}"
    return f"{ram} / GPU 확인 불가"


def _detect_ram_gb() -> float | None:
    if platform.system().lower() == "windows":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return status.ullTotalPhys / (1024**3)
        return None

    if hasattr(os, "sysconf"):
        try:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            return (pages * page_size) / (1024**3)
        except (OSError, ValueError):
            return None
    return None


def _detect_nvidia_gpu() -> tuple[str | None, float | None]:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None, None
    if result.returncode != 0:
        return None, None
    first_line = next((line.strip() for line in result.stdout.splitlines() if line.strip()), "")
    if not first_line:
        return None, None
    parts = [part.strip() for part in first_line.split(",")]
    name = parts[0] if parts else None
    vram_gb: float | None = None
    if len(parts) > 1:
        try:
            vram_gb = float(parts[1]) / 1024
        except ValueError:
            vram_gb = None
    return name, vram_gb
