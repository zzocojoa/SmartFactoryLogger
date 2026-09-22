# Temperature clock C1~C3 진행

기준/시작 HEAD: `376618267aa52c822e1692d50de637d657ddf28e`.
브랜치: `codex/temperature-remediation-20260909`. 시작 시 tracked/staged 변경 없음.
기존 untracked 34개와 G/T 보고서는 해시를 보존했다.

C1 → C2 → C3 순서로 production 경로 재현, 최소 수정, 회귀 검증을 진행한다.
로컬 코드/시험/필요한 계약 문서만 변경하며 Git 게시·장비·빌드·운영 변경은 하지 않는다.

- C1: monotonic 주기·양 loop Event 대기·이전 thread 종료 확인. UTC 동일 신규 표본 enqueue 누락을 재현해 내부 순번으로 구분. 신규 7시험 통과. 정상 wait 4.5~5초/오류 retry 1초와 소비자 retry 중 stop을 각각 확인. 독립 검토 승인.
- C2: source 게시 시 완료 monotonic/domain을 고정하고 read_data의 snapshot lock 안에서 통합 표본을 채택. service/queue/CSV는 같은 endpoint를 보존. 신규 8시험 통과. UTC finite guard를 보존하고 runtime 파일 불변 검증. 독립 검토 승인.
- C3: 원래 poll context의 시작~완료 monotonic으로 duration 계산. blank/사유 status와 CSV 2.3.1/2.4.2/2.5.2, fact 1.4.0 계약 추가. 과거 header/epoch 의미 보존. 신규 8시험 통과. diagnostics invalid endpoint 게시 예외도 재현·보완. production·계약 독립 검토 모두 차단 결함 없음.
- 최신 clock-final 23개 pass/0 fail/0 skip. affected-contracts-r2 182개 pass. 전체 health exit 0: backend 818, Electron 94, frontend Node 9/Vitest 291 pass; lint/typecheck/필수 QA 모두 통과.
- 로컬 코드 목표 완료. 운영 승격·새 현장 시험은 미실행이며 자동으로 이어가지 않는다. 상세 결과·한계는 TEMPERATURE_CLOCK_RESULT_C1_C3.md, 요구사항 대응은 새 회귀 행렬에 기록했다.

원문과 실행별 환경/종료코드는 `artifacts/temperature-clock-c1-c3/`에 보존한다.
첨부 감사는 함수/표현식 격리 합성 증거이며 현장 장애나 전체 production 검증으로 확대하지 않는다.
첨부 matrix의 ID와 상세 context 요구사항을 실제 시험 함수에 대응한다.
원본 첨부를 수정하지 않는다.

C1 기존 interval·overrun 후 0 대기·예외 retry 1초·thread join 각 1초를 유지한다.
동기 I/O 자체를 강제로 중단하는 보장은 하지 않으며 미종료 thread가 있으면 stop=False와 restart 거부로 드러낸다.
C2 proof는 strict 내부 필드로 model_copy/메모리 queue를 통과하고 공개 JSON에서는 제외된다.
공개 JSON/과거 replay를 다시 읽으면 proof가 없는 입력으로 fail-closed하며 측정값을 합성하지 않는다.
기존 정상 fixture에 선언된 합성 monotonic endpoint/domain을 추가했고 기존 판정 assertion을 유지했다.
