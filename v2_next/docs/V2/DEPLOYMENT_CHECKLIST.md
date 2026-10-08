# 배포 전 개발자 체크리스트 (Developer Deployment Checklist)

로직 수정 후 배포 버전을 생성하기 전에 반드시 확인해야 할 사항들입니다.
이 문서는 배포별 확인 양식입니다. 체크 표시는 해당 설치본의 실제 근거를 확인한 뒤 기록합니다.
현재 운영본과 다음 변경의 롤백 기준은
[운영본·롤백 기준](05_운영_배포/operating_rollback_baseline.md)을 확인합니다.

## 1. 버전 관리 (Versioning)

- [ ] **버전 표기**: `package.json`, `frontend/package.json`, `backend/version.py`의
      해당 배포 버전과 실제 실행본 표기를 확인.
- [ ] **소스·설치본 식별**: 전체 build commit, installer 파일명·길이·SHA256 및
      provenance의 결합을 확인. 같은 표시 버전의 서로 다른 빌드를 구분.
- [ ] **문서 commit 구분**: 후속 기록용 commit을 설치본의 build commit으로 바꾸어 쓰지 않음.
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
- [ ] **Backend Build**: 저장소의 `scripts/deploy.ps1`이 사용하는
      `backend/build_specs/SmartFactoryBackend.spec` 기준 패키징으로
      `SmartFactoryBackend.exe`가 정상 생성되는지.
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

- [ ] 새 빌드가 필요한 경우 `scripts/deploy.ps1`을 실행하여 파이프라인(빌드 -> 패키징 -> 압축)이
      자동화되어 잘 돌아가는지 최종 확인.

## 7. 운영 승격과 롤백 기준 갱신

- [ ] **배포 경로**: 서명 배포·개인 사용·개발 시험·미서명 내부 운영 중 적용 경로와
      [서명 정책](05_운영_배포/windows_authenticode_signing.md)의 해당 승인 범위를 기록.
- [ ] **실제 대상**: 교체 시점의 서버 실행 세대·설정·데이터 보존 조건을 확인.
      제품·금형 변경 및 IDLE/공란을 허용하고 과거 작업정보로 덮어쓰지 않음.
- [ ] **이전 정상본**: 이번 개선 작업의 복귀 기준을 전체 commit·installer 해시·보존 위치로 식별하고
      설정·데이터 호환성과 정상 종료·잔존·미완료 저장을 고려한 복구 절차를 확인.
- [ ] **변경 검증**: 실제 개선 코드와 설치본의 관련 회귀·패키지 및 승인된 적용 근거를 연결.
      미실행·실패·미관찰과 사용자 수용을 구분하고 이전 commit의 PASS를 복사하지 않음.
- [ ] **적용 확인**: 승인 범위에서 단일 실행 세대·수집·저장·설정/데이터 보존을 확인.
      동일 설치본의 문서 정리에 재빌드·추가 120분 시험을 자동으로 붙이지 않음.
- [ ] **기준 갱신**: 운영 승격·적용 확인 후 해당 본을 다음 개선 작업의 롤백 기준으로 등록.
      이전 기준 → 새 기준, 승인 근거·적용 확인 시점·수용한 한계를 기록.
- [ ] **이력 보존**: 이전 설치본·봉인 영수증·과거 실패를 보존. 고정 helper/manifest의 해시를
      새 기준으로 일괄 치환하거나 실패 카운터를 초기화하지 않음.

서명 상태와 기술 QA 상태는 운영 승인과 별도로 기록합니다. 이 양식의 갱신은 설치·자동 복구를 실행하지 않습니다.
