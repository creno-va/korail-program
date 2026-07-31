# Korail 지장수목 분석 프로그램

철도 주행 영상에서 전차선로 주변 지장수목 의심 프레임을 샘플링하고, GPT vision VQA로 위험 후보를 판정해 캡처와 HTML/Markdown 리포트를 생성하는 데스크톱 프로그램입니다.

Windows/macOS 납품판은 Python 개발 환경이 없는 PC에서도 설치 파일만으로 실행됩니다. 앱에는 PyInstaller 기반 실행 파일과 FFmpeg/FFprobe가 포함되며, 프레임 judge와 역명 OCR은 OpenAI GPT API를 사용합니다. Ollama나 로컬 모델 설치는 더 이상 필요하지 않습니다.

## 기술 방향

- Python 3.11+ CPython
- GUI: PySide6, Qt Widgets
- 디자인: Pretendard GOV, Material Design Icons, grayscale + success/warning/error 상태색
- 프레임 judge: OpenAI Responses API + vision-capable GPT model, 기본 `gpt-5.6-terra`
- 역명/OCR: 기본 GPT VLM OCR + 선택적 역명 사전 보정
- 결과: 캡처 이미지, HTML/Markdown 리포트, JSON 산출물

## API Key 설정

분석 전 `OPENAI_API_KEY`가 필요합니다. 키는 코드, 리포트, 릴리즈 asset에 기록하지 않습니다.

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\set_openai_key.ps1 -ApiKey "sk-..."
```

macOS:

```sh
sh scripts/set_openai_key.sh "sk-..."
```

또는 앱의 `API 설정` 창에서 key를 저장할 수 있습니다. 앱 저장 key는 해당 PC의 사용자 데이터 폴더에만 보관됩니다.

## 개발 실행

Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\scripts\run_gui.cmd
```

macOS:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
sh scripts/run_gui.sh
```

테스트:

```powershell
.\scripts\test.cmd
```

## 배치 분석

루트 디렉터리나 지정 경로의 `mp4`, `avi`, `mov`, `mkv` 영상을 일정 간격으로 샘플링합니다.

Windows:

```powershell
.\scripts\analyze_root_videos.cmd
```

macOS:

```sh
sh scripts/analyze_root_videos.sh
```

기본값:

- 모델: `gpt-5.6-terra`
- VQA 샘플링 간격: 10초
- 리포트 포함 기준: `medium` 이상
- 산출물: `output/analysis.../report.html`, `report.md`, `observations.json`, `events.json`, `captures/`

## 설치 마법사 빌드

Windows:

```powershell
.\scripts\package_windows.cmd
```

macOS:

```sh
sh scripts/package_macos.sh
```

산출물:

- Windows: `dist/installer/KorailAnalyzerSetup-<version>.exe`
- macOS: `dist/installer/KorailAnalyzerInstaller-<version>-macos-<arch>.pkg`
- macOS: `dist/installer/KorailAnalyzerInstaller-<version>-macos-<arch>.dmg`

자세한 내용은 [패키징 문서](./docs/packaging.md)를 참고하세요.

## 문서

- [문서 인덱스](./docs/README.md)
- [프로젝트 결정 사항](./docs/decisions.md)
- [사용자 플로우](./docs/user-flow.md)
- [분석 파이프라인 설계](./docs/pipeline-design.md)
- [개발 환경 및 배포](./docs/dev-env-and-packaging.md)
