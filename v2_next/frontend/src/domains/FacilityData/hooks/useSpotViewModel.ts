import { useCallback, useEffect, useRef, useState } from 'react';
import type { SpotConfig, SpotPollingDiagnostics } from '../../../shared/types';
import { useDashboardStore } from '../../../store/useDashboardStore';
import type { SpotImageResponseMetadata } from '../api/spotService.types';
import {
  controlSpotAction,
  controlSpotActuator,
  controlSpotFocus,
  fetchSpotConfig,
  fetchSpotImageResponse,
} from './useSpotViewModel.service';
import {
  resolveSpotImageErrorMessage,
  resolveSpotImageLoadErrorMessage,
  resolveSpotImageResponseMetadata,
  resolveSpotImageSuccessAt,
  type SpotImageErrorDetail,
} from './useSpotViewModel.selectors';
import { useSpotViewModelEffects } from './useSpotViewModelEffects';
import type { SpotFocusResponse } from '../../../shared/api/transport/spotService.transport';
import {
  SpotImagePayloadValidationError,
  buildSpotImageValidationLog,
  isSpotImagePayloadRejectionCode,
  toPayloadRejectionValidationCode,
  validateSpotImagePayload,
} from '../utils/spotImagePayloadValidation.pure';
import {
  getNextSpotImageRetryDelayMs,
  isSpotImageFailureRetryable,
} from '../utils/spotImageRecoveryPolicy.pure';
import type { UseSpotViewModel } from './useSpotViewModel.types';

interface SpotImageState {
  imageUrl: string;
  imageError: string | null;
  lastSuccessAt: number | null;
  metadata: SpotImageResponseMetadata | null;
}

const areSpotConfigsEqual = (first: SpotConfig, second: SpotConfig): boolean => {
  return (
    first.image_url === second.image_url &&
    first.refresh_interval === second.refresh_interval &&
    first.crosshair_x === second.crosshair_x &&
    first.crosshair_y === second.crosshair_y &&
    first.crosshair_color === second.crosshair_color &&
    first.crosshair_thickness === second.crosshair_thickness &&
    first.crosshair_size === second.crosshair_size &&
    first.crosshair_gap === second.crosshair_gap &&
    first.widget_width === second.widget_width &&
    first.widget_height === second.widget_height &&
    first.focus_step === second.focus_step &&
    first.actuator_step === second.actuator_step &&
    first.focus_enabled === second.focus_enabled
  );
};

type SpotPollingDiagnosticsWithImage = SpotPollingDiagnostics & {
  last_image_status: string | null;
  last_image_source: string | null;
  last_image_latency_ms: number | null;
};

class SpotImageRequestError extends Error {
  readonly retryable: boolean;

  constructor(message: string, retryable: boolean) {
    super(message);
    this.name = 'SpotImageRequestError';
    this.retryable = retryable;
  }
}

const resolveSpotImageErrorDetail = async (response: Response): Promise<SpotImageErrorDetail | null> => {
  try {
    const payload: unknown = await response.json();
    if (!payload || typeof payload !== 'object') {
      return null;
    }
    const candidate = 'detail' in payload ? (payload as { detail?: unknown }).detail : payload;
    if (!candidate || typeof candidate !== 'object') {
      return null;
    }
    return candidate as SpotImageErrorDetail;
  } catch {
    return null;
  }
};

const INITIAL_SPOT_DIAGNOSTICS: SpotPollingDiagnosticsWithImage = {
  in_flight: false,
  refresh_interval_ms: null,
  fetch_count: 0,
  error_count: 0,
  automatic_retry_count: 0,
  consecutive_retry_attempt: 0,
  automatic_retry_pending: false,
  automatic_retry_exhausted: false,
  next_retry_scheduled_at: null,
  last_failure_retryable: null,
  last_fetch_started_at: null,
  last_fetch_completed_at: null,
  last_fetch_latency_ms: null,
  next_fetch_scheduled_at: null,
  last_fetch_reason: null,
  last_image_status: null,
  last_image_source: null,
  last_image_latency_ms: null,
};

const resolveSpotControlErrorMessage = (error: unknown, fallbackMessage: string): string => {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return fallbackMessage;
};

const isNoMovementFocusStatus = (status: string): boolean => {
  const normalizedStatus = status.trim().toLowerCase();
  return (
    normalizedStatus === 'noop' ||
    normalizedStatus === 'no-op' ||
    normalizedStatus === 'limit' ||
    normalizedStatus === 'limited' ||
    normalizedStatus === 'unchanged' ||
    normalizedStatus.includes('limit')
  );
};

const isNoMovementFocusMessage = (message: string | undefined): boolean => {
  if (!message) {
    return false;
  }
  const normalizedMessage = message.trim().toLowerCase();
  return (
    normalizedMessage.includes('limit') ||
    normalizedMessage.includes('no-op') ||
    normalizedMessage.includes('noop') ||
    normalizedMessage.includes('unchanged') ||
    normalizedMessage.includes('clamp')
  );
};

const buildSpotFocusResponseContext = (steps: number, response: SpotFocusResponse): string => {
  const values = [
    `requested_steps=${steps}`,
    `status=${response.status}`,
    response.request_steps === undefined ? null : `response_steps=${response.request_steps}`,
    response.focus_step === undefined ? null : `focus_step=${response.focus_step}`,
    response.current === undefined ? null : `current=${response.current}`,
    response.new === undefined ? null : `new=${response.new}`,
    response.message?.trim() ? `message=${response.message.trim()}` : null,
  ];
  return values.filter((value): value is string => value !== null).join('; ');
};

const resolveSpotFocusResponseMessage = (steps: number, response: SpotFocusResponse): string | null => {
  const normalizedStatus = response.status.trim().toLowerCase();
  const hasNoPositionChange =
    response.current !== undefined &&
    response.new !== undefined &&
    response.current === response.new;
  const hasNoMovementStatus = isNoMovementFocusStatus(response.status);
  const hasNoMovementMessage = isNoMovementFocusMessage(response.message);
  const responseContext = buildSpotFocusResponseContext(steps, response);

  if (normalizedStatus !== 'ok' && normalizedStatus !== 'success') {
    return `SPOT focus response was not successful; ${responseContext}`;
  }
  if (hasNoPositionChange || hasNoMovementStatus || hasNoMovementMessage) {
    return `SPOT focus did not move; ${responseContext}`;
  }
  return null;
};

export const useSpotViewModel = (): UseSpotViewModel => {
  const [config, setConfig] = useState<SpotConfig | null>(null);
  const [imageUrl, setImageUrl] = useState<string>('');
  const [imageError, setImageError] = useState<string | null>(null);
  const [imageLoading, setImageLoading] = useState(false);
  const [lastSuccessAt, setLastSuccessAt] = useState<number | null>(null);
  const [metadata, setMetadata] = useState<SpotImageResponseMetadata | null>(null);
  const [focusBusy, setFocusBusy] = useState(false);
  const [diagnostics, setDiagnostics] = useState<SpotPollingDiagnosticsWithImage>(INITIAL_SPOT_DIAGNOSTICS);

  const hasImageRef = useRef(false);
  const prevUrlRef = useRef<string | null>(null);
  const pendingImageUrlRef = useRef<string | null>(null);
  const pendingPreviousImageStateRef = useRef<SpotImageState | null>(null);
  const inFlightRef = useRef(false);
  const automaticRetryAttemptRef = useRef(0);
  const automaticRetryTimerRef = useRef<number | null>(null);
  const runSpotFetchRef = useRef<(reason: string) => Promise<void>>(async () => undefined);
  const configRef = useRef<SpotConfig | null>(null);
  const imageStateRef = useRef<SpotImageState>({
    imageUrl: '',
    imageError: null,
    lastSuccessAt: null,
    metadata: null,
  });

  const setDashboardSpotConfig = useDashboardStore((state) => state.setSpotConfig);
  const setDashboardSpotImageState = useDashboardStore((state) => state.setSpotImageState);
  const setDashboardSpotControlError = useDashboardStore((state) => state.setSpotControlError);

  configRef.current = config;

  const syncDashboardSpotImageState = useCallback(
    (
      nextImageUrl: string,
      nextLoading: boolean,
      nextImageError: string | null,
      nextLastSuccessAt: number | null,
      nextMetadata: SpotImageResponseMetadata | null
    ) => {
      setDashboardSpotImageState(nextImageUrl, nextLoading, nextImageError, nextLastSuccessAt, nextMetadata);
    },
    [setDashboardSpotImageState]
  );

  const cancelPendingImageRetry = useCallback((): void => {
    if (automaticRetryTimerRef.current !== null) {
      window.clearTimeout(automaticRetryTimerRef.current);
      automaticRetryTimerRef.current = null;
    }
  }, []);

  const resetImageRecovery = useCallback((): void => {
    cancelPendingImageRetry();
    automaticRetryAttemptRef.current = 0;
    setDiagnostics((prev) => ({
      ...prev,
      consecutive_retry_attempt: 0,
      automatic_retry_pending: false,
      automatic_retry_exhausted: false,
      next_retry_scheduled_at: null,
      last_failure_retryable: null,
    }));
  }, [cancelPendingImageRetry]);

  const scheduleAutomaticImageRetry = useCallback((): void => {
    if (automaticRetryTimerRef.current !== null) {
      return;
    }

    const delayMs = getNextSpotImageRetryDelayMs(automaticRetryAttemptRef.current);
    if (delayMs === null) {
      setDiagnostics((prev) => ({
        ...prev,
        automatic_retry_pending: false,
        automatic_retry_exhausted: true,
        next_retry_scheduled_at: null,
        last_failure_retryable: true,
      }));
      return;
    }

    automaticRetryAttemptRef.current += 1;
    const scheduledAt = Date.now() + delayMs;
    automaticRetryTimerRef.current = window.setTimeout(() => {
      automaticRetryTimerRef.current = null;
      setDiagnostics((prev) => ({
        ...prev,
        automatic_retry_pending: false,
        next_retry_scheduled_at: null,
      }));
      void runSpotFetchRef.current('automatic-retry');
    }, delayMs);
    setDiagnostics((prev) => ({
      ...prev,
      automatic_retry_count: prev.automatic_retry_count + 1,
      consecutive_retry_attempt: automaticRetryAttemptRef.current,
      automatic_retry_pending: true,
      automatic_retry_exhausted: false,
      next_retry_scheduled_at: scheduledAt,
      last_failure_retryable: true,
    }));
  }, []);

  const applySpotConfig = useCallback(
    (nextConfig: SpotConfig): void => {
      const previousConfig = configRef.current;
      if (previousConfig && areSpotConfigsEqual(previousConfig, nextConfig)) {
        return;
      }
      if (previousConfig?.image_url !== nextConfig.image_url) {
        resetImageRecovery();
      }
      setConfig(nextConfig);
      setDashboardSpotConfig(nextConfig);
      setDiagnostics((prev) => ({
        ...prev,
        refresh_interval_ms: null,
        next_fetch_scheduled_at: null,
      }));
    },
    [resetImageRecovery, setDashboardSpotConfig]
  );

  const loadConfig = useCallback(async (): Promise<SpotConfig | null> => {
    try {
      return await fetchSpotConfig();
    } catch (error) {
      console.error('Failed to load spot config', error);
      return null;
    }
  }, []);

  const refreshConfig = useCallback(async (): Promise<void> => {
    const nextConfig = await loadConfig();
    if (!nextConfig) {
      return;
    }
    applySpotConfig(nextConfig);
  }, [applySpotConfig, loadConfig]);

  const publishImageFailure = useCallback(
    (
      nextImageError: string,
      nextMetadata: SpotImageResponseMetadata | null,
      retryable: boolean
    ): void => {
      const nextImageState = {
        ...imageStateRef.current,
        imageError: nextImageError,
        metadata: nextMetadata ?? imageStateRef.current.metadata,
      };
      imageStateRef.current = nextImageState;
      setImageError(nextImageError);
      setMetadata(nextImageState.metadata);
      syncDashboardSpotImageState(
        nextImageState.imageUrl,
        false,
        nextImageError,
        nextImageState.lastSuccessAt,
        nextImageState.metadata
      );
      setDiagnostics((prev) => ({
        ...prev,
        error_count: prev.error_count + 1,
        last_image_status: 'error',
        last_image_source: nextImageState.metadata?.source ?? prev.last_image_source,
        last_image_latency_ms: nextImageState.metadata?.latency_ms ?? prev.last_image_latency_ms,
        last_failure_retryable: retryable,
        automatic_retry_pending: retryable ? prev.automatic_retry_pending : false,
        automatic_retry_exhausted: false,
        next_retry_scheduled_at: retryable ? prev.next_retry_scheduled_at : null,
        consecutive_retry_attempt: retryable ? prev.consecutive_retry_attempt : 0,
      }));

      if (retryable) {
        scheduleAutomaticImageRetry();
        return;
      }
      cancelPendingImageRetry();
      automaticRetryAttemptRef.current = 0;
    },
    [cancelPendingImageRetry, scheduleAutomaticImageRetry, syncDashboardSpotImageState]
  );

  const runSpotFetch = useCallback(
    async (reason: string): Promise<void> => {
      const currentConfig = configRef.current;
      if (!currentConfig?.image_url) {
        return;
      }
      if (inFlightRef.current) {
        return;
      }

      const startedAt = Date.now();
      const currentImageState = imageStateRef.current;
      let latestResponseMetadata: SpotImageResponseMetadata | null = null;

      inFlightRef.current = true;
      setDiagnostics((prev) => ({
        ...prev,
        in_flight: true,
        refresh_interval_ms: null,
        fetch_count: prev.fetch_count + 1,
        last_fetch_started_at: startedAt,
        last_fetch_reason: reason,
      }));

      if (!hasImageRef.current) {
        setImageLoading(true);
        syncDashboardSpotImageState(
          currentImageState.imageUrl,
          true,
          currentImageState.imageError,
          currentImageState.lastSuccessAt,
          currentImageState.metadata
        );
      }

      try {
        const response = await fetchSpotImageResponse();
        const responseReceivedAt = Date.now();
        const responseMetadata = resolveSpotImageResponseMetadata(
          response.headers,
          responseReceivedAt,
          responseReceivedAt - startedAt
        );
        latestResponseMetadata = responseMetadata;
        if (!response.ok) {
          const detail = await resolveSpotImageErrorDetail(response);
          if (isSpotImagePayloadRejectionCode(detail?.code)) {
            throw new SpotImagePayloadValidationError(
              toPayloadRejectionValidationCode(detail?.code),
              {
                requestUrl: currentConfig.image_url,
                status: response.status,
                contentType: response.headers.get('content-type') ?? null,
                contentLength: response.headers.has('content-length')
                  ? Number.parseInt(response.headers.get('content-length') ?? '0', 10)
                  : null,
                byteLength: 0,
                declaredCapturedAt: responseMetadata.captured_at,
              },
              detail?.message ?? resolveSpotImageErrorMessage(response.status, detail)
            );
          }
          throw new SpotImageRequestError(
            resolveSpotImageErrorMessage(response.status, detail),
            isSpotImageFailureRetryable({
              responseStatus: response.status,
              code: detail?.code,
              upstreamStatus: detail?.upstream_status,
            })
          );
        }

        const rawPayload = new Uint8Array(await response.arrayBuffer());
        const validatedPayload = validateSpotImagePayload({
          bytes: rawPayload,
          status: response.status,
          headers: response.headers,
          metadata: responseMetadata,
          receivedAt: responseReceivedAt,
          requestUrl: currentConfig.image_url,
        });
        setDiagnostics((prev) => ({
          ...prev,
          last_image_status: 'ok',
          last_image_source: responseMetadata.source,
          last_image_latency_ms: responseMetadata.latency_ms,
        }));

        const effectiveAt = resolveSpotImageSuccessAt(responseMetadata, responseReceivedAt);
        const nextImageError = null;
        const nextImageUrl = URL.createObjectURL(new Blob([validatedPayload.bytes], { type: validatedPayload.mimeType }));
        const previousImageState = imageStateRef.current;
        const previousImageUrl = prevUrlRef.current;

        prevUrlRef.current = nextImageUrl;
        pendingImageUrlRef.current = nextImageUrl;
        pendingPreviousImageStateRef.current = previousImageUrl ? previousImageState : null;
        imageStateRef.current = {
          imageUrl: nextImageUrl,
          imageError: nextImageError,
          lastSuccessAt: effectiveAt,
          metadata: responseMetadata,
        };
        hasImageRef.current = true;

        setImageUrl(nextImageUrl);
        setImageError(nextImageError);
        setLastSuccessAt(effectiveAt);
        setMetadata(responseMetadata);
        syncDashboardSpotImageState(nextImageUrl, false, nextImageError, effectiveAt, responseMetadata);
      } catch (error) {
        if (error instanceof SpotImagePayloadValidationError) {
          console.error('Spot image payload validation failed', buildSpotImageValidationLog(error));
          publishImageFailure(error.message, latestResponseMetadata, false);
          return;
        }
        console.error('Image fetch failed', error);
        const nextImageError = error instanceof Error ? error.message : resolveSpotImageErrorMessage(0, null);
        const retryable = error instanceof SpotImageRequestError
          ? error.retryable
          : isSpotImageFailureRetryable({ transportException: true });
        publishImageFailure(nextImageError, latestResponseMetadata, retryable);
      } finally {
        const completedAt = Date.now();
        setImageLoading(false);
        inFlightRef.current = false;
        setDiagnostics((prev) => ({
          ...prev,
          in_flight: false,
          last_fetch_completed_at: completedAt,
          last_fetch_latency_ms: completedAt - startedAt,
        }));
      }
    },
    [publishImageFailure, syncDashboardSpotImageState]
  );

  runSpotFetchRef.current = runSpotFetch;

  const fetchInitialImage = useCallback(async (): Promise<void> => {
    await runSpotFetch('initial');
  }, [runSpotFetch]);

  const refreshImage = useCallback(() => {
    resetImageRecovery();
    void runSpotFetch('manual');
  }, [resetImageRecovery, runSpotFetch]);

  const controlSpot = useCallback(async (action: string, value?: number) => {
    try {
      await controlSpotAction(action, value);
      return true;
    } catch (error) {
      console.error('Spot control failed', error);
      return false;
    }
  }, []);

  const controlFocus = useCallback(
    async (steps: number) => {
      if (focusBusy) {
        return;
      }
      setFocusBusy(true);
      try {
        const response = await controlSpotFocus(steps);
        const responseMessage = resolveSpotFocusResponseMessage(steps, response);
        setDashboardSpotControlError(responseMessage);
      } catch (error) {
        const nextControlError = resolveSpotControlErrorMessage(error, 'SPOT focus control failed');
        console.error('Spot focus failed', error);
        setDashboardSpotControlError(nextControlError);
      } finally {
        setFocusBusy(false);
      }
    },
    [focusBusy, setDashboardSpotControlError]
  );

  const controlActuator = useCallback(
    async (step: number) => {
      if (focusBusy) {
        return;
      }
      setFocusBusy(true);
      try {
        await controlSpotActuator(step);
        setDashboardSpotControlError(null);
      } catch (error) {
        const nextControlError = resolveSpotControlErrorMessage(error, 'SPOT actuator control failed');
        console.error('Spot actuator failed', error);
        setDashboardSpotControlError(nextControlError);
      } finally {
        setFocusBusy(false);
      }
    },
    [focusBusy, setDashboardSpotControlError]
  );

  useEffect(() => {
    return () => {
      cancelPendingImageRetry();
      const pendingPreviousUrl = pendingPreviousImageStateRef.current?.imageUrl ?? null;
      if (pendingPreviousUrl && pendingPreviousUrl !== prevUrlRef.current) {
        URL.revokeObjectURL(pendingPreviousUrl);
      }
    };
  }, [cancelPendingImageRetry]);

  useSpotViewModelEffects({
    config,
    fetchInitialImage,
    loadConfig,
    applySpotConfig,
    prevUrlRef,
    cancelPendingImageRetry,
  });

  const handleImageLoad = useCallback((displayedImageUrl?: string) => {
    hasImageRef.current = true;
    setImageLoading(false);
    const currentImageState = imageStateRef.current;
    const pendingPreviousUrl = pendingPreviousImageStateRef.current?.imageUrl ?? null;
    const loadedImageUrl = displayedImageUrl ?? currentImageState.imageUrl;
    const shouldRequestNext =
      pendingImageUrlRef.current === currentImageState.imageUrl &&
      loadedImageUrl === currentImageState.imageUrl;
    if (shouldRequestNext) {
      resetImageRecovery();
      if (pendingPreviousUrl && pendingPreviousUrl !== currentImageState.imageUrl) {
        URL.revokeObjectURL(pendingPreviousUrl);
      }
      pendingImageUrlRef.current = null;
      pendingPreviousImageStateRef.current = null;
    }
    syncDashboardSpotImageState(
      currentImageState.imageUrl,
      false,
      currentImageState.imageError,
      currentImageState.lastSuccessAt,
      currentImageState.metadata
    );
    if (shouldRequestNext) {
      void runSpotFetch('completed');
    }
  }, [resetImageRecovery, runSpotFetch, syncDashboardSpotImageState]);

  const handleImageError = useCallback((displayedImageUrl?: string) => {
    setImageLoading(false);
    const currentImageState = imageStateRef.current;
    const isPendingCurrentImage =
      pendingImageUrlRef.current === currentImageState.imageUrl &&
      (displayedImageUrl ?? currentImageState.imageUrl) === currentImageState.imageUrl;
    if (isPendingCurrentImage) {
      const failedImageUrl = currentImageState.imageUrl;
      const previousImageState = pendingPreviousImageStateRef.current;
      const nextImageError = resolveSpotImageLoadErrorMessage();
      const restoredImageState: SpotImageState = previousImageState ?? {
        imageUrl: '',
        imageError: null,
        lastSuccessAt: null,
        metadata: null,
      };

      URL.revokeObjectURL(failedImageUrl);
      pendingImageUrlRef.current = null;
      pendingPreviousImageStateRef.current = null;
      prevUrlRef.current = restoredImageState.imageUrl || null;
      imageStateRef.current = restoredImageState;
      hasImageRef.current = Boolean(restoredImageState.imageUrl);
      setImageUrl(restoredImageState.imageUrl);
      setLastSuccessAt(restoredImageState.lastSuccessAt);
      setMetadata(restoredImageState.metadata);
      publishImageFailure(nextImageError, restoredImageState.metadata, true);
      return;
    }
    if (!currentImageState.imageError) {
      const nextImageError = resolveSpotImageLoadErrorMessage();
      publishImageFailure(nextImageError, currentImageState.metadata, true);
      return;
    }
    syncDashboardSpotImageState(
      currentImageState.imageUrl,
      false,
      currentImageState.imageError,
      currentImageState.lastSuccessAt,
      currentImageState.metadata
    );
  }, [publishImageFailure, syncDashboardSpotImageState]);

  return {
    config,
    imageUrl,
    imageError,
    imageLoading,
    lastSuccessAt,
    metadata,
    diagnostics,
    focusBusy,
    refreshConfig,
    refreshImage,
    handleImageLoad,
    handleImageError,
    controlSpot,
    controlFocus,
    controlActuator,
  };
};
