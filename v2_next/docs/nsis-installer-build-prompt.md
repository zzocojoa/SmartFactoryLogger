# NSIS Installer Build Prompt

Use this prompt when asking an agent to build the Windows installer directly.

```text
SmartFactoryLogger v2_next Windows 배포용 NSIS 설치 파일을 생성해 주세요.

작업 기준:
- 작업 경로: C:\Users\user\Documents\GitHub\SmartFactoryLogger\v2_next
- portable zip은 만들지 말고 NSIS installer만 만듭니다.
- Electron 설정은 package.json의 build.win.target = "nsis" 설정을 사용합니다.
- 프론트엔드는 npm --prefix frontend run build로 먼저 빌드합니다.
- 백엔드는 PyInstaller spec을 사용해 backend\dist\SmartFactoryBackend.exe를 다시 빌드합니다:
  .\backend\.venv\Scripts\pyinstaller.exe --noconfirm --clean --distpath backend\dist --workpath backend\build backend\build_specs\SmartFactoryBackend.spec
- 마지막에 npm run dist로 NSIS 설치 파일을 생성합니다.
- PyInstaller 또는 electron-builder가 AppData/cache 권한 문제로 실패하면 같은 명령을 승인 요청 후 다시 실행합니다.

필수 확인:
- main.js에서 Electron이 백엔드를 실행할 때 SFL_EMBEDDED_ELECTRON=1 환경 변수를 넘겨야 합니다.
- backend\scripts\legacy_servers\server_entry.py는 SFL_EMBEDDED_ELECTRON=1일 때 브라우저 자동 오픈을 하지 않아야 합니다.
- 설치 후 실행 시 Electron 창만 떠야 하며, 기본 웹브라우저가 자동으로 열리면 안 됩니다.

검증:
- npm --prefix frontend run typecheck
- npm --prefix frontend run lint
- $env:APPDATA='C:\tmp\sfl-test-appdata'; $env:SFL_CONFIG_PATH='C:\tmp\sfl-test-config.json'; .\backend\.venv\Scripts\python.exe -m unittest discover -s backend/tests
- 생성된 dist\smart-factory-logger-v2 Setup <version>.exe의 경로, 크기, SHA256을 보고합니다.
```
