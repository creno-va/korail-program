# 프로젝트 결정 사항

## D-001. Python 환경

결정: CPython 3.11+를 기본 런타임으로 사용한다.

이유:

- PySide6, PyInstaller, FFmpeg 연동의 Windows/macOS 패키징 안정성이 중요하다.
- 납품 PC에는 Python 개발 환경이 없어도 실행되는 설치 마법사를 제공한다.

## D-002. GUI 프레임워크

결정: PySide6 + Qt Widgets를 사용한다.

이유:

- Windows 업무용 데스크톱 프로그램에 적합하다.
- QThread 기반 백그라운드 분석과 설치형 배포가 단순하다.
- KRDS에 가까운 절제된 grayscale 업무 UI를 구성하기 쉽다.

## D-003. 프레임 판정 모델

결정: YOLO와 로컬 VLM 대신 OpenAI GPT API 기반 VQA judge를 기본 경로로 사용한다.

이유:

- YOLO는 현장 데이터 수집, 라벨링, 학습, 모델 검증 비용이 크다.
- 로컬 VLM은 설치 파일 크기, PC 사양, Ollama 런타임 오류, 처리 속도 문제가 컸다.
- GPT vision API는 별도 모델 설치 없이 더 안정적인 VQA 품질을 기대할 수 있다.

기본 모델:

- `gpt-5.6-terra`

선택 모델:

- `gpt-5.6-sol`
- `gpt-5.6-luna`
- `gpt-4.1-mini`

주의:

- GPT judge는 안전 진단의 최종 근거가 아니라 후보 이벤트 생성기다.
- false negative를 줄이는 방향으로 프롬프트와 샘플링 간격을 조정한다.
- API key, 네트워크, 비용/쿼터 관리가 운영 요구사항에 포함된다.

## D-004. 역명/OCR

결정: Judge와 분리된 OCR 파이프라인을 유지하되, 기본 백엔드는 GPT vision OCR 프롬프트로 둔다.

이유:

- PaddleOCR/PaddlePaddle 설치 부담을 기본 경로에서 제거한다.
- OCR 실패가 judge 결과에 직접 영향을 주지 않도록 책임을 분리한다.
- 역명 사전, 노선 힌트, 전후 타임코드 보간은 후처리로 보강한다.

## D-005. 배포 방식

결정: Windows는 PyInstaller + Inno Setup, macOS는 PyInstaller + pkg/dmg로 배포한다.

포함 항목:

- 앱 실행 파일
- PySide6/Qt runtime
- FFmpeg/FFprobe
- 폰트/아이콘 assets

제외 항목:

- Ollama
- 로컬 VLM 모델
- llama-server

## D-006. Secret 관리

결정: OpenAI API key는 git, 릴리즈 asset, 리포트, observations JSON에 기록하지 않는다.

허용 경로:

- `OPENAI_API_KEY` OS 환경변수
- `.env` 또는 `.env.local` 파일
- 앱 사용자 데이터 폴더의 `settings.json`

대화나 이슈에 노출된 key는 운영 전에 반드시 폐기하고 새 key로 교체한다.
