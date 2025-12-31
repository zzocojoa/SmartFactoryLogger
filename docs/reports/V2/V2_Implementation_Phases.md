# V2.0 (Web Tech) 구현 단계별 상세 가이드

`작성일: 2025-12-31`
`목표: 개발 환경 설정부터 최종 배포까지, 단계별 실행 계획 (Roadmap)`

## Phase 1. 환경 설정 (Foundation)

**"V1 코드를 보존하고, V2를 위한 깨끗한 도화지를 준비합니다."**

1. **Git 구조 개편** (참고: `V2_0_Migration_Strategy.md`)
   - `v1_legacy` 폴더 생성 및 기존 코드 이동.
   - `v2_next` 폴더 생성.
2. **프로젝트 초기화 (Scaffolding)**
   - **Backend**: `v2_next` 안에 Python 가상환경 생성 및 필요
     라이브러리(FastAPI, Uvicorn) 설치.
   - **Frontend**: `v2_next` 안에 React 프로젝트 생성
     (`npx create-react-app frontend`).
   - **Electron**: Electron Wrapper 설치 (`npm install electron`).

## Phase 2. 핵심 개발 (Core Development)

**"뇌(Python)와 얼굴(React)을 각각 만들고 연결합니다."**

1. **Step 1: Backend API 서버 구축**
   - 기존 V1 로직(로그 수집, DB 저장)을 재활용하되, UI와 통신할 수 있도록 **HTTP
     API**로 포장합니다.
   - 예: `GET /api/status` -> `{"status": "Run", "speed": 2.5}` 반환.
2. **Step 2: Frontend 대시보드 구현**
   - React로 예쁜 게이지, 차트, 설정 화면을 만듭니다. (드래그 앤 드롭 라이브러리
     `react-grid-layout` 적용)
   - 0.5초마다 Backend API를 호출하여 화면을 갱신합니다.
3. **Step 3: Electron 통합 테스트**
   - React 화면을 Electron 창에 띄워보고, `.exe`처럼 잘 뜨는지 확인합니다.

## Phase 3. 배포 및 이식 (Deployment Phase)

**"개발자 PC에서 만든 것을 현장 PC로 옮길 준비를 합니다."** (참고:
`V2_Deployment_Standard.md`)

1. **Step 1: 통합 빌드 (Bundling)**
   - Backend(Python) -> 실행 파일(`server.exe`)로 변환.
   - Frontend(React) -> 정적 파일(HTML/JS)로 변환.
2. **Step 2: 인스톨러 생성 (Installer)**
   - `electron-builder`를 돌려서 최종 **`Setup.exe`** 파일 하나를 생성합니다.
3. **Step 3: 현장 설치 (On-site)**
   - USB에 `Setup.exe`를 담아가서 공장 PC에 설치.
   - 바탕화면 아이콘 더블 클릭 -> 실행 확인.

---

## [Checklist] 시작 전 준비물

- [ ] **Node.js** 설치 (Frontend 개발용)
- [ ] **Python 3.10+** (Backend 개발용)
- [ ] **VS Code** (에디터)
- [ ] **마음의 준비**: "더 이상 Tkinter와 싸우지 않아도 된다"는 안도감.
