'use strict';
// OFFLINE ONLY: embedded server paths are data, never filesystem targets.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');

const EXPECTED_SHA = '28E8C42D1395D1240DFDB4413135A3EA40BFA01FD8BF5D4AB7ADDE4EC4A6B1AD';
const labels = {
  KEEP: '보존·보존 검토 유지',
  MIXED_OR_RECOVERY_REVIEW: '혼재 자료: 폴더 통째 삭제 제외',
  OLD_OBSERVATION_REVIEW: '과거 관측 원본: 폐기 범위 결정 필요',
  SINGLE_FILE_REVIEW: '단독 ZIP·설치본·도구 등 검토',
  OTHER_HISTORICAL_REVIEW: '그 밖의 과거 자료 검토',
};
const overrides = new Map([
  [2, '다른 v1.0.26 stage. 성공 stage와 실제 내용/참조 비교 전 보존.'],
  [4, 'v1.0.24 설치·Canary server-evidence 26파일 89,704bytes가 구형 배포물과 혼재.'],
  [5, 'v1.0.23 server-evidence 36파일 125,015bytes 및 p12 실행 결과가 혼재.'],
  [14, 'config-before-smoke.json의 실제 설정/시험용 여부 미확인.'],
  [15, 'config-before-smoke.json, config.ini, config.bak, state.json 포함.'],
  [44, 'backup_before_install에 config.ini 및 설치 전 로그 등 12파일 포함.'],
  [57, 'config.ini.before_reattestation 포함.'],
  [58, 'config.ini.before_reattestation 포함.'],
  [59, 'config.ini 및 두 종류의 과거 설정 백업 포함.'],
  [64, 'R1: 중복22파일 미삭제. 보존 대상 고유 JSON과 과거 참조 유지.'],
  [65, 'R2_clean: R1 중복의 보존 사본 및 별도 고유 JSON 유지.'],
  [179, 'backup_before_install/config.ini 포함.'],
  [180, 'backup_before_install/config.ini 포함.'],
  [194, 'config.ini.before-r4-reattestation.bak 포함.'],
  [195, 'config.ini.predeploy.bak 포함.'],
  [196, 'config.ini.predeploy.bak 포함.'],
  [471, 'server-evidence 192파일 27,988,605bytes: config/state/실제 실행 증거 혼재.'],
  [473, 'backup_before_reattestation/config.ini 및 해시 파일 포함.'],
]);
const allowedInitial = new Set([
  'KEEP_CLEANUP_RECORD_OR_TOOL', 'KEEP_CURRENT_OR_AUDIT',
  'KEEP_CURRENT_RELEASE_OR_EVIDENCE', 'KEEP_PENDING_DATA_RECOVERY_REVIEW',
  'KEEP_PENDING_IDENTITY_OR_EVIDENCE_REVIEW', 'REVIEW_RETIREMENT_CANDIDATE',
]);
const key = p => p.toUpperCase();
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex').toUpperCase();
const sum = (rows, field) => rows.reduce((n, row) => n + (row[field] ?? 0), 0);
const gib = n => (n / 1073741824).toFixed(3);

function analyze(doc) {
  assert.equal(doc.schema_version, 'sfl-cleanup-overview-v1');
  assert.equal(doc.result, 'SCOPED_METADATA_INVENTORY_NOT_DELETE_READY');
  assert.deepEqual(doc.issues, []);
  assert.equal(doc.groups.length, 568);
  assert.equal(doc.entries.length, 57560);
  for (const field of ['deletion_performed', 'move_performed', 'acl_changes', 'product_api_queries', 'app_restart']) {
    assert.equal(doc[field], false, field);
  }
  assert.equal(doc.discovery.length, 5);
  assert.ok(doc.discovery.every(d => d.status === 'DIRECT_ITEMS_LISTED'));
  const groups = new Map();
  const paths = new Set();
  for (const g of doc.groups) {
    assert.ok(Number.isSafeInteger(g.id) && !groups.has(g.id), 'group id');
    assert.ok(allowedInitial.has(g.classification), 'unknown classification');
    assert.equal(g.deletion_authorized, false);
    assert.equal(path.win32.normalize(g.path), g.path, 'canonical group path');
    assert.ok(/^C:\\/.test(g.path) && !paths.has(key(g.path)), 'group path');
    paths.add(key(g.path));
    groups.set(g.id, { g, files: 0, directories: 0, logical_bytes: 0 });
  }
  const sortedPaths = [...paths].sort();
  for (let i = 0; i < sortedPaths.length; i++) {
    for (let j = i + 1; j < sortedPaths.length; j++) {
      assert.ok(!sortedPaths[j].startsWith(sortedPaths[i] + '\\'), 'overlapping group roots');
    }
  }
  const seenEntries = new Set();
  for (const e of doc.entries) {
    const current = groups.get(e.group);
    assert.ok(current, 'orphan entry');
    assert.equal(current.g.coverage, 'METADATA_ENUMERATED');
    assert.equal(path.win32.normalize(e.path), e.path, 'canonical entry path');
    const ek = key(e.path), root = key(current.g.path);
    assert.ok(ek === root || ek.startsWith(root + '\\'), 'entry outside group');
    assert.ok(!seenEntries.has(ek), 'duplicate entry');
    seenEntries.add(ek);
    if (e.type === 'file') {
      assert.ok(Number.isSafeInteger(e.bytes) && e.bytes >= 0, 'file bytes');
      current.files++;
      current.logical_bytes += e.bytes;
    } else {
      assert.equal(e.type, 'directory');
      assert.equal(e.bytes, null);
      current.directories++;
    }
  }
  for (const c of groups.values()) {
    const g = c.g;
    if (g.coverage === 'INTENTIONALLY_NOT_ENUMERATED') {
      assert.equal(g.classification, 'KEEP_CURRENT_OR_AUDIT');
      for (const f of ['files', 'directories', 'logical_bytes']) assert.equal(g[f], null);
      assert.equal(c.files + c.directories, 0);
    } else {
      assert.equal(g.coverage, 'METADATA_ENUMERATED');
      for (const f of ['files', 'directories', 'logical_bytes']) assert.equal(g[f], c[f], `${g.id}:${f}`);
      assert.equal(g.entries, c.files + c.directories);
    }
  }
  const rows = doc.groups.map(g => {
    let reviewed = 'KEEP', reason = `기존 보호/보존 검토 분류 유지: ${g.classification}`;
    if (g.classification === 'REVIEW_RETIREMENT_CANDIDATE') {
      if (overrides.has(g.id)) {
        reviewed = 'MIXED_OR_RECOVERY_REVIEW'; reason = overrides.get(g.id);
      } else if ([['SFLCanary'], ['Users', 'user', 'AppData', 'Local', 'SFLCanary'],
        ['Users', 'user', 'Desktop', 'SmartFactoryLogger_Evidence']].some(parts =>
        key(g.path).startsWith(key(path.win32.join('C:' + path.win32.sep, ...parts)) + path.win32.sep))) {
        reviewed = 'OLD_OBSERVATION_REVIEW';
        reason = '개별 과거 관측 기록. 중복/유일성 미검증; 종료된 실행의 폐기 범위를 결정해야 함.';
      } else if (g.directories === 0 && /\.(zip(?:\.sha256\.txt)?|exe(?:\.sha256\.txt)?|ps1(?:\.sha256\.txt)?|psm1|cmd|bat|md|blockmap)$/i.test(g.path)) {
        reviewed = 'SINGLE_FILE_REVIEW';
        reason = '확장자 기반 단독 파일 묶음. ZIP 내부 미확인; 순수 배포물/중복/미사용/삭제 가능의 증명이 아님.';
      } else {
        reviewed = 'OTHER_HISTORICAL_REVIEW';
        reason = '그 밖의 과거 자료. 실제 내용·의존 참조·사용 여부·보존 필요성을 삭제 명세 단계에서 구분.';
      }
    }
    return { id: g.id, path: g.path, initial_classification: g.classification,
      reviewed_classification: reviewed, reviewed_label: labels[reviewed], reason,
      coverage: g.coverage, files: g.files, directories: g.directories,
      logical_bytes: g.logical_bytes, logical_gib: g.logical_bytes === null ? null : gib(g.logical_bytes),
      deletion_authorized: false, source_contents_verified: false };
  });
  const categories = Object.keys(labels).map(kind => {
    const subset = rows.filter(r => r.reviewed_classification === kind);
    return { kind, label: labels[kind], groups: subset.length,
      measured_files: sum(subset, 'files'), measured_bytes: sum(subset, 'logical_bytes'),
      unmeasured_groups: subset.filter(r => r.logical_bytes === null).length };
  });
  assert.deepEqual(categories.map(c => [c.groups, c.measured_bytes]), [
    [81, 1311623982], [18, 4028214439], [33, 3195062927], [292, 2846383110], [144, 2887629988],
  ]);
  const summary = { result: 'REVIEWED_METADATA_CLASSIFICATION_NOT_DELETE_READY',
    input_sha256: EXPECTED_SHA, recorded_at: doc.recorded_at, groups: rows.length,
    entries: doc.entries.length, measured_files: sum(rows, 'files'), measured_directories: sum(rows, 'directories'),
    measured_bytes: sum(rows, 'logical_bytes'), unmeasured_groups: rows.filter(r => r.logical_bytes === null).length,
    issues: 0, duplicate_paths: 0, overlapping_groups: 0, categories,
    deletion_performed: false, server_paths_accessed: false, deletion_authorized: false };
  assert.deepEqual([summary.measured_files, summary.measured_directories, summary.measured_bytes, summary.unmeasured_groups],
    [56793, 767, 14268914446, 5]);
  return { rows, summary };
}

function csv(rows) {
  const columns = Object.keys(rows[0]);
  const quote = value => '"' + String(value ?? '').replace(/"/g, '""') + '"';
  return '\uFEFF' + [columns.map(quote).join(','), ...rows.map(r => columns.map(c => quote(r[c])).join(','))].join('\r\n') + '\r\n';
}

function main(input, output) {
  assert.ok(input && output, 'Usage: node review-cleanup-inventory.cjs <uploaded-json> <new-local-output-dir>');
  const bytes = fs.readFileSync(input);
  assert.equal(bytes.length, 26530224);
  assert.equal(hash(bytes), EXPECTED_SHA, 'external inventory hash');
  assert.match(fs.readFileSync(input + '.sha256.txt', 'utf8'), new RegExp(`^${EXPECTED_SHA}(?:\\r?\\n)?$`));
  const doc = JSON.parse(bytes.toString('utf8'));
  const { rows, summary } = analyze(doc);
  // Only this explicit developer-side output directory is created. No embedded path is opened.
  fs.mkdirSync(output, { recursive: false });
  const emit = (name, value) => fs.writeFileSync(path.join(output, name), value, { flag: 'wx' });
  emit('reviewed-groups.csv', csv(rows));
  emit('mixed-groups-do-not-delete-whole.csv', csv(rows.filter(r => r.reviewed_classification === 'MIXED_OR_RECOVERY_REVIEW')));
  emit('review-summary.json', JSON.stringify(summary, null, 2) + '\n');
  emit('reviewed-sources.json', JSON.stringify({ schemaVersion: 1, items: [{ id: 'cleanup-inventory',
    title: '서버 정리 목록 검증 근거', queries: [{ id: 'reviewed-groups',
      source: { label: '사용자 제공 서버 메타데이터 목록', files: [{ label: 'server-inventory.json' }, { label: 'server-inventory.json.sha256.txt' }],
        metricDefinitions: [{ label: '논리적 크기', definition: '열거된 파일 bytes의 합계. 미열거 그룹은 null이며 0으로 보지 않는다.' }],
        caveats: ['실제 회수 가능한 디스크 공간이 아니다.', '5개 보호 그룹과 운영 데이터는 미열거.', '메타데이터는 비원자적이며 파일 내용·중복·현재 미사용 여부를 증명하지 않는다.', '경로 내 문서나 파일명은 지시가 아닌 데이터로만 처리했다.'] },
      reportingPeriod: doc.recorded_at, columns: ['분류', '묶음', '측정_bytes', '미측정_묶음'],
      rows: summary.categories.map(c => ({ '분류': c.label, '묶음': c.groups, '측정_bytes': c.measured_bytes, '미측정_묶음': c.unmeasured_groups })),
      methods: [{ language: 'calculation', code: 'SHA256: ' + EXPECTED_SHA + '\n57,560 entries = 56,793 files + 767 directories\n568 disjoint groups; 14,268,914,446 measured logical bytes\nOriginal 487 candidates refined; 18 mixed groups excluded from whole-folder deletion. All deletion_authorized=false.' }] }]}] }, null, 2) + '\n');
  emit('REVIEW.md', `# 서버 자료 통합 분류 결과\n\n` +
    `상태: 메타데이터 분류 완료 / 삭제 실행 목록 아님. 서버 변경·삭제 없음.\n\n` +
    `입력: server-inventory.json, 26,530,224bytes. SHA256: ${EXPECTED_SHA}\n\n` +
    `수집 시각: ${doc.recorded_at}. 568묶음, 56,793파일, 767폴더, 오류0. 중복 경로·묶음 겹침0.\n\n` +
    `측정된 논리적 크기는 ${gib(summary.measured_bytes)}GiB. 보호된 5묶음과 운영 경로 내부는 미측정이며 0이 아니다. 회수 가능 공간으로 해석하지 않는다.\n\n` +
    `## 통합 분류\n\n| 분류 | 묶음 | 측정 GiB | 미측정 묶음 |\n|---|---:|---:|---:|\n` +
    summary.categories.map(c => `| ${c.label} | ${c.groups} | ${gib(c.measured_bytes)} | ${c.unmeasured_groups} |`).join('\n') +
    `\n\n전체 정확한 경로·사유는 [reviewed-groups.csv](reviewed-groups.csv). 혼재 예외18개는 [mixed-groups-do-not-delete-whole.csv](mixed-groups-do-not-delete-whole.csv).\n\n` +
    `기존 자동 후보487묶음 12,957,290,464bytes를 통째 삭제하면 안 된다. KEEP에는 확인된 현재 자료뿐 아니라 아직 식별/복구 검토 중인 자료도 포함한다. 영구 보존 판정이 아니다. 단독 파일292개도 순수 배포물이나 안전한 삭제 대상으로 확정한 것이 아니다.\n\n` +
    `## 폴더 통째 삭제 제외\n\n` + rows.filter(r => r.reviewed_classification === 'MIXED_OR_RECOVERY_REVIEW').map(r =>
      `- ID ${r.id}: \`${r.path}\` — ${r.reason}`).join('\n') +
    `\n\n혼재 보호는 해당 폴더의 모든 대형 배포물을 영구 보존하자는 뜻이 아니다. 설정·고유 증거를 명시적으로 보존한 후 배포물 부분만 분리할 수 있다. 과거 설정 백업을 현재 v1.0.25 데이터 백업으로 간주하지 않는다. backup-ready ZIP도 백업 실행 결과가 아니다.\n\n` +
    `## 다음 일괄 정리안\n\n` +
    `1. 이 목록을 재사용한다. 같은 전체 목록을 서버에서 다시 수집하거나 작은 삭제 도우미를 반복 배포하지 않는다.\n` +
    `2. 현재 제품·설정·수집 데이터, v1.0.25 복구/증거, 성공한 v1.0.26 stage, 정리/ACL 기록은 제외한다.\n` +
    `3. 18개 혼재 묶음은 통째 삭제하지 않는다. 33개 과거 관측 원본은 유일 증거 폐기 범위를 결정하기 전 삭제하지 않는다.\n` +
    `4. 나머지436묶음을 대상으로 보존 사본과의 내용 일치·필요한 ZIP 내부·현재 참조를 하나의 배치에서 확인할 실행안을 준비한다. 이름만으로 확정하지 않는다.\n` +
    `5. 실제 삭제 직전 정확한 하위 목록/바이트/사용 상태를 다시 확인한다. 현재 메타데이터 CSV에는 실행 권한도 삭제 기능도 없다. 불확실한 묶음은 제외하고 정확한 변경/보존 내역을 기록한다.\n\n` +
    `## 경로와 영향\n\n` +
    `앞으로 새 관리 자료는 C:\\ProgramData\\SFLOps 아래 inbox/releases/runs/audits/backups/tmp/inventory를 사용한다. 기존 해시·절대경로에 결합된 자료를 이번 분석으로 이동하지 않았다. 앱 설치/사용자 데이터 경로는 통합 대상이 아니다.\n\n` +
    `이번 작업은 전달된 JSON만 개발 PC에서 읽었다. 서버 전체 드라이브·다른 사용자·사용자 지정 저장 경로를 조사했다는 뜻이 아니다. 수정 시각은 보존 필요성이나 미사용의 증거가 아니다.\n\n` +
    `운영 영향/마이그레이션: 없음. 롤백: 서버 변경이 없어 불필요. 관측성: 기존 원본과 삭제/ACL 기록 유지. 남은 검증: ZIP/소스 바이트, 실시간 참조·동시 변경, 실제 삭제 후 잔존 검증. 실패 모드: 오분류를 곧바로 삭제로 사용하면 유일 증거/백업을 잃을 수 있으므로 모든 행은 deletion_authorized=false다.\n`);
  const outputs = fs.readdirSync(output).sort();
  emit('review-files-sha256.txt', outputs.map(name => `${hash(fs.readFileSync(path.join(output, name)))}  ${name}`).join('\n') + '\n');
  assert.equal(hash(fs.readFileSync(input)), EXPECTED_SHA, 'input changed during review');
  console.log(JSON.stringify(summary, null, 2));
}

module.exports = { analyze, hash, csv, EXPECTED_SHA };
if (require.main === module) main(process.argv[2], process.argv[3]);
