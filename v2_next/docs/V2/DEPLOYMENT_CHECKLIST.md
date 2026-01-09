# 배포 전 개발자 체크리스트 (Developer Deployment Checklist)

로직 수정 후 배포 버전을 생성하기 전에 반드시 확인해야 할 사항들입니다.

## 1. 버전 관리 (Versioning)

- [x] **Frontend 버전**: `frontend/package.json`의 `version` 필드가
      업데이트되었는지 확인. (Current: `1.0.0`)
  - 예: `0.1.0` -> `1.0.0`
- [x] **Backend 버전**: `backend/version.py` (또는 `config.py`)의 버전 상수가
      Frontend와 일치하는지 확인. (Current: `1.0.0`)
- [ ] **Changlog**: `CHANGELOG.md` 또는 릴리즈 노트에 변경 사항이 기록되었는지
      확인.

## 2. 의존성 확인 (Dependencies)

### Frontend

- [ ] **새로운 라이브러리**: `npm install`로 추가한 패키지가 있다면
      `package.json`과 `package-lock.json`이 커밋에 포함되었는지 확인.
- [ ] **Unused Package**: 사용하지 않는 라이브러리가 남아있지 않은지 확인.
- [ ] **Worker 호환성**: (이번 변경 관련) `polling.worker.ts` 등 Web Worker에서
      사용하는 라이브러리가 브라우저/Worker 환경 호환성에 문제가 없는지 확인
      (예: `window` 객체 접근).

### Backend

- [ ] **requirements.txt**: `pip install`로 추가한 패키지가 있다면
      `backend/requirements.txt`에 추가되었는지 확인.
  - _주의: PyInstaller로 빌드할 때 `requirements.txt` 기반으로 패키징되지
    않으므로, 빌드 환경에 해당 패키지가 설치되어 있어야 함._
- [ ] **Async 라이브러리**: `asyncio` 외에 `httpx`, `aiohttp` 등을 새로
      사용했다면 의존성 추가 필수.

## 3. 빌드 및 패키징 (Build & Packaging)

- [ ] **Frontend Build**: `npm run build` 명령어가 에러 없이 완료되는지 확인.
  - 빌드 결과물(`dist/`)이 정상적으로 생성되는지.
  - Worker 파일(`assets/polling.worker-*.js`)이 별도로 잘 생성되는지 (Vite
    기준).
- [ ] **Backend Build**: `pyinstaller SmartFactoryLogger.spec` 명령어로 실행
      파일(`server.exe`)이 정상 생성되는지.
  - 실행 파일 용량이 터무니없이 작거나 크지 않은지 확인.

## 4. 환경 변수 및 설정 (Configuration)

- [ ] **.env 파일**: 로컬 개발용 `.env`에 새로 추가된 환경 변수가 있다면, 배포
      환경(운영)에도 적용 계획이 있는지 확인.
- [ ] **config.py 기본값**: 코드 내 `default` 값이 프로덕션 환경에 적합한지 확인
      (예: `DEBUG=False`).
- [ ] **특수 권한**: 새로운 기능이 관리자 권한이나 파일 시스템 접근
      권한(읽기/쓰기)을 필요로 하는지 확인.

## 5. 기능 검증 (Smoke Test)

- [ ] **Clean Install**: 기존 설치 폴더가 아닌 깨끗한 환경에서 실행
      파일(`exe`)을 실행했을 때 정상 동작하는지.
- [ ] **주요 기능**:
  - [ ] 대시보드 그래프 렌더링 (Web Worker 적용 확인).
  - [ ] 설정 저장 및 재시작 (`Restart Required` 플래그 확인).
  - [ ] 카메라/PLC 연결 실패 시 에러 처리 (Timeout 확인).

## 6. 배포 스크립트

- [ ] `deploy.ps1`을 실행하여 전체 파이프라인(빌드 -> 패키징 -> 압축)이
      자동화되어 잘 돌아가는지 최종 확인.
