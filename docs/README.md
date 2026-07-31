# Korail 지장수목 분석 프로그램 문서

이 문서는 철도 주행 영상을 GPT vision VQA로 분석해 지장수목 의심 구간을 리포트하는 데스크톱 프로그램의 개발 기준을 정리합니다.

## 현재 방향

- 배포 형태: Windows/macOS 설치형 데스크톱 앱
- 개발 언어: Python 3.11+ CPython
- GUI: PySide6, Qt Widgets
- 프레임 judge: OpenAI GPT API 기반 VQA
- 역명/OCR: GPT VLM OCR + 선택적 역명 사전 보정
- 영상 처리: FFmpeg
- 산출물: HTML/Markdown/JSON 리포트와 캡처 이미지

## 문서 목록

- [프로젝트 결정 사항](./decisions.md)
- [사용자 플로우](./user-flow.md)
- [분석 파이프라인 설계](./pipeline-design.md)
- [개발 환경 및 배포 방향](./dev-env-and-packaging.md)
- [패키징](./packaging.md)
- [참고 자료](./references.md)
