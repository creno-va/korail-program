"""Local multimodal model catalog and hardware-based recommendations."""

from __future__ import annotations

import ctypes
import json
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ModelOption:
    tag: str
    name: str
    family: str
    tier: str
    size_gb: float
    min_ram_gb: int
    recommended_vram_gb: int | None
    description: str

    @property
    def size_label(self) -> str:
        return f"약 {self.size_gb:g}GB"


@dataclass(frozen=True, slots=True)
class SystemProfile:
    os_name: str = ""
    cpu_name: str | None = None
    ram_gb: float | None = None
    gpu_name: str | None = None
    gpu_vram_gb: float | None = None
    free_disk_gb: float | None = None
    apple_silicon: bool = False


MODEL_OPTIONS: tuple[ModelOption, ...] = (
    ModelOption(
        tag="qwen3-vl:2b",
        name="Qwen3-VL 2B",
        family="qwen",
        tier="경량",
        size_gb=1.9,
        min_ram_gb=8,
        recommended_vram_gb=3,
        description="저사양 PC용. 빠른 1차 판정과 한국어 역명 OCR에 적합합니다.",
    ),
    ModelOption(
        tag="qwen3-vl:4b",
        name="Qwen3-VL 4B",
        family="qwen",
        tier="균형",
        size_gb=3.3,
        min_ram_gb=12,
        recommended_vram_gb=5,
        description="속도, 한국어 OCR, 전차선 주변 공간 판정의 균형이 좋은 기본 모델입니다.",
    ),
    ModelOption(
        tag="qwen3-vl:8b",
        name="Qwen3-VL 8B",
        family="qwen",
        tier="정밀",
        size_gb=6.1,
        min_ram_gb=16,
        recommended_vram_gb=8,
        description="여유 있는 GPU에서 작은 수목과 전차선의 위치 관계를 더 정밀하게 판정합니다.",
    ),
    ModelOption(
        tag="gemma4:e2b",
        name="Gemma 4 E2B",
        family="gemma4",
        tier="Gemma 경량",
        size_gb=7.2,
        min_ram_gb=12,
        recommended_vram_gb=8,
        description="Gemma 4 엣지 모델. 이미지 이해와 추론을 지원하는 비교적 가벼운 옵션입니다.",
    ),
    ModelOption(
        tag="gemma4:e4b",
        name="Gemma 4 E4B",
        family="gemma4",
        tier="Gemma 균형",
        size_gb=9.6,
        min_ram_gb=16,
        recommended_vram_gb=10,
        description="Gemma 계열을 선호하는 고사양 노트북·데스크톱용 균형 모델입니다.",
    ),
    ModelOption(
        tag="gemma4:12b",
        name="Gemma 4 12B",
        family="gemma4",
        tier="Gemma 정밀",
        size_gb=7.6,
        min_ram_gb=20,
        recommended_vram_gb=12,
        description="판정 품질을 우선하는 워크스테이션용 Gemma 4 모델입니다.",
    ),
)


def get_model_option(tag: str) -> ModelOption:
    normalized = normalize_model_tag(tag)
    for option in MODEL_OPTIONS:
        if normalize_model_tag(option.tag) == normalized:
            return option
    return MODEL_OPTIONS[1]


def normalize_model_tag(tag: str) -> str:
    normalized = tag.strip().lower()
    return normalized[:-7] if normalized.endswith(":latest") else normalized


def detect_system_profile(*, data_dir: Path | None = None) -> SystemProfile:
    os_name = platform.platform(aliased=True, terse=True)
    machine = platform.machine().lower()
    apple_silicon = platform.system() == "Darwin" and machine in {"arm64", "aarch64"}
    gpu_name, gpu_vram_gb = _detect_gpu()
    return SystemProfile(
        os_name=os_name,
        cpu_name=_detect_cpu_name(),
        ram_gb=_detect_ram_gb(),
        gpu_name=gpu_name,
        gpu_vram_gb=gpu_vram_gb,
        free_disk_gb=_detect_free_disk_gb(data_dir or Path.home()),
        apple_silicon=apple_silicon,
    )


def recommend_model(profile: SystemProfile) -> ModelOption:
    """Choose a conservative model that should fit without heavy memory swapping."""

    ram = profile.ram_gb or 0
    vram = profile.gpu_vram_gb
    if vram is not None:
        if ram >= 16 and vram >= 8:
            return get_model_option("qwen3-vl:8b")
        if ram >= 12 and vram >= 5:
            return get_model_option("qwen3-vl:4b")
        return get_model_option("qwen3-vl:2b")
    if profile.apple_silicon:
        if ram >= 24:
            return get_model_option("qwen3-vl:8b")
        if ram >= 16:
            return get_model_option("qwen3-vl:4b")
        return get_model_option("qwen3-vl:2b")
    if ram >= 24:
        return get_model_option("qwen3-vl:8b")
    if ram >= 12:
        return get_model_option("qwen3-vl:4b")
    return get_model_option("qwen3-vl:2b")


def recommended_reason(profile: SystemProfile, option: ModelOption) -> str:
    if profile.gpu_vram_gb is not None:
        if profile.ram_gb:
            basis = f"RAM {profile.ram_gb:.0f}GB, GPU 메모리 {profile.gpu_vram_gb:.0f}GB"
        else:
            basis = f"GPU 메모리 {profile.gpu_vram_gb:.0f}GB"
    elif profile.apple_silicon:
        basis = (
            f"Apple 통합 메모리 {profile.ram_gb:.0f}GB"
            if profile.ram_gb
            else "Apple Silicon"
        )
    else:
        basis = (
            f"RAM {profile.ram_gb:.0f}GB (전용 GPU 메모리 확인 불가)"
            if profile.ram_gb
            else "확인 가능한 메모리 정보"
        )
    return f"{basis} 기준으로 {option.name}을 권장합니다."


def ordered_model_options(profile: SystemProfile) -> tuple[ModelOption, ...]:
    recommended = recommend_model(profile)
    return (recommended,) + tuple(
        option for option in MODEL_OPTIONS if option.tag != recommended.tag
    )


def system_profile_label(profile: SystemProfile) -> str:
    ram = f"RAM {profile.ram_gb:.0f}GB" if profile.ram_gb else "RAM 확인 불가"
    if profile.gpu_name and profile.gpu_vram_gb:
        return f"{ram} · {profile.gpu_name} {profile.gpu_vram_gb:.0f}GB"
    if profile.gpu_name:
        return f"{ram} · {profile.gpu_name}"
    return f"{ram} · 전용 GPU 확인 불가"


def system_profile_details(profile: SystemProfile) -> list[str]:
    details = [f"운영체제: {profile.os_name or '확인 불가'}"]
    details.append(f"CPU: {profile.cpu_name or '확인 불가'}")
    details.append(f"메모리: {profile.ram_gb:.1f}GB" if profile.ram_gb else "메모리: 확인 불가")
    if profile.gpu_name:
        gpu = profile.gpu_name
        if profile.gpu_vram_gb:
            gpu += f" / VRAM {profile.gpu_vram_gb:.1f}GB"
        details.append(f"GPU: {gpu}")
    else:
        details.append("GPU: 전용 GPU 확인 불가 (CPU 실행 가능)")
    details.append(
        f"모델 저장 여유 공간: {profile.free_disk_gb:.1f}GB"
        if profile.free_disk_gb is not None
        else "모델 저장 여유 공간: 확인 불가"
    )
    return details


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


def _detect_cpu_name() -> str | None:
    if platform.system() == "Windows":
        registry_name = _detect_windows_cpu_name()
        if registry_name:
            return registry_name
    name = platform.processor().strip() or os.environ.get("PROCESSOR_IDENTIFIER", "").strip()
    if name:
        return " ".join(name.split())
    try:
        result = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def _detect_gpu() -> tuple[str | None, float | None]:
    name, vram = _detect_nvidia_gpu()
    if name:
        return name, vram
    if platform.system() == "Windows":
        return _detect_windows_gpu()
    if platform.system() == "Darwin":
        return _detect_macos_gpu()
    return None, None


def _detect_windows_cpu_name() -> str | None:
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "ProcessorNameString")
    except (ImportError, OSError):
        return None
    return " ".join(str(value).split()) or None


def _detect_windows_gpu() -> tuple[str | None, float | None]:
    """Read display-adapter metadata without requiring WMI administrator access."""

    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Video",
        ) as video_key:
            candidates: list[tuple[str, float | None]] = []
            for index in range(winreg.QueryInfoKey(video_key)[0]):
                adapter_id = winreg.EnumKey(video_key, index)
                try:
                    with winreg.OpenKey(video_key, rf"{adapter_id}\0000") as adapter_key:
                        name_value, _ = winreg.QueryValueEx(
                            adapter_key, "HardwareInformation.AdapterString"
                        )
                        try:
                            memory_value, _ = winreg.QueryValueEx(
                                adapter_key, "HardwareInformation.qwMemorySize"
                            )
                        except OSError:
                            memory_value, _ = winreg.QueryValueEx(
                                adapter_key, "HardwareInformation.MemorySize"
                            )
                except OSError:
                    continue
                if isinstance(name_value, bytes):
                    decoded_name = name_value.decode("utf-16-le", errors="ignore").rstrip("\x00")
                else:
                    decoded_name = str(name_value)
                name = " ".join(decoded_name.split())
                if not name or "basic render" in name.lower():
                    continue
                try:
                    vram_gb = int(memory_value) / (1024**3)
                except (TypeError, ValueError):
                    vram_gb = None
                candidates.append((name, vram_gb))
    except (ImportError, OSError):
        return None, None
    if not candidates:
        return None, None
    return max(candidates, key=lambda item: item[1] or 0)


def _detect_nvidia_gpu() -> tuple[str | None, float | None]:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
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
    parts = [part.strip() for part in first_line.split(",")]
    if not parts or not parts[0]:
        return None, None
    try:
        vram_gb = float(parts[1]) / 1024 if len(parts) > 1 else None
    except ValueError:
        vram_gb = None
    return parts[0], vram_gb


def _detect_macos_gpu() -> tuple[str | None, float | None]:
    try:
        result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
        displays = json.loads(result.stdout).get("SPDisplaysDataType", [])
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None, None
    if not displays:
        return None, None
    item = displays[0]
    name = str(item.get("sppci_model") or item.get("_name") or "").strip() or None
    raw_vram = str(item.get("spdisplays_vram") or item.get("spdisplays_vram_shared") or "")
    try:
        vram = float(raw_vram.split()[0]) if raw_vram else None
    except ValueError:
        vram = None
    return name, vram


def _detect_free_disk_gb(path: Path) -> float | None:
    try:
        existing = path
        while not existing.exists() and existing != existing.parent:
            existing = existing.parent
        return shutil.disk_usage(existing).free / (1024**3)
    except OSError:
        return None
