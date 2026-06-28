# Memory Diagnostics R06 Leak Slope Do Checklist

## 1. Rule

- [ ] `memory-diagnostics-r05-budget-severity` Report 완료를 확인한다.
- [ ] 완료 전에는 `memory-diagnostics-r07-gc-snapshot`을 구현하지 않는다.

## 2. Implementation

- [ ] `_calc_slope_bytes_per_min()`을 추가한다.
- [ ] monotonic ratio 계산 helper를 추가한다.
- [ ] process history에서 `rss_bytes` series를 만든다.
- [ ] process history에서 `uss_bytes` series를 만든다.
- [ ] process history에서 `private_bytes` series를 만든다.
- [ ] collector history에서 name별 bytes series를 만든다.
- [ ] 최소 샘플 미달 시 빈 result를 반환한다.
- [ ] slope threshold를 budget과 연결한다.
- [ ] baseline 대비 20% 증가 조건을 적용한다.
- [ ] `self._latest_leak_suspects`를 추가한다.
- [ ] `_apply_snapshot()` 이후 trend analysis를 호출한다.
- [ ] `/api/memory/details`에 `leak_suspects`를 추가한다.
- [ ] UI에 누수 의심 섹션을 추가한다.
- [ ] UI 문구에서 leak 확정 표현을 사용하지 않는다.

## 3. Tests

- [ ] slope helper test를 추가한다.
- [ ] monotonic growth detected test를 추가한다.
- [ ] spike false-positive 방지 test를 추가한다.
- [ ] insufficient samples test를 추가한다.
- [ ] frontend leak suspect rendering test를 추가한다.

## 4. Validation

- [ ] targeted trend analysis tests를 실행한다.
- [ ] frontend tests를 실행한다.
- [ ] `npm run health`를 실행한다.
- [ ] `git diff --check`를 실행한다.

## 5. PDCA Close Gate

- [ ] analysis 문서를 작성한다.
- [ ] bkit analyze match rate가 90% 이상이다.
- [ ] iterate 필요 시 재분석한다.
- [ ] report 문서를 작성한다.
- [ ] 다음 feature 시작 가능 상태로 status를 갱신한다.

