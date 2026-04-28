# Supplemental bundle analysis

## 목적

이 문서는 이전 리포트에서 미반영 또는 제한 반영된 항목을 4개 서브에이전트로 다시 병렬 분석한 보완 결과다.

코드 수정 여부: 없음. `.gstack/benchmark-reports/bundle-treemap/` 아래 분석 산출물만 추가했다.

## 수행 항목

| 항목 | 상태 | 반영 내용 |
|---|---|---|
| 문자열 스캔 및 Vite/Rollup 보조 분석 | 완료 | App chunk 문자열 밀도, sourcemap source 수, Vite 설정 특징 확인 |
| import-owner graph 확정 | 완료 | Grafana 경유 vendor 유입 주체를 확정/추정/미확정으로 구분 |
| visualizer treemap 산출물 | 완료 | 로컬 visualizer 패키지 부재 확인 후 JSON 기반 self-contained treemap HTML 생성 |
| gzip 크기와 분리 실험 설계 | 완료 | 전체 gzip 재확인, 카테고리별 gzip 한계와 실험 계획 정리 |

## 문자열 스캔 보조 근거

문자열 스캔은 크기 산출 근거가 아니라 포함 흔적 보조 지표다. 정량 크기는 `app-chunk-analysis.json`의 sourcemap generated-column attribution을 우선한다.

| 항목 | App JS 출현 | 출현/MiB | map 출현 | sourcemap source 수 | 판단 |
|---|---:|---:|---:|---:|---|
| `monaco` | 575 | 70.6 | 1,547 | 688 | App chunk 최대 원인과 일치 |
| `grafana` | 991 | 121.6 | 1,939 | 379 | Grafana 직접 패키지 원인과 일치 |
| `moment-timezone/timezone` | 411 | 50.4 | 1,049 | 2 direct, broad 70 | `@grafana/data` 경유와 일치 |
| `slate` | 214 | 26.3 | 524 | 14 | Grafana UI transitive vendor |
| `react-select` | 45 | 5.5 | 184 | 10 | Grafana UI transitive vendor |
| `floating-ui` | 30 | 3.7 | 278 | 9 | Grafana UI 및 Scenes 양쪽 dependency |
| `react-markdown/markdown` | 142 | 17.4 | 820 | 84 | App 내부 Markdown 부가 기능 |
| `uplot` | 15 | 1.8 | 97 | 1 | 차트 라이브러리, App 내 영향은 작음 |
| `html2canvas` | 1 | 0.1 | 5 | 0 direct path | 본체는 별도 `html2canvas.esm-*.js` chunk |
| `recharts` | 0 | 0.0 | 1 | 0 direct path | `/dashboard` App chunk 원인 아님 |
| `settings/setting` | 1,177 | 144.4 | 2,488 | 22 direct config/settings src | generic 단어라 과대 신호, sourcemap상 설정 코드는 100.37 KiB |

Vite/Rollup 확인:

- `frontend/vite.config.ts`에는 `manualChunks`나 visualizer 설정이 없다.
- `@grafana/scenes`는 `@grafana/scenes/dist/index.js`로 alias된다.
- App chunk 선두에 `__vite__mapDeps`가 있고 동적 dependency 26개를 참조한다.
- Monaco language/mode chunk, `TimeSeriesWidget`, `AIChatbot`, `settings`는 별도 chunk 참조가 있으나 Monaco 본체는 App chunk 내부에 크게 포함된다.

## import-owner graph

`/dashboard` App chunk 유입 경로는 다음으로 확정된다.

```text
frontend/src/App.tsx
  -> @grafana/scenes
  -> @grafana/scenes/dist/index.js
  -> @grafana/ui, @grafana/data, @grafana/runtime
```

근거:

- `frontend/src/App.tsx`가 `@grafana/scenes`를 정적으로 import한다.
- `@grafana/scenes/dist/index.js`가 `@grafana/data`, `@grafana/runtime`, `@grafana/ui`를 import한다.

| 항목 | owner 판정 | 근거 | 상태 |
|---|---|---|---|
| `monaco-editor` | `@grafana/ui` | `@grafana/ui/package.json`, `ReactMonacoEditor-D9FbtxTh.js` | 확정 |
| `@monaco-editor/react` | `@grafana/ui` | `@grafana/ui/package.json`, `ReactMonacoEditor-D9FbtxTh.js` | 확정 |
| `moment-timezone` | `@grafana/data` | `@grafana/data/package.json`, `@grafana/data/dist/cjs/index.cjs` | 확정 |
| `slate` 계열 | `@grafana/ui` | `@grafana/ui/package.json`, `@grafana/ui/dist/cjs/index.cjs` | 확정 |
| `react-select` | `@grafana/ui` | `@grafana/ui/package.json`, `@grafana/ui/dist/cjs/index.cjs` | 확정 |
| `@floating-ui/react` | `@grafana/ui` 및 `@grafana/scenes` | 두 package.json 모두 dependency 보유 | 확정 |
| `@hello-pangea/dnd` | `@grafana/ui` | `@grafana/ui/package.json`, `@grafana/ui/dist/cjs/index.cjs` | 확정 |
| `rc-picker` | `@grafana/ui` | `@grafana/ui/package.json`, `@grafana/ui/dist/cjs/index.cjs` | 확정 |
| `react-table` | `@grafana/ui` | `@grafana/ui/package.json`, `@grafana/ui/dist/cjs/index.cjs` | 확정 |
| `react-dropzone` | `@grafana/ui` | `@grafana/ui/package.json`, `@grafana/ui/dist/cjs/index.cjs` | 확정 |

구분:

- `frontend/src` 직접 import: 위 vendor 대상에서는 발견하지 못했다.
- Grafana package dependency: 위 항목 대부분은 `@grafana/ui`, `@grafana/data`, `@grafana/scenes` dependency로 확정된다.
- `/mes-dashboard`: 이번 대상 vendor 직접 유입 근거는 없다. `/mes-dashboard` 쪽은 `recharts` 계열이며 `/dashboard` App chunk 원인과 별개다.

추정:

- `@grafana/ui`가 CommonJS 단일 index 형태라 Rollup/Vite tree-shaking이 약하게 작동한 것으로 보인다.
- `@grafana/ui/dist/cjs/index.cjs`의 `ReactMonacoEditor` 동적 require가 Monaco 포함의 주요 후보다.

미확정:

- 각 vendor가 `@grafana/ui` 내부 어떤 exported component 사용 때문에 최종적으로 필요한지는 완전히 확정하지 못했다.
- package owner와 source import owner는 확정됐고, App chunk 유입 주체는 `@grafana/scenes`/`@grafana/runtime` 경유 `@grafana/ui`로 보는 것이 맞다.

## visualizer treemap 산출물

로컬 dependency 확인:

- `rollup-plugin-visualizer`: 로컬 설치 없음
- `source-map-explorer`: 로컬 설치 없음
- `npx --yes` 및 새 dependency 설치는 사용하지 않음

생성 산출물:

| 파일 | 크기 | 설명 |
|---|---:|---|
| `visualizer/app-chunk-treemap.html` | 15,065 B | 기존 sourcemap 분석 JSON 기반 self-contained SVG treemap |
| `visualizer/visualizer-status.md` | 633 B | visualizer 로컬 패키지 확인 결과 |

주의:

- 이 treemap은 `rollup-plugin-visualizer` 원본 treemap이 아니라 `app-chunk-analysis.json`의 `categories`, `topPackages`를 시각화한 보조 HTML이다.
- source map 기반 수치와 동일한 데이터에서 생성됐으므로 숫자 기준은 기존 JSON과 같다.

## gzip 분석

전체 App chunk 재확인:

| 항목 | 값 |
|---|---:|
| App chunk | `frontend/dist/assets/App-BAswA52Z.js` |
| raw | 8,545,720 B, 8.15 MiB |
| gzip | 2,270,849 B, 2,217.63 KiB, 2.17 MiB |
| gzip ratio | 26.57% |

기존 raw category와 대조:

| 카테고리 | raw bytes | MiB |
|---|---:|---:|
| 기타 vendor | 3,379,176 | 3.22 |
| Monaco | 2,782,338 | 2.65 |
| Grafana strict `@grafana/*` | 1,974,669 | 1.88 |
| 대시보드 자체 코드 | 124,739 | 0.12 |
| SettingsModal | 102,781 | 0.10 |
| AIChatbot/Markdown/html2canvas | 87,912 | 0.08 |
| 차트 라이브러리 | 74,092 | 0.07 |

카테고리별 gzip을 단순 산출하지 않은 이유:

- gzip은 전체 App chunk를 하나의 byte stream으로 압축한다.
- 모듈별/카테고리별 경계가 압축 경계가 아니다.
- DEFLATE dictionary, 반복 문자열, Huffman table, 32KiB sliding window가 카테고리 사이에서 공유된다.
- 따라서 “Monaco raw bytes만 잘라서 gzip”한 값은 실제 App chunk 안에서 Monaco가 차지한 gzip 기여도와 같지 않다.

보수적 추정:

- raw bytes 순위를 우선순위 판단 기준으로 사용한다.
- 단순 참고치로 `category_raw_bytes * 0.2657`을 적용할 수 있다.
- 예시: Monaco 약 722 KiB gzip, Grafana strict 약 512 KiB gzip, `moment-timezone` 약 190 KiB gzip 후보.
- 확정값은 실험 patch 전후의 `App chunk gzip 감소량 + 새 chunk gzip 증가량 + 초기 로드 요청 여부`로 측정해야 한다.

## 분리 실험 계획

| 순위 | 대상 | 실험 branch | 성공 지표 | 리스크 |
|---:|---|---|---|---|
| 1 | Monaco | `codex/experiment-split-monaco` | App raw 2.6 MiB 후보 감소, App gzip 700 KiB 전후 후보 감소, 초기 네트워크에서 Monaco chunk 제외 | 중간~높음, worker/language/CSS와 Grafana UI 내부 import 검증 필요 |
| 2 | `moment-timezone` | `codex/experiment-trim-moment-timezone` | raw 714 KiB 중 유의미한 감소, gzip 190 KiB 후보 감소 | 중간, Grafana data timezone 동작 회귀 가능 |
| 3 | `SettingsModal` | `codex/experiment-lazy-settings-modal` | raw 100 KiB 감소 후보, 설정 버튼 클릭 시 새 chunk 로드 | 중간, props와 상태 계산 경계 큼 |
| 4 | `MarkdownWidget` | `codex/experiment-lazy-markdown-widget` | raw 40~90 KiB 후보 감소, 기본 대시보드 초기 요청 제외 | 낮음 |
| 5 | Grafana scene boundary | `codex/experiment-split-grafana-scene` | strict 1.88 MiB + transitive 일부 감소 후보, shell first paint 가능 | 높음, `/dashboard` 핵심 렌더러라 회귀 위험 큼 |

공통 측정 명령:

```powershell
cd frontend
npm run build
node -e "const fs=require('fs'),zlib=require('zlib'); const f=fs.readdirSync('dist/assets').find(x=>/^App-.*\.js$/.test(x)); const b=fs.readFileSync('dist/assets/'+f); console.log({file:f, bytes:b.length, gzip:zlib.gzipSync(b).length});"
npx vite build --sourcemap
```

전체 JS chunk gzip 확인:

```powershell
node -e "const fs=require('fs'),zlib=require('zlib'); for (const f of fs.readdirSync('dist/assets').filter(x=>x.endsWith('.js'))) { const b=fs.readFileSync('dist/assets/'+f); console.log(f,b.length,zlib.gzipSync(b).length); }"
```

## 보완 후 결론

기존 리포트의 우선순위는 유지하되, 근거가 더 강해졌다.

1. `monaco-editor`는 `@grafana/ui` owner로 확정됐다.
2. `moment-timezone`은 `@grafana/data` owner로 확정됐다.
3. `slate`, `react-select`, `rc-picker`, `react-table`, `react-dropzone`, `@hello-pangea/dnd`는 `@grafana/ui` owner로 확정됐다.
4. `other_vendor` 중 상당 부분은 Grafana UI transitive vendor로 보는 것이 맞다.
5. 시각 treemap은 새 의존성 없이 보조 HTML로 생성됐다.
6. 카테고리별 gzip은 숫자를 단정하지 않고, patch 전후 delta로 확정해야 한다.
