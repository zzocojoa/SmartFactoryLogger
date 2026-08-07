'use strict';

const http = require('http');

function requestBackendConnectionTest(serializedPayload, options) {
  const {
    controlToken,
    port,
    maxResponseBytes,
    timeoutMs,
    requestImpl = http.request,
  } = options;

  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (callback, value) => {
      if (settled) {
        return;
      }
      settled = true;
      callback(value);
    };
    const fail = (error) => finish(reject, error);

    const request = requestImpl({
      hostname: '127.0.0.1',
      port,
      path: '/api/control/test-connection',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(serializedPayload),
        'X-SFL-Control-Token': controlToken,
      },
    }, (response) => {
      const chunks = [];
      let responseBytes = 0;
      let responseEnded = false;

      response.on('data', (chunk) => {
        if (settled) {
          return;
        }
        responseBytes += chunk.length;
        if (responseBytes > maxResponseBytes) {
          fail(new Error('Backend connection-test response exceeded the size limit.'));
          response.destroy();
          return;
        }
        chunks.push(chunk);
      });
      response.once('aborted', () => {
        fail(new Error('Backend connection-test response was aborted.'));
      });
      response.once('error', () => {
        fail(new Error('Backend connection-test response failed.'));
      });
      response.once('close', () => {
        if (!responseEnded) {
          fail(new Error('Backend connection-test response closed before completion.'));
        }
      });
      response.once('end', () => {
        responseEnded = true;
        if (settled) {
          return;
        }
        const body = Buffer.concat(chunks).toString('utf8');
        let parsed;
        try {
          parsed = JSON.parse(body);
        } catch (_error) {
          fail(new Error('Backend connection-test response was not valid JSON.'));
          return;
        }
        if (response.statusCode >= 200 && response.statusCode < 300) {
          finish(resolve, parsed);
          return;
        }
        fail(new Error(`Backend connection-test endpoint returned HTTP ${response.statusCode}.`));
      });
    });
    request.setTimeout(timeoutMs, () => {
      request.destroy(new Error('Backend connection-test request timed out.'));
    });
    request.once('error', fail);
    request.end(serializedPayload);
  });
}

function requestBackendGracefulShutdown(options) {
  const {
    controlToken,
    port,
    reason,
    timeoutMs,
    requestImpl = http.request,
  } = options;
  const serializedPayload = JSON.stringify({ reason });

  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (callback, value) => {
      if (settled) {
        return;
      }
      settled = true;
      callback(value);
    };
    const fail = (error) => finish(reject, error);

    const request = requestImpl({
      hostname: '127.0.0.1',
      port,
      path: '/api/control/shutdown',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(serializedPayload),
        'X-SFL-Control-Token': controlToken,
      },
    }, (response) => {
      let responseEnded = false;
      response.once('aborted', () => {
        fail(new Error('Backend shutdown response was aborted.'));
      });
      response.once('error', () => {
        fail(new Error('Backend shutdown response failed.'));
      });
      response.once('close', () => {
        if (!responseEnded) {
          fail(new Error('Backend shutdown response closed before completion.'));
        }
      });
      response.once('end', () => {
        responseEnded = true;
        if (response.statusCode >= 200 && response.statusCode < 300) {
          finish(resolve);
          return;
        }
        fail(new Error(`Backend shutdown endpoint returned HTTP ${response.statusCode}.`));
      });
      response.resume();
    });
    request.setTimeout(timeoutMs, () => {
      request.destroy(new Error('Backend shutdown request timed out.'));
    });
    request.once('error', fail);
    request.end(serializedPayload);
  });
}

function requestBackendHealth(options) {
  const {
    controlToken,
    port,
    maxResponseBytes,
    timeoutMs,
    requestImpl = http.request,
  } = options;

  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (callback, value) => {
      if (settled) {
        return;
      }
      settled = true;
      callback(value);
    };
    const fail = (error) => finish(reject, error);
    const request = requestImpl({
      hostname: '127.0.0.1',
      port,
      path: '/api/control/health',
      method: 'GET',
      headers: {
        'X-SFL-Control-Token': controlToken,
      },
    }, (response) => {
      const chunks = [];
      let responseBytes = 0;
      let responseEnded = false;
      response.on('data', (chunk) => {
        if (settled) {
          return;
        }
        responseBytes += chunk.length;
        if (responseBytes > maxResponseBytes) {
          fail(new Error('Backend health response exceeded the size limit.'));
          response.destroy();
          return;
        }
        chunks.push(chunk);
      });
      response.once('aborted', () => fail(new Error('Backend health response was aborted.')));
      response.once('error', () => fail(new Error('Backend health response failed.')));
      response.once('close', () => {
        if (!responseEnded) {
          fail(new Error('Backend health response closed before completion.'));
        }
      });
      response.once('end', () => {
        responseEnded = true;
        if (settled) {
          return;
        }
        if (response.statusCode < 200 || response.statusCode >= 300) {
          fail(new Error(`Backend health endpoint returned HTTP ${response.statusCode}.`));
          return;
        }
        try {
          finish(resolve, JSON.parse(Buffer.concat(chunks).toString('utf8')));
        } catch (_error) {
          fail(new Error('Backend health response was not valid JSON.'));
        }
      });
    });
    request.setTimeout(timeoutMs, () => {
      request.destroy(new Error('Backend health request timed out.'));
    });
    request.once('error', fail);
    request.end();
  });
}

module.exports = {
  requestBackendConnectionTest,
  requestBackendGracefulShutdown,
  requestBackendHealth,
};
