const { spawnSync } = require('child_process');
const path = require('path');

const repoRoot = path.resolve(__dirname, '..');
const appDataRoot = path.join(repoRoot, '.tmp_test_appdata');

const env = {
  ...process.env,
  APPDATA: appDataRoot,
  SFL_CONFIG_PATH: path.join(appDataRoot, 'config.ini'),
};

const pythonExe = path.join(repoRoot, 'backend', '.venv', 'Scripts', 'python.exe');
const result = spawnSync(
  pythonExe,
  ['-m', 'unittest', 'discover', '-s', 'backend/tests'],
  {
    cwd: repoRoot,
    env,
    stdio: 'inherit',
  },
);

if (result.error) {
  console.error(result.error.message);
  process.exit(1);
}

process.exit(result.status ?? 1);
