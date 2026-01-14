# 화면 라우팅 구조 개선 명세서 (Specification)

## 1. 개요 (Overview)

본 명세서는 Smart Factory Logger 애플리케이션의 단일 페이지(Single Page)
대시보드 구조를 홈 페이지와 대시보드 페이지로 분리하는 라우팅 개선 작업에 대한
요구사항과 설계를 정의합니다.

## 2. 요구사항 (Requirements)

### 2.1 기능적 요구사항

1. **홈 페이지 (New)**
   - 사용자가 루트 URL(`/`)로 접속 시, 가장 먼저 노출되는 "대문" 페이지여야
     한다.
   - 애플리케이션의 정체성을 보여주는 "프리미엄"한 디자인(비주얼, 로고)을
     포함해야 한다.
   - "Dashboard 입장" 버튼을 클릭하면 대시보드 페이지로 이동해야 한다.
2. **대시보드 페이지 (Migrated)**
   - 기존의 메인 대시보드 기능은 `/dashboard` 경로에서 제공되어야 한다.
   - 기존 대시보드의 모든 기능(차트, 실시간 데이터, 스냅샷 등)은 동일하게
     동작해야 한다.
3. **URL 구조**
   - `http://HOST:8000/` -> 홈 페이지
   - `http://HOST:8000/dashboard` -> 대시보드

### 2.2 비기능적 요구사항

1. **새로고침 지원**: `/dashboard` 경로에서 브라우저 새로고침(F5) 시 404 에러
   없이 대시보드가 다시 로드되어야 한다. (Backend SPA Fallback 지원)
2. **네트워크 접속**: 로컬(`127.0.0.1`) 뿐만 아니라 외부 IP(`192.168.x.x`)로
   접속 시에도 동일한 라우팅이 적용되어야 한다.

## 3. 아키텍처 (Architecture)

### 3.1 Frontend Routing

- **Library**: `react-router-dom` (Latest version)
- **Router**: `BrowserRouter`를 사용하여 History API 기반의 라우팅을 구현한다.
- **Structure**:
  ```tsx
  <BrowserRouter>
      <Routes>
          <Route path="/" element={<Home />} /> {/* 신규 홈 */}
          <Route path="/dashboard" element={<App />} /> {/* 기존 대시보드 */}
      </Routes>
  </BrowserRouter>;
  ```

### 3.2 Backend Configuration

- **Static Serving**: `backend/app.py`의 `serve_spa` 핸들러가 이미 SPA
  Fallback(`/{full_path:path}` -> `index.html`)을 지원하고 있으므로, 백엔드 로직
  변경 없이 프론트엔드 빌드 결과물만 교체하면 된다.

## 4. 데이터 모델 (Data Model)

- 본 작업은 UI 라우팅 구조 변경에 해당하므로, Backend DB 스키마나 데이터 모델의
  변경은 없다.

## 5. 테스트 전략 (Testing Strategy)

1. **로컬 라우팅 테스트**
   - 브라우저에서 `http://127.0.0.1:8000/` 접속 시 홈 페이지가 뜨는지 확인.
   - "Dashboard 입장" 클릭 시 `/dashboard`로 URL이 바뀌고 대시보드가 뜨는지
     확인.
2. **새로고침 테스트**
   - `/dashboard` 화면에서 F5 키를 눌러 404 없이 정상 로드되는지 확인.
3. **네트워크 테스트**
   - 다른 PC 또는 모바일에서 `http://192.168.0.7:8000/` 접속 시 홈 화면이
     노출되는지 확인.

---

**작성일**: 2026-01-14 **작성자**: Antigravity AI
