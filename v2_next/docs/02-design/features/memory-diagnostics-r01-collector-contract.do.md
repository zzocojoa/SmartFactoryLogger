# Memory Diagnostics R01 Collector Contract Do Checklist

## 1. Rule

- [ ] 이 feature의 Report가 완료되기 전에는 `memory-diagnostics-r02-plc-history`를 구현하지 않는다.
- [ ] 구현 전 관련 파일마다 bkit pre-write check를 통과한다.

## 2. Implementation

- [ ] `MemoryService`에 `_collector_runtime_state`를 추가한다.
- [ ] `_collector_latency_warn_ms = 250.0`을 추가한다.
- [ ] `_collector_stale_after_sec = 60.0`을 추가한다.
- [ ] `_run_collectors()`에서 collector 호출 latency를 측정한다.
- [ ] 정상 collector item에 `latency_ms`를 추가한다.
- [ ] 정상 collector item에 `status=ok|slow`를 추가한다.
- [ ] error collector item에 `status=error`를 추가한다.
- [ ] collector별 `last_ok_at`을 저장한다.
- [ ] collector별 `last_error_at`을 저장한다.
- [ ] collector별 `error_count`를 저장한다.
- [ ] collector별 `last_latency_ms`를 저장한다.
- [ ] collector별 `last_value`를 저장한다.
- [ ] collector별 `last_value_at`을 저장한다.
- [ ] stale 여부를 계산하고 item에 `stale`을 추가한다.
- [ ] item에 `source=backend`를 추가한다.
- [ ] hard timeout 대신 soft timeout과 previous cache reuse 정책을 구현한다.
- [ ] previous cache reuse item이 새 실행 결과와 구분되도록 status/note/source metadata를 설정한다.
- [ ] 기존 collector item field를 유지한다.
- [ ] frontend type에 optional field를 추가한다.
- [ ] MemorySection에 latency/status/stale 표시를 추가한다.
- [ ] 구버전 payload fallback을 유지한다.

## 3. Tests

- [ ] collector exception isolation test를 추가한다.
- [ ] collector latency recording test를 추가한다.
- [ ] slow status threshold test를 추가한다.
- [ ] stale state test를 추가한다.
- [ ] previous cache reuse test를 추가한다.
- [ ] old payload compatibility rendering test를 추가한다.

## 4. Validation

- [ ] targeted backend MemoryService tests를 실행한다.
- [ ] frontend typecheck를 실행한다.
- [ ] `npm run health`를 실행한다.
- [ ] `git diff --check`를 실행한다.
- [ ] gstack review를 실행하거나 equivalent pre-landing review를 남긴다.

## 5. PDCA Close Gate

- [ ] `docs/03-analysis/memory-diagnostics-r01-collector-contract.analysis.md`를 작성한다.
- [ ] bkit analyze match rate가 90% 이상이다.
- [ ] gap이 있으면 iterate 후 재분석한다.
- [ ] `docs/04-report/memory-diagnostics-r01-collector-contract.report.md`를 작성한다.
- [ ] `.pdca-status.json`에서 이 feature를 report/completed 상태로 갱신한다.
