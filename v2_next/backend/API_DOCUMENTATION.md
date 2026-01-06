# Smart Factory Logger V2 - 백엔드 API 문서

> **버전:** 2.1.0\
> **기본 URL:** `http://localhost:8000` (기본값)\
> **프레임워크:** FastAPI

---

## 목차

1. [핵심 데이터 API (Core Data API)](#core-data-api)
2. [상태 및 모니터링 (Health & Monitoring)](#health--monitoring)
3. [관측 가능성 (Observability)](#observability)
4. [설정 관리 (Configuration Management)](#configuration-management)
5. [레이아웃 관리 (Layout Management)](#layout-management)
6. [제어 작업 (Control Operations)](#control-operations)
7. [로깅 (Logging)](#logging)
8. [검증 (Verification)](#verification)
9. [SPOT 카메라 (SPOT Camera)](#spot-camera)
10. [시스템 (System)](#system)

---

## Core Data API

### GET `/api/data`

PLC 서비스에서 최신 공장 데이터 스냅샷을 가져옵니다.

**응답 모델:** `FactoryData`

**응답:**

```json
{
  "timestamp": 1704528000.0,
  "status": {...},
  "process": {...},
  "environment": {...},
  ...
}
```

**사용법:**

```javascript
const response = await fetch("http://localhost:8000/api/data");
const data = await response.json();
```

---

## Health & Monitoring

### GET `/health`

시스템 상태 및 서비스 상태를 가져옵니다.

**응답:**

```json
{
  "running": true,
  "plc_connected": true,
  "last_update": 1704528000.0,
  ...
}
```

### GET `/stats`

백엔드 서버 통계를 가져옵니다.

**응답:**

```json
{
  "uptime_sec": 3600,
  "total_requests": 1234,
  "total_errors": 5,
  "avg_latency_ms": 12.5,
  ...
}
```

---

## Observability

### GET `/api/observability/errors`

기록된 모든 에러를 요약 통계와 함께 나열합니다.

**쿼리 파라미터:**

- `limit` (int, 선택사항): 반환할 최대 에러 수 (기본값: 50)

**응답:**

```json
{
  "items": [
    {
      "time": 1704528000.0,
      "type": "connection",
      "message": "PLC timeout",
      "detail": "...",
      ...
    }
  ],
  "summary": {
    "total": 10,
    "by_type": {...}
  }
}
```

### POST `/api/observability/errors/clear`

기록된 모든 에러를 지웁니다.

**응답:**

```json
{
    "ok": true
}
```

### POST `/api/observability/export`

상태, 통계, 에러를 포함한 관측 가능성 스냅샷을 내보냅니다.

**요청 본문:**

```json
{
    "include_errors": true,
    "front_errors": [
        {
            "time": 1704528000,
            "type": "render_error",
            "message": "Chart failed",
            "detail": "...",
            "stack": "..."
        }
    ],
    "tolerance_abs": { "Speed": 0.5 },
    "tolerance_pct": { "Press": 5.0 }
}
```

**응답:**

```json
{
    "ok": true,
    "path": "C:\\logs\\observability_snapshot_20260106_162530.json",
    "size": 12345
}
```

### POST `/api/observability/export/open-file`

가장 최근에 내보낸 관측 가능성 파일을 엽니다.

**응답:**

```json
{
    "ok": true,
    "path": "C:\\logs\\observability_snapshot_20260106_162530.json"
}
```

### POST `/api/observability/export/open-folder`

내보낸 관측 가능성 파일이 있는 폴더를 엽니다.

**응답:**

```json
{
    "ok": true,
    "path": "C:\\logs"
}
```

### GET `/api/observability/export/latest`

가장 최근에 내보낸 관측 가능성 스냅샷에 대한 정보를 가져옵니다.

**응답:**

```json
{
    "path": "C:\\logs\\observability_snapshot_20260106_162530.json",
    "updated_at": 1704528000.0
}
```

---

## Configuration Management

### GET `/api/config`

현재 설정 스냅샷을 가져옵니다.

**응답:**

```json
{
  "extruder_ip": "192.168.1.100",
  "extruder_port": 8501,
  "interval_sec": 1.0,
  "thresholds": {...},
  "log_path": "C:\\logs",
  ...
}
```

### GET `/api/config/notice`

사용자 정의 공지/메모 내용을 가져옵니다.

**응답:**

```json
{
    "content": "현재 교대 근무 지침..."
}
```

### POST `/api/config/notice`

사용자 정의 공지/메모 내용을 저장합니다.

**요청 본문:**

```json
{
    "content": "업데이트된 교대 근무 지침..."
}
```

**응답:**

```json
{
    "status": "ok"
}
```

### POST `/api/config/override`

오버라이드 모드를 토글합니다 (비밀번호 필요).

**요청 본문:**

```json
{
    "enabled": true,
    "password": "admin123",
    "actor": "operator_name"
}
```

**응답:**

```json
{
    "ok": true,
    "override_enabled": true
}
```

**에러 응답 (403):**

```json
{
    "detail": "비밀번호가 올바르지 않습니다"
}
```

### POST `/api/config/restore-defaults`

설정을 공장 초기값으로 복원합니다.

**응답:**

```json
{
    "ok": true,
    "message": "기본값으로 복원됨"
}
```

### POST `/api/config/restore-backup`

백업 파일에서 설정을 복원합니다.

**응답:**

```json
{
    "ok": true,
    "message": "백업에서 복원됨"
}
```

**에러 응답 (404):**

```json
{
    "detail": "백업 파일을 찾을 수 없습니다"
}
```

### POST `/api/config/pending/apply`

보류 중인 설정 변경 사항을 적용합니다.

**응답:**

```json
{
    "ok": true,
    "message": "보류 중인 변경 사항 적용됨"
}
```

### POST `/api/config/pending/clear`

보류 중인 설정 변경 사항을 지웁니다.

**응답:**

```json
{
    "ok": true,
    "message": "보류 중인 변경 사항 초기화됨"
}
```

### GET `/api/config/central-status`

중앙 설정 서버 상태를 가져옵니다.

**응답:**

```json
{
    "connected": true,
    "last_sync": 1704528000.0,
    "url": "http://central-server:9000"
}
```

### POST `/api/config/sync`

중앙 설정 서버와 즉시 동기화를 트리거합니다.

**응답:**

```json
{
    "ok": true,
    "synced": true
}
```

---

## Layout Management

### GET `/api/layout`

활성 대시보드 레이아웃을 가져옵니다.

**응답:**

```json
{
  "layout": {
    "widget-1": {
      "x": 0,
      "y": 0,
      "width": 20,
      "height": 6,
      "type": "notice",
      "title": "알림"
    },
    ...
  },
  "cols": 40,
  "version": "1.0"
}
```

**에러 응답 (404):**

```json
{
    "detail": "레이아웃을 찾을 수 없습니다"
}
```

### GET `/api/layout/meta`

레이아웃 메타데이터를 가져옵니다.

**응답:**

```json
{
    "last_modified": 1704528000.0,
    "version": "1.0",
    "cols": 40
}
```

### GET `/api/layouts`

저장된 모든 레이아웃 슬롯을 나열합니다.

**응답:**

```json
{
  "slots": [
    {
      "slot_id": "layout-001",
      "name": "주간 근무 레이아웃",
      "created_at": 1704528000.0,
      "version": "1.0"
    },
    ...
  ]
}
```

### POST `/api/layout`

현재 활성 레이아웃을 저장합니다.

**요청 본문:**

```json
{
  "layout": {
    "widget-1": {...},
    ...
  },
  "cols": 40,
  "version": "1.0"
}
```

**응답:**

```json
{
    "ok": true,
    "slot_id": "layout-active"
}
```

### POST `/api/layouts`

이름이 지정된 레이아웃 슬롯을 저장합니다.

**요청 본문:**

```json
{
  "name": "야간 근무 레이아웃",
  "layout": {...},
  "cols": 40,
  "version": "1.0",
  "slot_id": "layout-002"
}
```

**응답:**

```json
{
    "ok": true,
    "slot_id": "layout-002"
}
```

### POST `/api/layouts/restore`

저장된 레이아웃 슬롯을 복원합니다.

**요청 본문:**

```json
{
    "slot_id": "layout-002"
}
```

**응답:**

```json
{
    "ok": true,
    "message": "레이아웃 복원됨"
}
```

### POST `/api/layouts/delete`

저장된 레이아웃 슬롯을 삭제합니다.

**요청 본문:**

```json
{
    "slot_id": "layout-002"
}
```

**응답:**

```json
{
    "ok": true,
    "message": "레이아웃 삭제됨"
}
```

### POST `/api/layout/restore`

자동 백업에서 레이아웃을 복원합니다.

**응답:**

```json
{
    "ok": true,
    "message": "백업에서 레이아웃 복원됨"
}
```

---

## Control Operations

### POST `/api/control/reconnect`

PLC 서비스에 다시 연결합니다.

**응답:**

```json
{
    "ok": true,
    "running": true
}
```

### POST `/api/control/test-connection`

설정된 장치에 대한 연결을 테스트합니다.

**요청 본문:**

```json
{
    "extruder": {
        "ip": "192.168.1.100",
        "port": 8501
    },
    "ls_plc": {
        "ip": "192.168.1.101",
        "port": 8502
    },
    "spot": {
        "url": "http://192.168.1.102/image.jpg"
    }
}
```

**응답:**

```json
{
    "results": {
        "extruder": {
            "connected": true,
            "latency_ms": 25,
            "message": "OK"
        },
        "ls_plc": {
            "connected": false,
            "latency_ms": 0,
            "message": "연결 시간 초과"
        },
        "spot": {
            "connected": true,
            "latency_ms": 150,
            "status_code": 200
        }
    }
}
```

### POST `/api/control/path-health`

파일 시스템 경로의 상태와 액세스 가능성을 확인합니다.

**요청 본문:**

```json
{
    "paths": [
        {
            "key": "log_path",
            "path": "C:\\Logs\\Factory"
        },
        {
            "key": "data_path",
            "path": "\\\\NAS\\Data"
        }
    ]
}
```

**응답:**

```json
{
    "results": {
        "log_path": {
            "status": "OK",
            "exists": true,
            "writable": true,
            "is_dir": true,
            "is_network": false,
            "latency_ms": 5,
            "message": "OK"
        },
        "data_path": {
            "status": "WARN",
            "exists": true,
            "writable": true,
            "is_dir": true,
            "is_network": true,
            "latency_ms": 250,
            "message": "네트워크 경로 지연"
        }
    }
}
```

### POST `/api/control/path-create`

디렉토리 경로를 생성합니다.

**요청 본문:**

```json
{
    "path": "C:\\Logs\\NewFolder"
}
```

**응답:**

```json
{
    "ok": true,
    "message": "생성됨"
}
```

### POST `/api/control/snapshot`

차트/대시보드 스냅샷을 저장합니다.

**요청 본문:**

```json
{
    "image_base64": "data:image/png;base64,iVBORw0KGgo...",
    "name": "morning_production",
    "format": "png"
}
```

**응답:**

```json
{
    "ok": true,
    "path": "C:\\Snapshots\\morning_production_20260106_162530.png",
    "filename": "morning_production_20260106_162530.png"
}
```

### POST `/api/control/shutdown`

백엔드 서버를 정상적으로 종료합니다.

**요청 본문:**

```json
{
    "reason": "유지보수 기간"
}
```

**응답:**

```json
{
    "ok": true,
    "message": "종료 시작됨"
}
```

---

## Logging

### GET `/api/logs/comm-metrics`

통신 지표 로그 파일 경로를 가져옵니다.

**응답:**

```json
{
    "path": "C:\\Logs\\comm_metrics_20260106.log"
}
```

### POST `/api/logs/comm-metrics/open`

통신 지표 로그 폴더를 엽니다.

**응답:**

```json
{
    "ok": true,
    "path": "C:\\Logs"
}
```

### POST `/api/logs/comm-metrics/open-file`

통신 지표 로그 파일을 엽니다.

**응답:**

```json
{
    "ok": true,
    "path": "C:\\Logs\\comm_metrics_20260106.log"
}
```

---

## Verification

### POST `/api/verify/compare`

현재 PLC 데이터와 참조 CSV 파일을 비교합니다.

**요청 본문:**

```json
{
    "reference_csv_path": "C:\\References\\golden_sample.csv",
    "sample_count": 50,
    "interval_sec": 1.0,
    "tolerance_abs": {
        "Speed": 0.5,
        "Press": 1.0
    },
    "tolerance_pct": {
        "Temp_F": 2.0,
        "Temp_B": 2.0
    }
}
```

**응답:**

```json
{
    "ok": true,
    "match": true,
    "samples_collected": 50,
    "differences": [],
    "summary": "모든 샘플이 허용 오차 내에 있음"
}
```

**에러 응답 (404):**

```json
{
    "detail": "참조 파일을 찾을 수 없습니다"
}
```

---

## SPOT Camera

### GET `/api/spot/config`

SPOT 카메라 위젯 설정을 가져옵니다.

**응답:**

```json
{
    "image_url": "http://192.168.1.102/image.jpg",
    "refresh_interval": 1000,
    "crosshair_x": 50,
    "crosshair_y": 50,
    "crosshair_color": "#00FF00",
    "crosshair_thickness": 2,
    "crosshair_size": 20,
    "crosshair_gap": 5,
    "widget_width": 640,
    "widget_height": 480,
    "focus_step": 10,
    "focus_enabled": true
}
```

### POST `/api/spot/focus`

SPOT 카메라 초점 액추에이터를 조정합니다.

**쿼리 파라미터:**

- `steps` (int): 이동할 단계 수 (+/-로 방향 설정)

**예시:**

```
POST /api/spot/focus?steps=10
```

**응답:**

```json
{
    "ok": true,
    "moved": 10,
    "message": "초점 조정됨"
}
```

### GET `/api/spot/proxy_image`

원격 클라이언트를 위해 SPOT 카메라 이미지를 프록시합니다 (CORS 이슈 방지).

**응답:**

- **Content-Type:** `image/jpeg`
- **Body:** 바이너리 이미지 데이터

**에러 응답 (404):**

```json
{
    "detail": "SPOT URL이 설정되지 않음"
}
```

**에러 응답 (502):**

```json
{
    "detail": "업스트림 이미지 가져오기 실패: 타임아웃"
}
```

---

## System

### GET `/`

루트 엔드포인트. 프론트엔드 대시보드 또는 API 정보를 제공합니다.

**응답 (프론트엔드 빌드 시):**

- HTML 페이지 (대시보드)

**응답 (프론트엔드 없을 시):**

```json
{
    "system": "Smart Factory Logger V2",
    "status": "Online",
    "backend": "FastAPI with Service Layer (Frontend missing)"
}
```

### GET `/{full_path:path}`

프론트엔드 정적 파일을 제공하기 위한 캐치올(catch-all) 라우트입니다.

**사용법:** `dist` 폴더의 번들링된 React 프론트엔드를 자동으로 제공합니다.

---

## Error Handling

모든 엔드포인트는 표준 HTTP 상태 코드를 따릅니다:

| 상태 코드 | 의미                                                 |
| --------- | ---------------------------------------------------- |
| **200**   | 성공 (Success)                                       |
| **400**   | 잘못된 요청 (Bad Request - 유효하지 않은 파라미터)   |
| **403**   | 금지됨 (Forbidden - 권한 없음, 잘못된 비밀번호)      |
| **404**   | 찾을 수 없음 (Not Found - 리소스 없음)               |
| **500**   | 내부 서버 오류 (Internal Server Error)               |
| **502**   | 불량 게이트웨이 (Bad Gateway - 업스트림 서비스 실패) |

**에러 응답 형식:**

```json
{
    "detail": "무엇이 잘못되었는지 설명하는 에러 메시지"
}
```

---

## Authentication

현재 API는 토큰 기반 인증을 구현하지 않습니다. 오버라이드 토글이나 설정 복원과
같은 일부 작업은 요청 본문에 비밀번호 확인이 필요합니다.

---

## CORS

API는 모든 오리진(`allow_origins=["*"]`)에 대해 CORS가 활성화되어 있어 개발 중
모든 도메인에서 프론트엔드 접근이 가능합니다.

---

## Logging

모든 API 요청은 다음과 함께 기록됩니다:

- 클라이언트 IP 주소
- 요청 메서드 및 경로
- 응답 상태 코드
- 요청 지연 시간 (밀리초)

로그 저장 위치:

- `system.log`: 일반 애플리케이션 로그
- `crash.log`: 처리되지 않은 예외
- `comm_metrics_YYYYMMDD.log`: 통신 지표

---

## Base Configuration

기본 백엔드 서버 설정:

```python
HOST = "0.0.0.0"
PORT = 8000
```

시작 명령어:

```bash
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

---

## Notes

- 모든 타임스탬프는 Unix 에포크 초 (float) 단위입니다.
- 경로는 절대 윈도우 경로입니다 (예: `C:\\Logs\\...`).
- 네트워크 경로는 UNC 표기법을 사용합니다 (예: `\\\\NAS\\Share`).
- 이미지 데이터는 선택적 데이터 URI 접두사가 있는 base64 인코딩입니다.
- 레이아웃 위젯 위치는 그리드 좌표 (x, y, width, height)를 사용합니다.

---

## API Versioning

현재 버전: **2.1.0**

API 버전은 FastAPI 앱 정의에 지정되어 있으며 `/docs`의 OpenAPI 문서에서 확인할
수 있습니다.
