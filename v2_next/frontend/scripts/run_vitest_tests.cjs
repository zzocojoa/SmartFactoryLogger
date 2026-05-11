const { spawnSync } = require('node:child_process');

const ignoredJestArgs = new Set(['--runInBand', '--watchAll=false']);
const vitestArgs = process.argv.slice(2).filter((arg) => !ignoredJestArgs.has(arg));
const command = process.platform === 'win32' ? 'vitest.cmd' : 'vitest';
const result = spawnSync(command, ['run', ...vitestArgs], {
  shell: process.platform === 'win32',
  stdio: 'inherit',
});

if (result.error) {
  throw result.error;
}

process.exit(result.status ?? 1);
