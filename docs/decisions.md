# 프로젝트 결정 사항

## D-001. Python 런타임

결정: CPython을 기본 런타임으로 사용한다.

PyPy는 Python 구현체이며 패키지 매니저가 아니다. 순수 Python 코드에는 장점이 있지만, 이 프로젝트는 PySide6, PyInstaller, 영상 처리, 로컬 모델 런타임 연동처럼 Windows 패키징 안정성이 중요하다. 따라서 호환성과 납품 안정성을 우선해 CPython을 기준으로 한다.

권장 버전:

- Python 3.11 또는 3.12
- Windows 11 64-bit

## D-002. 패키지/환경 관리

결정: uv를 우선 검토한다.

이유:

- 빠른 의존성 설치와 lockfile 관리
- pip 호환 워크플로우
- CI/빌드 스크립트로 옮기기 쉬움

초기에는 다음 구조를 목표로 한다.

```text
pyproject.toml
uv.lock
src/korail_program/
tests/
docs/
```

## D-003. GUI 프레임워크

결정: PySide6 + Qt Widgets를 사용한다.

이유:

- Windows 데스크톱 업무 프로그램에 적합
- 파일 대기열, 테이블, 썸네일, 설정창, 로그, 진행률 UI 구현이 안정적
- PyQt보다 납품 라이선스 검토 부담이 작음
- 백그라운드 작업은 QThread 또는 QProcess로 UI와 분리 가능

## D-004. 프레임 판정 모델

결정: 초기 MVP에서는 YOLO를 배제하고 `qwen2.5vl:3b` 로컬 멀티모달 LLM으로 VQA judge를 수행한다.

역할:

- 프레임에 지장수목/대나무 의심 객체가 있는지 판단
- 전차선로 근접 여부 판단
- 위험도 상/중/하/없음 판정
- 판단 근거 문장 생성
- 가능하면 위치 힌트 bbox 생성

주의:

- Gemma judge는 안전 진단의 최종 근거가 아니라 후보 이벤트 생성기다.
- 놓침(false negative)을 줄이는 방향으로 프롬프트와 후처리를 설계한다.
- 모든 프레임을 처리하지 않고 샘플링 + 이벤트 병합을 사용한다.

## D-005. 역명/위치 OCR

결정: Gemma judge와 분리된 OCR 파이프라인을 두되, 기본 백엔드는 같은 로컬 멀티모달 LLM의 VLM OCR 프롬프트로 둔다.

이유:

- 납품 PC에 Python 개발 환경, PaddleOCR, PaddlePaddle을 별도로 설치하지 않아도 앱 기본 기능이 동작해야 함
- 앱 내 모델 설치로 받은 `qwen2.5vl:3b`를 judge와 OCR이 공유하면 설치 리소스와 장애 지점이 줄어듦
- OCR 실패가 judge 결과에 직접 영향을 주지 않도록 책임은 계속 분리함
- 역명 사전, 노선 정보, 전후 보간을 결합해 오인식을 줄일 수 있음

보류:

- PaddleOCR은 사내 검증 후 정확도와 속도가 충분할 때 선택형 고속 백엔드로 다시 포함한다.

## D-006. 데이터 저장

결정: SQLite를 기본 내장 DB로 사용한다.

저장 대상:

- 영상 파일 메타데이터
- OCR 관측값
- Judge 관측값
- 병합된 이벤트
- 캡처 이미지 경로
- 리포트 생성 이력

## D-007. 배포 방식

결정: 초기 납품은 one-folder 앱을 Inno Setup 설치 마법사로 감싸 배포한다.

이유:

- Ollama standalone 런타임, FFmpeg, 리포트 템플릿 포함이 쉬움
- one-file은 대형 모델과 CUDA 의존성 때문에 실행 지연과 장애 원인 추적이 어려움
- 설치 프로그램은 Inno Setup 또는 NSIS를 검토한다.
