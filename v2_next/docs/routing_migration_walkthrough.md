# 화면 라우팅 구조 개선 워크플로우 (Home & Dashboard 분리)

## 1. 개요

- **목표**: 단일 페이지(대시보드) 구조를 홈(`/`)과 대시보드(`/dashboard`)로
  분리.
- **접근 주소**:
  - `http://HOST:8000/` → **홈 페이지 (New)**
  - `http://HOST:8000/dashboard` → **기존 대시보드**
- **기술 스택**: React Router (`react-router-dom`)

## 2. 사전 점검 (Brainstorming & Check)

- **Backend (`backend/app.py`)**:
  - 현재 정적 파일 서빙 로직(`/{full_path:path}`)은 SPA(Single Page
    Application)를 지원하도록 이미 구성되어 있습니다. (`index.html` fallback
    존재)
  - 따라서 백엔드 코드 수정은 불필요합니다.
- **Frontend (`frontend/src`)**:
  - 현재 `App.tsx`가 대시보드 전체를 담당하고 있습니다.
  - `react-router-dom` 라이브러리 설치가 필요합니다.
  - `index.tsx`에서 라우팅 설정이 필요합니다.

## 3. 구현 계획 (Implementation Steps)

### Step 1: 라이브러리 설치

`react-router-dom` 패키지를 설치합니다.

```bash
cd frontend
npm install react-router-dom
```

### Step 2: 홈 페이지 컴포넌트 생성 (`frontend/src/pages/Home.tsx`)

새로운 홈 페이지를 만듭니다. "프리미엄"한 디자인 감각을 적용합니다.

- **위치**: `frontend/src/pages/Home.tsx` (폴더 생성 필요)
- **내용**:
  - 헤더: "Smart Factory Logger"
  - 메인 비주얼: 공장 모니터링을 암시하는 배경 또는 그래픽
  - **Action 버튼**: "Dashboard 입장" (클릭 시 `/dashboard`로 이동)

### Step 3: 라우터 설정 (`frontend/src/Router.tsx` or `index.tsx`)

기존 `App` 컴포넌트를 `/dashboard` 경로로 옮기고, `/` 경로에 `Home`을
배치합니다.

**변경 전 (`index.tsx`):**

```tsx
root.render(
    <App />,
);
```

**변경 후 (`index.tsx` 또는 `Router.tsx`):**

```tsx
import { BrowserRouter, Route, Routes } from "react-router-dom";
import App from "./App";
import Home from "./pages/Home";

// ...
root.render(
    <BrowserRouter>
        <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/dashboard" element={<App />} />
        </Routes>
    </BrowserRouter>,
);
```

### Step 4: 기존 `App.tsx` 점검

- `App.tsx` 내부에서 URL을 조작하거나 경로에 의존하는 로직이 있는지 확인합니다.
  (대부분 없을 것으로 예상되나, 만약 있다면 수정 필요)
- 대시보드 내에서 홈으로 돌아가는 버튼("Exit" 또는 "Home") 추가도 고려할 수
  있습니다.

### Step 5: 빌드 및 배포

- `npm run build`로 프론트엔드를 빌드합니다.
- `deploy.ps1`을 실행하여 변경 사항을 적용하고 EXE를 재빌드합니다.

## 4. 고려 사항 (Edge Cases)

1. **새로고침 문제**: `/dashboard`에서 F5를 눌렀을 때 404가 뜨지 않아야 합니다.
   (백엔드의 SPA fallback 로직이 이를 처리해 줄 것입니다. -> **확인됨**)
2. **네트워크 접속**: `192.168.0.7:8000`으로 접속 시에도 라우팅은
   클라이언트(브라우저)에서 처리되므로 동일하게 동작합니다.

---

**작성일**: 2026-01-14 **작성자**: Antigravity AI
