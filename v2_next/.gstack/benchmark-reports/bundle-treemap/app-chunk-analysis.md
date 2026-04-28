# App chunk analysis

## 측정 환경

- 프로젝트: `v2_next`
- 브랜치: `codex/benchmark-dashboard-performance`
- Frontend: `frontend`
- Vite: `7.3.0`
- 빌드 명령:
  - `npm run build`, 성공
  - `npm run build -- --sourcemap`, 성공했지만 이 Windows/npm 실행에서는 `.map` 파일 미생성
  - `npx vite build --sourcemap`, 성공 및 최종 분석에 사용
- 변환 모듈 수: `6,160`
- 코드 수정 여부: 없음

## 현재 App chunk 크기

| 항목 | 값 |
|---|---:|
| App chunk | `App-BAswA52Z.js` |
| App chunk bytes | 8,545,720 B |
| App chunk KiB | 8,345.43 KiB |
| App chunk MiB | 8.15 MiB |
| gzip bytes | 2,270,849 B |
| gzip KiB | 2,217.63 KiB |
| source map | `App-BAswA52Z.js.map` |
| source map size | 29.88 MiB |
| source count | 3,036 |
| sourcesContent count | 3,036 |
| mapped coverage | 99.77% |
| unmapped bytes | 20,013 B |

## 분석 방법

1. `npm run build`로 현재 chunk 이름과 크기를 확인했다.
2. `npm run build -- --sourcemap`는 성공했지만 map 파일을 만들지 않아, `npx vite build --sourcemap` 산출물을 분석 기준으로 사용했다.
3. `App-BAswA52Z.js.map`의 generated line/column mapping을 원본 source path별 byte 범위로 환산했다.
4. source path를 카테고리 규칙에 매핑해 MB/KiB 단위로 합산했다.
5. `frontend/src`에는 Monaco 직접 import가 없고, `@grafana/ui/package.json`에 `monaco-editor`, `@monaco-editor/react`가 있음을 확인했다.

## 관련 산출물 상위 파일

| 파일 | bytes | KiB | MiB |
|---|---:|---:|---:|
| `App-BAswA52Z.js` | 8,545,720 B | 8,345.43 KiB | 8.15 MiB |
| `index-DnjEpVNQ.js` | 236,516 B | 230.97 KiB | 0.23 MiB |
| `html2canvas.esm-DXEQVQnt.js` | 201,094 B | 196.38 KiB | 0.19 MiB |
| `App-CqmJMvlr.css` | 180,632 B | 176.40 KiB | 0.17 MiB |
| `MesDashboard-DY_WPVx0.js` | 54,249 B | 52.98 KiB | 0.05 MiB |
| `AIChatbot-Bs62FBeT.js` | 13,249 B | 12.94 KiB | 0.01 MiB |
| `polling.worker-B3PXkacu.js` | 37,526 B | 36.65 KiB | 0.04 MiB |

## 카테고리별 크기

| 카테고리 | bytes | KiB | MiB | App 비중 | 기준 |
|---|---:|---:|---:|---:|---|
| 기타 vendor 코드 | 3,379,176 B | 3,299.98 KiB | 3.22 MiB | 39.54% | source path 기준, 일부 Grafana transitive 추정 |
| Monaco editor 관련 코드 | 2,782,338 B | 2,717.13 KiB | 2.65 MiB | 32.56% | source map path 기준 |
| Grafana 관련 코드, strict `@grafana/*` source path 기준 | 1,974,669 B | 1,928.39 KiB | 1.88 MiB | 23.11% | source map path 기준 |
| 대시보드 자체 코드 | 124,739 B | 121.82 KiB | 0.12 MiB | 1.46% | source map path 기준 |
| 설정창 코드 | 102,781 B | 100.37 KiB | 0.10 MiB | 1.20% | source map path 기준 |
| AIChatbot / Markdown / html2canvas 등 부가 기능 | 87,912 B | 85.85 KiB | 0.08 MiB | 1.03% | source map path 기준 |
| 차트 라이브러리 | 74,092 B | 72.36 KiB | 0.07 MiB | 0.87% | source map path 기준 |

## App chunk 상위 패키지

| 순위 | 패키지/source group | bytes | KiB | MiB | App 비중 |
|---:|---|---:|---:|---:|---:|
| 1 | `monaco-editor` | 2,770,459 B | 2,705.53 KiB | 2.64 MiB | 32.42% |
| 2 | `@grafana/ui` | 777,309 B | 759.09 KiB | 0.74 MiB | 9.10% |
| 3 | `moment-timezone` | 731,894 B | 714.74 KiB | 0.70 MiB | 8.56% |
| 4 | `@grafana/scenes` | 379,786 B | 370.88 KiB | 0.36 MiB | 4.44% |
| 5 | `@grafana/data` | 307,464 B | 300.26 KiB | 0.29 MiB | 3.60% |
| 6 | app source | 227,858 B | 222.52 KiB | 0.22 MiB | 2.67% |
| 7 | `rxjs` | 165,901 B | 162.01 KiB | 0.16 MiB | 1.94% |
| 8 | `date-fns` | 159,785 B | 156.04 KiB | 0.15 MiB | 1.87% |
| 9 | `slate` | 159,299 B | 155.57 KiB | 0.15 MiB | 1.86% |
| 10 | `@react-aria/utils` | 157,779 B | 154.08 KiB | 0.15 MiB | 1.85% |

## App chunk 상위 5개 원인

| 순위 | 원인 | 크기 | 초기 로드에서 분리 가능성 | 분리 리스크 |
|---:|---|---:|---|---|
| 1 | Monaco editor가 App chunk에 포함됨 | 2.64 MiB | 높음. 대시보드 첫 화면에서 editor가 필요 없다면 lazy boundary, manualChunks, alias 전략 후보 | 중간~높음. Monaco worker, language chunk, CSS, Grafana UI 내부 import 경계 검증 필요 |
| 2 | Grafana 직접 패키지, `@grafana/ui`, `@grafana/scenes`, `@grafana/data` | 1.88 MiB | 중간. `/dashboard` 자체가 Scenes 기반이라 완전 제외는 어렵고 route 내부 shell/scene renderer 경계가 필요 | 높음. `SceneGridLayout`, layout edit, runtime init, data frame 타입 의존성이 App과 결합 |
| 3 | `moment-timezone` 전체 데이터가 포함됨 | 0.70 MiB | 높음. timezone data 축소 또는 필요한 시점 lazy load 후보 | 중간. 날짜/타임존 표시와 Grafana data API 회귀 확인 필요 |
| 4 | Grafana UI transitive vendor로 보이는 기타 vendor 묶음 | 3.22 MiB | 중간. Grafana UI import boundary를 분리하면 함께 줄어들 가능성 있음 | 중간~높음. source path만으로 import 주체가 확정되지 않아 dependency graph 검증 필요 |
| 5 | `SettingsModal`과 설정 관련 앱 코드가 정적 import됨 | 0.10 MiB | 높음. `settingsOpen=true` 시점 lazy load 후보 | 중간. props와 설정 상태 계산 경계가 커서 모달 컨테이너 단위 분리 필요 |

## 원인별 근거

1. Monaco: `frontend/src`와 `frontend/package.json`에는 직접 import/dependency가 없고, `@grafana/ui/package.json`이 `monaco-editor`, `@monaco-editor/react`를 가진다. source map 기준 `monaco-editor`가 2.64 MiB다.
2. Grafana 직접 패키지: `App.tsx`, `src/scenes/*`, timeseries 데이터프레임 코드가 `@grafana/*`를 정적으로 import한다. strict `@grafana/*` source path 합계는 1.88 MiB다.
3. `moment-timezone`: `@grafana/data/package.json`이 `moment-timezone`에 의존하고, source map 기준 `moment-timezone/moment-timezone.js`가 714.68 KiB다.
4. 기타 vendor: `slate`, `react-select`, `floating-ui`, `@hello-pangea/dnd`, `rc-picker`, `react-table` 등이 App chunk에 포함된다. 이 중 일부는 Grafana UI 기원으로 추정된다.
5. SettingsModal: `App.tsx`가 `SettingsModal`과 `useSettingsModalState`를 정적으로 import하고 항상 렌더 트리에 둔다. source map 기준 설정창 코드는 100.37 KiB다.

## 분리 우선순위

| 순위 | 대상 | 기대 효과 | 이유 | 리스크 |
|---:|---|---|---|---|
| 1 | Monaco editor / Grafana UI editor 경계 | 2.64 MiB 후보 | 가장 큰 단일 패키지이며 `/dashboard` 소스에서 직접 쓰지 않음 | 중간~높음 |
| 2 | Grafana Scenes/UI/Data import boundary | strict 1.88 MiB + transitive vendor 일부 | App chunk 대부분의 원인. 단, 대시보드 핵심 경로라 설계 필요 | 높음 |
| 3 | `moment-timezone` 축소 | 714.68 KiB 후보 | 단일 파일 크기가 매우 크고 `@grafana/data`를 통해 유입 | 중간 |
| 4 | `SettingsModal` lazy load | 100.37 KiB | 절대 크기는 작지만 분리 난이도 대비 효과가 명확 | 중간 |
| 5 | `MarkdownWidget` / `react-markdown` lazy load | 85.85 KiB 범주 일부 | 기본 화면에서 markdown 위젯이 없으면 초기 로드 제외가 쉬움 | 낮음 |

## 정확도 한계

- source map generated-column 범위 기반 추정이다. mapped coverage가 99.77%라 문자열 스캔보다 정확하지만 Rollup helper와 minifier output 때문에 완전한 treemap과 1:1로 같지는 않다.
- `other_vendor` 중 일부는 Grafana UI의 transitive dependency로 추정된다. source path만으로 import 주체를 완전히 확정하지 않았다.
- 카테고리별 gzip 크기는 제공하지 않는다. gzip은 여러 모듈이 dictionary를 공유해서 카테고리별 합산이 부정확하다.
- `npm run build -- --sourcemap`가 map을 만들지 않았으므로, 최종 분석은 `npx vite build --sourcemap` 기준이다.

## 다음 단계 권장 작업

1. `monaco-editor`가 왜 App chunk에 묶이는지 `@grafana/ui` import chain을 확정하고, editor 관련 코드 lazy/manual chunk 분리를 실험한다.
2. `@grafana/scenes`, `@grafana/data`, `@grafana/ui` 경계를 route shell과 scene renderer로 나눌 수 있는지 설계한다.
3. `moment-timezone` data 축소 또는 timezone 기능 지연 로드를 검토한다.
4. `SettingsModal`을 `settingsOpen` 시점 lazy load로 분리한다.
5. `MarkdownWidget`의 `react-markdown` 정적 import를 위젯 렌더 시점 lazy load로 분리한다.

## 코드 수정 여부

없음. 빌드/분석 산출물만 생성했다.
