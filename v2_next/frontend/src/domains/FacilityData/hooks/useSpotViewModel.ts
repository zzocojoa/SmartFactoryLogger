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
  resolveSpotImageDiagnosticMessage,
  resolveSpotImageErrorMessage,
  resolveSpotImageLoadErrorMessage,
  resolveSpotImageResponseMetadata,
  resolveSpotImageSuccessAt,
  resolveSpotRefreshMs,
  type SpotProxyErrorDetail,
} from './useSpotViewModel.selectors';
import { useSpotViewModelEffects } from './useSpotViewModelEffects';
import {
  SpotImagePayloadValidationError,
  buildSpotImageValidationLog,
  isSpotImagePayloadProxyRejectionCode,
  toPayloadRejectionValidationCode,
  validateSpotImagePayload,
} from '../utils/spotImagePayloadValidation.pure';
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
    first.focus_enabled === second.focus_enabled
  );
};

type SpotPollingDiagnosticsWithImage = SpotPollingDiagnostics & {
  last_image_status: string | null;
  last_image_source: string | null;
  last_image_age_sec: number | null;
  last_image_latency_ms: number | null;
  last_image_retry_after_sec: number | null;
};

const resolveSpotProxyErrorDetail = async (response: Response): Promise<SpotProxyErrorDetail | null> => {
  try {
    const payload: unknown = await response.json();
    if (!payload || typeof payload !== 'object') {
      return null;
    }
    const candidate = 'detail' in payload ? (payload as { detail?: unknown }).detail : payload;
    if (!candidate || typeof candidate !== 'object') {
      return null;
    }
    return candidate as SpotProxyErrorDetail;
  } catch {
    return null;
  }
};

const INITIAL_SPOT_DIAGNOSTICS: SpotPollingDiagnosticsWithImage = {
  in_flight: false,
  refresh_interval_ms: null,
  fetch_count: 0,
  error_count: 0,
  last_fetch_started_at: null,
  last_fetch_completed_at: null,
  last_fetch_latency_ms: null,
  next_fetch_scheduled_at: null,
  last_fetch_reason: null,
  last_image_status: null,
  last_image_source: null,
  last_image_age_sec: null,
  last_image_latency_ms: null,
  last_image_retry_after_sec: null,
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
  const configRef = useRef<SpotConfig | null>(null);
  const nextFetchScheduledAtRef = useRef<number | null>(null);
  const imageStateRef = useRef<SpotImageState>({
    imageUrl: '',
    imageError: null,
    lastSuccessAt: null,
    metadata: null,
  });

  const setDashboardSpotConfig = useDashboardStore((state) => state.setSpotConfig);
  const setDashboardSpotImageState = useDashboardStore((state) => state.setSpotImageState);

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

  const applySpotConfig = useCallback(
    (nextConfig: SpotConfig): void => {
      const previousConfig = configRef.current;
      if (previousConfig && areSpotConfigsEqual(previousConfig, nextConfig)) {
        return;
      }
      setConfig(nextConfig);
      setDashboardSpotConfig(nextConfig);
      setDiagnostics((prev) => ({
        ...prev,
        refresh_interval_ms: resolveSpotRefreshMs(nextConfig.refresh_interval),
      }));
    },
    [setDashboardSpotConfig]
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

  const setNextFetchScheduledAt = useCallback((nextFetchScheduledAt: number | null) => {
    if (nextFetchScheduledAt === nextFetchScheduledAtRef.current) {
      return;
    }
    nextFetchScheduledAtRef.current = nextFetchScheduledAt;
    setDiagnostics((prev) => ({
      ...prev,
      next_fetch_scheduled_at: nextFetchScheduledAt,
      refresh_interval_ms: configRef.current
        ? resolveSpotRefreshMs(configRef.current.refresh_interval)
        : null,
    }));
  }, []);

  const shouldFetchOnVisibility = useCallback((): boolean => {
    if (inFlightRef.current) {
      return false;
    }
    const nextFetchScheduledAt = nextFetchScheduledAtRef.current;
    if (nextFetchScheduledAt === null) {
      return true;
    }
    return nextFetchScheduledAt - Date.now() > 250;
  }, []);

  const runSpotFetch = useCallback(
    async (reason: string): Promise<void> => {
      const currentConfig = configRef.current;
      if (!currentConfig?.image_url) {
        return;
      }
      if (inFlightRef.current) {
        return;
      }

      const refreshIntervalMs = resolveSpotRefreshMs(currentConfig.refresh_interval);
      const startedAt = Date.now();
      const currentImageState = imageStateRef.current;
      let latestResponseMetadata: SpotImageResponseMetadata | null = null;

      inFlightRef.current = true;
      setDiagnostics((prev) => ({
        ...prev,
        in_flight: true,
        refresh_interval_ms: refreshIntervalMs,
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
          const detail = await resolveSpotProxyErrorDetail(response);
          if (isSpotImagePayloadProxyRejectionCode(detail?.code)) {
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
                declaredAgeSec: responseMetadata.age_sec,
                declaredCapturedAt: responseMetadata.captured_at,
              },
              detail?.message ?? resolveSpotImageErrorMessage(response.status, detail)
            );
          }
          setDiagnostics((prev) => ({
            ...prev,
            last_image_status: responseMetadata.status,
            last_image_source: responseMetadata.source,
            last_image_age_sec: responseMetadata.age_sec,
            last_image_latency_ms: responseMetadata.latency_ms,
            last_image_retry_after_sec: responseMetadata.retry_after_sec,
          }));
          const diagnosticMessage = resolveSpotImageDiagnosticMessage(responseMetadata);
          throw new Error(diagnosticMessage ?? resolveSpotImageErrorMessage(response.status, detail));
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
          last_image_status: responseMetadata.status,
          last_image_source: responseMetadata.source,
          last_image_age_sec: responseMetadata.age_sec,
          last_image_latency_ms: responseMetadata.latency_ms,
          last_image_retry_after_sec: responseMetadata.retry_after_sec,
        }));

        const effectiveAt = resolveSpotImageSuccessAt(responseMetadata, responseReceivedAt);
        const nextImageError = resolveSpotImageDiagnosticMessage(responseMetadata);
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
          const nextImageState = {
            ...imageStateRef.current,
            imageError: error.message,
          };
          imageStateRef.current = nextImageState;
          setImageError(error.message);
          setMetadata(nextImageState.metadata);
          return;
        }
        console.error('Image fetch failed', error);
        const nextImageError = error instanceof Error ? error.message : resolveSpotImageErrorMessage(0, null);
        const nextImageState = {
          ...imageStateRef.current,
          imageError: nextImageError,
          metadata: latestResponseMetadata ?? imageStateRef.current.metadata,
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
        }));
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
    [syncDashboardSpotImageState]
  );

  const fetchScheduledImage = useCallback(async (): Promise<void> => {
    await runSpotFetch('scheduled');
  }, [runSpotFetch]);

  const fetchVisibleImage = useCallback(async (): Promise<void> => {
    await runSpotFetch('visible');
  }, [runSpotFetch]);

  const refreshImage = useCallback(() => {
    void runSpotFetch('manual');
  }, [runSpotFetch]);

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
        await controlSpotFocus(steps);
      } catch (error) {
        console.error('Spot focus failed', error);
      } finally {
        setFocusBusy(false);
      }
    },
    [focusBusy]
  );

  const controlActuator = useCallback(async (step: number) => {
    try {
      await controlSpotActuator(step);
    } catch (error) {
      console.error('Spot actuator failed', error);
    }
  }, []);

  useEffect(() => {
    return () => {
      const pendingPreviousUrl = pendingPreviousImageStateRef.current?.imageUrl ?? null;
      if (pendingPreviousUrl && pendingPreviousUrl !== prevUrlRef.current) {
        URL.revokeObjectURL(pendingPreviousUrl);
      }
    };
  }, []);

  useSpotViewModelEffects({
    config,
    fetchScheduledImage,
    fetchVisibleImage,
    loadConfig,
    applySpotConfig,
    prevUrlRef,
    setNextFetchScheduledAt,
    shouldFetchOnVisibility,
  });

  const handleImageLoad = useCallback(() => {
    hasImageRef.current = true;
    setImageLoading(false);
    const currentImageState = imageStateRef.current;
    const pendingPreviousUrl = pendingPreviousImageStateRef.current?.imageUrl ?? null;
    if (pendingImageUrlRef.current === currentImageState.imageUrl) {
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
  }, [syncDashboardSpotImageState]);

  const handleImageError = useCallback(() => {
    setImageLoading(false);
    const currentImageState = imageStateRef.current;
    if (
      pendingImageUrlRef.current === currentImageState.imageUrl &&
      pendingPreviousImageStateRef.current
    ) {
      const failedImageUrl = currentImageState.imageUrl;
      const previousImageState = pendingPreviousImageStateRef.current;
      const nextImageError = resolveSpotImageLoadErrorMessage();
      const restoredImageState = {
        ...previousImageState,
        imageError: nextImageError,
      };

      URL.revokeObjectURL(failedImageUrl);
      pendingImageUrlRef.current = null;
      pendingPreviousImageStateRef.current = null;
      prevUrlRef.current = restoredImageState.imageUrl || null;
      imageStateRef.current = restoredImageState;
      setImageUrl(restoredImageState.imageUrl);
      setImageError(nextImageError);
      setLastSuccessAt(restoredImageState.lastSuccessAt);
      setMetadata(restoredImageState.metadata);
      syncDashboardSpotImageState(
        restoredImageState.imageUrl,
        false,
        nextImageError,
        restoredImageState.lastSuccessAt,
        restoredImageState.metadata
      );
      return;
    }
    if (!currentImageState.imageError) {
      const nextImageError = resolveSpotImageLoadErrorMessage();
      imageStateRef.current = {
        ...currentImageState,
        imageError: nextImageError,
      };
      setImageError(nextImageError);
      syncDashboardSpotImageState(
        currentImageState.imageUrl,
        false,
        nextImageError,
        currentImageState.lastSuccessAt,
        currentImageState.metadata
      );
      return;
    }
    syncDashboardSpotImageState(
      currentImageState.imageUrl,
      false,
      currentImageState.imageError,
      currentImageState.lastSuccessAt,
      currentImageState.metadata
    );
  }, [syncDashboardSpotImageState]);

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
