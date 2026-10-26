const { test } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const net = require('node:net');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require('playwright');
const { observePage, summarize, resolveImageOrigin } = require('./observe_operator_image.cjs');

test('file pages require an exact loopback origin without weakening HTTP page isolation', () => {
  const file = 'file:///C:/fixture/index.html#/dashboard';
  for (const origin of [undefined, 'null', 'file:///C:/fixture/', 'http://192.168.0.7:8000',
    'http://127.0.0.1.example.com:8000', 'http://user:secret@127.0.0.1:8000',
    'http://127.0.0.1:8000/path', 'http://127.0.0.1:8000/?token=secret',
    'http://127.0.0.1:8000/#fragment', 'http://127.0.0.1:0', 'https://127.0.0.1:8000']) {
    assert.throws(() => resolveImageOrigin(file, origin));
  }
  assert.equal(resolveImageOrigin(file, 'http://127.0.0.1:8000'), 'http://127.0.0.1:8000');
  assert.equal(resolveImageOrigin(file, 'http://localhost:8000/'), 'http://localhost:8000');
  assert.equal(resolveImageOrigin('http://127.0.0.1:8000/dashboard'), 'http://127.0.0.1:8000');
  assert.throws(() => resolveImageOrigin('http://127.0.0.1:8000/dashboard', 'http://127.0.0.1:8001'));
});

test('packaged file page observes only its explicit loopback image origin', { timeout: 30_000 }, async () => {
  let imageRequests = 0;
  const server = http.createServer((_req, res) => {
    imageRequests++;
    res.writeHead(200, { 'Content-Type': 'image/svg+xml',
      'Access-Control-Allow-Origin': '*', 'Cache-Control': 'no-store' });
    res.end('<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2"/>');
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  let unrelatedRequests = 0;
  const unrelated = http.createServer((_req, res) => {
    unrelatedRequests++;
    res.writeHead(200, { 'Access-Control-Allow-Origin': '*' });
    res.end('unrelated fixture response');
  });
  await new Promise((resolve) => unrelated.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'sfl-file-image-test-'));
  const html = path.join(root, 'index.html');
  await fs.writeFile(html, `<img class="camera-image"><script>
    const img = document.querySelector('img');
    window.fixture = { loads: 0 };
    async function next() {
      const response = await fetch('${origin}/api/spot/live_image.jpg?t=' + Date.now());
      img.src = URL.createObjectURL(await response.blob());
    }
    img.onload = () => {
      fixture.loads++; URL.revokeObjectURL(img.src);
      if (fixture.loads < 3) setTimeout(next, 100);
    };
    window.startFixture = next;
  </script>`);
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    await page.goto(pathToFileURL(html).href);
    const observation = observePage(page, { durationMs: 1500, runId: 'file-fixture',
      imageOrigin: origin, context: 'HEADLESS_FILE_FIXTURE_NOT_FIELD_UI' });
    await page.waitForFunction(() => Boolean(window.__sflOperatorImageObservationV2));
    await page.evaluate(() => window.startFixture());
    await page.evaluate((port) => fetch(`http://127.0.0.1:${port}/api/spot/live_image.jpg`),
      unrelated.address().port);
    const result = await observation;
    assert.equal(imageRequests, 3);
    assert.equal(unrelatedRequests, 1);
    assert.equal(result.summary.image_request_count, 3);
    assert.equal(result.dom.resources.length, 3);
    assert.equal(result.summary.image_load_events, 3);
    assert.equal(result.summary.measurement_status, 'COMPLETE', JSON.stringify(result.summary));
    assert.equal(result.summary.runtime_generation_binding, 'NOT_EVALUATED');
    assert.equal(result.summary.display_freeze_status, 'NOT_EVALUATED');
    assert.equal(result.summary.release_gate, 'HOLD');
    assert.equal(await page.evaluate(() => Boolean(window.__sflOperatorImageObservationV2)), false);
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
    await new Promise((resolve) => unrelated.close(resolve));
    // Keep the tiny fixture as evidence; no recursive temp deletion.
  }
});

function completeEvidence() {
  return { started_at: 10_000, ended_at: 11_000, finished: true, overflow: false,
    requests: [
      { kind: 'request', id: 0, at: 10_010 },
      { kind: 'response', id: 0, at: 10_020, status: 200 },
      { kind: 'finished', id: 0, at: 10_050 },
      { kind: 'request', id: 1, at: 10_350 },
      { kind: 'response', id: 1, at: 10_400, status: 200 },
      { kind: 'finished', id: 1, at: 10_600 },
    ],
    dom: { overflow: false, clock: 'PAGE_MONOTONIC_MS', started_at: 0, ended_at: 1000,
      resources: [
        { start_ms: 10, response_end_ms: 50 },
        { start_ms: 350, response_end_ms: 600 },
      ],
      events: [
        { kind: 'state', at: 0, visible: true, focused: true },
        { kind: 'load', at: 100, visible: true, focused: true },
        { kind: 'load', at: 650, visible: true, focused: true },
        { kind: 'state', at: 1000, visible: true, focused: true },
      ],
    } };
}

test('DOM loads without HTTP evidence cannot complete an observation', () => {
  const raw = completeEvidence();
  raw.requests = [];
  const result = summarize(raw);
  assert.equal(result.measurement_status, 'INCOMPLETE');
  assert.equal(result.image_request_status, 'NOT_EVALUATED');
  assert.equal(result.operational_performance, 'NOT_EVALUATED');
});

test('request lifecycle, observer errors and clock failures remain incomplete', () => {
  for (const change of ['no-response', 'duplicate-id', 'backwards-dom', 'backwards-request',
    'collector-error', 'observer-lost', 'missing-resource']) {
    const raw = completeEvidence();
    if (change === 'no-response') raw.requests = raw.requests.filter((e) => e.kind !== 'response');
    if (change === 'duplicate-id') raw.requests[3].id = 0;
    if (change === 'backwards-dom') raw.dom.events[2].at = 10;
    if (change === 'backwards-request') raw.requests[2].at = 10_000;
    if (change === 'collector-error') raw.collector_error = true;
    if (change === 'observer-lost') raw.dom.observer_lost = true;
    if (change === 'missing-resource') raw.dom.resources = [];
    assert.equal(summarize(raw).measurement_status, 'INCOMPLETE', change);
  }
});

test('load intervals and next-request waits use only the page monotonic clock', () => {
  const raw = completeEvidence();
  const result = summarize(raw);
  assert.equal(result.measurement_status, 'COMPLETE');
  assert.equal(result.max_inter_load_gap_ms, 550);
  assert.equal(result.load_to_next_request_ms.min, 250);
  assert.equal(result.load_to_next_request_ms.max, 250);
  assert.equal(result.start_to_first_load_ms, 100);
  assert.equal(result.end_since_last_load_ms, 350);
  assert.equal(result.load_to_next_request_contract, 'NOT_EVALUATED');
  assert.equal(result.display_freeze_status, 'NOT_EVALUATED');
  assert.equal(result.network_to_display_pairing, 'NOT_EVALUATED');
  // Moving the host clock origin cannot change browser-side intervals.
  raw.started_at += 5_000_000;
  raw.ended_at += 5_000_000;
  for (const event of raw.requests) event.at += 5_000_000;
  assert.deepEqual(summarize(raw).load_to_next_request_ms, result.load_to_next_request_ms);
});

test('hidden, empty or unfinished observation never passes measurement', () => {
  const raw = completeEvidence();
  raw.dom.events[0].focused = false;
  raw.dom.events[1].at = 10;
  raw.dom.events[2].at = 800;
  const result = summarize(raw);
  assert.equal(result.measurement_status, 'INCOMPLETE');
  assert.equal(result.max_inter_load_gap_ms, 790);
  assert.equal(result.operational_performance, 'NOT_EVALUATED');
  assert.equal(result.stored_image_integrity, 'NOT_EVALUATED');
  assert.equal(result.promotion_allowed, false);
  raw.dom.events.splice(-1, 0, { kind: 'error', at: 900 });
  assert.equal(summarize(raw).image_request_and_load_status, 'FAIL');
  raw.dom.events = [];
  assert.equal(summarize(raw).image_request_and_load_status, 'NOT_EVALUATED');
});

test('an unresponsive renderer cannot block observer initialization indefinitely',
  { timeout: 10_000 }, async () => {
    const listeners = new Map();
    const page = {
      url() { return 'http://127.0.0.1:8000/dashboard'; },
      on(name, fn) { listeners.set(name, fn); },
      off(name) { listeners.delete(name); },
      evaluate() { return new Promise(() => {}); },
    };
    const result = await observePage(page, { durationMs: 100, runId: 'unresponsive-fixture' });
    assert.equal(result.collector_error, true);
    assert.equal(result.summary.measurement_status, 'INCOMPLETE');
    assert.equal(listeners.size, 0);
  });

test('passive browser observation follows load-complete plus wait and cleans up', { timeout: 30_000 }, async () => {
  let deviceRequests = 0;
  const server = http.createServer((req, res) => {
    if (req.url === '/api/spot/live_image.jpg') {
      deviceRequests++;
      setTimeout(() => {
        res.writeHead(200, { 'Content-Type': 'image/svg+xml', 'Cache-Control': 'no-store' });
        res.end('<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2"><rect width="2" height="2"/></svg>');
      }, 300);
    } else {
      res.setHeader('Content-Type', 'text/html');
      res.end(`<img class="camera-image"><script>
        const img = document.querySelector('img');
        window.fixture = { requests: 0, loads: 0, starts: [], loaded: [], done: false };
        async function next() {
          fixture.requests++; fixture.starts.push(performance.now());
          const r = await fetch('/api/spot/live_image.jpg');
          img.src = URL.createObjectURL(await r.blob());
        }
        img.onload = () => {
          fixture.loads++; fixture.loaded.push(performance.now());
          URL.revokeObjectURL(img.src);
          if (fixture.loads < 4) setTimeout(next, 250); else fixture.done = true;
        };
        window.startFixture = next;
      </script>`);
    }
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const reservation = net.createServer();
  await new Promise((resolve) => reservation.listen(0, '127.0.0.1', resolve));
  const debugPort = reservation.address().port;
  await new Promise((resolve) => reservation.close(resolve));
  const browser = await chromium.launch({ headless: true,
    args: [`--remote-debugging-port=${debugPort}`, '--remote-debugging-address=127.0.0.1'] });
  try {
    const page = await browser.newPage();
    await page.goto(`http://127.0.0.1:${server.address().port}/dashboard`);
    const observation = observePage(page, { durationMs: 3000, runId: 'fixture',
      context: 'HEADLESS_FIXTURE_NOT_FIELD_UI' });
    await page.waitForFunction(() => Boolean(window.__sflOperatorImageObservationV2));
    await page.evaluate(() => window.startFixture());
    const result = await observation;
    const fixture = await page.evaluate(() => window.fixture);
    assert.equal(fixture.loads, 4);
    assert.equal(deviceRequests, 4); // The observer did not add requests.
    assert.equal(result.summary.image_request_count, 4);
    assert.equal(result.summary.image_load_events, 4);
    assert.equal(result.dom.resources.length, 4);
    assert.equal(result.summary.measurement_status, 'COMPLETE', JSON.stringify(result.summary));
    assert.equal(result.summary.load_to_next_request_ms.count, 3);
    assert.ok(result.summary.load_to_next_request_ms.min >= 240);
    assert.ok(result.summary.image_load_interval_ms.min >= 540);
    assert.equal(result.summary.configured_wait_ms, null);
    assert.equal(result.summary.load_to_next_request_contract, 'NOT_EVALUATED');
    for (let i = 1; i < fixture.starts.length; i++) {
      assert.ok(fixture.starts[i] - fixture.loaded[i - 1] >= 240);
      assert.ok(fixture.starts[i] - fixture.starts[i - 1] >= 540);
    }
    assert.equal(result.summary.operational_performance, 'NOT_EVALUATED');
    assert.equal(result.summary.release_gate, 'HOLD');
    assert.equal(page.isClosed(), false);
    assert.equal(await page.evaluate(() => Boolean(window.__sflOperatorImageObservationV2)), false);
    const attached = await chromium.connectOverCDP(`http://127.0.0.1:${debugPort}`, { noDefaults: true });
    await attached.close();
    assert.equal(browser.isConnected(), true);
    assert.equal(await page.evaluate(() => window.fixture.done), true);
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
});

async function boundaryFixture(outcome, verify) {
  let imageRequests = 0;
  const timers = new Set();
  const server = http.createServer((req, res) => {
    if (req.url.startsWith('/api/spot/live_image.jpg')) {
      imageRequests++;
      if (imageRequests === 4) return; // A new request after cutoff must not extend the cohort.
      const reply = () => {
        if (outcome === 'failed' && imageRequests >= 3) {
          // Start a response before truncation so Chromium cannot retry an unopened socket.
          res.writeHead(200, { 'Content-Type': 'image/svg+xml', 'Content-Length': '100' });
          res.write('partial');
          timers.add(setTimeout(() => res.destroy(), 50));
          return;
        }
        res.writeHead(200, { 'Content-Type': 'image/svg+xml', 'Cache-Control': 'no-store' });
        res.end('<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2"/>');
      };
      if (imageRequests < 3) reply();
      else if (outcome !== 'pending') timers.add(setTimeout(reply, 900));
      return;
    }
    res.setHeader('Content-Type', 'text/html');
    res.end(`<img class="camera-image"><script>
      const img = document.querySelector('img');
      window.fixture = { loads: 0 };
      async function next() {
        const response = await fetch('/api/spot/live_image.jpg');
        img.src = URL.createObjectURL(await response.blob());
      }
      img.onload = () => {
        fixture.loads++; URL.revokeObjectURL(img.src);
        if (fixture.loads < 3) next().catch(() => {});
      };
      window.startFixture = () => {
        next();
        setTimeout(() => fetch('/api/spot/live_image.jpg?after-cutoff').catch(() => {}), 600);
      };
    </script>`);
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    await page.goto(`http://127.0.0.1:${server.address().port}/dashboard`);
    const listenerNames = ['request', 'response', 'requestfinished', 'requestfailed'];
    const before = listenerNames.map((name) => page.listenerCount(name));
    const observation = observePage(page, { durationMs: 400, runId: `boundary-${outcome}`,
      context: 'HEADLESS_BOUNDARY_FIXTURE_NOT_FIELD_UI' });
    await page.waitForFunction(() => Boolean(window.__sflOperatorImageObservationV2));
    await page.evaluate(() => window.startFixture());
    if (outcome === 'closed') timers.add(setTimeout(() => page.close().catch(() => {}), 700));
    const result = await observation;
    assert.deepEqual(listenerNames.map((name) => page.listenerCount(name)), before);
    assert.equal(page.isClosed(), outcome === 'closed');
    if (!page.isClosed()) {
      assert.equal(await page.evaluate(() => Boolean(window.__sflOperatorImageObservationV2)), false);
    }
    await verify(result);
    assert.equal(imageRequests, 4); // Two warm images, one in flight, one excluded new request.
    console.log(JSON.stringify({ fixture: outcome, summary: result.summary,
      boundary: result.boundary, recording_ended_at: result.dom.recording_ended_at,
      window_ended_at: result.dom.ended_at }));
  } finally {
    for (const timer of timers) clearTimeout(timer);
    await browser.close();
    server.closeAllConnections();
    await new Promise((resolve) => server.close(resolve));
  }
}

test('in-flight request completes in bounded tail without extending the image measurement window',
  { timeout: 15_000 }, () => boundaryFixture('finished', async (raw) => {
    assert.equal(raw.summary.measurement_status, 'COMPLETE', JSON.stringify(raw.summary));
    assert.equal(raw.summary.image_request_count, 3);
    assert.equal(raw.summary.image_load_events, 2);
    assert.equal(raw.summary.completion_tail.completed, 1);
    assert.equal(raw.summary.completion_tail.excluded_new_requests, 1);
    assert.equal(raw.summary.completion_tail.unresolved, 0);
    assert.ok(raw.dom.recording_ended_at - raw.dom.ended_at >= 300);
    assert.ok(raw.summary.end_since_last_load_ms < 600);
    assert.equal(raw.dom.resources.length, 3);
    assert.equal(raw.summary.resource_completion_tail_count, 1);
    assert.equal(raw.summary.measurement_scope, 'WINDOW_DOM_AND_STARTED_HTTP_COHORT');
    assert.equal(raw.summary.tail_dom_events_are_cohort_paired, false);
    assert.equal(raw.summary.operational_performance, 'NOT_EVALUATED');
    assert.equal(raw.summary.release_gate, 'HOLD');
  }));

test('invalid completion-tail evidence cannot complete a revision4 observation', () => {
  const original = completeEvidence();
  original.observer_revision = 4;
  original.dom.recording_ended_at = 1100;
  original.dom.tail_events = [];
  original.dom.tail_collection_complete = true;
  original.boundary = { cutoff_at: 10_700, ended_at: 10_700, budget_ms: 2000,
    inflight_ids: [], unresolved_ids: [], excluded_request_starts: 0 };
  assert.equal(summarize(original).measurement_status, 'COMPLETE');
  for (const change of ['wrong-cohort', 'invented-unresolved', 'backwards-boundary',
    'wrong-budget', 'tail-clock', 'late-resource', 'negative-excluded']) {
    const raw = structuredClone(original);
    if (change === 'wrong-cohort') raw.boundary.cutoff_at = 10_360;
    if (change === 'invented-unresolved') raw.boundary.unresolved_ids = [99];
    if (change === 'backwards-boundary') raw.boundary.ended_at = 9000;
    if (change === 'wrong-budget') raw.boundary.budget_ms = 3000;
    if (change === 'tail-clock') raw.dom.tail_events = [{ kind: 'load', at: 999 }];
    if (change === 'late-resource') raw.dom.resources[1].response_end_ms = 1200;
    if (change === 'negative-excluded') raw.boundary.excluded_request_starts = -1;
    assert.equal(summarize(raw).measurement_status, 'INCOMPLETE', change);
  }
});

test('in-flight request failure after cutoff is retained as FAIL',
  { timeout: 15_000 }, () => boundaryFixture('failed', async (raw) => {
    assert.equal(raw.summary.image_request_status, 'FAIL');
    assert.equal(raw.summary.completion_tail.failed, 1);
    assert.equal(raw.summary.completion_tail.unresolved, 0);
    assert.equal(raw.summary.promotion_allowed, false);
  }));

test('page closure during completion tail retains the window snapshot and stays incomplete',
  { timeout: 15_000 }, () => boundaryFixture('closed', async (raw) => {
    assert.equal(raw.summary.measurement_status, 'INCOMPLETE');
    assert.equal(raw.finished, false);
    assert.equal(raw.collector_error, true);
    assert.equal(raw.dom.tail_collection_complete, false);
    assert.equal(raw.summary.image_load_events, 2);
    assert.ok(raw.summary.incomplete_reasons.includes('observer-not-complete'));
  }));

test('in-flight request exceeding the bounded tail remains incomplete without aborting the page',
  { timeout: 15_000 }, () => boundaryFixture('pending', async (raw) => {
    assert.equal(raw.summary.measurement_status, 'INCOMPLETE');
    assert.equal(raw.summary.image_request_status, 'NOT_EVALUATED');
    assert.equal(raw.summary.completion_tail.unresolved, 1);
    assert.equal(raw.summary.completion_tail.excluded_new_requests, 1);
    assert.equal(raw.summary.completion_tail.budget_ms, 2000);
    assert.ok(raw.summary.completion_tail.elapsed_ms < 3000);
    assert.ok(raw.summary.incomplete_reasons.includes('completion-tail-unresolved'));
  }));
