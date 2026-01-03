# UI 구현 5단계 스타일 토큰·클래스 설계

## 1. 목표
- UI 구현에 사용할 색상/타이포/상태 토큰과 클래스 규칙을 확정한다.

## 2. 기본 토큰
```css
:root {
  --bg-main: #1b1f24;
  --bg-card: #242a30;
  --bg-card-muted: #1f2328;
  --text-primary: #e6edf3;
  --text-secondary: #b0bac4;
  --text-muted: #7b8794;

  --state-ok: #25c49a;
  --state-warn: #f2c94c;
  --state-danger: #f66b6b;
  --state-offline: #7a7a7a;
  --state-cool: #56a6dc;

  --card-radius: 12px;
  --card-padding: 14px;
  --card-gap: 12px;

  --font-number: "Pretendard", "IBM Plex Sans KR", "Segoe UI", sans-serif;
  --font-ui: "Pretendard", "Segoe UI", sans-serif;

  /* 기존 변수 호환(alias) */
  --bg-color: var(--bg-main);
  --panel-color: var(--bg-card-muted);
  --card-color: var(--bg-card);
  --text-color: var(--text-primary);
  --text-dim: var(--text-secondary);
  --success-color: var(--state-ok);
  --danger-color: var(--state-danger);
  --warning-color: var(--state-warn);
}
```

## 3. 공통 클래스
```css
.card {
  background: var(--bg-card);
  color: var(--text-primary);
  border-radius: var(--card-radius);
  padding: var(--card-padding);
}

.state-ok { color: var(--state-ok); }
.state-warn { color: var(--state-warn); }
.state-danger { color: var(--state-danger); }
.state-offline { color: var(--state-offline); }
.state-cool { color: var(--state-cool); }
```

## 4. KPI 라벨 클래스
```css
.label-speed-very-fast { color: var(--state-danger); }
.label-speed-fast { color: var(--state-warn); }
.label-speed-normal { color: var(--state-ok); }
.label-speed-slow { color: var(--state-cool); }
.label-speed-very-slow { color: var(--text-muted); }

.label-press-high { color: var(--state-warn); }
.label-press-normal { color: var(--state-ok); }
.label-press-low { color: var(--state-cool); }
```

## 5. 상태 강조 클래스
```css
.card-warning { border: 1px solid var(--state-warn); }
.card-danger { border: 2px solid var(--state-danger); }
.card-danger-tint { background: color-mix(in srgb, var(--bg-card) 85%, var(--state-danger)); }
```

## 6. 카메라 상태 오버레이
```css
.camera-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-primary);
  background: rgba(0, 0, 0, 0.45);
}

/* 크로스헤어 전용 */
.camera-crosshair {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
```

## 7. 확정 결과
- 토큰/클래스는 이후 단계의 CSS 구현 기준으로 사용한다.
