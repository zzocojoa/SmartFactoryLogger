'use strict';

const STATEFUL_RENDERER_EVENTS = new Set([
  'renderer.dashboard-ready',
  'renderer.backend-health-ready',
  'renderer.first-data-snapshot',
  'renderer.first-live-data',
]);

function normalizeDocumentUrl(value) {
  if (typeof value !== 'string' || value.length === 0) {
    return null;
  }

  try {
    const url = new URL(value);
    url.hash = '';
    return url.href;
  } catch (_error) {
    return null;
  }
}

function isTrustedStartupSender(event, mainWindow, expectedDocumentUrl) {
  if (!mainWindow || mainWindow.isDestroyed()) {
    return false;
  }

  const expectedUrl = normalizeDocumentUrl(expectedDocumentUrl);
  const senderUrl = normalizeDocumentUrl(event?.senderFrame?.url);
  return Boolean(
    expectedUrl &&
    senderUrl === expectedUrl &&
    event?.sender === mainWindow.webContents &&
    event?.senderFrame === mainWindow.webContents.mainFrame
  );
}

function createStartupIpcHandlers(options) {
  const {
    getMainWindow,
    getExpectedDocumentUrl,
    allowedEventNames,
    eventCounts,
    maxEventsPerName,
    coordinator,
    sanitizePayload,
    normalizeRejectedEventName,
    logStartupEvent,
    onAcceptedEvent = () => undefined,
    getRendererGeneration,
    setRendererGeneration,
    restartBackend,
    quitApplication,
  } = options;

  const trusted = (event) => isTrustedStartupSender(
    event,
    getMainWindow(),
    getExpectedDocumentUrl()
  );

  return {
    recordStartupEvent: async (event, name, payload) => {
      if (!trusted(event)) {
        return { ok: false, reason: 'untrusted_sender' };
      }
      if (typeof name !== 'string' || !allowedEventNames.has(name)) {
        logStartupEvent('renderer.startup-event-rejected', {
          reason: 'invalid_event',
          name: normalizeRejectedEventName(name),
        });
        return { ok: false, reason: 'invalid_event' };
      }

      const nextCount = (eventCounts.get(name) ?? 0) + 1;
      eventCounts.set(name, nextCount);
      if (nextCount > maxEventsPerName) {
        logStartupEvent('renderer.startup-event-rejected', {
          reason: 'event_limit',
          name,
        });
        return { ok: false, reason: 'event_limit' };
      }

      const sanitizedPayload = sanitizePayload(payload);
      if (
        name === 'renderer.preload-start' &&
        typeof sanitizedPayload.renderer_time_origin_ms === 'number' &&
        Number.isFinite(sanitizedPayload.renderer_time_origin_ms) &&
        typeof setRendererGeneration === 'function'
      ) {
        setRendererGeneration(sanitizedPayload.renderer_time_origin_ms);
      }
      if (STATEFUL_RENDERER_EVENTS.has(name) && typeof getRendererGeneration === 'function') {
        const expectedGeneration = getRendererGeneration();
        if (
          typeof expectedGeneration !== 'number' ||
          sanitizedPayload.renderer_time_origin_ms !== expectedGeneration
        ) {
          logStartupEvent('renderer.startup-event-rejected', {
            reason: 'invalid_generation',
            name,
          });
          return { ok: false, reason: 'invalid_generation' };
        }
      }
      if (
        STATEFUL_RENDERER_EVENTS.has(name) &&
        !coordinator.handleRendererEvent(name, sanitizedPayload)
      ) {
        logStartupEvent('renderer.startup-event-rejected', {
          reason: 'invalid_payload',
          name,
        });
        return { ok: false, reason: 'invalid_payload' };
      }

      logStartupEvent(name, sanitizedPayload);
      onAcceptedEvent(name, sanitizedPayload);
      return { ok: true };
    },

    getStartupState: async (event) => {
      if (!trusted(event)) {
        return null;
      }
      return coordinator.getState();
    },

    retryStartup: async (event) => {
      if (!trusted(event)) {
        return { ok: false, reason: 'untrusted_sender' };
      }
      if (!coordinator.getState().can_retry) {
        return { ok: false, reason: 'not_available' };
      }
      try {
        const restarted = await restartBackend();
        return restarted
          ? { ok: true }
          : { ok: false, reason: 'restart_cancelled' };
      } catch (error) {
        logStartupEvent('backend.restart-failed', {
          message: error instanceof Error ? error.message : String(error),
        });
        return { ok: false, reason: 'backend_stop_failed' };
      }
    },

    continueStartupOffline: async (event) => {
      if (!trusted(event)) {
        return { ok: false, reason: 'untrusted_sender' };
      }
      if (!coordinator.getState().can_continue_offline) {
        return { ok: false, reason: 'not_available' };
      }
      return { ok: coordinator.continueOffline() };
    },

    exitStartup: async (event) => {
      if (!trusted(event)) {
        return { ok: false, reason: 'untrusted_sender' };
      }
      if (!coordinator.getState().can_exit) {
        return { ok: false, reason: 'not_available' };
      }
      quitApplication();
      return { ok: true };
    },
  };
}

module.exports = {
  STATEFUL_RENDERER_EVENTS,
  createStartupIpcHandlers,
  isTrustedStartupSender,
  normalizeDocumentUrl,
};
