# 화면 라우팅 구조 개선 구현 계획 (Implementation Plan)

본 문서는 명세서(`routing_migration_spec.md`)를 바탕으로 화면 라우팅 구조 개선을
위한 구체적인 작업 목록을 정의합니다.

## 1. 환경 설정 (Setup)

- [x] **패키지 설치**: `frontend` 디렉토리에서 `react-router-dom` 설치.
  ```bash
  cd frontend
  npm install react-router-dom
  ```

## 2. 컴포넌트 개발 (Component Development)

- [x] **Home 페이지 생성**: `frontend/src/pages/Home.tsx` 파일 생성.
  - [x] 헤더 ("Smart Factory Logger") 및 로고 배치.
  - [x] 메인 비주얼 (공장/데이터 모니터링 컨셉의 배경 또는 텍스트).
  - [x] 진입 버튼 ("Dashboard", "Monitoring Start" 등) 생성 및 스타일링 (Hover
        효과 등 Premium 느낌 적용).

## 3. 라우팅 구현 (Routing Implementation)

- [x] **메인 엔트리 포인트 수정**: `frontend/src/index.tsx` 수정.
  - [x] `BrowserRouter` 도입.
  - [x] `Routes` 및 `Route` 설정.
    - `/`: `Home` 컴포넌트 연결.
    - `/dashboard`: 기존 `App` 컴포넌트 연결.
- [x] **기존 리소스 연결 확인**: `App.tsx`가 `/dashboard` 하위에서 정상
      렌더링되는지 확인 (기존 CSS 등 영향도 파악).

## 4. 검증 및 테스트 (Verification)

- [x] **로컬 기능 테스트**: `npm run dev` 실행.
  - [x] `http://localhost:3000/` (Vite 기본 포트) 접속 시 Home 화면 노출 확인.
  - [x] 버튼 클릭 시 `/dashboard`로 이동 및 대시보드 로드 확인.
  - [x] `/dashboard` 주소 직접 입력 시 대시보드 로드 확인.
- [x] **새로고침 테스트**:
  - [x] `/dashboard`에서 브라우저 새로고침(F5) 시 404 없이 정상 로드 확인.

## 5. 빌드 및 배포 (Build & Deploy)

- [ ] **프론트엔드 빌드**: `npm run build` 실행하여 `frontend/dist` 갱신.
- [ ] **시스템 배포**: `deploy.ps1` 실행하여 EXE 재빌드.
- [ ] **통합 테스트**:
  - [ ] 생성된 `SmartFactory_v1.0.0.exe` 실행.
  - [ ] `http://127.0.0.1:8000/` 접속 및 라우팅 동작 최종 확인.
