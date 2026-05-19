const http = require('node:http');

const port = Number.parseInt(process.env.SF_PROFILER_MOCK_PORT ?? '8000', 10);
let tick = 0;
let startedAt = Date.now();

const spotImageBody = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGN4+fIFAAQjApwOFy5VAAAAAElFTkSuQmCC',
  'base64',
);

const writeJson = (res, value) => {
  const body = JSON.stringify(value);
  res.writeHead(200, {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'no-store',
    'access-control-allow-origin': '*',
    'access-control-allow-methods': 'GET,POST,OPTIONS,DELETE',
    'access-control-allow-headers': 'content-type,authorization',
  });
  res.end(body);
};

const buildFactoryData = () => {
  tick += 1;
  const now = new Date().toISOString();

  return {
    Time: now,
    Status: 'Running',
    Speed: Number((3 + Math.sin(tick / 5) * 1.2).toFixed(1)),
    Press: Number((128 + Math.cos(tick / 6) * 8).toFixed(1)),
    Count: tick,
    EndPos: 1015,
    Billet_Length: Number((tick % 30).toFixed(1)),
    Die_ID: 'D-01',
    Billet_Cycle_ID: `C-${tick}`,
    Spot: Number((520 + Math.sin(tick / 8) * 16).toFixed(1)),
    Temp_F: 430,
    Temp_B: 431,
    Billet_Temp: Number((300 + Math.sin(tick / 10) * 28).toFixed(1)),
    Mold1: 478,
    Mold2: 480,
    Mold3: 479,
    Mold4: 479,
    Mold5: 478,
    Mold6: 478,
    At_Temp: Number((32 + Math.sin(tick / 12) * 2).toFixed(1)),
    At_Pre: Number((34 + Math.cos(tick / 12) * 2).toFixed(1)),
    Computed: {
      speed_level: 'normal',
      press_level: 'normal',
      spot_level: 'normal',
      spot_warning: false,
      env_temp_level: 'hot',
      env_pre_level: 'comfort',
      mold_levels: {
        Mold1: 'alert',
        Mold2: 'alert',
        Mold3: 'alert',
        Mold4: 'alert',
        Mold5: 'alert',
        Mold6: 'alert',
      },
      jam_level: 'normal',
      thresholds: {
        speed: false,
        press: false,
        spot: false,
        temp_f: false,
        temp_b: false,
        billet: false,
        billet_temp: false,
        at_temp: true,
        at_pre: false,
        count: false,
        endpos: false,
      },
    },
  };
};

const buildHealth = () => ({
  running: true,
  thread_alive: true,
  driver_thread_alive: true,
  last_update: Date.now() / 1000,
  driver_connected: true,
  mode: 'mock',
  app_version: 'profiler-mock',
  runtime_kind: 'node',
});

const buildStats = () => ({
  uptime_sec: Math.round((Date.now() - startedAt) / 1000),
  total_requests: tick,
  avg_latency_ms: 2,
  last_latency_ms: 2,
  last_path: '/api/data',
  last_status: 200,
  error_count: 0,
  errors: {
    total: 0,
    recent: [],
  },
  window: {
    count: tick,
    error_count: 0,
    p95_latency_ms: 2,
  },
});

const buildSpotConfig = () => ({
  image_url: '/api/spot/proxy_image',
  refresh_interval: 5,
  crosshair_x: 50,
  crosshair_y: 50,
  crosshair_color: '#00ff00',
  crosshair_thickness: 2,
  crosshair_size: 28,
  crosshair_gap: 4,
  widget_width: 640,
  widget_height: 360,
  focus_step: 1,
  actuator_step: 1,
  focus_enabled: true,
});

const server = http.createServer((req, res) => {
  const url = new URL(req.url ?? '/', `http://${req.headers.host ?? '127.0.0.1'}`);

  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'access-control-allow-origin': '*',
      'access-control-allow-methods': 'GET,POST,OPTIONS,DELETE',
      'access-control-allow-headers': 'content-type,authorization',
    });
    res.end();
    return;
  }

  if (url.pathname === '/api/data') {
    writeJson(res, buildFactoryData());
    return;
  }

  if (url.pathname === '/health') {
    writeJson(res, buildHealth());
    return;
  }

  if (url.pathname === '/stats') {
    writeJson(res, buildStats());
    return;
  }

  if (url.pathname === '/api/spot/config') {
    writeJson(res, buildSpotConfig());
    return;
  }

  if (url.pathname === '/api/spot/proxy_image') {
    res.writeHead(200, {
      'content-type': 'image/png',
      'content-length': String(spotImageBody.length),
      'cache-control': 'no-store',
      'access-control-allow-origin': '*',
      'access-control-expose-headers': 'X-Spot-Image-Status,X-Spot-Cache-Status,X-Spot-Proxy-State,X-Spot-Image-Age',
      'x-spot-image-status': 'ok',
      'x-spot-cache-status': 'mock',
      'x-spot-proxy-state': 'mock',
      'x-spot-image-age': '0',
    });
    res.end(spotImageBody);
    return;
  }

  if (url.pathname === '/api/layout' || url.pathname.endsWith('/latest')) {
    writeJson(res, null);
    return;
  }

  if (url.pathname === '/api/layouts' || url.pathname.endsWith('/list')) {
    writeJson(res, []);
    return;
  }

  if (url.pathname === '/api/observability/errors') {
    writeJson(res, []);
    return;
  }

  if (url.pathname === '/api/log/status') {
    writeJson(res, { ok: true, path: null, size: 0 });
    return;
  }

  res.writeHead(404, {
    'content-type': 'application/json; charset=utf-8',
    'access-control-allow-origin': '*',
    'access-control-allow-methods': 'GET,POST,OPTIONS,DELETE',
    'access-control-allow-headers': 'content-type,authorization',
  });
  res.end(JSON.stringify({ detail: `Mock endpoint not found: ${url.pathname}` }));
});

server.listen(port, '127.0.0.1', () => {
  process.stdout.write(`react-profiler-mock-backend listening on http://127.0.0.1:${port}\n`);
});
