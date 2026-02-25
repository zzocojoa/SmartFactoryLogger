# Domain-Driven Design (DDD) Architecture Guide

본 문서는 `SmartFactoryLogger v2_next` 프로젝트에 적용된 **Domain-Driven Design
(DDD)** 기반의 폴더 및 파일 구조 명세서입니다. 기존의 기능 중심(레이어드)
아키텍처에서 비즈니스 도메인(관심사) 중심의 아키텍처로 리팩토링되어 유지보수성과
확장성을 극대화했습니다.

---

## 🏗️ 1. Backend Architecture (FastAPI)

백엔드는 `backend/` 디렉토리 하위에 위치하며, 각 비즈니스 도메인별로 폴더가
분리되어 응집도를 높였습니다.

```text
backend/
├── app.py                         # FastAPI 메인 엔트리포인트 (앱 초기화, 라우터 등록)
├── Base/                          # 프로젝트 공통 기반 모듈 (의존성 최소화)
│   ├── Base_Database.py           # DB 연결, 세션 관리 등 코어 데이터베이스 로직
│   └── Base_Config.py             # 전역 환경변수(env) 및 기본 설정 로드
│
├── Api/                           # 중앙 라우팅 및 외부 API 노출 레이어
│   ├── Api_Router.py              # 프론트엔드용 통합 비즈니스 데이터 라우터
│   └── Api_AITools.py             # AI 챗봇용 도메인 툴(Functions) 통합 및 스키마 제공 모듈
│
├── FacilityData/                  # [도메인] 현장 설비(PLC/Sensor) 원시 데이터 수집 및 처리
│   ├── FacilityData_Logic_PLC.py  # 모의/실제 PLC 통신 로직 및 데이터 읽기
│   ├── FacilityData_Logic_Store.py# 수집된 설비 데이터의 인메모리 저장소 관리
│   ├── FacilityData_Models.py     # 설비 관련 Pydantic DTO 스키마
│   └── FacilityData_AITool.py     # AI Agent가 실행할 설비 조회 Tool Call 래퍼
│
├── MESSync/                       # [도메인] MES 시스템 동기화 및 페이지 크롤링/브릿지 처리
│   ├── MESSync_Logic_Scheduler.py # 백그라운드 MES 데이터 수집 스케줄러 (Playwright/Request)
│   ├── MESSync_AITool.py          # AI Agent가 스케줄러 상태 확인 및 강제 트리거하는 Tool Call 래퍼
│   ├── MESSync_Router.py          # MES 전용 별도 API 엔드포인트
│   └── scripts/                   # MES 인증 처리, 캡챠 풀이 등 보조 스크립트 모음
│
├── Configuration/                 # [도메인] 사용자 설정, 알람 임계치 설정 관리
│   ├── Configuration_Logic_*.py   # 시스템/설비별 설정 로드 및 업데이트 코어 로직
│   └── Configuration_AITool.py    # AI Agent용 시스템 환경설정 조회/수정 Tool Call 래퍼
│
└── Observability/                 # [도메인] 백엔드 자체 헬스체크 및 리소스 모니터링
    ├── Observability_Logic_*.py   # CPU, 메모리, 지연시간 모니터링 인터페이스
    ├── log/                       # 앱 구동 로그 (에러, 런타임 로그) 파일 및 로테이션 관리
    └── Observability_AITool.py    # AI Agent 전용 시스템 상태 요약 및 조회 Tool Call
```

### 💡 Backend 특징 요약

1. **각 도메인 내 로직 독립**: 모든 도메인은 `Context`를 공유하지 않도록
   느슨하게 결합되어 있으며, 도메인 내부의 `_Logic_` 파일들이 해당 영역을
   캡슐화합니다.
2. **AI Tool 네이티브 통합**: 백엔드 내 모든 주요 도메인들은 `_AITool.py` 모듈을
   소유합니다. 각 모듈은 LLM이 인식 가능한 `TOOLS_SCHEMA`와 이를 받아 실행하는
   `execute_tool()` 함수를 노출하여 `Api_AITools`가 중앙에서 조립합니다.

---

## 🎨 2. Frontend Architecture (React + Vite)

프론트엔드는 `frontend/src/` 디렉토리 하위에 위치하며, 도메인 관점의 폴더링으로
컴포넌트, 상태(State), 로직을 묶었습니다.

```text
frontend/
├── index.html                 # React 애플리케이션 진입 HTML
├── src/
│   ├── App.tsx                # 최상위 컴포넌트, 화면 레이아웃 스캐폴딩 
│   ├── index.css              # 글로벌 Tailwind 기반 및 CSS 변수 테마 설정
│   │
│   ├── domain/                # 🧩 도메인 단위로 분리된 주요 기능 디렉토리
│   │   ├── Configuration/     # 시스템 / 타임시리즈 환경 설정 도메인
│   │   │   ├── components/    # 설정 모달, 드롭다운 등 연관 컴포넌트
│   │   │   └── context/       # 설정 전용 React Context 
│   │   │
│   │   ├── FacilityData/      # PLC 등 라이브 차트 및 데이터 시각화 도메인
│   │   │   ├── components/    # TimeSeriesWidget, Gauge, Heatmap 등 시각화 패널
│   │   │   └── hooks/         # 실시간 데이터 스트리밍(SSE/Short Polling) 처리 훅
│   │   │
│   │   ├── MESSync/           # 백그라운드 MES 스케줄링 현황 모니터링 도메인
│   │   │   ├── components/    # 동기화 상태 배지, 마지막 수집 시간 패널
│   │   │   └── api/           # MES 관련 데이터 Fetch 로직
│   │   │
│   │   └── Observability/     # 프론트엔드/백엔드 알람 및 알림 모니터링
│   │       ├── components/    # Notification 리스트, 에러 스낵바
│   │       └── context/       # 글로벌 에러 모니터링 메니저
│   │
│   ├── AI/                    # 🤖 AI 챗봇 시스템 (단독 도메인)
│   │   ├── components/        
│   │   │   ├── AIChatbot.tsx  # 글래스모피즘(Glassmorphism) 기반 플로팅 챗봇 UI 메인
│   │   │   └── ChatMessage.tsx# Markdown 기반 LLM 답변 / 로딩 상태 렌더러
│   │   ├── hooks/
│   │   │   └── useAIAgent.ts  # 멀티턴(Multi-turn) 대화 흐름 제어, API 툴 호출 실행 컨텍스트
│   │   └── api/
│   │       └── ai_service.ts  # 백엔드 Tool Schema 획득 및 OpenAI 직접 통신 Axios 래퍼
│   │
│   └── shared/                # 🔗 여러 도메인에서 공통으로 재사용되는 유틸 모음
│       ├── components/        # 버튼, 모달 래퍼(CustomDialog), 로딩 스피너 등
│       ├── hooks/             # 커스텀 이벤트 버스, 테마 제어(Dark/Light) 훅
│       ├── constants/         # UI 텍스트(uiText.ts), 하드코딩된 레이블 상수 매핑
│       └── api/               # 기본 Axios 인스턴스 클라이언트 구성 (client.ts)
```

### 💡 Frontend 특징 요약

1. **도메인 응집성 향상**: 기존에 거대한 하나의 App에 몰려있던 로직들을 각
   도메인(`Configuration`, `FacilityData`) 내의 `hooks` 및 `context`로 이동하여
   단일 책임 원칙을 적용했습니다.
2. **단독 AI 시스템 레이어 (`AI/`)**: 기존 UI에 침범하지 않는 자연스러운 확장을
   위해 Chatbot은 별도의 폴더(`AI/`)로 분리되었습니다. 뷰(components),
   제어(hooks), 통신(api) 영역을 완전히 분리하여 향후 확장(음성 인식 등)이
   용이하도록 설계되었습니다.
3. **App.tsx 경량화**: `App.tsx`는 이제 라우팅과 레이아웃 배치, 공통 Context
   Provider 감싸기(DI) 등 최적의 책임을 가지며 복잡한 연산은 개별 하위
   컴포넌트로 위임되었습니다.
