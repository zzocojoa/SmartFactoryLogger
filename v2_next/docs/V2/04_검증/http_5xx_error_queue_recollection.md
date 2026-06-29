# HTTP 5xx / Error Queue 재수집 검증

Date: 2026-06-29 KST

## 목적

운영 중 `/stats`의 HTTP 5xx 증가와 observability error queue FAIL을 route/source/status/type 기준으로 분리한다. 기존 sanitized zip에서 `raw_file_sha256.txt` path가 잘려 raw payload basename 대조가 제한된 문제를 피하기 위해, 재수집 산출물은 basename, relative path, full SHA-256, size를 모두 보존한다.

## 코드 기준 원인 분리 경로

- `/stats`
  - `window.http_5xx_count`: 최근 window의 전체 5xx 수
  - `polling.paths["/api/spot/live_image"].http_5xx_count`: SPOT live image route 5xx
  - `polling.paths["/api/spot/proxy_image"].http_5xx_count`: SPOT proxy image route 5xx
  - 각 polling path에는 `http_4xx_count`, `http_5xx_count`, `failure_count`, `success_count`, `stale_count`가 같이 들어간다.
- `/api/observability/errors`
  - 각 item은 `source`, `message`, `path`, `status_code`, `error_type`, `repeat`를 제공한다.
  - summary는 `source_repeat_counts`, `type_counts`, `status_counts`, `path_counts`, `route_status_counts`, `top_route_statuses`를 제공한다.
- backend error log
  - plain stderr/log formatter에서도 `Observability error recorded source=<source> status=<status> type=<type> path=<route>`를 남긴다.
  - 민감 detail은 log message에 포함하지 않고 structured `extra` field에만 유지한다.
- SPOT handler source 매핑
  - `/api/spot/live_image` 502/503: `source=spot_live_image`
  - `/api/spot/proxy_image` 502/503: `source=spot_proxy`
  - middleware fallback 5xx: `source=api`, `message=HTTP <status>`, `path=<route>`

## 재수집 명령

Backend가 기본 로컬 API base에서 실행 중일 때 60분 수집:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\collect_operational_observability.ps1 `
  -ApiBase <backend-api-base> `
  -Samples 60 `
  -IntervalSec 60 `
  -TimeoutSec 10 `
  -OutputRoot .\.tmp_operational_observability
```

산출물:

- `raw\sample_###_*.json`: 원본 HTTP response envelope. Git에 추가하지 않는다.
- `sanitized\operational_observability_summary.json`: 민감 detail을 제외한 stats/error 요약.
  - `analysis.observed_5xx_routes`: route별 최대 window 5xx, 관측 sample 범위.
  - `analysis.final_error_*_counts`: 마지막 error queue 기준 source/message/status/type/path 집계.
  - `analysis.final_error_route_status_counts`: 마지막 error queue 기준 route/status 조합 집계.
- `sanitized\raw_file_sha256.txt`: TSV, `basename`, `relative_path`, `sha256`, `size`.
- `sanitized\raw_file_sha256.csv`: 자동 검증용 CSV.
- `sanitized\raw_file_sha256.json`: 자동 검증용 JSON.
- `operational_observability_sanitized.zip`: sanitized 폴더만 포함한다.

스크립트 종료 stdout에는 다음 자체 검증 라인이 포함된다.

- `summary_json=<path>`
- `raw_hash_rows=<n>`
- `raw_hash_bad_rows=0`
- `observed_5xx_routes_count=<n>`
- `final_error_source_counts_count=<n>`
- `final_error_route_status_counts_count=<n>`

## Hash manifest 검증

스크립트 stdout에서 `raw_hash_bad_rows=0`이면 basename, relative path, full SHA-256, size의 기본 형식 검증이 통과한 것이다. 독립 검증이 필요하면 아래 명령을 실행한다.

```powershell
$csv = ".\.tmp_operational_observability\<session>\sanitized\raw_file_sha256.csv"
$rows = @(Import-Csv $csv)
$bad = @(
  $rows | Where-Object {
    [string]::IsNullOrWhiteSpace($_.basename) -or
    [string]::IsNullOrWhiteSpace($_.relative_path) -or
    $_.sha256.Length -ne 64 -or
    -not ($_.size -match '^\d+$')
  }
)
"rows=$($rows.Count) bad=$($bad.Count)"
```

기대값: `bad=0`.

## 기존 운영 zip 재확인

후속 확인에서 기존 운영 sanitized zip을 찾았고, 원본 파일은 수정하지 않고 zip entry만 읽었다.

확정 가능한 내용:

- sample: `sample_0000.json`부터 `sample_0058.json`까지 59개.
- `total_http_5xx_count`: 10에서 302로 증가.
- `errors.summary.queue_size`: 6에서 152로 증가.
- final `observability_snapshot_20260629_095059.json` 기준 error repeat 합계:
  - `source=api`: 302
  - `message=HTTP 503`: 226
  - `message=HTTP 502`: 76

확정 불가능한 내용:

- 기존 zip의 `stats.polling.paths`, `stats.window.top_paths`, `errors.items[].path`가 모두 `***REDACTED***`로 저장되어 route를 복원할 수 없다.
- `errors.items`에는 `status_code`와 `error_type` 필드가 없어서 status는 `message=HTTP <status>`에서만 추출된다.

따라서 기존 운영 증거로는 `source=api`와 `HTTP 502/503` 누적은 확정되지만, 어느 route가 5xx를 만들었는지는 미확정이다. 이 브랜치의 재수집 스크립트와 backend 변경은 route/source/status/type를 다음 운영 수집에서 직접 검증 가능하게 하기 위한 최소 수정이다.

## 추가 로그 복원 시도

운영 zip 주변의 같은 시간대 Desktop 로그 후보도 확인했다. `barrier.log`, `barrier.log.1`에서는 `HTTP 502`, `HTTP 503`, `/api/...` route 후보가 발견되지 않았다.

프로젝트 임시 backend stdout에는 SPOT image route의 502/503 access log가 존재한다. 재확인 시 route/status 후보는 `/api/spot/live_image 503`, `/api/spot/proxy_image 503`, `/api/spot/live_image 502`, `/api/spot/proxy_image 502` 순으로 집계됐다. 하지만 해당 파일은 timestamp가 없는 누적 stdout이고, exact status 파싱 기준 5xx access log 수가 기존 운영 zip의 `total_http_5xx_count=302`와 맞지 않는다. 따라서 이 파일은 SPOT image route가 5xx를 만들 수 있다는 참고 정황일 뿐, 기존 운영 zip의 route 확정 증거로 사용하지 않는다.

프로젝트 임시 backend stderr에는 기존 zip window와 겹치는 `Observability error recorded` 로그가 있으나, 기존 plain log formatter가 `source`, `path`, `status`, `type`를 메시지에 넣지 않아 route 복원이 불가능했다. 같은 window 기준 timestamp가 있는 observability event 수도 기존 운영 zip의 repeat 합계 302와 맞지 않아, stderr 역시 route 확정 증거로 사용하지 않는다.

따라서 현재 로컬 증거 세트에서 기존 운영 zip의 route를 복원할 수 있는 남은 근거는 없다. 다음 운영 중 재수집 산출물의 `analysis.observed_5xx_routes`와 `analysis.final_error_route_status_counts`가 route/source 확정의 기준 증거다.
