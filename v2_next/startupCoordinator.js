'use strict';

const STARTUP_STATE_SCHEMA_VERSION = 'electron-startup-state-v1';
const BACKEND_PROGRESS_PREFIX = 'SFL_STARTUP_PROGRESS ';
const DEFAULT_STARTUP_TIMEOUT_MS = 30_000;
const MAX_BACKEND_PROGRESS_LINE_LENGTH = 1_024;
const MAX_BACKEND_PROGRESS_BUFFER_LENGTH = 8_192;

const MAIN_MILESTONES = Object.freeze({
  electron_ready: Object.freeze({
    phase: 'electron_ready',
    progress: 10,
    message: '프로그램 환경을 준비하고 있습니다.',
  }),
  backend_spawn_start: Object.freeze({
    phase: 'backend_spawn_start',
    progress: 15,
    message: '백엔드 프로세스를 시작하고 있습니다.',
  }),
  backend_spawned: Object.freeze({
    phase: 'backend_spawned',
    progress: 22,
    message: '백엔드 초기화를 기다리고 있습니다.',
  }),
});

const BACKEND_STAGE_MILESTONES = Object.freeze({
  lifespan_begin: Object.freeze({
    phase: 'backend_lifespan',
    progress: 28,
    message: '백엔드 서비스를 초기화하고 있습니다.',
  }),
  csv_logger_ready: Object.freeze({
    phase: 'csv_logger_ready',
    progress: 34,
    message: '데이터 기록 서비스를 준비하고 있습니다.',
  }),
  config_sync_ready: Object.freeze({
    phase: 'config_sync_ready',
    progress: 42,
    message: '설비 설정을 불러오고 있습니다.',
  }),
  config_watch_ready: Object.freeze({
    phase: 'config_watch_ready',
    progress: 48,
    message: '설비 설정 변경 감시를 준비하고 있습니다.',
  }),
  plc_service_ready: Object.freeze({
    phase: 'plc_service_ready',
    progress: 58,
    message: '설비 통신 서비스를 준비하고 있습니다.',
  }),
  comm_metrics_ready: Object.freeze({
    phase: 'comm_metrics_ready',
    progress: 64,
    message: '통신 상태 진단을 준비하고 있습니다.',
  }),
  memory_service_ready: Object.freeze({
    phase: 'memory_service_ready',
    progress: 70,
    message: '시스템 상태 진단을 준비하고 있습니다.',
  }),
  spot_poll_ready: Object.freeze({
    phase: 'spot_poll_ready',
    progress: 74,
    message: 'SPOT 센서 서비스를 준비하고 있습니다.',
  }),
  lifespan_complete: Object.freeze({
    phase: 'backend_lifespan_complete',
    progress: 78,
    message: '백엔드 응답을 확인하고 있습니다.',
  }),
});

const RENDERER_MILESTONES = Object.freeze({
  dashboard_paint: Object.freeze({
    phase: 'dashboard_paint_ready',
    progress: 82,
    message: '대시보드 화면을 구성하고 있습니다.',
  }),
  backend_health: Object.freeze({
    phase: 'backend_health_ready',
    progress: 90,
    message: '백엔드 연결을 확인했습니다.',
  }),
  data_snapshot: Object.freeze({
    phase: 'data_snapshot_ready',
    progress: 96,
    message: '첫 설비 데이터를 확인했습니다.',
  }),
});

const HANDOFF_STATUSES = new Set(['ready', 'degraded']);
const VERIFIED_DATA_SNAPSHOT_STATUSES = new Set(['running', 'offline', 'error']);

function clampProgress(value) {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round(value)));
}

function normalizeElapsedMs(value) {
  if (!Number.isFinite(value) || value < 0) {
    return 0;
  }
  return Math.round(value * 10) / 10;
}

function cloneState(state) {
  return { ...state };
}

class StartupCoordinator {
  constructor(options = {}) {
    const now = options.now ?? (() => Date.now());
    const setTimer = options.setTimer ?? ((callback, delayMs) => setTimeout(callback, delayMs));
    const clearTimer = options.clearTimer ?? ((timerId) => clearTimeout(timerId));

    if (typeof now !== 'function' || typeof setTimer !== 'function' || typeof clearTimer !== 'function') {
      throw new TypeError('StartupCoordinator timing options must be functions.');
    }

    this._sessionId = String(options.sessionId ?? '').slice(0, 120);
    this._now = now;
    this._setTimer = setTimer;
    this._clearTimer = clearTimer;
    this._onChange = typeof options.onChange === 'function' ? options.onChange : () => undefined;
    this._timeoutMs = Number.isFinite(options.timeoutMs)
      ? Math.max(1, Math.round(options.timeoutMs))
      : DEFAULT_STARTUP_TIMEOUT_MS;
    this._originMs = this._now();
    this._deadlineId = null;
    this._deadlineGeneration = 0;
    this._state = this._createInitialState(0, 'process_start');
  }

  _createInitialState(sequence, reason) {
    return {
      schema_version: STARTUP_STATE_SCHEMA_VERSION,
      session_id: this._sessionId,
      sequence,
      status: 'loading',
      phase: 'process_start',
      message: 'Smart Factory Logger를 시작하고 있습니다.',
      progress: 2,
      elapsed_ms: 0,
      backend_health_ready: false,
      data_snapshot_ready: false,
      data_running: false,
      dashboard_paint_ready: false,
      can_retry: false,
      can_continue_offline: false,
      can_exit: false,
      reason,
    };
  }

  getState() {
    return cloneState(this._state);
  }

  isHandoffComplete() {
    return HANDOFF_STATUSES.has(this._state.status);
  }

  start() {
    if (this._state.status !== 'loading') {
      return this.getState();
    }
    this._armDeadline();
    this.handleMainMilestone('electron_ready');
    return this.getState();
  }

  reset(reason = 'manual_retry') {
    this._clearDeadline();
    this._originMs = this._now();
    this._state = this._createInitialState(this._state.sequence + 1, reason);
    this._publish(reason);
    this._armDeadline();
    this.handleMainMilestone('electron_ready');
    return this.getState();
  }

  dispose() {
    this._clearDeadline();
  }

  handleMainMilestone(name) {
    const milestone = MAIN_MILESTONES[name];
    if (!milestone || this._state.status === 'error' || this.isHandoffComplete()) {
      return false;
    }
    this._applyMilestone(milestone, name);
    return true;
  }

  handleBackendStage(stage) {
    const milestone = BACKEND_STAGE_MILESTONES[stage];
    if (!milestone || this._state.status === 'error' || this.isHandoffComplete()) {
      return false;
    }
    this._applyMilestone(milestone, `backend:${stage}`);
    return true;
  }

  handleRendererEvent(name, payload = {}) {
    if (this._state.status === 'error' || this.isHandoffComplete()) {
      return false;
    }

    if (name === 'renderer.dashboard-ready') {
      if (payload.ready_strategy !== 'raf') {
        return false;
      }
      this._applyMilestone(RENDERER_MILESTONES.dashboard_paint, name, {
        dashboard_paint_ready: true,
      });
      this._maybeComplete();
      return true;
    }

    if (name === 'renderer.backend-health-ready') {
      if (payload.running !== true) {
        return false;
      }
      this._applyMilestone(RENDERER_MILESTONES.backend_health, name, {
        backend_health_ready: true,
      });
      this._maybeComplete();
      return true;
    }

    if (name === 'renderer.first-data-snapshot') {
      const normalizedStatus = typeof payload.status === 'string'
        ? payload.status.trim().toLowerCase()
        : '';
      if (
        payload.timestamp_present !== true ||
        !VERIFIED_DATA_SNAPSHOT_STATUSES.has(normalizedStatus)
      ) {
        return false;
      }
      this._applyMilestone(RENDERER_MILESTONES.data_snapshot, name, {
        data_snapshot_ready: true,
        data_running: normalizedStatus === 'running',
      });
      this._maybeComplete();
      return true;
    }

    if (name === 'renderer.first-live-data') {
      const normalizedStatus = typeof payload.status === 'string'
        ? payload.status.trim().toLowerCase()
        : '';
      if (payload.timestamp_present !== true || normalizedStatus !== 'running') {
        return false;
      }
      this._applyMilestone(RENDERER_MILESTONES.data_snapshot, name, {
        data_snapshot_ready: true,
        data_running: true,
      });
      this._maybeComplete();
      return true;
    }

    return false;
  }

  failBackend(reason = 'backend_failed') {
    if (this._state.status === 'error' || this.isHandoffComplete()) {
      return false;
    }
    this._clearDeadline();
    this._transition({
      status: 'error',
      phase: 'backend_failed',
      message: '백엔드를 시작하지 못했습니다.',
      can_retry: true,
      can_continue_offline: true,
      can_exit: true,
      reason,
    }, reason);
    return true;
  }

  continueOffline() {
    if (this.isHandoffComplete()) {
      return false;
    }
    this._clearDeadline();
    this._transition({
      status: 'degraded',
      phase: 'continued_offline',
      message: '오프라인 상태로 대시보드를 엽니다.',
      progress: 100,
      can_retry: false,
      can_continue_offline: false,
      can_exit: false,
      reason: 'manual_offline_continue',
    }, 'manual_offline_continue');
    return true;
  }

  _armDeadline() {
    this._clearDeadline();
    const generation = ++this._deadlineGeneration;
    this._deadlineId = this._setTimer(() => {
      if (generation !== this._deadlineGeneration || this.isHandoffComplete() || this._state.status === 'error') {
        return;
      }
      this._deadlineId = null;
      this._transition({
        status: 'timeout',
        phase: 'startup_timeout',
        message: '시작 준비가 지연되고 있습니다.',
        can_retry: true,
        can_continue_offline: true,
        can_exit: true,
        reason: 'deadline_exceeded',
      }, 'deadline_exceeded');
    }, this._timeoutMs);
  }

  _clearDeadline() {
    this._deadlineGeneration += 1;
    if (this._deadlineId !== null) {
      this._clearTimer(this._deadlineId);
      this._deadlineId = null;
    }
  }

  _applyMilestone(milestone, reason, extra = {}) {
    this._transition({
      ...extra,
      status: this._state.status === 'timeout' ? 'timeout' : 'loading',
      phase: milestone.phase,
      message: milestone.message,
      progress: Math.max(this._state.progress, milestone.progress),
      reason,
    }, reason);
  }

  _maybeComplete() {
    if (
      !this._state.backend_health_ready ||
      !this._state.data_snapshot_ready ||
      !this._state.dashboard_paint_ready
    ) {
      return false;
    }

    this._clearDeadline();
    const isRunning = this._state.data_running;
    this._transition({
      status: isRunning ? 'ready' : 'degraded',
      phase: isRunning ? 'ready' : 'degraded_ready',
      message: isRunning
        ? '준비가 완료되었습니다.'
        : '장비 연결 상태를 대시보드에서 확인하십시오.',
      progress: 100,
      can_retry: false,
      can_continue_offline: false,
      can_exit: false,
      reason: isRunning ? 'all_gates_ready' : 'degraded_gates_ready',
    }, isRunning ? 'all_gates_ready' : 'degraded_gates_ready');
    return true;
  }

  _applyElapsed(state) {
    return {
      ...state,
      progress: clampProgress(state.progress),
      elapsed_ms: normalizeElapsedMs(this._now() - this._originMs),
    };
  }

  _transition(patch, reason) {
    this._state = this._applyElapsed({
      ...this._state,
      ...patch,
      sequence: this._state.sequence + 1,
      reason,
    });
    this._onChange(this.getState());
  }

  _publish(reason) {
    this._state = this._applyElapsed({
      ...this._state,
      reason,
    });
    this._onChange(this.getState());
  }
}

function createBackendProgressParser(options = {}) {
  const onStage = typeof options.onStage === 'function' ? options.onStage : () => undefined;
  const onRejected = typeof options.onRejected === 'function' ? options.onRejected : () => undefined;
  let buffer = '';

  const reject = (reason) => {
    onRejected(reason);
  };

  const processLine = (rawLine) => {
    const line = rawLine.trim();
    if (!line.startsWith(BACKEND_PROGRESS_PREFIX)) {
      return;
    }
    if (line.length > MAX_BACKEND_PROGRESS_LINE_LENGTH) {
      reject('line_too_long');
      return;
    }

    const rawPayload = line.slice(BACKEND_PROGRESS_PREFIX.length);
    let payload;
    try {
      payload = JSON.parse(rawPayload);
    } catch (_error) {
      reject('invalid_json');
      return;
    }

    if (
      !payload ||
      typeof payload !== 'object' ||
      Array.isArray(payload) ||
      Object.keys(payload).length !== 1 ||
      typeof payload.stage !== 'string' ||
      !Object.prototype.hasOwnProperty.call(BACKEND_STAGE_MILESTONES, payload.stage)
    ) {
      reject('invalid_payload');
      return;
    }

    onStage(payload.stage);
  };

  const push = (chunk) => {
    if (chunk === null || chunk === undefined) {
      return;
    }
    buffer += Buffer.isBuffer(chunk) ? chunk.toString('utf8') : String(chunk);

    while (true) {
      const lineFeedIndex = buffer.indexOf('\n');
      if (lineFeedIndex < 0) {
        break;
      }
      const rawLine = buffer.slice(0, lineFeedIndex).replace(/\r$/, '');
      buffer = buffer.slice(lineFeedIndex + 1);
      processLine(rawLine);
    }

    if (buffer.length > MAX_BACKEND_PROGRESS_BUFFER_LENGTH) {
      buffer = '';
      reject('buffer_overflow');
    }
  };

  const flush = () => {
    if (buffer.length > 0) {
      processLine(buffer.replace(/\r$/, ''));
      buffer = '';
    }
  };

  return {
    push,
    flush,
    getBufferedLength: () => buffer.length,
  };
}

module.exports = {
  BACKEND_PROGRESS_PREFIX,
  BACKEND_STAGE_MILESTONES,
  DEFAULT_STARTUP_TIMEOUT_MS,
  STARTUP_STATE_SCHEMA_VERSION,
  StartupCoordinator,
  createBackendProgressParser,
};
