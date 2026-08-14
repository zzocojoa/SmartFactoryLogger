const crypto = require('node:crypto');
const path = require('node:path');
const { execFileSync } = require('node:child_process');

const asar = require('@electron/asar');

const REQUIRED_RUNTIME_FILES = Object.freeze([
  'main.js',
  'backendControlClient.js',
  'backendProcessLifecycle.js',
  'electronRuntimeSafety.js',
  'shutdownDiagnosticTrace.js',
  'shutdownDiagnosticTraceWorker.js',
]);

function getArgument(name) {
  const index = process.argv.indexOf(name);
  if (index === -1 || index + 1 >= process.argv.length) {
    throw new Error(`Missing required argument: ${name}`);
  }
  return process.argv[index + 1];
}

function sha256(buffer) {
  return crypto.createHash('sha256').update(buffer).digest('hex').toUpperCase();
}

function normalizeText(buffer) {
  return Buffer.from(buffer.toString('utf8').replaceAll('\r\n', '\n'), 'utf8');
}

function main() {
  const sourceRoot = path.resolve(getArgument('--source-root'));
  const archivePath = path.resolve(getArgument('--asar'));
  const expectedCommit = getArgument('--expected-commit');
  if (!/^[0-9a-f]{40}$/i.test(expectedCommit)) {
    throw new Error(`Invalid expected commit: ${expectedCommit}`);
  }

  const gitPrefix = execFileSync(
    'git',
    ['-C', sourceRoot, 'rev-parse', '--show-prefix'],
    { encoding: 'utf8' },
  ).trim().replaceAll('\\', '/');
  const readGitBlob = (relativePath) => execFileSync(
    'git',
    ['-C', sourceRoot, 'show', `${expectedCommit}:${gitPrefix}${relativePath}`],
    { encoding: 'buffer', maxBuffer: 16 * 1024 * 1024 },
  );
  const sourcePackage = JSON.parse(
    readGitBlob('package.json').toString('utf8'),
  );
  const packagedPackage = JSON.parse(
    asar.extractFile(archivePath, 'package.json').toString('utf8'),
  );

  for (const field of ['name', 'version', 'main']) {
    if (packagedPackage[field] !== sourcePackage[field]) {
      throw new Error(
        `Packaged package ${field} mismatch: expected=${sourcePackage[field]} actual=${packagedPackage[field]}`,
      );
    }
  }

  const files = REQUIRED_RUNTIME_FILES.map((relativePath) => {
    const source = normalizeText(readGitBlob(relativePath));
    const packaged = normalizeText(asar.extractFile(archivePath, relativePath));
    const sourceSHA256 = sha256(source);
    const packagedSHA256 = sha256(packaged);
    if (sourceSHA256 !== packagedSHA256) {
      throw new Error(
        `Packaged Electron source mismatch: ${relativePath} expected=${sourceSHA256} actual=${packagedSHA256}`,
      );
    }
    return { relative_path: relativePath, sha256: sourceSHA256 };
  });

  process.stdout.write(
    `${JSON.stringify({
      status: 'PASS',
      archive: archivePath,
      expected_commit: expectedCommit,
      comparison: 'utf8-lf-normalized',
      package: {
        name: packagedPackage.name,
        version: packagedPackage.version,
        main: packagedPackage.main,
      },
      files,
    })}\n`,
  );
}

try {
  main();
} catch (error) {
  process.stderr.write(`[FAIL] ${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
}
