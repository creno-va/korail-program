# 실행파일 및 설치 마법사 빌드

## 배포 구조

현재 배포판은 GPT API 기반입니다. 설치 파일에는 다음 항목만 포함합니다.

- PyInstaller 앱 번들
- FFmpeg/FFprobe runtime
- Pretendard GOV font assets
- Qt/PySide6 runtime

Ollama, 로컬 VLM 모델, `llama-server`는 더 이상 포함하지 않습니다. 분석 전 `OPENAI_API_KEY`가 필요하며, 사용자는 OS 환경변수나 앱의 `API 설정` 창으로 key를 공급합니다.

## Windows

Windows 배포는 두 단계로 구성됩니다.

1. PyInstaller로 `dist/KorailAnalyzer/KorailAnalyzer.exe` one-folder 앱 생성
2. Inno Setup으로 `dist/installer/KorailAnalyzerSetup-<version>.exe` 설치 마법사 생성

```powershell
.\scripts\package_windows.cmd
```

또는:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package_windows.ps1
```

`-BuildAppOnly`를 주면 Inno Setup 설치 마법사 없이 앱 번들까지만 생성합니다.

## macOS

macOS 배포는 macOS runner 또는 실제 Mac에서만 빌드합니다.

1. PyInstaller로 `dist/Korail Analyzer.app` 생성
2. `pkgbuild`/`productbuild`로 `.pkg` 설치 마법사 생성
3. `hdiutil`로 `.dmg` 생성

```sh
sh scripts/package_macos.sh
```

GitHub Actions의 `Build macOS installer` workflow는 arm64와 x86_64 pkg/dmg를 생성하고 릴리즈 asset으로 업로드할 수 있습니다.

## 서명/공증

기본 빌드는 내부 검수용 unsigned 패키지입니다. 기관 납품용 macOS 배포에는 다음 값을 설정한 뒤 Apple notarization을 별도 수행해야 합니다.

- `KORAIL_CODESIGN_IDENTITY`
- `KORAIL_INSTALLER_SIGN_IDENTITY`

## 설치 PC 기본 상태

- Python 미설치 가능
- Ollama 미설치 가능
- FFmpeg 미설치 가능
- 인터넷 연결 필요
- OpenAI API key 필요
