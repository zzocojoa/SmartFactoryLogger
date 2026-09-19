'use strict';
// Explicit test allowlist: never discover or execute operational entrypoints.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const repo = path.resolve(__dirname, '..');
if (process.platform !== 'win32') throw new Error('Windows on NTFS is required');
const pwsh = process.env.SFL_TEST_PWSH || 'pwsh.exe';
const desktop = path.join(process.env.SystemRoot, 'System32/WindowsPowerShell/v1.0/powershell.exe');
const nodes = [
  'attestation-extraction-cleanup', 'build-intermediate-cleanup', 'chrome-test-cache',
  'dist-migration', 'finalize-verification-retention', 'isolated-test-cache',
  'manage-verification-entrypoints', 'manage-verification-files', 'plan-dependency-cleanup',
  'plan-dist-acl-scope', 'plan-dist-cleanup', 'rehearse-build-dependencies',
  'review-artifacts-temp', 'review-build-dependencies', 'review-build-intermediates',
  'review-dist-artifacts', 'review-large-verification-files', 'stage-extraction-cleanup',
].map(n => 'scripts/' + n + '.test.cjs');
const ps7 = [
  'attestation-extraction-cleanup', 'build-intermediate-cleanup', 'chrome-test-cache',
  'dist-migration', 'isolated-test-cache', 'migrate-desktop-test', 'remove-dependency-cleanup',
  'repair-dependency-acl', 'review-build-cache', 'stage-extraction-cleanup',
].map(n => 'scripts/' + n + '.test.ps1');
const audits = [
  'test-read-server-paths', 'test-read-quarantine-pre-v1020', 'test-cleanup-archive',
  'test-acl-repair-launch', 'test-repair-sflops-acl',
];
const auditMarkers = [
  /"result"\s*:\s*"READ_ONLY_PATH_DISCOVERY_FUNCTION_TEST_PASS"/,
  /"result"\s*:\s*"QUARANTINE_READ_ONLY_TEST_PASS"/,
  /"result"\s*:\s*"CLEANUP_SYNTHETIC_TEST_PASS"/,
  /"result"\s*:\s*"ACL_REPAIR_BYTE_BOUND_LAUNCH_TEST_PASS"/,
  /"result"\s*:\s*"SFLOPS_ACL_REPAIR_TEST_PASS"/,
];
const stage = [
  'test-stage', 'test-current-v1025', 'test-error-details-v1025',
  'test-storage-recovery-v1025', 'test-minimal-backup-preflight-v1025',
  'test-cold-backup', 'test-install-cold-boundary-r2',
];
const stageMarkers = [
  /^\[FIXTURE PASS\] \d+ checks\./m,
  /"result"\s*:\s*"V1026_CURRENT_BASELINE_LOCAL_FIXTURES_PASS"/,
  /"result"\s*:\s*"V1025_ERROR_DETAIL_LOCAL_FIXTURES_PASS"/,
  /"result"\s*:\s*"V1025_STORAGE_RECOVERY_LOCAL_FIXTURES_PASS"/,
  /"result"\s*:\s*"V1025_MINIMAL_BACKUP_PREFLIGHT_LOCAL_TEST_PASS"/,
  /^result\s*:\s*COLD_BACKUP_SYNTHETIC_TEST_PASS\s*$/m,
  /"result"\s*:\s*"V1026_INSTALL_R2_COLD_BOUNDARY_TEST_PASS"/,
];
const id = crypto.randomUUID();
function plain(p) {
  for (let n = p; ; n = path.dirname(n)) {
    if (fs.existsSync(n) && fs.lstatSync(n).isSymbolicLink()) throw new Error('Linked fixture parent');
    if (path.dirname(n) === n) return;
  }
}
for (const leaf of ['.tmp', 'artifacts']) {
  const p = path.join(repo, leaf);
  plain(p);
  fs.mkdirSync(p, { recursive: true });
}
// Keep historical PS5.1 fixtures below their intentional 240-character limit.
const root = path.join(repo, '.tmp', 'ops-offline-' + id.slice(0, 12));
fs.mkdirSync(root); // Unique, no overwrite or recursive deletion.
const results = [];
function run(label, executable, args, marker) {
  console.log('[RUN] ' + label);
  const started = Date.now();
  const p = spawnSync(executable, args, {
    cwd: repo, encoding: 'utf8', windowsHide: true, timeout: 180000, maxBuffer: 8 * 1024 * 1024,
    env: executable === desktop ? {
      ...Object.fromEntries(Object.entries(process.env).filter(([k]) => k.toLowerCase() !== 'psmodulepath')),
      PSModulePath: path.join(path.dirname(desktop), 'Modules'),
    } : process.env,
  });
  const output = (p.stdout || '') + (p.stderr || '');
  // Only synthetic fixture output; no deployment receipts or registry are read.
  fs.writeFileSync(path.join(root, String(results.length).padStart(2, '0') + '.log'), output, { flag: 'wx' });
  const ok = !p.error && p.status === 0 && (!marker || marker.test(output));
  const result = { test: label, passed: ok, elapsed_ms: Date.now() - started };
  const count = output.match(/# tests (\d+)/) || output.match(/"assertions"\s*:\s*(\d+)/) || output.match(/^assertions\s*:\s*(\d+)/m) ||
    output.match(/^\[(?:PASS|FIXTURE PASS)\] (\d+)/m);
  if (count) result.reported_checks = Number(count[1]);
  if (label.endsWith('dist-migration.test.ps1')) {
    result.administrator_acl_copy_tests = /administrator_acl_copy_tests=True/.test(output);
  }
  if (label.endsWith('repair-dependency-acl.test.ps1')) result.native_acl_inheritance_tested = false;
  results.push(result);
  if (!ok) {
    console.error(output, p.error || '');
    throw new Error('Offline test failed: ' + label);
  }
  console.log('[PASS] ' + label);
}
function ps(exe, file, args = [], marker = /^\[PASS\] /m) {
  run(file, exe, ['-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File',
    path.join(repo, file), ...args], marker);
}
try {
  ps(pwsh, 'scripts/test-ops-syntax.ps1');
  ps(desktop, 'scripts/test-ops-syntax.ps1', ['-DesktopOnly']);
  run('Node fixture suites', process.execPath, ['--test', ...nodes], /# fail 0/);
  for (const file of ps7) ps(pwsh, file,
    file.endsWith('repair-dependency-acl.test.ps1') ? ['-PureOnly'] : []);
  for (const [i, n] of audits.entries()) ps(desktop, 'scripts/server-path-audit/' + n + '.ps1', [], auditMarkers[i]);
  for (const [i, n] of stage.entries()) ps(desktop, 'scripts/server-stage-v1026/' + n + '.ps1', [
    '-OutputRoot', path.join(root, 's' + i),
  ], stageMarkers[i]);
  ps(desktop, 'scripts/server-stage-v1026/test-root-inbox-acl.ps1', [
    '-Helper', path.join(repo, 'scripts/server-stage-v1026/repair-root-inbox-acl.ps1'),
    '-OutputRoot', path.join(repo, 'artifacts', 'ops-offline-' + id),
  ], /"result"\s*:\s*"ROOT_INBOX_ACL_LOCAL_TEST_PASS"/);
} finally {
  fs.writeFileSync(path.join(root, 'summary.json'), JSON.stringify({
    schema_version: 'ops-offline-tests-v1', results, fixture_root: root,
    real_server_tests_run: false, deployment_authorized: false,
    excluded: [
      'test-cleanup-batch-preparation.ps1', 'test-cleanup-release-pair.ps1',
      'test-release-pair-resume.ps1', 'test-cold-backup-transfer.ps1',
      'test-minimal-cold-backup-v1025.ps1', 'test-install-v1026-after-minimal-backup.ps1',
      'test-installed-read-v1026.ps1',
      'test-review-cleanup-inventory.cjs',
    ],
  }, null, 2), { flag: 'wx' });
  console.log('[RESULT] ' + path.join(root, 'summary.json'));
}
console.log('[COMPLETE] Synthetic offline suites passed. No operational entrypoint executed.');
