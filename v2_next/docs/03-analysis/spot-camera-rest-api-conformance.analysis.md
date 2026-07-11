# Gap Analysis: spot-camera-rest-api-conformance

> Date: 2026-07-11 | Design: docs/02-design/features/spot-camera-rest-api-conformance.design.md

---

## Match Rate: 92%

## Summary

설계의 런타임 항목 22개는 모두 구현됐다. 남은 2개 gap은 clean commit이
필요한 PyInstaller/NSIS 패키지 검증과 실장비 서버의 장시간 운영 관찰이다.
개발 컴퓨터에서 수행 가능한 정적 검사, 전체 health, production frontend
build, 단일 경로 API 및 완료 기반 UI 회귀 테스트는 통과했다.

## Implemented Items

- [x] 장비 URL은 `SPOT_IP`에서 `http://{SPOT_IP}/image.jpg`로만 생성된다.
- [x] `SPOT_IMAGE_URL`, `SPOT_LIVE_IMAGE_URL`, `imageurl`, `liveimageurl`
      런타임 override가 제거됐다.
- [x] 기존 설정 파일의 `imageurl` 및 `liveimageurl`은 저장/기동 시 제거된다.
- [x] 장비 응답은 JPEG signature로 검증되고 HTML·빈 body·비 JPEG는 거부된다.
- [x] backend image cache, stale response, alternate path, retry backoff 및 image
      prefetch가 제거됐다.
- [x] backend upstream 요청은 async lock으로 single-flight가 보장된다.
- [x] 성공한 공식 JPEG만 기존 evidence writer에 전달된다.
- [x] 앱 image route는 `GET /api/spot/image.jpg` 하나다.
- [x] 제거된 live/proxy route는 404를 반환한다.
- [x] route는 no-store JPEG 또는 404/502만 반환하며 stale 200은 없다.
- [x] `/api/spot/config.image_url`은 내부 단일 route를 반환한다.
- [x] frontend transport는 단일 route만 요청한다.
- [x] 35ms success delay, 500ms error retry 및 interval image polling이 제거됐다.
- [x] 첫 요청 후 표시 완료된 pending Blob만 다음 요청을 시작한다.
- [x] Blob URL identity guard가 늦게 도착한 다른 consumer의 load event를 무시한다.
- [x] display error는 재귀를 중단하고 explicit refresh만 허용한다.
- [x] Dashboard와 Settings가 동일 Blob URL과 동일 load/error handler를 사용한다.
- [x] image cache/backoff/stale/age 및 internal-temperature 결합 UI가 제거됐다.
- [x] JPEG 이외 범용 image format 허용이 backend/frontend/evidence 경로에서 제거됐다.
- [x] observability는 단일 route의 request, latency, success/failure만 기록한다.
- [x] API 및 운영 진단 문서가 단일 route로 갱신됐다.
- [x] 과거 live-image PDCA/QA 문서는 superseded 이력으로 명시됐다.
- [x] package에 포함되는 서버 QA script도 단일 route의 completion-driven 관찰로 교체됐다.

## Missing Items

- [ ] Dirty worktree에서 fail-closed 되는 build provenance 정책 때문에, clean commit
      기반 PyInstaller/NSIS package smoke는 아직 수행하지 않았다.
- [ ] 실장비가 있는 서버 컴퓨터에서 새 EXE를 실행한 15분 이상 PLC/Temperature/CSV/
      camera error queue 관찰은 아직 수행하지 않았다.

## Changed Items (Deviations from Design)

- [x] 설계는 기존 image evidence schema 보존만 요구했으나, 성공 upstream이 JPEG로
      고정됐으므로 evidence metadata detector도 JPEG만 허용하도록 더 엄격하게 정리했다.
- [x] 과거 URL key redaction은 외부에서 유입될 수 있는 legacy export payload 보호를
      위해 유지했다. 이는 URL 선택 runtime을 유지하는 것이 아니다.

## Validation Evidence

- `npm run health`: PASS
  - frontend typecheck, ESLint, 27 files / 180 tests
  - backend ruff, mypy, 462 tests
- `npm run build` in frontend: PASS
- focused backend SPOT/config tests: 67 passed, 6 subtests passed
- focused frontend camera/settings/image tests: 29 passed
- Python compile and `git diff --check`: PASS
- `scripts/qa_spot_image_server.ps1` PowerShell parse: PASS
- runtime source search: removed contracts 없음; legacy option 삭제 코드만 존재

## Recommendations

1. 변경을 검토한 뒤 clean commit을 생성한다.
2. clean commit에서 PyInstaller/NSIS package와 bundled provenance를 검증한다.
3. 서버 컴퓨터에 승인된 package를 설치하고 단일 route 및 error queue를 관찰한다.

## Next Steps

- [x] Runtime gap 수정 완료
- [ ] Clean package 검증
- [ ] Server device validation 후 completion report 확정
