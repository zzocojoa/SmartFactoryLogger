# 의존성 보안 보완 결과

**로컬 코드 보완·회귀 완료. 기존 설치본과 서버 운영 승격은 HOLD다.**

## 기준과 범위

- 기준: 병합본 `60f1734dc9c02d9e183b53ea5205224537820808`.
- 별도 로컬 clone/브랜치 `codex/dependency-security-20260930`에서 작업했다.
- 사용자가 완료된 서버 점검 콘솔을 닫았다고 확인하고 로컬 보완을 승인했다.
- 기존 작업본·R4 후보·현장 점검 증거를 보존했다. commit/push/PR/merge, 설치본 재빌드·설치·서버 조작은 수행하지 않았다.

## 최소 변경

| 대상 | 이전 | 수정 |
|---|---|---|
| brace-expansion 각 사용 계열 | 1.1.18 / 2.1.4 / 5.0.9 | 1.1.21 / 2.1.7 / 5.0.12 |
| fast-uri | 3.1.7 | 3.1.8 |
| moment | 2.30.1 | 2.31.0 |

Root 7개·frontend 3개 설치 경로의 version/resolved/integrity만 바뀌었고 lock 패키지 집합은 같다. Moment의 직접 선언을 고정하고, 이전 버전을 고정한 Grafana data/ui 두 경로에만 `$moment` override를 둔다. Grafana 12.4.10, Scenes 8.17.0, Router 7.18.3, moment-timezone 0.5.47은 유지한다. 강제 major 업그레이드나 audit 예외 처리는 없다.

`npm run health:dependencies`를 전체 health와 Windows PR artifact workflow에 연결했다. 프런트엔드 신규 시험은 실제 production `buildTimeRangeFromSamples`, Grafana 날짜 API와 Vite의 timezone alias를 사용한다. 제품 수집·종료·저장 알고리즘, 설정·schema·UI는 변경하지 않았다.

## 검증 결과

환경: Windows 11 x64, Node 22.22.2, npm 10.9.7, Python 3.12.6. 별도 venv에는 R4의 freeze 버전을 설치했다. `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`, `CI=true`. 백엔드 표준 runner가 별도 임시 AppData/설정과 모의 장비를 사용했다.

| 검증 | 실제 결과 |
|---|---|
| root/frontend `npm ci --no-audit --no-fund`, 변경 전·후 | 모두 exit0; frontend postinstall 계약 검사 포함 |
| 변경 전 root/frontend `npm audit --package-lock-only --json` | exit1/1, high1+moderate1 / high1+moderate4 |
| 변경 후 root/frontend `npm audit --json` | exit0/0, 둘 다 전체 0건 |
| `node --test --test-timeout=30000 scripts/dependencySecurity.test.cjs` 변경 전 | 실제 설치 모듈 10 FAIL: 8 brace 경로·fast-uri·Moment |
| 최종 `npm run health:dependencies` | 10 PASS / 0 FAIL / 0 SKIP |
| 실제 Grafana/Moment 및 기존 timezone 집중시험 | 7 PASS, 신규4+기존3 |
| 최종 `npm run health` | exit0, 1,288개 중 1,287 PASS / 0 FAIL / 1 SKIP |
| health 세부 | 보안10·Electron94·frontend Node9·Vitest305·backend869 PASS+1 SKIP |
| F01 조건부 시험 별도 보완 | fixture 해시 확인 후 1 PASS / 0 FAIL / 0 SKIP, exit0 |
| 서로 다른 시험 최종 검증 합계 | health 1,287 PASS + 별도 F01 1 PASS = 1,288개 통과 |
| lint/typecheck | frontend ESLint/TypeScript, backend Ruff/mypy 통과 |
| 종료·배포 계약 QA | operational-ready/startup-trace/closeout/signature/workflow 5개 그룹 통과 |
| 실제 production Vite 설정을 통한 build+모듈 그래프 | exit0, Moment 2.31.0 한 경로, 기존 10년 timezone 번들, brace/fast-uri 모듈0 |
| lock/실제 설치 버전·npm tree·diff | 대상만 변경, 모듈 공유, `git diff --check` 통과 |

처음 `health`는 기능 1,287개 통과·1개 skip 후 QA에서 `Get-FileHash`를 찾지 못해 exit1이었다. 초기 로그를 보존했다. npm 하위 Windows PowerShell 5.1이 상위 Codex PowerShell 7 모듈 경로를 상속받는 현상을 별도 probe로 재현했다. QA 프로세스의 `PSMODULEPATH`만 Windows PowerShell 경로로 지정하자 같은 probe가 exit0으로 바뀌었고 전체 health를 재실행해 exit0을 확인했다. OS의 영구 환경·제품 코드는 이 문제로 수정하지 않았다.

두 health 모두 backend 원문은 `OK (skipped=1)`이다. 시험 목록의 유일한 활성 조건부 skip은 `FactPollingTests.test_f01_raw_inputs_poll_publish_csv_continue_during_fact_initialization`이며 `TEMPERATURE_GOAL_PACKAGE` 미설정에 따른 private F01 자료 조건이었다. 870개 시험 목록과 skip 조건을 별도 기록했다. Downloads의 기존 F01 fixture SHA-256 `bab8f61354124b5fdfa155abdb289255a2514fb710f4fa5e23a7e43418dec4b4`를 확인하고, 독립된 임시 AppData와 모의 장비 환경에서 그 production 경로 시험 하나를 실행해 PASS를 확인했다. 입력 해시는 전후 동일하다. health의 skip을 0으로 고치지 않고 별도 실행으로 검증을 보완했다. F01은 원시 자료를 쓰는 합성 Event/transport 시험이며 새 현장 실측이 아니다.

변경 전 brace 시험은 첫 중첩 입력에서 실패하므로 10 FAIL을 모든 advisory별 완전 재현으로 해석하지 않는다. 별도 전후 rewrite probe는 8사본 모두에서 기존 2개 확장 결과와 수정 후 원문 literal fallback을 확인했다. 최종 회귀에도 이 결정적 검사를 포함하며 기기 속도 기준으로 통과시키지 않는다. Moment 시험은 실제 패키지의 locale 처리에서 모듈 로딩 경계만 관찰하고 복원하며, probe 파일을 실제 로딩하거나 경로 밖 파일을 실행하지 않는다. 이는 합성 재현이며 현장 공격·장애 증거가 아니다.

실제 Vite/Rollup 빌드는 변경하지 않은 production 설정에 읽기용 그래프 관찰 plugin을 추가해 수행했다. Moment 모듈은 `moment/dist/moment.js` 한 경로였다. 브라우저 번들에서 build/lint 도구 모듈이 없다는 확인이 해당 도구의 개발 입력 위험까지 없다는 뜻은 아니다. 감사 0건은 실행 시점의 npm 권고 결과다.

## 파일과 증거

- `.github/workflows/windows-release-artifact.yml`: 신규 보안 시험을 PR 검사에 연결.
- `v2_next/package.json`, `package-lock.json`: health 항목과 build 도구 보안 수정판.
- `v2_next/frontend/package.json`, `package-lock.json`: Moment 고정·좁은 override와 brace 수정판.
- `v2_next/scripts/dependencySecurity.test.cjs`: 실제 패키지 보안 경계 회귀.
- `v2_next/frontend/src/shared/build/momentCompatibility.test.ts`: 공유 인스턴스·production 시간 범위·UTC/KST/DST·정상 locale 회귀.
- `v2_next/README.md`, 이 보고서: 검증 범위와 호환·복귀 한계.

개발 PC의 `Desktop/SmartFactory/DEPENDENCY_SECURITY_R1`에 실행 명령·환경·시각·종료코드·원문 해시를 가진 `logs`, `REGRESSION_MATRIX_R1.json`, `production-module-graph.json`, `lock-diff-review.json`, 기존 파일 보존 검사, 독립 검토, 전체 diff와 신규 파일 manifest를 보존한다. 재실행·집중시험은 위 1,288개 고유 시험의 합계에 중복해서 더하지 않았다. 원본 private CSV는 Git 또는 증거 archive에 복사하지 않았다.

## 위험·복귀·다음 단계

위험은 중간이다. Moment minor 업데이트를 Grafana의 선언된 고정 버전 밖에서 적용하므로 프로젝트가 해당 호환 계약을 책임진다. 이번 실제 경로 시험과 production 빌드는 통과했지만 새 Electron 설치본의 렌더링·설치·서버 운전은 미검증이다. 그 단계는 commit-bound 새 후보에서 검증해야 한다. 원격 GitHub CI도 아직 실행하지 않았다.

소스 복귀는 package/lock·검증·workflow 변경을 기준 조합으로 함께 되돌리고 `npm ci`하는 방식이다. 이전 보안 상태로 복귀하는 것이므로 운영 승인을 자동으로 부여하지 않는다. 데이터 이관은 없고 관측 필드·로그·저장 구조의 변경도 없다. 잔여 운용 실패 위험은 새 패키지의 화면/시간 표시 호환성과 아직 해결되지 않은 원본 종료·미완료 저장 증거다.

R4 미서명 후보와 현재 서버 원본에는 이 diff가 포함되지 않는다. 과거 이미지 실패 13, 원본 최종 worker/drain/unfinished 증거 미지원, 기존 fingerprint 미검증 상태는 유지한다. 이번 소스 감사 0건으로 이를 해제하지 않는다.

읽기 전용 독립 검토에서 중대 코드 차단사항이 없음을 확인했다. 다음 단계는 검증된 변경의 커밋·푸시·PR 검토이며, 병합본의 새 후보 빌드·격리 검증은 그 다음 단계다.

## 공식 보안 근거

- [brace 중첩 제한](https://github.com/advisories/GHSA-qhr7-859c-m2p7), [brace 파싱 제한](https://github.com/advisories/GHSA-6j4f-fj2g-mc7p), [brace 반복 재작성 제한](https://github.com/advisories/GHSA-q2hr-2g5m-vwhr).
- [fast-uri 호스트 정규화](https://github.com/advisories/GHSA-hrr3-gc8f-f4qj).
- [Moment 비문자열 locale](https://github.com/advisories/GHSA-4p3w-j4w9-5jqw), [공식 수정 변경](https://github.com/moment/moment/commit/5f7d983).
