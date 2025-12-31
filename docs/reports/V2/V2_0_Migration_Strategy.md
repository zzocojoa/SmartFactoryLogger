# V2.0 (Web Tech) 전환을 위한 Git 브랜치 및 저장소 관리 전략

`작성일: 2025-12-31`
`목표: 기존 Tkinter(V1) 버전을 유지하면서, Web Stack(V2) 개발을 안전하게 병행하는 Git 전략 수립`

## 1. 추천 전략: "Two-Track" (V1 유지보수 + V2 신규개발)

V2.0은 기술 스택이 완전히 다르므로(Python -> React/Node/Electron), 기존 코드
위에 덮어쓰거나 단순 브랜치로 관리하면 **폴더 구조가 꼬일 위험**이 큽니다. 가장
깔끔하고 추천하는 방식은 **"폴더 분리형 모노레포(Mono-repo) 전략"**입니다.

### 1.1. 저장소(Repository) 구조 변경안

하나의 Git 저장소 안에서, 프로젝트의 세대를 명확히 나누는 구조입니다.

```bash
SmartFactoryLogger/
├── .git/
├── README.md              # 통합 안내 (V1, V2 링크)
├── v1_legacy/             # [현재 프로젝트 이동] 기존 Tkinter 버전
│   ├── src/
│   ├── docs/
│   └── requirements.txt
└── v2_next/               # [신규 생성] React + Electron 버전
    ├── frontend/          # React UI
    ├── backend/           # Python FastAPI (기존 로직 재사용)
    └── package.json
```

---

## 2. 구체적인 실행 가이드 (Step-by-Step)

지금 당장 V2를 시작하기 위해 Git을 어떻게 조작해야 하는지 단계별로 안내합니다.

### Step 1. 현재 상태 보존 (Tagging)

현재의 안정적인 Tkinter 버전을 언제든 돌아갈 수 있도록 'V1.0' 꼬리표를 붙입니다.

```bash
git tag -a v1.0.0-stable -m "Official Release of Tkinter Version"
git push origin v1.0.0-stable
```

### Step 2. V2 개발용 브랜치 생성

메인 `main` 브랜치는 당분간 V1 유지보수용으로 두고, V2 개발을 위한 격리된 공간을
만듭니다.

```bash
git checkout -b feature/v2.0-web-migration
```

### Step 3. 폴더 구조 재편 (Refactoring)

이 브랜치에서 과감하게 폴더를 정리합니다.

1. 새 폴더 `v1_legacy`를 만듭니다.
2. 현재의 모든 소스(`src`, `config`, `*.spec` 등)를 `v1_legacy` 안으로
   이동시킵니다.
3. 새 폴더 `v2_next`를 만듭니다.
4. 이 구조를 커밋합니다.
   (`git commit -m "Refactor: Prepare folder structure for V2"`)

### Step 4. 병행 개발 (Development)

- **V1 수정이 필요할 때**: `main` 브랜치에서 작업 -> `v1_legacy` 폴더 안의 내용
  수정.
- **V2 개발할 때**: `feature/v2.0` 브랜치에서 작업 -> `v2_next` 폴더 안에 React
  프로젝트 설치(`npx create-react-app ...`).

---

## 3. 왜 이 방식인가? (장점)

1. **완벽한 격리**: V2 개발 중 실수로 V1 코드를 망가뜨릴 일이 없습니다.
2. **참조 용이성**: V2를 짜다가 V1의 로직을 보고 싶을 때, 다른 저장소를 열 필요
   없이 폴더만 건너가서 보면 됩니다. (코드 재사용성 극대화)
3. **히스토리 보존**: V1의 무수한 Git 커밋 기록(`commit history`)을 버리지 않고
   그대로 안고 갈 수 있습니다.

## 4. 결론

**"새 저장소(New Repo)를 파지 마세요."** 기존 히스토리는 소중한 자산입니다. 위
가이드처럼 **`v1_legacy` / `v2_next` 폴더 구조**로 개편하여 하나의 지붕 아래서
세대 교체를 진행하는 것이 가장 효율적입니다.
