# 설정 UI 7단계: 저장 경로 검증 상세 설계

## 1. 목표
- 로그/스냅샷 저장 경로가 유효/접근 가능/쓰기 가능한지 즉시 확인한다.
- NAS(Z:) 사용 시 연결 상태와 권한 문제를 사전에 감지한다.
- 잘못된 경로로 인해 데이터가 누락되지 않도록 저장 전 차단/경고를 제공한다.

## 2. 적용 범위
- 대상 필드: `Log Path`, `Snapshot Path`
- 환경: Windows 현장 PC, NAS(Z:) 매핑 사용 가능

## 3. 상태 모델(경로 상태)
- `OK`: 존재 + 쓰기 가능
- `WARN`: 존재하지 않음(생성 가능), 네트워크 경로 지연
- `ERROR`: 접근 불가/권한 없음/경로 형식 오류
- `UNKNOWN`: 확인 중/검증 실패

## 4. UI 구성
### 4.1 저장 설정 섹션 하단에 경로 상태 카드 추가
- 항목: Log Path, Snapshot Path
- 표시 요소:
  - 상태 배지(OK/WARN/ERROR)
  - 최근 검사 시각
  - 세부 메시지(예: "쓰기 권한 없음")
  - `검사` 버튼(수동 재검사)
  - `폴더 생성` 버튼(WARN 상태일 때만)
  - NAS 배지(Z:) 감지 시 표시

### 4.2 경로 입력 필드 하이라이트
- WARN/ERROR 시 경로 입력 필드에 강조 테두리 표시
- 오류 메시지를 바로 아래에 표시

## 5. 검증 로직
### 5.1 프론트엔드 트리거
- 모달 오픈 시: 즉시 검사 실행
- 입력 변경 시: 500ms 디바운스 후 검사
- 저장 버튼 클릭 시: 재검사 후 통과 시 저장

### 5.2 백엔드 검사 항목
- 경로 문자열 유효성(Windows/UNC 형식)
- 존재 여부(`exists`)
- 디렉터리 여부(`is_dir`)
- 쓰기 가능(`writable`: temp 파일 생성 후 삭제)
- 네트워크 드라이브 여부(`is_network_drive`)
- NAS 지연 감지(쓰기 테스트 소요 시간 기준)

## 6. 백엔드 API 설계(신규)
### 6.1 검사 API
- `POST /api/control/path-health`
- Request
```json
{
  "paths": [
    {"key": "log", "path": "C:\\Logs"},
    {"key": "snapshot", "path": "Z:\\Snapshots"}
  ]
}
```
- Response
```json
{
  "results": {
    "log": {
      "status": "OK",
      "exists": true,
      "writable": true,
      "is_dir": true,
      "is_network": false,
      "latency_ms": 12,
      "message": "OK"
    },
    "snapshot": {
      "status": "WARN",
      "exists": false,
      "writable": false,
      "is_dir": false,
      "is_network": true,
      "latency_ms": 140,
      "message": "경로 없음(생성 가능)"
    }
  }
}
```

### 6.2 경로 생성 API(선택)
- `POST /api/control/path-create`
- Request
```json
{"path": "Z:\\Snapshots"}
```
- Response
```json
{"ok": true, "message": "created"}
```

## 7. UX 정책
- `ERROR`가 하나라도 있으면 저장 버튼 비활성화
- `WARN` 상태는 저장 가능하나, 저장 전 확인 다이얼로그 표시
- NAS(Z:) 경로는 별도 배지 표시 + 네트워크 연결 안내 문구 제공
- 경로 검사 실패 시 기본 저장 경로(AppData)로 대체될 수 있음 안내

## 8. 에러 메시지 가이드
- "경로가 존재하지 않습니다. 생성 후 저장하세요."
- "쓰기 권한이 없습니다. 관리자 권한을 확인하세요."
- "네트워크 드라이브가 연결되어 있지 않습니다."
- "경로 형식이 올바르지 않습니다."

## 9. 수용 기준(AC)
- 저장 전 검사에서 ERROR가 있으면 저장 불가
- WARN은 사용자 확인 후 저장 가능
- NAS 경로는 배지 표시 및 지연 감지
- 경로 생성 버튼이 존재하며 성공/실패가 표시됨

## 10. 테스트 케이스
- 존재하는 로컬 경로 → OK
- 존재하지 않는 로컬 경로 → WARN(생성 가능)
- 읽기 전용 경로 → ERROR
- Z: 매핑 해제 상태 → ERROR
- Z: 매핑 정상 + 쓰기 가능 → OK
- UNC 경로 → OK 또는 WARN(지연)
