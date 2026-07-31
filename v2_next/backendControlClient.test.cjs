'use strict';

const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const test = require('node:test');

const {
  requestBackendConnectionTest,
} = require('./backendControlClient');

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
