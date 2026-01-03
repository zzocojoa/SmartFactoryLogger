# V2 UI 레이아웃 정렬/스냅 개선 리포트
작성일: 2026-01-01
목표: 드래그/리사이즈 후 무질서한 배치 방지와 격자감 제공

## 1. 문제 요약
- 카드 이동/크기 조절 후 배치가 흐트러짐.
- 스냅 기준이 불명확해 격자 정렬을 기대하기 어려움.
- 자동 재배치가 의도와 달라 안정감이 낮음.

## 2. 실무 관점 권장 접근
### 2.1 정렬/충돌 정책
- cols/rowHeight/margin 고정으로 스냅 단위 통일.
- 중첩 방지: preventCollision=true.
- allowOverlap=false 유지.
- compactType 명시로 재배치 방향 고정.
- 배치 보존 우선이면 compactType=null 고려.
- Scenes 기본 그리드(24 cols)와 배경 그리드(60 cols) 불일치를 해소해야 가로 스냅이 일관됨.
- 적용 위치: `v2_next/frontend/scripts/patch_grafana_scenes_grid.js` (npm run patch:scenes-grid).

### 2.2 크기 제약
- 카드별 minW/minH로 최소 크기 보장.
- 필요 시 maxW/maxH로 과도 확대 제한.
- 카드별 권장 비율을 템플릿으로 관리.

### 2.3 격자 시각화
- 배경에 미세한 점/선 그리드 적용.
- repeating-linear-gradient로 스냅 위치 암시.
- 대비는 5~8% 수준으로 낮게 적용.

### 2.4 배치 저장/복원
- SceneGridLayout 상태 구독으로 최신 레이아웃 맵 유지 후 저장 시 반영.
- 저장 위치: 서버/파일(`layout.json`).
- 슬롯 3개/이름 지정 저장 + 선택 복구 + 삭제 지원.
- 재접속 시 활성 슬롯 복원.
- `layout.backup.json`은 비상 복구 API(`/api/layout/restore`) 용도로 유지.

### 2.5 UX 실수 방지
- draggableHandle로 헤더 영역만 드래그 허용.
- draggableCancel로 버튼/입력 요소 드래그 차단.
- 배치 잠금/해제 토글 제공.

## 3. 권장 설정(React Grid Layout)
- 컨테이너: compactType, preventCollision, allowOverlap, isBounded
- 리사이즈: resizeHandles=['s','e','w','se']
- 카드 제약: minW/minH, 필요 시 maxW/maxH
- 저장: SceneGridLayout 상태 구독으로 최신 layouts 저장
- Scenes 내부 그리드 상수는 60 cols/20 row/4 margin으로 통일(패치 스크립트 적용)

## 4. 단계별 적용 계획
1) 정렬 정책 확정
2) 크기 제약 적용
3) 배치 저장/복원 적용
4) 격자 시각화 적용
5) 실수 방지 UX 도입

## 5. 검증 방법
- 10회 이상 드래그/리사이즈 후 배치 안정성 확인
- 재접속 시 레이아웃 유지 여부 확인
- 가로 스냅이 1칸 단위로 맞는지 확인(60 cols 기준)
- 최소/최대 크기 제한 동작 확인
- 배치 잠금 상태에서 이동 방지 확인
- 배치 잠금 상태에서 리사이즈 방지 확인

## 6. 결론
- 기본 드래그/리사이즈만으로는 부족.
- 정렬 정책과 충돌 방지는 필수.
- 크기 제약과 배치 저장도 필수.
- 격자 시각화 적용 시 사용성 개선.

