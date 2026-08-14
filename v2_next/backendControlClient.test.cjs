'use strict';

const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const test = require('node:test');

const {
  requestBackendConnectionTest,
  requestBackendGracefulShutdown,
  requestBackendHealth,
} = require('./backendControlClient');
const { stopProcessTree } = require('./backendProcessLifecycle');

function createRequestHarness() {
  const request = new EventEmitter();
  request.setTimeout = (_timeoutMs, callback) => {
    request.timeoutCallback = callback;
  };
  request.destroy = (error) => {
    request.emit('error', error);
  };
  request.end = (body) => {
    request.body = body;
  };

  let responseCallback;
  const requestImpl = (options, callback) => {
    request.options = options;
    responseCallback = callback;
    return request;
  };

  return {
    request,
    requestImpl,
    respond(statusCode = 200) {
      const response = new EventEmitter();
      response.statusCode = statusCode;
      response.resume = () => {
        response.resumed = true;
      };
      response.destroy = () => {
        response.emit('aborted');
        response.emit('close');
      };
      responseCallback(response);
      return response;
    },
  };
}

function requestWith(harness, overrides = {}) {
  return requestBackendConnectionTest('{"spot":{}}', {
    controlToken: 'test-control-token',
    port: 8000,
    maxResponseBytes: 64,
    timeoutMs: 50,
    requestImpl: harness.requestImpl,
    ...overrides,
  });
}

function shutdownWith(harness, overrides = {}) {
  return requestBackendGracefulShutdown({
    controlToken: 'test-control-token',
    port: 8000,
    reason: 'electron_exit',
    timeoutMs: 50,
    requestImpl: harness.requestImpl,
    ...overrides,
  });
}

function healthWith(harness, overrides = {}) {
  return requestBackendHealth({
    controlToken: 'test-control-token',
    port: 8000,
    maxResponseBytes: 64,
    timeoutMs: 50,
    requestImpl: harness.requestImpl,
    ...overrides,
  });
}

test('backend connection-test client returns a complete successful JSON response', async () => {
  const harness = createRequestHarness();
  const resultPromise = requestWith(harness);
  const response = harness.respond();
  response.emit('data', Buffer.from('{"ok":true}'));
  response.emit('end');
  response.emit('close');

  assert.deepEqual(await resultPromise, { ok: true });
  assert.equal(harness.request.options.hostname, '127.0.0.1');
  assert.equal(harness.request.options.headers['X-SFL-Control-Token'], 'test-control-token');
  assert.equal(harness.request.body, '{"spot":{}}');
});

test('backend connection-test client rejects oversized and malformed responses', async () => {
  const oversizedHarness = createRequestHarness();
  const oversizedPromise = requestWith(oversizedHarness, { maxResponseBytes: 4 });
  oversizedHarness.respond().emit('data', Buffer.from('{"ok":true}'));
  await assert.rejects(oversizedPromise, /exceeded the size limit/);

  const malformedHarness = createRequestHarness();
  const malformedPromise = requestWith(malformedHarness);
  const malformedResponse = malformedHarness.respond();
  malformedResponse.emit('data', Buffer.from('not-json'));
  malformedResponse.emit('end');
  await assert.rejects(malformedPromise, /not valid JSON/);
});

test('backend connection-test client rejects non-success HTTP responses', async () => {
  const harness = createRequestHarness();
  const resultPromise = requestWith(harness);
  const response = harness.respond(503);
  response.emit('data', Buffer.from('{"detail":"unavailable"}'));
  response.emit('end');

  await assert.rejects(resultPromise, /HTTP 503/);
});

test('backend connection-test client rejects every premature response termination mode', async () => {
  for (const eventName of ['aborted', 'error', 'close']) {
    const harness = createRequestHarness();
    const resultPromise = requestWith(harness);
    const response = harness.respond();
    if (eventName === 'error') {
      response.emit(eventName, new Error('socket reset'));
    } else {
      response.emit(eventName);
    }
    await assert.rejects(resultPromise, /aborted|failed|closed before completion/);
  }
});

test('backend connection-test client rejects request timeout and socket errors', async () => {
  const timeoutHarness = createRequestHarness();
  const timeoutPromise = requestWith(timeoutHarness);
  timeoutHarness.request.timeoutCallback();
  await assert.rejects(timeoutPromise, /timed out/);

  const errorHarness = createRequestHarness();
  const errorPromise = requestWith(errorHarness);
  errorHarness.request.emit('error', new Error('connect refused'));
  await assert.rejects(errorPromise, /connect refused/);
});

test('backend graceful-shutdown client sends the authenticated closeout request', async () => {
  const harness = createRequestHarness();
  const phases = [];
  const resultPromise = shutdownWith(harness, {
    onPhase: (phase) => phases.push(phase),
  });
  const response = harness.respond(202);
  response.emit('end');
  response.emit('close');

  await resultPromise;
  assert.equal(harness.request.options.hostname, '127.0.0.1');
  assert.equal(harness.request.options.port, 8000);
  assert.equal(harness.request.options.path, '/api/control/shutdown');
  assert.equal(harness.request.options.method, 'POST');
  assert.equal(harness.request.options.headers['X-SFL-Control-Token'], 'test-control-token');
  assert.deepEqual(JSON.parse(harness.request.body), { reason: 'electron_exit' });
  assert.equal(response.resumed, true);
  assert.deepEqual(phases, [
    'request-create-start',
    'request-create-complete',
    'request-end-start',
    'request-end-complete',
    'response-received',
    'response-end',
  ]);
});

test('backend health client reads only a bounded local health response', async () => {
  const harness = createRequestHarness();
  const resultPromise = healthWith(harness);
  const response = harness.respond(200);
  response.emit('data', Buffer.from('{"running":true}'));
  response.emit('end');
  response.emit('close');

  assert.deepEqual(await resultPromise, { running: true });
  assert.equal(harness.request.options.hostname, '127.0.0.1');
  assert.equal(harness.request.options.path, '/api/control/health');
  assert.equal(harness.request.options.method, 'GET');
  assert.equal(
    harness.request.options.headers['X-SFL-Control-Token'],
    'test-control-token'
  );
  assert.equal(harness.request.body, undefined);
});

test('backend health client fails closed on malformed and oversized responses', async () => {
  const malformedHarness = createRequestHarness();
  const malformedPromise = healthWith(malformedHarness);
  const malformedResponse = malformedHarness.respond(200);
  malformedResponse.emit('data', Buffer.from('not-json'));
  malformedResponse.emit('end');
  await assert.rejects(malformedPromise, /not valid JSON/);

  const oversizedHarness = createRequestHarness();
  const oversizedPromise = healthWith(oversizedHarness, { maxResponseBytes: 4 });
  oversizedHarness.respond(200).emit('data', Buffer.from('{"running":true}'));
  await assert.rejects(oversizedPromise, /exceeded the size limit/);
});

test('backend health client fails closed on HTTP, timeout, socket, and premature-close errors', async () => {
  const httpHarness = createRequestHarness();
  const httpPromise = healthWith(httpHarness);
  const httpResponse = httpHarness.respond(503);
  httpResponse.emit('data', Buffer.from('{"detail":"unavailable"}'));
  httpResponse.emit('end');
  await assert.rejects(httpPromise, /HTTP 503/);

  const timeoutHarness = createRequestHarness();
  const timeoutPromise = healthWith(timeoutHarness);
  timeoutHarness.request.timeoutCallback();
  await assert.rejects(timeoutPromise, /timed out/);

  const socketHarness = createRequestHarness();
  const socketPromise = healthWith(socketHarness);
  socketHarness.request.emit('error', new Error('connect refused'));
  await assert.rejects(socketPromise, /connect refused/);

  for (const eventName of ['aborted', 'error', 'close']) {
    const harness = createRequestHarness();
    const resultPromise = healthWith(harness);
    const response = harness.respond();
    if (eventName === 'error') {
      response.emit(eventName, new Error('socket reset'));
    } else {
      response.emit(eventName);
    }
    await assert.rejects(resultPromise, /aborted|failed|closed before completion/);
  }
});

test('backend graceful-shutdown client rejects HTTP, timeout, and socket failures', async () => {
  const httpHarness = createRequestHarness();
  const httpPromise = shutdownWith(httpHarness);
  const httpResponse = httpHarness.respond(503);
  httpResponse.emit('end');
  await assert.rejects(httpPromise, /HTTP 503/);

  const timeoutHarness = createRequestHarness();
  const timeoutPromise = shutdownWith(timeoutHarness);
  timeoutHarness.request.timeoutCallback();
  await assert.rejects(timeoutPromise, /timed out/);

  const errorHarness = createRequestHarness();
  const errorPromise = shutdownWith(errorHarness);
  errorHarness.request.emit('error', new Error('connect refused'));
  await assert.rejects(errorPromise, /connect refused/);

  const setupHarness = createRequestHarness();
  await assert.rejects(
    shutdownWith(setupHarness, {
      requestImpl: () => {
        throw new ReferenceError('transport dependency unavailable');
      },
    }),
    /transport dependency unavailable/
  );
});

test('backend graceful-shutdown client rejects every premature response termination mode', async () => {
  for (const eventName of ['aborted', 'error', 'close']) {
    const harness = createRequestHarness();
    const resultPromise = shutdownWith(harness);
    const response = harness.respond();
    if (eventName === 'error') {
      response.emit(eventName, new Error('socket reset'));
    } else {
      response.emit(eventName);
    }
    await assert.rejects(resultPromise, /aborted|failed|closed before completion/);
  }
});

test('authenticated shutdown request completes the process lifecycle without force', async (t) => {
  const child = new EventEmitter();
  child.pid = 4321;
  child.exitCode = null;
  child.signalCode = null;
  const observed = {};
  const server = http.createServer((request, response) => {
    const chunks = [];
    request.on('data', (chunk) => chunks.push(chunk));
    request.on('end', () => {
      observed.method = request.method;
      observed.path = request.url;
      observed.token = request.headers['x-sfl-control-token'];
      observed.body = JSON.parse(Buffer.concat(chunks).toString('utf8'));
      response.writeHead(200, { 'Content-Type': 'application/json' });
      response.end('{"ok":true}');
      setImmediate(() => {
        child.exitCode = 0;
        child.emit('close', 0, null);
      });
    });
  });
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  t.after(() => new Promise((resolve) => server.close(resolve)));
  const address = server.address();
  assert.notEqual(address, null);
  assert.equal(typeof address, 'object');

  const result = await stopProcessTree(child, {
    killTree: () => assert.fail('force kill must not run after authenticated shutdown'),
    requestGracefulStop: () => requestBackendGracefulShutdown({
      controlToken: 'integration-control-token',
      port: address.port,
      reason: 'electron_exit',
      timeoutMs: 500,
    }),
    graceMs: 1_000,
    forceCloseMs: 100,
  });

  assert.deepEqual(result, {
    stopped: true,
    reason: 'close',
    exitCode: 0,
    signalCode: null,
    forced: false,
  });
  assert.deepEqual(observed, {
    method: 'POST',
    path: '/api/control/shutdown',
    token: 'integration-control-token',
    body: { reason: 'electron_exit' },
  });
});

test('Electron before-quit delegates shutdown transport to the tested control client', () => {
  const mainText = fs.readFileSync(path.join(__dirname, 'main.js'), 'utf8');

  assert.match(
    mainText,
    /requestBackendGracefulShutdown:\s*sendBackendGracefulShutdown/
  );
  assert.match(mainText, /return sendBackendGracefulShutdown\(\{/);
  assert.doesNotMatch(mainText, /\bhttp\.request\b/);
});
