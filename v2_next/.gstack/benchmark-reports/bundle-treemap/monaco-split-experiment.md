# Monaco split experiment

## 결론

Monaco 분리 실험의 유효한 해법은 `manualChunks`가 아니라 `@grafana/scenes`를 CJS entry에서 ESM source entry로 바꾸는 것이다.

최종 patch:

```ts
{
  find: '@grafana/scenes',
  replacement: resolve(__dirname, 'node_modules/@grafana/scenes/dist/esm/packages/scenes/src/index.js'),
}
```

코드 수정 파일:

- `frontend/vite.config.ts`

## 기준값

기준 build는 기존 `@grafana/scenes/dist/index.js` CJS alias 기준이다.

| 항목 | 파일 | raw | gzip |
|---|---|---:|---:|
| 기준 App chunk | `App-BAswA52Z.js` | 8,545,720 B, 8.15 MiB | 2,270,849 B, 2.17 MiB |

## 시도 1: Monaco manualChunks

`monaco-editor`, `@monaco-editor/*`를 `monaco-editor` chunk로 강제 분리했다.

결과:

| 항목 | raw | gzip |
|---|---:|---:|
| App chunk | 5,754,136 B | 1,560,502 B |
| `monaco-editor` JS chunk | 3,315,106 B | 839,763 B |
| `monaco-editor` CSS chunk | 82,392 B | 14,002 B |

판정: 실패.

이유:

- `index.html`이 `monaco-editor` JS/CSS를 즉시 modulepreload/stylesheet로 로드했다.
- `index`와 `App` chunk 모두 `monaco-editor` chunk를 import했다.
- 파일은 분리됐지만 초기 로드에서는 빠지지 않았다.

## 시도 2: React vendor + Monaco manualChunks

React 계열을 `react-vendor`, Monaco 계열을 `monaco-editor`로 분리했다.

결과:

| 항목 | raw | gzip |
|---|---:|---:|
| App chunk | 5,612,219 B | 1,515,152 B |
| `monaco-editor` JS chunk | 3,307,700 B | 837,277 B |
| `react-vendor` JS chunk | 368,088 B | 119,835 B |

판정: 실패.

이유:

- `index.html`이 여전히 `monaco-editor` JS/CSS를 즉시 preload했다.
- `react-vendor`와 `monaco-editor` 사이에 import 연결이 생겼다.
- App chunk raw는 줄었지만 초기 네트워크 비용은 유지됐다.

## 시도 3: `@grafana/scenes` ESM source entry alias

`@grafana/scenes` alias를 CJS entry에서 ESM source entry로 변경하고 manualChunks는 제거했다.

결과:

| 항목 | 파일 | raw | gzip |
|---|---|---:|---:|
| App chunk | `App-Bz_Ymavl.js` | 2,696,880 B, 2.57 MiB | 652,754 B, 637.46 KiB |
| index chunk | `index-RArPjYSl.js` | 167,998 B | 55,723 B |
| total JS | 여러 JS chunks | 3,347,006 B | 867,479 B |

기준 대비 App chunk 감소:

| 항목 | 감소량 |
|---|---:|
| raw bytes | 5,848,840 B |
| raw MiB | 5.58 MiB |
| gzip bytes | 1,618,095 B |
| gzip MiB | 1.54 MiB |

판정: 성공 후보.

근거:

- `dist/assets`에 `monaco` 이름의 JS/CSS asset이 생성되지 않았다.
- `index.html`에 Monaco preload가 없다.
- `App-Bz_Ymavl.js.map` 기준 `monaco` source path count가 0이다.
- `@grafana/ui/dist/cjs` source path count가 0이고 `@grafana/ui/dist/esm` source path count가 141이다.
- 변환 모듈 수가 6,160에서 4,542로 줄었다.

## 최종 index.html 초기 preload 확인

최종 `index.html`은 다음만 직접 로드한다.

```html
<script type="module" crossorigin src="./assets/index-RArPjYSl.js"></script>
<link rel="stylesheet" crossorigin href="./assets/index-WLe6_l97.css">
```

Monaco JS/CSS preload는 없다.

## 검증

실행한 명령:

```powershell
cd frontend
npm run build
npx vite build --sourcemap
```

둘 다 성공했다.

로컬 preview:

```text
http://127.0.0.1:4173/
```

`Invoke-WebRequest` 기준 HTTP 200 응답을 확인했다.

## 리스크

- `@grafana/scenes`의 published package `module` entry와 다른 내부 source entry를 직접 alias한다.
- `@grafana/scenes` 패키지 내부 dist 구조가 바뀌면 alias가 깨질 수 있다.
- 런타임에서 scene 기능, layout edit, panel schema lazy chunks가 정상 동작하는지 브라우저 QA가 필요하다.
- App chunk는 크게 줄었지만 `grafana-scenes.json-*` chunk가 다수 생성된다. 이들은 schema 관련 lazy chunks로 보이며 초기 preload에는 포함되지 않는다.

## 다음 확인

1. 브라우저에서 `/dashboard` 렌더링 확인.
2. layout edit, widget add/remove, preset, settings open, snapshot 등 dashboard 핵심 기능 smoke test.
3. `@grafana/scenes` ESM entry를 더 안정적인 public `module` path로 잡을 수 있는지 검토.
4. 이 patch를 유지할 경우 `vite.config.ts`에 왜 CJS alias 대신 ESM source entry를 쓰는지 한국어 주석을 추가할지 결정.
