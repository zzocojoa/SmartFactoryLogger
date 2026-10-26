// Observe the actual UI without fetching images, replacing timers or changing focus.
const { performance } = require('node:perf_hooks');
const fs = require('node:fs');
const path = require('node:path');
const { createHash } = require('node:crypto');

const KEY = '__sflOperatorImageObservationV2';
const IMAGE_PATH = '/api/spot/live_image.jpg';
const COMPLETION_TAIL_MS = 2000;
const now = () => performance.timeOrigin + performance.now();
const finite = (value) => typeof value === 'number' && Number.isFinite(value);

function resolveImageOrigin(pageUrl, explicitOrigin) {
  const page = new URL(pageUrl);
  if (!['file:', 'http:', 'https:'].includes(page.protocol)) throw new Error('Unsupported page protocol');
  if (explicitOrigin === undefined && page.protocol !== 'file:') return page.origin;
  if (typeof explicitOrigin !== 'string') throw new Error('File page requires an explicit loopback image origin');
  const image = new URL(explicitOrigin);
  if (image.username || image.password || image.pathname !== '/' || image.search || image.hash
      || image.port === '0' || !['http:', 'https:'].includes(image.protocol)) {
    throw new Error('Exact image origin required');
  }
  if (page.protocol === 'file:') {
    if (image.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(image.hostname)) {
      throw new Error('File page requires an explicit loopback image origin');
    }
  } else if (image.origin !== page.origin) throw new Error('HTTP page image origin must match the page');
  return image.origin;
}

function distribution(values) {
  const sorted = values.slice().sort((a, b) => a - b);
  const percentile = (q) => sorted[Math.ceil(sorted.length * q) - 1] ?? null;
  return { count: sorted.length, min: sorted[0] ?? null, max: sorted.at(-1) ?? null,
    p50: percentile(.5), p95: percentile(.95), p99: percentile(.99) };
}

async function evaluateBounded(page, fn, args) {
  let timer;
  try {
    return await Promise.race([page.evaluate(fn, args), new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error('Observer evaluation deadline')), 5000);
    })]);
  } finally { clearTimeout(timer); }
}

function summarize(raw) {
  const hasTail = raw.observer_revision === 4;
  const loads = raw.dom.events.filter((e) => e.kind === 'load');
  const visibility = raw.dom.events.filter((e) => e.kind === 'state');
  const starts = raw.requests.filter((e) => e.kind === 'request');
  const domErrors = raw.dom.events.filter((e) => e.kind === 'error').length;
  const httpErrors = raw.requests.filter((e) => e.kind === 'failed'
    || (e.kind === 'response' && e.status >= 400)).length;
  const transactions = new Map();
  let httpValid = finite(raw.started_at) && finite(raw.ended_at) && raw.ended_at >= raw.started_at;
  let previous = raw.started_at;
  for (const event of raw.requests) {
    if (!Number.isInteger(event.id) || event.id < 0 || !finite(event.at)
        || event.at < previous || event.at > raw.ended_at) httpValid = false;
    previous = event.at;
    const state = transactions.get(event.id);
    if (event.kind === 'request' && !state) transactions.set(event.id, { phase: 'request' });
    else if (event.kind === 'response' && state?.phase === 'request'
        && Number.isInteger(event.status) && event.status >= 100 && event.status <= 599) {
      state.phase = 'response';
    } else if ((event.kind === 'finished' && state?.phase === 'response')
        || (event.kind === 'failed' && ['request', 'response'].includes(state?.phase))) {
      state.phase = 'ended';
    } else httpValid = false;
  }
  httpValid = httpValid && starts.length > 0 && [...transactions.values()].every((s) => s.phase === 'ended');
  const dom = raw.dom;
  const resourceEnd = hasTail ? dom.recording_ended_at : dom.ended_at;
  let pageClockValid = dom.clock === 'PAGE_MONOTONIC_MS' && finite(dom.started_at)
    && finite(dom.ended_at) && dom.ended_at >= dom.started_at
    && (!hasTail || (finite(resourceEnd) && resourceEnd >= dom.ended_at));
  previous = dom.started_at;
  for (const event of dom.events) {
    if (!finite(event.at) || event.at < previous || event.at > dom.ended_at) pageClockValid = false;
    previous = event.at;
  }
  if (hasTail) {
    previous = dom.ended_at;
    for (const event of dom.tail_events ?? []) {
      if (!finite(event.at) || event.at < previous || event.at > resourceEnd) pageClockValid = false;
      previous = event.at;
    }
  }
  const resources = (dom.resources ?? []).slice().sort((a, b) => a.start_ms - b.start_ms);
  const resourcesValid = pageClockValid && dom.resources_supported !== false
    && resources.length > 0 && resources.length === starts.length
    && resources.every((r) => finite(r.start_ms) && finite(r.response_end_ms)
      && dom.started_at <= r.start_ms && r.start_ms <= dom.ended_at
      && r.start_ms <= r.response_end_ms && r.response_end_ms <= resourceEnd);
  const gaps = pageClockValid ? loads.slice(1).map((e, i) => e.at - loads[i].at) : [];
  const waits = [];
  let next = 0;
  if (resourcesValid) {
    for (const load of loads) {
      while (next < resources.length && resources[next].start_ms < load.at) next++;
      if (next < resources.length) waits.push(resources[next++].start_ms - load.at);
    }
  }
  const ends = resourcesValid ? resources.filter((r) => r.response_end_ms <= dom.ended_at)
    .map((r) => r.response_end_ms).sort((a, b) => a - b) : [];
  const reasons = [];
  let tail;
  if (hasTail) {
    const boundary = raw.boundary ?? {};
    const cutoff = boundary.cutoff_at;
    const phases = new Map();
    for (const event of raw.requests.filter((e) => e.at <= cutoff)) {
      phases.set(event.id, event.kind);
    }
    const inflight = [...phases].filter(([, phase]) => !['finished', 'failed'].includes(phase))
      .map(([id]) => id).sort((a, b) => a - b);
    const unresolved = [...transactions].filter(([, state]) => state.phase !== 'ended')
      .map(([id]) => id).sort((a, b) => a - b);
    const sameIds = (actual, expected) => Array.isArray(actual)
      && actual.length === expected.length && actual.every((id, i) => id === expected[i]);
    const boundaryValid = finite(cutoff) && raw.started_at <= cutoff
      && finite(boundary.ended_at) && cutoff <= boundary.ended_at && boundary.ended_at <= raw.ended_at
      && boundary.budget_ms === COMPLETION_TAIL_MS
      && Number.isInteger(boundary.excluded_request_starts) && boundary.excluded_request_starts >= 0
      && sameIds(boundary.inflight_ids, inflight) && sameIds(boundary.unresolved_ids, unresolved)
      && starts.every((e) => e.at <= cutoff)
      && raw.requests.every((e) => e.at <= boundary.ended_at
        && (e.at <= cutoff || e.at <= cutoff + COMPLETION_TAIL_MS));
    const outcomes = raw.requests.filter((e) => e.at > cutoff && inflight.includes(e.id));
    tail = { status: boundaryValid && !unresolved.length ? 'COMPLETE' : 'INCOMPLETE',
      budget_ms: COMPLETION_TAIL_MS,
      elapsed_ms: finite(boundary.ended_at) && finite(cutoff) ? boundary.ended_at - cutoff : null,
      in_flight_at_cutoff: inflight.length,
      completed: outcomes.filter((e) => e.kind === 'finished').length,
      failed: outcomes.filter((e) => e.kind === 'failed').length,
      unresolved: unresolved.length,
      excluded_new_requests: boundary.excluded_request_starts ?? null };
    if (!boundaryValid) reasons.push('completion-tail-invalid');
    if (unresolved.length) reasons.push('completion-tail-unresolved');
    if (dom.tail_collection_complete !== true) reasons.push('completion-tail-dom-incomplete');
  }
  if (!raw.finished || raw.collector_error || dom.observer_lost) reasons.push('observer-not-complete');
  if (raw.overflow || dom.overflow) reasons.push('record-budget-exceeded');
  if (loads.length < 2) reasons.push('insufficient-load-events');
  if (!visibility.length || visibility.some((e) => e.visible !== true || e.focused !== true)) {
    reasons.push('visibility-or-focus-unconfirmed');
  }
  if (!httpValid) reasons.push('http-observation-incomplete');
  if (!pageClockValid) reasons.push('page-clock-invalid');
  if (!resourcesValid) reasons.push('resource-timing-incomplete');
  const requestStatus = httpErrors ? 'FAIL' : httpValid ? 'PASS' : 'NOT_EVALUATED';
  const loadStatus = domErrors ? 'FAIL' : loads.length ? 'PASS' : 'NOT_EVALUATED';
  return {
    policy: 'operational-evidence-v2',
    observer_revision: hasTail ? 4 : 3,
    measurement_status: reasons.length ? 'INCOMPLETE' : 'COMPLETE',
    incomplete_reasons: reasons,
    image_request_status: requestStatus, image_load_status: loadStatus,
    image_request_and_load_status: [requestStatus, loadStatus].includes('FAIL') ? 'FAIL'
      : requestStatus === 'PASS' && loadStatus === 'PASS' ? 'PASS' : 'NOT_EVALUATED',
    image_load_events: loads.length, image_request_count: starts.length,
    observed_error_events: domErrors + httpErrors, // Not a lost-frame count.
    max_inter_load_gap_ms: distribution(gaps).max,
    image_load_interval_ms: distribution(gaps),
    response_completion_interval_ms: distribution(ends.slice(1).map((end, i) => end - ends[i])),
    load_to_next_request_ms: distribution(waits),
    interval_clock: 'PAGE_MONOTONIC_MS',
    load_to_next_request_contract: 'NOT_EVALUATED',
    configured_wait_ms: null, // Never infer a setting from a measured gap.
    end_since_last_load_ms: pageClockValid && loads.length ? dom.ended_at - loads.at(-1).at : null,
    start_to_first_load_ms: pageClockValid && loads.length ? loads[0].at - dom.started_at : null,
    image_request_policy: 'PASSIVE_ACTUAL_UI_NO_SYNTHETIC_REQUESTS',
    load_event_is_physical_display_proof: false,
    display_freeze_status: 'NOT_EVALUATED',
    network_to_display_pairing: 'NOT_EVALUATED',
    device_frame_age: 'NOT_EVALUATED',
    operational_performance: 'NOT_EVALUATED',
    stored_image_integrity: 'NOT_EVALUATED',
    runtime_generation_binding: 'NOT_EVALUATED',
    field_gate: 'NOT_EVALUATED', release_gate: 'HOLD', promotion_allowed: false,
    ...(hasTail ? { completion_tail: tail,
      measurement_scope: 'WINDOW_DOM_AND_STARTED_HTTP_COHORT',
      tail_dom_events: Object.fromEntries(['load', 'error', 'state'].map((kind) =>
        [kind, (dom.tail_events ?? []).filter((event) => event.kind === kind).length])),
      tail_dom_events_are_cohort_paired: false,
      resource_completion_tail_count: resourcesValid
        ? resources.filter((r) => r.response_end_ms > dom.ended_at).length : null,
      measurement_window_ms: pageClockValid ? dom.ended_at - dom.started_at : null } : {}),
  };
}

async function observePage(page, { durationMs, runId, imageOrigin, context = 'ATTACHED_BROWSER' }) {
  if (!Number.isInteger(durationMs) || durationMs < 100 || durationMs > 7_200_000
      || !/^[A-Za-z0-9_-]{1,80}$/.test(runId)) throw new Error('Invalid bounded observation');
  const expectedImageOrigin = resolveImageOrigin(page.url(), imageOrigin);
  const raw = { schema: 'sfl-operator-image-observation-v2', observer_revision: 4, run_id: runId, context,
    started_at: now(), duration_ms: durationMs, requests: [], overflow: false,
    finished: false, dom: { events: [], overflow: false } };
  const ids = new Map();
  let sequence = 0;
  let acceptingRequests = true;
  let tailTimer;
  let settleTail;
  let tailClosed = false;
  const append = (row) => {
    if (raw.requests.length >= 200_000) raw.overflow = true;
    else raw.requests.push({ ...row, at: now() });
  };
  const belongs = (request) => {
    try {
      return request.frame() === page.mainFrame()
        && new URL(request.url()).pathname === IMAGE_PATH
        && new URL(request.url()).origin === expectedImageOrigin;
    } catch { return false; }
  };
  const request = (r) => {
    if (!belongs(r)) return;
    if (!acceptingRequests) { raw.boundary.excluded_request_starts++; return; }
    const id = sequence++;
    ids.set(r, id);
    append({ kind: 'request', id });
  };
  const canRecordCompletion = () => {
    if (tailClosed) return false;
    if (raw.boundary && now() > raw.boundary.cutoff_at + COMPLETION_TAIL_MS) {
      settleTail();
      return false;
    }
    return true;
  };
  const response = (r) => {
    if (ids.has(r.request()) && canRecordCompletion()) {
      append({ kind: 'response', id: ids.get(r.request()), status: r.status() });
    }
  };
  const finish = (r) => {
    if (!ids.has(r) || !canRecordCompletion()) return;
    append({ kind: 'finished', id: ids.get(r) });
    ids.delete(r);
    if (!acceptingRequests && !ids.size) settleTail();
  };
  const failed = (r) => {
    if (!ids.has(r) || !canRecordCompletion()) return;
    append({ kind: 'failed', id: ids.get(r) });
    ids.delete(r);
    if (!acceptingRequests && !ids.size) settleTail();
  };
  let installed = false;
  page.on('request', request);
  page.on('response', response);
  page.on('requestfinished', finish);
  page.on('requestfailed', failed);
  try {
    await evaluateBounded(page, ({ key, duration, imagePath, expectedOrigin, tailBudget }) => {
      if (window[key]) throw new Error('Image observer already active');
      const state = { events: [], tail_events: [], resources: [], overflow: false, clock: 'PAGE_MONOTONIC_MS',
        started_at: performance.now(), resources_supported: false };
      const stamp = () => performance.now();
      const record = (kind) => {
        if (state.events.length + state.tail_events.length >= 100_000) { state.overflow = true; return; }
        const target = state.ended_at === undefined ? state.events : state.tail_events;
        target.push({ kind, at: stamp(), visible: document.visibilityState === 'visible',
          focused: document.hasFocus() });
      };
      const onImage = (event) => {
        if (event.target instanceof HTMLImageElement && event.target.matches('.camera-image')) {
          record(event.type);
        }
      };
      const onState = () => record('state');
      const recordResources = (entries) => {
        for (const entry of entries) {
          const url = new URL(entry.name, location.href);
          if (url.origin !== expectedOrigin || url.pathname !== imagePath
              || entry.startTime < state.started_at
              || (state.ended_at !== undefined && entry.startTime > state.ended_at)) continue;
          if (state.resources.length >= 100_000) { state.overflow = true; break; }
          state.resources.push({ start_ms: entry.startTime, response_end_ms: entry.responseEnd });
        }
      };
      let resources;
      try {
        resources = new PerformanceObserver((list) => recordResources(list.getEntries()));
        resources.observe({ type: 'resource', buffered: false });
        state.resources_supported = true;
      } catch { /* Missing performance evidence remains INCOMPLETE. */ }
      document.addEventListener('load', onImage, true);
      document.addEventListener('error', onImage, true);
      document.addEventListener('visibilitychange', onState);
      window.addEventListener('focus', onState);
      window.addEventListener('blur', onState);
      const timer = setInterval(onState, 1000);
      let expiry;
      record('state');
      state.sealWindow = () => {
        if (state.ended_at !== undefined) return;
        record('state');
        state.ended_at = stamp();
      };
      state.dispose = () => {
        state.sealWindow();
        record('state');
        if (resources) {
          recordResources(resources.takeRecords());
          resources.disconnect();
        }
        clearInterval(timer);
        clearTimeout(expiry);
        document.removeEventListener('load', onImage, true);
        document.removeEventListener('error', onImage, true);
        document.removeEventListener('visibilitychange', onState);
        window.removeEventListener('focus', onState);
        window.removeEventListener('blur', onState);
        state.recording_ended_at = stamp();
      };
      window[key] = state;
      // A disconnected/crashed collector cannot leave a permanent page timer.
      expiry = setTimeout(() => { state.dispose(); delete window[key]; }, duration + tailBudget + 11_000);
    }, { key: KEY, duration: durationMs, imagePath: IMAGE_PATH, expectedOrigin: expectedImageOrigin,
      tailBudget: COMPLETION_TAIL_MS });
    installed = true;
    await new Promise((resolve) => setTimeout(resolve, durationMs));
    acceptingRequests = false;
    raw.boundary = { cutoff_at: now(), budget_ms: COMPLETION_TAIL_MS,
      inflight_ids: [...ids.values()].sort((a, b) => a - b), excluded_request_starts: 0 };
    const drain = new Promise((resolve) => {
      settleTail = () => {
        if (tailClosed) return;
        tailClosed = true;
        clearTimeout(tailTimer);
        raw.boundary.ended_at = now();
        raw.boundary.unresolved_ids = [...ids.values()].sort((a, b) => a - b);
        resolve();
      };
      tailTimer = setTimeout(settleTail, COMPLETION_TAIL_MS);
      if (!ids.size) settleTail();
    });
    // End the DOM window before waiting. Only the existing HTTP cohort may complete.
    raw.dom = await evaluateBounded(page, (key) => {
      const state = window[key];
      if (!state) throw new Error('Observer missing at cutoff');
      state.sealWindow();
      return { events: state.events, tail_events: [], overflow: state.overflow,
        resources: state.resources, resources_supported: state.resources_supported,
        clock: state.clock, started_at: state.started_at, ended_at: state.ended_at,
        recording_ended_at: state.ended_at, tail_collection_complete: false };
    }, KEY);
    await drain;
    raw.finished = !page.isClosed();
  } catch {
    raw.collector_error = true; // Do not retain exception strings containing URLs/secrets.
  } finally {
    clearTimeout(tailTimer);
    if (settleTail && !tailClosed) settleTail();
    page.off('request', request);
    page.off('response', response);
    page.off('requestfinished', finish);
    page.off('requestfailed', failed);
    if (installed) {
      try {
        const finalDom = await evaluateBounded(page, (key) => {
          const state = window[key];
          if (!state) return { events: [], overflow: false, observer_lost: true };
          state.dispose();
          delete window[key];
          return { events: state.events, tail_events: state.tail_events,
            overflow: state.overflow, resources: state.resources,
            resources_supported: state.resources_supported, clock: state.clock,
            started_at: state.started_at, ended_at: state.ended_at,
            recording_ended_at: state.recording_ended_at, tail_collection_complete: true };
        }, KEY);
        if (finalDom.observer_lost) {
          raw.dom.observer_lost = true;
          raw.finished = false;
        } else raw.dom = finalDom;
      } catch { raw.finished = false; raw.collector_error = true; }
    }
    ids.clear();
  }
  raw.ended_at = now();
  return { ...raw, summary: summarize(raw) };
}

async function main(argv) {
  const options = {};
  for (let i = 0; i < argv.length; i += 2) {
    const key = argv[i];
    if (!['--cdp', '--page-url', '--run-id', '--duration-ms', '--out', '--image-origin'].includes(key)
        || !argv[i + 1] || Object.hasOwn(options, key)) throw new Error('Invalid argument');
    options[key] = argv[i + 1];
  }
  if (!['--cdp', '--page-url', '--run-id', '--duration-ms', '--out'].every((key) => options[key])) {
    throw new Error('All five base arguments required');
  }
  resolveImageOrigin(options['--page-url'], options['--image-origin']);
  const cdp = new URL(options['--cdp']);
  if (cdp.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(cdp.hostname)
      || cdp.username || cdp.password || cdp.search || cdp.hash || cdp.pathname !== '/') {
    throw new Error('Existing local CDP endpoint required');
  }
  const destination = options['--out'];
  if (!path.isAbsolute(destination) || fs.existsSync(destination)
      || !fs.statSync(path.dirname(destination)).isDirectory()) throw new Error('New absolute output file required');
  const durationMs = Number(options['--duration-ms']);
  if (!Number.isInteger(durationMs) || durationMs < 100 || durationMs > 7_200_000
      || !/^[A-Za-z0-9_-]{1,80}$/.test(options['--run-id'])) throw new Error('Invalid duration or run ID');
  const { chromium } = require('playwright');
  const browser = await chromium.connectOverCDP(options['--cdp'], { noDefaults: true });
  try {
    const pages = browser.contexts().flatMap((c) => c.pages()).filter((p) => p.url() === options['--page-url']);
    if (pages.length !== 1) throw new Error('Exactly one existing target page required');
    const value = await observePage(pages[0], { durationMs, runId: options['--run-id'],
      imageOrigin: options['--image-origin'] });
    value.collector_sha256 = createHash('sha256').update(fs.readFileSync(__filename)).digest('hex');
    const bytes = Buffer.from(`${JSON.stringify(value, null, 2)}\n`);
    const fd = fs.openSync(destination, 'wx');
    try { fs.writeFileSync(fd, bytes); fs.fsyncSync(fd); } finally { fs.closeSync(fd); }
    console.log(JSON.stringify({ result_path: destination,
      sha256: createHash('sha256').update(bytes).digest('hex'), summary: value.summary }));
    process.exitCode = value.summary.measurement_status === 'COMPLETE'
      && value.summary.image_request_and_load_status === 'PASS' ? 0 : 1;
  } finally {
    // For connectOverCDP, Playwright closes its connection, not the existing browser.
    await browser.close();
  }
}

module.exports = { observePage, summarize, resolveImageOrigin };
if (require.main === module) main(process.argv.slice(2)).catch(() => {
  console.error('Operator image observation failed; no release approval.');
  process.exitCode = 1;
});
