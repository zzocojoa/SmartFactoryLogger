const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const readArg = (name, fallback) => {
  const index = process.argv.indexOf(name);
  if (index === -1 || index + 1 >= process.argv.length) {
    return fallback;
  }
  return process.argv[index + 1];
};

const round = (value) => Number(value.toFixed(3));

const url = readArg('--url', 'http://127.0.0.1:3000/dashboard');
const label = readArg('--label', 'current');
const outPath = readArg('--out', path.join('.gstack', 'benchmark-reports', `${label}-react-profiler.json`));
const durationMs = Number.parseInt(readArg('--duration-ms', '30000'), 10);

if (!Number.isFinite(durationMs) || durationMs <= 0) {
  throw new Error(`Invalid --duration-ms value: ${readArg('--duration-ms', '30000')}`);
}

const appendProfilerParams = (value) => {
  const parsed = new URL(value);
  parsed.searchParams.set('sfReactProfiler', '1');
  parsed.searchParams.set('sfReactProfilerReset', '1');
  return parsed.toString();
};

const maskUrlForArtifact = (value) => {
  try {
    const parsed = new URL(value);
    return `masked-origin${parsed.pathname}`;
  } catch {
    return 'masked-url';
  }
};

const assertSafeProfilerArtifactUrl = () => {
  const sentinel = 'QUERY_SENTINEL_DO_NOT_PERSIST';
  const testOrigin = `${'http'}${'://'}${'example.invalid'}`;
  const sensitiveParams = new URLSearchParams();
  sensitiveParams.set('token', sentinel);
  sensitiveParams.set('debug', 'true');
  const targetUrl = appendProfilerParams(
    `${testOrigin}/dashboard?${sensitiveParams.toString()}#fragment-${sentinel}`,
  );
  const maskedUrl = maskUrlForArtifact(targetUrl);
  const errorPayload = JSON.stringify({
    message: 'React profiler collector did not capture samples.',
    targetUrl: maskedUrl,
  });
  const forbiddenValues = [
    sentinel,
    ['http', '://'].join(''),
    ['https', '://'].join(''),
    'example.invalid',
    'token=',
    'debug=',
    'sfReactProfiler',
    'sfReactProfilerReset',
    '#fragment',
  ];

  for (const forbidden of forbiddenValues) {
    if (maskedUrl.includes(forbidden) || errorPayload.includes(forbidden)) {
      throw new Error(`Unsafe profiler artifact URL retained forbidden value: ${forbidden}`);
    }
  }

  if (maskedUrl !== 'masked-origin/dashboard') {
    throw new Error(`Unexpected profiler artifact URL mask: ${maskedUrl}`);
  }

  process.stdout.write('mask-url-self-test passed\n');
};

if (process.argv.includes('--self-test-mask-url')) {
  assertSafeProfilerArtifactUrl();
  process.exit(0);
}

const main = async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
    const pageErrors = [];
    const consoleErrors = [];

    page.on('pageerror', (error) => {
      pageErrors.push(error.message);
    });
    page.on('console', (message) => {
      if (message.type() === 'error') {
        consoleErrors.push(message.text());
      }
    });

    const targetUrl = appendProfilerParams(url);
    await page.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForSelector('.App', { timeout: 30000 });
    await page.waitForTimeout(durationMs);

    const result = await page.evaluate(() => {
      const collector = window.__SF_REACT_PROFILER__;
      return {
        collectorFound: Boolean(collector),
        sampleCount: collector?.samples.length ?? 0,
        summary: collector?.summarize() ?? [],
      };
    });

    if (!result.collectorFound || result.sampleCount === 0) {
      throw new Error(JSON.stringify({
        message: 'React profiler collector did not capture samples.',
        targetUrl: maskUrlForArtifact(targetUrl),
        durationMs,
        collectorFound: result.collectorFound,
        sampleCount: result.sampleCount,
        pageErrors,
        consoleErrors,
      }, null, 2));
    }

    const payload = {
      label,
      url: maskUrlForArtifact(targetUrl),
      durationMs,
      capturedAt: new Date().toISOString(),
      sampleCount: result.sampleCount,
      summary: result.summary.map((item) => ({
        ...item,
        totalActualDuration: round(item.totalActualDuration),
        totalBaseDuration: round(item.totalBaseDuration),
        maxActualDuration: round(item.maxActualDuration),
        avgActualDuration: round(item.avgActualDuration),
      })),
      pageErrors,
      consoleErrors,
    };

    fs.mkdirSync(path.dirname(outPath), { recursive: true });
    fs.writeFileSync(outPath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
    process.stdout.write(`${outPath}\n`);
  } finally {
    await browser.close();
  }
};

main().catch(async (error) => {
  process.stderr.write(`${error.stack ?? error.message}\n`);
  process.exit(1);
});
