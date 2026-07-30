# Korail 지장수목 분석 프로그램 문서

이 문서는 전차선로 지장수목 후보 구간을 오프라인으로 분석하는 데스크톱 프로그램의 개발 기준을 정리합니다.

## 현재 방향

- 납품 형태: Windows/macOS 오프라인 설치형 프로그램
- 개발 실행: Windows와 macOS 모두 지원
- 개발 언어: Python 3.11+ CPython
- GUI: PySide6, Qt Widgets
- 프레임 judge: 로컬 멀티모달 LLM
- 역명/OCR: 기본 VLM OCR + 선택형 역명 사전 보정
- 영상 처리: FFmpeg
- 저장소: SQLite
- 리포트: PDF + Excel

## 문서 목록

- [프로젝트 결정 사항](./decisions.md)
- [사용자 플로우](./user-flow.md)
- [분석 파이프라인 설계](./pipeline-design.md)
- [개발 환경 및 배포 방향](./dev-env-and-packaging.md)
- [참고 자료](./references.md)

## 우선 확인할 입력 자료

- 실제 샘플 주행 영상
- 영상 내 역명/위치 오버레이 위치와 표기 형식
- 노선별 역명 사전
- 위험도 판정 기준
- 납품 리포트 양식
