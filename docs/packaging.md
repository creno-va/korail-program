# 실행파일 및 설치 마법사 빌드

## 배포 구조

설치본 포함 항목:

- PyInstaller 앱과 PySide6 리소스
- FFmpeg/FFprobe
- Ollama CLI와 CPU/GPU runner 전체
- Pretendard GOV 폰트와 앱 브랜딩

설치본 제외 항목:

- Gemma/Qwen 모델 blob
- 사용자 영상과 분석 결과
- API key 또는 기타 secret

모델은 최초 실행 후 앱 모달에서 내려받으며 사용자 데이터 폴더에 유지됩니다.

## Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package_windows.ps1
```

스크립트는 공식 `ollama-windows-amd64.zip`을 사용합니다. `ollama.exe`, `llama-server.exe`, `libllama-server-impl.dll`, `libllama.dll`, `ggml.dll`이 모두 있어야 빌드가 진행됩니다. 완성된 `dist/KorailAnalyzer/runtime/ollama`와 `runtime/ffmpeg`는 Inno Setup 설치 마법사에 재귀 포함됩니다.

## macOS

```sh
sh scripts/package_macos.sh
```

공식 `Ollama-darwin.zip`의 `Ollama.app/Contents/Resources`를 앱 내부 `Contents/MacOS/runtime/ollama`로 복사합니다. postinstall 단계에서 Ollama, llama-server, FFmpeg 실행 권한을 보정합니다.

## 설치 PC 기본 상태

Python, FFmpeg, Ollama, API key가 없어도 설치 마법사만으로 앱을 실행할 수 있습니다. 모델 설치 시에만 인터넷 연결과 모델 용량 이상의 저장 공간이 필요하며, 설치 후 분석은 오프라인으로 동작합니다.
