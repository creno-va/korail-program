# Windows 실행파일 및 설치 마법사 빌드

Windows 배포는 두 단계로 구성합니다.

1. PyInstaller로 `dist/KorailAnalyzer/KorailAnalyzer.exe` one-folder 앱 생성
2. Inno Setup으로 `dist/installer/KorailAnalyzerSetup-<version>.exe` 설치 마법사 생성

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
