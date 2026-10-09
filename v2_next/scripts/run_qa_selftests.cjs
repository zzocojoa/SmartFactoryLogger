const path = require('node:path');
const { spawnSync } = require('node:child_process');

const selfTests = [
  'measure_nsis_operational_ready.ps1',
  'collect_nsis_startup_trace.ps1',
  'run_closeout_hang_reproduction.ps1',
  'verify_windows_release_signature.ps1',
  'verify_windows_release_workflow_contract.ps1',
];

// PowerShell 7's inherited module paths can shadow Windows PowerShell 5.1's
// built-ins. Let powershell.exe reconstruct its native paths for each child.
const childEnv = Object.fromEntries(Object.entries(process.env)
  .filter(([key]) => key.toLowerCase() !== 'psmodulepath'));

for (const selfTest of selfTests) {
  const result = spawnSync('powershell.exe', [
    '-NoProfile', '-ExecutionPolicy', 'Bypass',
    '-File', path.join(__dirname, selfTest), '-SelfTest',
  ], { env: childEnv, stdio: 'inherit', windowsHide: true });
  if (result.error) {
    console.error(`Could not run ${selfTest}: ${result.error.message}`);
    process.exitCode = 1;
    break;
  }
  if (result.status !== 0) {
    process.exitCode = result.status ?? 1;
    break;
  }
}
