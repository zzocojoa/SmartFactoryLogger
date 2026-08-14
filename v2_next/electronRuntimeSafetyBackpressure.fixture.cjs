'use strict';

const path = require('node:path');

const { createRotatingFileLogger } = require('./electronRuntimeSafety');
const { createShutdownDiagnosticTrace } = require('./shutdownDiagnosticTrace');

async function main() {
  const directoryPath = process.argv[2];
  const trace = createShutdownDiagnosticTrace({
    directoryPath,
    sessionId: 'backpressure-fixture',
    processId: process.pid,
  });
  const first = trace.mark('fixture.before-log');
  await trace.waitFor(first);

  const logger = createRotatingFileLogger({
    logPath: path.join(directoryPath, 'unused.log'),
    fsImpl: {
      statSync: () => ({ size: 0 }),
      appendFileSync: () => undefined,
    },
    diagnosticObserver: (phase, details) => {
      trace.mark(`logger.${phase}`, details);
    },
    echoToConsole: false,
  });

  logger.log('x'.repeat(1024 * 1024));
  const completed = trace.mark('fixture.after-log');
  await trace.waitFor(completed);
  await trace.close();
}

main().catch((error) => {
  process.stderr.write(`${error.stack ?? error}\n`);
  process.exitCode = 1;
});
