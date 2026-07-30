# Windows 실행파일 및 설치 마법사 빌드

Windows 배포는 두 단계로 구성합니다.

1. PyInstaller로 `dist/KorailAnalyzer/KorailAnalyzer.exe` one-folder 앱 생성
2. Inno Setup으로 `dist/installer/KorailAnalyzerSetup-<version>.exe` 설치 마법사 생성

빌드 스크립트는 설치 exe에 다음 런타임도 함께 포함합니다.

- Ollama standalone Windows runtime: `runtime/ollama/ollama.exe`
- Ollama model runner files: `runtime/ollama/lib/ollama/llama-server.exe`, `libllama*.dll`, CPU/GPU backend libraries
- FFmpeg/FFprobe: `runtime/ffmpeg/bin/`

앱의 모델 설정은 설치된 PC의 PATH가 아니라 이 번들 런타임을 우선 사용합니다. 기본 역명 OCR도 선택된 Qwen VL 모델의 VLM OCR 프롬프트를 사용하므로 별도 OCR 패키지 설치가 필요 없습니다.

## 로컬 빌드

```powershell
.\scripts\package_windows.cmd
```

또는:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package_windows.ps1
```

Inno Setup이 설치되어 있지 않으면 스크립트는 Chocolatey가 있을 때 `innosetup` 설치를 시도합니다. 설치 권한이 없거나 Inno Setup 없이 앱 번들만 만들려면:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package_windows.ps1 -BuildAppOnly
```

## 산출물

- 앱 번들: `dist/KorailAnalyzer/KorailAnalyzer.exe`
- 설치 마법사: `dist/installer/KorailAnalyzerSetup-<version>.exe`

설치 마법사는 시작 메뉴 바로가기, 선택형 바탕화면 바로가기, 설치 후 앱 실행 옵션을 제공합니다.

## 설치 PC 기대 상태

- Python 미설치 가능
- Ollama 미설치 가능
- FFmpeg 미설치 가능
- 앱 최초 실행 후 `모델 설정`에서 권장 모델 다운로드
- 모델 다운로드 완료 후 네트워크 없이 영상 분석 가능
