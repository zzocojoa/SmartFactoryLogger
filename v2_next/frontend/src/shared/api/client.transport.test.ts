import axios from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from './client';

// Exercise Axios's real browser adapter without contacting a backend or camera.
class ControlledXHR {
  static requests: ControlledXHR[] = [];
  method = '';
  url = '';
  timeout = 0;
  status = 0;
  statusText = '';
  responseText = '';
  headers: Record<string, string> = {};
  body: unknown;
  aborted = false;
  onloadend: (() => void) | null = null;
  onabort: (() => void) | null = null;
  ontimeout: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor() {
    ControlledXHR.requests.push(this);
  }

  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }

  setRequestHeader(name: string, value: string) {
    this.headers[name.toLowerCase()] = value;
  }

  getAllResponseHeaders() {
    return 'content-type: application/json\r\n';
  }

  send(body: unknown) {
    this.body = body;
  }

  abort() {
    this.aborted = true;
    this.onabort?.();
  }

  respond(status: number, data: unknown) {
    this.status = status;
    this.responseText = JSON.stringify(data);
    this.onloadend?.();
  }
}

function onlyRequest() {
  expect(ControlledXHR.requests).toHaveLength(1);
  return ControlledXHR.requests[0];
}

describe('apiClient browser transport contract', () => {
  beforeEach(() => {
    // Fail before issuing any request if an upgrade changes adapter selection.
    expect(axios.getAdapter(apiClient.defaults.adapter ?? [])).toBe(axios.getAdapter('xhr'));
    ControlledXHR.requests = [];
    vi.stubGlobal('XMLHttpRequest', ControlledXHR);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('keeps XHR as the default browser adapter', () => {
    expect(axios.getAdapter(apiClient.defaults.adapter ?? [])).toBe(axios.getAdapter('xhr'));
  });

  it('preserves query parameters and decodes local config JSON', async () => {
    const pending = apiClient.get('/api/spot/config', {
      baseURL: 'http://127.0.0.1:8000',
      params: { sample: 1 },
    });
    const request = onlyRequest();
    expect(request.method).toBe('GET');
    expect(request.url).toBe('http://127.0.0.1:8000/api/spot/config?sample=1');
    request.respond(200, { image: { image_status: 'ok' } });
    await expect(pending).resolves.toMatchObject({
      status: 200,
      data: { image: { image_status: 'ok' } },
    });
  });

  it('preserves JSON request serialization including Korean metadata', async () => {
    const data = { product_number: '제품-01', mold_number: 'M-02' };
    const pending = apiClient.post('/test-only/metadata', data);
    const request = onlyRequest();
    expect(request.method).toBe('POST');
    expect(request.headers['content-type']).toBe('application/json');
    expect(JSON.parse(String(request.body))).toEqual(data);
    request.respond(200, { applied: true });
    await expect(pending).resolves.toMatchObject({ data: { applied: true } });
  });

  it('keeps HTTP failure details and does not retry on its own', async () => {
    const pending = apiClient.get('/test-only/failure');
    onlyRequest().respond(503, { detail: 'temporarily unavailable' });
    await expect(pending).rejects.toMatchObject({
      code: 'ERR_BAD_RESPONSE',
      response: { status: 503, data: { detail: 'temporarily unavailable' } },
    });
    expect(ControlledXHR.requests).toHaveLength(1);
  });

  it('keeps timeout errors distinct from HTTP responses', async () => {
    const pending = apiClient.get('/test-only/timeout', { timeout: 1200 });
    const request = onlyRequest();
    expect(request.timeout).toBe(1200);
    request.ontimeout?.();
    await expect(pending).rejects.toMatchObject({ code: 'ECONNABORTED' });
    expect(ControlledXHR.requests).toHaveLength(1);
  });

  it('preserves a browser network error without retrying', async () => {
    const pending = apiClient.get('/test-only/network');
    onlyRequest().onerror?.();
    await expect(pending).rejects.toMatchObject({ code: 'ERR_NETWORK' });
    expect(ControlledXHR.requests).toHaveLength(1);
  });

  it('aborts the in-flight request when polling is cancelled', async () => {
    const controller = new AbortController();
    const pending = apiClient.get('/test-only/poll', { signal: controller.signal });
    const request = onlyRequest();
    controller.abort();
    await expect(pending).rejects.toMatchObject({ code: 'ERR_CANCELED' });
    expect(request.aborted).toBe(true);
    expect(ControlledXHR.requests).toHaveLength(1);
  });
});
