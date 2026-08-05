# 개발 환경 및 배포 방향

## 기본 환경

- Python 3.11+
- PySide6
- FFmpeg/FFprobe
- Ollama 0.12.7 이상(Qwen3-VL 기준)

## 개발 설치

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev,packaging]"
```

소스 GUI는 시스템 Ollama를 fallback으로 찾습니다. 앱과 동일한 격리 환경은 다음과 같습니다.

```powershell
$env:OLLAMA_HOST = "127.0.0.1:11435"
$env:OLLAMA_MODELS = "$env:LOCALAPPDATA\KorailAnalyzer\ollama\models"
$env:OLLAMA_NO_CLOUD = "1"
ollama serve
```

## CLI

```powershell
.\.venv\Scripts\korail-analyzer.exe analyze-videos D:\videos `
  --out output\analysis `
  --model qwen3-vl:4b `
  --ollama-url http://127.0.0.1:11435
```

## 배포

Windows는 `scripts/package_windows.ps1`, macOS는 `scripts/package_macos.sh`를 사용합니다. 둘 다 PyInstaller 결과에 FFmpeg와 Ollama 런타임을 복사한 뒤 설치 마법사를 만듭니다. 모델 파일은 포함하지 않습니다.
