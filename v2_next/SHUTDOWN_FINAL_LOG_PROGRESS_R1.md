# 최종 종료 로그 보완 진행

## 목적과 기준

- 실제 후보 Sandbox 시험에서 발견한 마지막 `Control shutdown complete` 누락만 수정한다.
- 기준 HEAD `151de1408635df779696ac161501459498895c29`는 병합본
  `507a93b3112d6f7c51b20ae67cde07d7baf884b7`과 동일한 tree다.
- 기존 사용자 checkout, engineering worktree의 선행 미추적 11개 파일과 과거 HOLD 증거를 보존한다.
- G/T/C/L1, image drain·실패 이력·receipt·실패 exit2 계약과 서비스 timeout은 유지한다.
- 실제 장비·서버·운영 설정·데이터는 대상이 아니다.

## 구현

- 실제 `SafeRotatingFileHandler`가 최종 레코드의 write/flush 완료를 알린다.
- `handleError`로 내부 처리된 저장 오류도 실패 ack로 전달하며 ack 객체는 JSON에서 제외한다.
- 기존 마지막 0.2초를 한 deadline으로 사용하고 추가 sleep·무한 join을 넣지 않는다.
- await 이후 모든 receipt를 다시 검사한다. 실패는 유지하고 같은 예산에서 정정 실패 로그를
  한 번만 허용한다. 로그·receipt는 종료 전 관측이며 실제 OS 종료 증명과 구분한다.

## 재현과 검증

- 이전 production 소스를 별도 경로에 보존하고 신규 시험만 얹어 실제 subprocess와 os._exit를 실행했다.
- 파일 쓰기 경계에 Event를 사용한 같은 시험: 이전 소스는 최종 로그 0건으로 실패, 수정본은 통과.
- 최초 두 시험 실행의 파서 오류도 원문 보존했다. 초기화 로그가 섞인 파일 전체를 JSON으로
  읽던 시험을 최종 대상 레코드만 파싱하도록 고친 뒤 동일 시험으로 전후를 비교했다.
- 이미지 종료 회귀 28개 통과. 정상 기록·inflight·정체·write/flush 오류·취소·새 peer 실패를 포함한다.
- 기존 peer 시험은 특정 sleep 수치 대신 실제 막힌 파일 쓰기 경계로 주입을 옮겼다.
  exit2·worker 참조·미검증 상태 assertion은 유지·강화했다.
- backend 전체 회귀 867개(실패·skip 0), Electron 종료 계약 94개(실패·skip 0),
  backend ruff/mypy 및 종료·설치 QA SelfTest 5개군을 통과했다.
- workflow QA 최초 실행은 작업 폴더의 js-yaml 부재로 실패했다. 원문을 보존하고 동일 package/lock의
  검증용 의존성(js-yaml 4.3.2)을 NODE_PATH로 지정한 후 같은 SelfTest를 통과했다.
- 독립 읽기 검토에서 차단 사항 없음. Windows scheduling 허용 폭을 둔 시간 시험의 한계를 기록한다.

## 남은 작업

- 전체 backend 회귀와 코드 독립 검토 완료. diff와 기존 파일 보존 대조 증거를 정리한다.
- 검증된 변경의 clean commit에 결합한 새 후보 빌드 및 frozen 격리 설치 시험이 필요하다.
- 이전 미서명 후보의 로그 QA HOLD와 기존 서버 HOLD는 source 시험만으로 해제하지 않는다.

## 영향과 복귀

- 위험도 중간: 종료 기록 확인 실패도 exit2가 되므로 느리거나 정체된 로그 저장소는 성공으로
  표시되지 않는다. 데이터 schema·운영 설정·HTTP 인증·수집 interval·UI는 변경하지 않는다.
- 이번 단계는 코드·합성 시험이다. 데이터 이관은 없고 서버 복귀 조작도 없다.
- 코드 복귀는 이번 파일 diff만 되돌리는 경로이며 이전 로그 누락도 되살아난다.
  이전 후보나 현재 서버를 새 검증 통과 대상으로 바꾸지 않는다.
